"""Artificial peak/ns fixtures; temporary codec/CLI smoke inputs are not a study."""
from __future__ import annotations

import copy
import csv
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src import memory_stability_validation as runner


def read_json(path):
    return runner.strict_json(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def fixture_environment():
    return {**{key: "artificial-fixture" for key in runner.ENVIRONMENT_KEYS},
            "pid": os.getpid(), "bytecode_disabled": sys.dont_write_bytecode,
            "available_physical_memory_bytes": 1000000, "memory_load_percent": 10}


def fixture_git():
    return dict(commit_hash="a" * 40, worktree_dirty=False, status_porcelain="")


EVENTS = dict(power_mode="fixture", manual_reboot_since_previous_run=False,
              concurrent_activity="none", os_update_events="none", other_events="none",
              no_research_jobs_running=True)


def timing_payload(request, status="ok"):
    records = []
    for phase in runner.PHASES:
        for index in range(1, 6):
            records.append(dict(phase=phase, repeat_index=index, elapsed_ns=1000 * index,
                                actual_output_sha256=request["compressed_sha256" if phase == "compress" else "original_sha256"],
                                verified=True, status="ok", error=""))
    return dict(schema_version=1, design_id=runner.DESIGN_ID, measurement_status="validation_only",
                score_inclusion=False, request_id=request["request_id"], algorithm=request["algorithm"],
                timer="time.perf_counter_ns", **{k: request[k] for k in ("original_size", "compressed_size", "original_sha256", "compressed_sha256")},
                records=records, status=status, error="" if status == "ok" else "fixture failure")


def fixture_worker(request, paths):
    if request["kind"] == "timing":
        payload = timing_payload(request)
        runner._validate_timing(payload, request, 0)
    else:
        payload = dict(operation=request["phase"], algorithm=request["algorithm"],
                       peak_process_working_set_bytes=1000 + 10 * request["repeat_index"], verified=True)
        runner._validate_memory(payload, request, 0)
    return dict(status="ok", error="", return_code=0, stdout=runner._json(payload), stderr="", payload=payload,
                argv=runner._json(["artificial-fixture"]), python_executable=sys.executable,
                subprocess_options=runner._json(runner.OPTIONS), started_at_utc=runner.common._now(),
                finished_at_utc=runner.common._now(), input_verified_before=True, input_verified_after=True)


class PlanTests(unittest.TestCase):
    def test_full_plan_independent_schedule_and_keys(self):
        plan = runner.build_plan("fixture")
        self.assertEqual(plan, runner.build_plan("fixture"))
        self.assertEqual(len(plan["samples"]), 84)
        core, tiny = plan["samples"][:72], plan["samples"][72:]
        self.assertEqual([(s["size"], s["generator"], s["replicate_index"]) for s in core],
                         [(size, gen, rep) for size in (16384, 65536, 262144, 1048576)
                          for gen in ("random", "small_alphabet", "repeated_pattern", "long_runs", "structured", "mixed") for rep in (0, 1, 2)])
        for index, spec in enumerate(plan["samples"]):
            self.assertEqual(spec["sample_id"], f"stability_{index:06d}")
            self.assertEqual(spec["seed"], 20261007 + index if spec["stratum"] == "core" or spec["family"] == "uniform_random" else None)
        self.assertEqual([(s["size"], s["family"]) for s in tiny], [(s, f) for s in (64, 256, 1024, 4096) for f in ("zero_bytes", "periodic_16", "uniform_random")])
        for run_id in range(1, 7):
            rows = plan["schedules"][str(run_id)]
            self.assertEqual(len(rows), 3696)
            self.assertEqual(sum(r["kind"] == "memory" for r in rows), 3360)
            self.assertEqual(sum(r["kind"] == "timing" for r in rows), 336)
            canonical = [("memory", s["sample_id"], a, p, i) for s in plan["samples"]
                         for a in ("gzip", "bz2", "lzma", "zstd") for p in ("compress", "decompress") for i in range(1, 6)]
            canonical += [("timing", s["sample_id"], a, None, None) for s in plan["samples"] for a in ("gzip", "bz2", "lzma", "zstd")]
            random.Random(20262007 + run_id).shuffle(canonical)
            self.assertEqual([(r["kind"], r["sample_id"], r["algorithm"], r["phase"], r["repeat_index"]) for r in rows], canonical)
            self.assertEqual([r["schedule_index"] for r in rows], list(range(3696)))
            self.assertEqual(len({r["request_id"] for r in rows}), 3696)
            self.assertEqual(len(set(plan["expected_keys"]["memory"])), 3360)
        self.assertFalse(plan["score_inclusion"])
        self.assertEqual(plan["criteria"]["memory_span_limit"], .005 / (2 * .20))
        self.assertAlmostEqual(plan["criteria"]["memory_span_limit"], .0125)
        for weight in plan["candidate_weights"].values():
            self.assertAlmostEqual(sum(weight.values()), 1)

    def test_generation_reproduction_and_duplicate_records(self):
        core = runner.build_plan("fixture")["samples"][0]
        expected = runner.data_generator.generate_sample(core["generator"], core["size"], core["seed"])
        self.assertEqual(runner.generate_input(core), (expected.data, expected.parameters))
        for spec in runner.build_plan("fixture")["samples"][72:]:
            first = runner.generate_input(spec)
            self.assertEqual(first, runner.generate_input(spec))
            self.assertEqual(len(first[0]), spec["size"])
            if spec["family"] == "uniform_random":
                self.assertEqual(first[0], random.Random(spec["seed"]).randbytes(spec["size"]))
        spec = runner.build_plan("fixture")["samples"][72]
        duplicate = {**spec, "sample_id": "duplicate"}
        rows = runner._sample_records([spec, duplicate])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["duplicate_of"], spec["sample_id"])
        with patch.object(runner, "generate_input", side_effect=ValueError("fixture failure")):
            rows = runner._sample_records([spec])
        self.assertEqual(rows[0]["status"], "preparation_failed")
        self.assertIsNone(rows[0]["input_sha256"])
        for bad in (None, "", "../escape", "with space"):
            with self.assertRaises(ValueError):
                runner.build_plan(bad)

    def test_schedule_windows_boundaries_and_local_dates(self):
        start = datetime(2026, 10, 14, 14, 45, tzinfo=timezone.utc)  # 23:45 Seoul
        previous = [dict(started_at_utc=start.isoformat(), finished_at_utc=(start + timedelta(minutes=10)).isoformat())]
        self.assertEqual(runner.schedule_issues(1, start.isoformat(), []), [])
        for minutes in (30, 90):
            # Separate daytime anchor to test gap inclusivity without crossing dates.
            anchor = datetime(2026, 10, 14, 0, tzinfo=timezone.utc)
            history = [dict(started_at_utc=anchor.isoformat(), finished_at_utc=anchor.isoformat())]
            self.assertEqual(runner.schedule_issues(2, (anchor + timedelta(minutes=minutes)).isoformat(), history), [])
        self.assertIn("second_run_on_different_local_date", runner.schedule_issues(2, (start + timedelta(minutes=40)).isoformat(), previous))
        self.assertEqual(runner.schedule_issues(3, (start + timedelta(hours=24)).isoformat(), previous * 2), [])
        self.assertIn("first_run_outside_daily_window", runner.schedule_issues(3, (start + timedelta(hours=26)).isoformat(), previous * 2))
        self.assertIn("nonconsecutive_local_date", runner.schedule_issues(3, (start + timedelta(hours=25)).isoformat(), previous * 2))
        with self.assertRaises(ValueError):
            runner.schedule_issues(1, "2026-10-14T00:00:00", [])

    def test_json_types_and_events_fail_explicitly(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}'):
            with self.assertRaises(ValueError):
                runner.strict_json(text)
        self.assertFalse(runner._same(True, 1))
        self.assertEqual(runner._check_events(EVENTS), EVENTS)
        for changed in ({}, {**EVENTS, "manual_reboot_since_previous_run": 0}, {**EVENTS, "power_mode": ""}):
            with self.assertRaises((TypeError, ValueError)):
                runner._check_events(changed)

    def test_parent_requires_windows_and_disabled_bytecode(self):
        for name, value in (("platform", "linux"), ("dont_write_bytecode", False)):
            with patch.object(runner.sys, name, value), self.assertRaises(RuntimeError):
                runner._check_config()


class AdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="stability_adapter_fixture_")
        self.addCleanup(temporary.cleanup)
        self.paths = {p: Path(temporary.name) / (p + ".bin") for p in runner.PHASES}
        self.data = b"ABCD" * 16
        self.compressed = runner.compressors.compress_data(self.data, "gzip")
        self.paths["compress"].write_bytes(self.data)
        self.paths["decompress"].write_bytes(self.compressed)
        self.request = dict(kind="timing", request_id="fixture:1:0", algorithm="gzip", phase="compress", repeat_index=1,
                            original_size=len(self.data), compressed_size=len(self.compressed),
                            original_sha256=runner.common._digest(self.data), compressed_sha256=runner.common._digest(self.compressed),
                            input_size=len(self.data), input_sha256=runner.common._digest(self.data), expected_output_sha256=runner.common._digest(self.compressed))

    def call(self, payload, code=0, stderr=b"", raw=None):
        evidence = runner._json(payload) if raw is None else raw
        completed = subprocess.CompletedProcess([], code, evidence.encode(), stderr)
        with patch.object(runner.subprocess, "run", return_value=completed) as launch:
            result = runner.run_worker(self.request, self.paths)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(launch.call_args.kwargs["timeout"], 120)
        self.assertEqual(launch.call_args.kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertIn("-B", launch.call_args.args[0])
        self.assertEqual(result["stdout"], evidence)
        self.assertEqual(result["return_code"], code)
        self.assertTrue(result["input_verified_before"])
        self.assertTrue(result["input_verified_after"])
        return result

    def test_memory_success_false_and_invalid_contracts(self):
        self.request["kind"] = "memory"
        valid = dict(operation="compress", algorithm="gzip", peak_process_working_set_bytes=1234, verified=True)
        self.assertEqual(self.call(valid)["status"], "ok")
        self.assertEqual(self.call({**valid, "verified": False}, 2)["status"], "verification_failed")
        for change in ({"operation": "decompress"}, {"algorithm": "zstd"}, {"verified": 1},
                       {"peak_process_working_set_bytes": True}, {"peak_process_working_set_bytes": 0},
                       {"peak_process_working_set_bytes": 1.5}):
            with self.subTest(change=change):
                self.assertEqual(self.call({**valid, **change})["status"], "invalid_result")
        self.assertEqual(self.call(valid, 2)["status"], "invalid_result")
        self.assertEqual(self.call(valid, stderr=b"unexpected warning")["status"], "invalid_result")
        for raw in ('{"verified":true,"verified":true}', '{"value":NaN}', '{"value":1e999}', 'not json'):
            self.assertEqual(self.call(None, raw=raw)["status"], "invalid_result")

    def test_timing_success_and_partial_failure(self):
        payload = timing_payload(self.request)
        self.assertEqual(self.call(payload)["status"], "ok")
        failed = copy.deepcopy(payload)
        failed.update(status="verification_failed", error="fixture mismatch")
        failed["records"][0].update(status="verification_failed", error="fixture mismatch", verified=False, actual_output_sha256="0" * 64)
        self.assertEqual(self.call(failed, 2)["status"], "verification_failed")
        partial = copy.deepcopy(payload)
        partial.update(status="worker_failed", error="fixture codec error", records=partial["records"][:3])
        partial["records"][-1].update(elapsed_ns=None, verified=None, actual_output_sha256=None, status="worker_failed", error="fixture codec error")
        result = self.call(partial, 1)
        self.assertEqual(result["status"], "worker_failed")
        request = {**self.request, "attempt_id": "fixture", "run_id": 1, "sample_id": "stability_000000", "schedule_index": 0,
                   "reference_roundtrip_verified": True}
        rows = runner._raw_rows(request, result)
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["elapsed_ns"], 1000)
        self.assertTrue(rows[0]["verified"])
        self.assertEqual(rows[0]["bundle_status"], "worker_failed")
        self.assertEqual(rows[3]["status"], "missing_record")
        self.assertIsNone(rows[3]["elapsed_ns"])

    def test_timing_identity_records_and_types_rejected(self):
        payload = timing_payload(self.request)
        mutations = [{"schema_version": True}, {"request_id": "other"}, {"score_inclusion": 0},
                     {"algorithm": "zstd"}, {"original_size": True}, {"compressed_sha256": "0" * 64},
                     {"status": "worker_failed"}, {"error": "contradiction"}, {"records": []}]
        for changes in mutations:
            with self.subTest(changes=changes):
                self.assertEqual(self.call({**payload, **changes})["status"], "invalid_result")
        for change in ({"repeat_index": True}, {"repeat_index": 2}, {"elapsed_ns": True}, {"elapsed_ns": 0},
                       {"elapsed_ns": 1.5}, {"verified": 1}, {"actual_output_sha256": "0" * 64}, {"error": "contradiction"}):
            changed = copy.deepcopy(payload)
            changed["records"][0].update(change)
            self.assertEqual(self.call(changed)["status"], "invalid_result")
        changed = copy.deepcopy(payload)
        changed["records"][1] = changed["records"][0]
        self.assertEqual(self.call(changed)["status"], "invalid_result")
        for key in payload:
            changed = copy.deepcopy(payload)
            del changed[key]
            self.assertEqual(self.call(changed)["status"], "invalid_result", key)
        self.assertEqual(self.call(payload, 7)["status"], "worker_failed")

    def test_response_validation_remains_active_under_optimization(self):
        script = '''
from src import memory_stability_validation as runner
request = dict(phase='compress', algorithm='gzip')
for payload in (dict(operation='compress', algorithm='gzip', peak_process_working_set_bytes=True, verified=True),
                dict(operation='compress', algorithm='gzip', peak_process_working_set_bytes=0, verified=True)):
    try:
        runner._validate_memory(payload, request, 0)
    except ValueError:
        pass
    else:
        raise RuntimeError('invalid response accepted')
for text in ('{"a":1,"a":2}', '{"a":1e999}'):
    try:
        runner.strict_json(text)
    except ValueError:
        pass
    else:
        raise RuntimeError('invalid JSON accepted')
'''
        for option in (None, "-O", "-OO"):
            command = [sys.executable, "-B"] + ([option] if option else []) + ["-c", script]
            completed = subprocess.run(command, cwd=runner.ROOT, capture_output=True, timeout=120,
                                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_timeout_crash_input_changes_and_interrupt(self):
        error = subprocess.TimeoutExpired([], 120, output=b"partial", stderr=b"detail")
        with patch.object(runner.subprocess, "run", side_effect=error):
            result = runner.run_worker(self.request, self.paths)
        self.assertEqual((result["status"], result["stdout"], result["stderr"]), ("timeout", "partial", "detail"))
        self.assertTrue(result["input_verified_after"])
        with patch.object(runner.subprocess, "run", side_effect=OSError("fixture spawn")):
            self.assertEqual(runner.run_worker(self.request, self.paths)["status"], "worker_failed")
        for exc in (KeyboardInterrupt, SystemExit):
            with patch.object(runner.subprocess, "run", side_effect=exc), self.assertRaises(exc):
                runner.run_worker(self.request, self.paths)
        payload = timing_payload(self.request)
        def mutate(*args, **kwargs):
            self.paths["compress"].write_bytes(b"changed")
            return subprocess.CompletedProcess([], 0, runner._json(payload).encode(), b"")
        with patch.object(runner.subprocess, "run", side_effect=mutate):
            result = runner.run_worker(self.request, self.paths)
        self.assertEqual(result["status"], "input_changed")
        self.assertFalse(result["input_verified_after"])
        with patch.object(runner.subprocess, "run") as launch:
            result = runner.run_worker(self.request, self.paths)
        launch.assert_not_called()
        self.assertEqual(result["status"], "input_changed")

    def test_postcheck_failure_cannot_swallow_original_interrupt(self):
        for kind in (KeyboardInterrupt, SystemExit):
            self.paths["compress"].write_bytes(self.data)
            error = kind("original fixture interrupt")
            def interrupt(*args, **kwargs):
                self.paths["compress"].write_bytes(b"changed during interrupt")
                raise error
            with patch.object(runner.subprocess, "run", side_effect=interrupt), self.assertRaises(kind) as caught:
                runner.run_worker(self.request, self.paths)
            self.assertIs(caught.exception, error)
            self.assertIn("Input verification after worker also failed", " ".join(error.__notes__))
        self.paths["compress"].write_bytes(self.data)
        def timeout(*args, **kwargs):
            self.paths["compress"].write_bytes(b"changed during timeout")
            raise subprocess.TimeoutExpired([], 120, output=b"partial evidence")
        with patch.object(runner.subprocess, "run", side_effect=timeout):
            result = runner.run_worker(self.request, self.paths)
        self.assertEqual(result["status"], "input_changed")
        self.assertIn("previous worker error", result["error"])
        self.assertEqual(result["stdout"], "partial evidence")


@unittest.skipUnless(sys.platform == "win32", "Windows runner fixtures")
class RunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="stability_runner_artificial_fixture_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = "2026-10-14T00:00:00+00:00"
        for owner, name, value in ((runner, "CORE_SIZES", ()), (runner, "TINY_SIZES", (64,)),
                                   (runner, "FAMILIES", ("periodic_16",))):
            patcher = patch.object(owner, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for owner, name, effect in ((runner, "_environment", fixture_environment),
                                    (runner.common, "_git_information", fixture_git),
                                    (runner.common, "_now", lambda: self.now)):
            patcher = patch.object(owner, name, side_effect=effect)
            patcher.start()
            self.addCleanup(patcher.stop)
        result = runner.initialize(attempt_id="fixture", results_root=self.root)
        self.study = Path(result["study_dir"])
        self.plan = read_json(self.study / "plan.json")

    def parent(self, command, **kwargs):
        run_id = int(command[command.index("--run-id") + 1])
        token = command[command.index("--token") + 1]
        self.assertEqual(command[:5], [sys.executable, "-B", "-m", "src.memory_stability_validation", "_run"])
        self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        result = runner.run_one(self.study, run_id, token)
        kwargs["stdout"].write(runner._json({k: result[k] for k in ("run_status", "repeat_count", "failed_repeat_count", "run_id")}).encode())
        return subprocess.CompletedProcess(command, 0 if result["run_status"] == "completed" else 1)

    def run_fixture(self, measure=fixture_worker, events=None):
        with patch.object(runner, "run_worker", side_effect=measure), patch.object(runner.subprocess, "run", side_effect=self.parent):
            return runner.run_next(self.study, EVENTS if events is None else events)

    def test_initialize_is_exclusive_clean_and_has_no_codec_calls(self):
        before = (self.study / "plan.json").read_bytes()
        with self.assertRaises(FileExistsError):
            runner.initialize(attempt_id="fixture", results_root=self.root)
        self.assertEqual((self.study / "plan.json").read_bytes(), before)
        with patch.object(runner.compressors, "compress_data") as codec:
            runner.initialize(attempt_id="other", results_root=self.root)
        codec.assert_not_called()
        with patch.object(runner.common, "_git_information", return_value={"commit_hash": "a" * 40, "worktree_dirty": True, "status_porcelain": " M src/compressors.py\n"}):
            with self.assertRaisesRegex(RuntimeError, "outside"):
                runner.initialize(attempt_id="dirty", results_root=self.root)
        self.assertEqual(read_json(self.study / "metadata.json")["run_status"], "initialized")
        self.assertEqual(read_csv(self.study / "samples.csv")[0]["stratum"], "tiny")

    def test_preparation_precedes_all_jobs_and_aggregates_match_raw(self):
        prepared, calls = [], []
        real_prepare = runner._prepare
        def prepare(*args):
            result = real_prepare(*args)
            prepared.extend(result)
            return result
        def measure(request, paths):
            self.assertEqual(len(prepared), 4)
            calls.append(request["request_id"])
            for phase in runner.PHASES:
                self.assertEqual(runner.common._digest(paths[phase].read_bytes()), request["original_sha256" if phase == "compress" else "compressed_sha256"])
            return fixture_worker(request, paths)
        with patch.object(runner, "_prepare", side_effect=prepare):
            result = self.run_fixture(measure)
        self.assertEqual(result["run_status"], "awaiting_next_run")
        self.assertEqual(calls, [r["request_id"] for r in self.plan["schedules"]["1"]])
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual((child["memory_repeat_count"], child["timing_repeat_count"]), (40, 40))
        self.assertEqual(child["job_count"], 44)
        self.assertTrue(child["recording_checks_passed"])
        self.assertEqual(child["technical_validity_status"], "pending_independent_audit")
        measurements = read_csv(self.study / "run_01/measurements.csv")
        self.assertEqual(len(measurements), 4)
        for row in measurements:
            self.assertEqual(row["verified"], "True")
            self.assertEqual(float(row["compression_time_ms"]), .003)
            self.assertEqual(int(row["peak_memory_bytes"]), 1030)
        for name, digest in child["artifact_sha256"].items():
            self.assertEqual(runner.common._digest((self.study / "run_01" / name).read_bytes()), digest)
        self.assertFalse((self.study / "candidate_labels.csv").exists())
        self.assertFalse((self.study / "audit.json").exists())

    def test_failed_timing_bundle_retains_good_raw_values_but_nulls_pair(self):
        failed = next(r for r in self.plan["schedules"]["1"] if r["kind"] == "timing")
        def measure(request, paths):
            result = fixture_worker(request, paths)
            if request["request_id"] == failed["request_id"]:
                payload = result["payload"]
                payload.update(status="worker_failed", error="fixture failure", records=payload["records"][:3])
                payload["records"][-1].update(status="worker_failed", error="fixture failure", elapsed_ns=None, actual_output_sha256=None, verified=None)
                runner._validate_timing(payload, request, 1)
                result.update(status="worker_failed", error="fixture failure", return_code=1, stdout=runner._json(payload))
            return result
        self.run_fixture(measure)
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual(child["failed_repeat_count"], 10)
        rows = read_csv(self.study / "run_01/timing_repeats.csv")
        affected = [r for r in rows if r["request_id"] == failed["request_id"]]
        self.assertEqual(affected[0]["elapsed_ns"], "1000")
        self.assertEqual(affected[0]["status"], "ok")
        self.assertEqual(affected[3]["status"], "missing_record")
        bad = [r for r in read_csv(self.study / "run_01/measurements.csv") if r["verified"] == "False"]
        self.assertEqual(len(bad), 1)
        self.assertTrue(all(bad[0][k] == "" for k in runner.MEASUREMENT_FIELDS[4:]))

    def test_generation_and_reference_failure_emit_all_keys_without_workers(self):
        for target in (patch.object(runner, "generate_input", side_effect=ValueError("fixture generation")),
                       patch.object(runner.compressors, "decompress_data", return_value=b"wrong")):
            # Each scenario gets a distinct new attempt, never an overwritten run.
            with tempfile.TemporaryDirectory(prefix="stability_failure_fixture_") as directory:
                self.study = Path(runner.initialize(attempt_id="fixture", results_root=Path(directory))["study_dir"])
                with target, patch.object(runner, "run_worker") as worker, patch.object(runner.subprocess, "run", side_effect=self.parent):
                    runner.run_next(self.study, EVENTS)
                worker.assert_not_called()
                child = read_json(self.study / "run_01/metadata.json")
                self.assertEqual(child["failed_repeat_count"], 80)
                self.assertEqual({r["status"] for r in read_csv(self.study / "run_01/memory_repeats.csv")}, {"preparation_failed"})

    def test_six_separate_runs_schedule_immutability_and_no_extra_runs(self):
        before = {n: (self.study / n).read_bytes() for n in ("plan.json", "samples.csv")}
        base = datetime.fromisoformat(self.now)
        for run_id in range(1, 7):
            self.now = (base + timedelta(hours=24 * ((run_id - 1) // 2), minutes=31 if run_id % 2 == 0 else 0)).isoformat()
            result = self.run_fixture()
            self.assertEqual(result["runs"][-1]["run_id"], run_id)
            self.assertEqual(result["validity_issues"], [])
        self.assertEqual(result["run_status"], "completed")
        self.assertEqual(result["repeat_count"], 480)
        self.assertTrue(result["recording_checks_passed"])
        with self.assertRaises(ValueError):
            self.run_fixture()
        for name, value in before.items():
            self.assertEqual((self.study / name).read_bytes(), value)
        self.assertFalse((self.study / "run_07").exists())

    def test_schedule_violation_and_environment_drift_are_recorded(self):
        self.run_fixture()
        self.now = "2026-10-14T00:01:00+00:00"
        env = fixture_environment()
        env["processor"] = "changed fixture CPU"
        with patch.object(runner, "_environment", return_value=env):
            result = self.run_fixture()
        self.assertIn("run_02:second_run_outside_gap_window", result["validity_issues"])
        self.assertIn("run_02:environment_differs_from_plan", result["validity_issues"])
        self.assertFalse(result["recording_checks_passed"])

    def test_reported_concurrent_jobs_abort_before_codec_or_workers(self):
        with patch.object(runner.compressors, "compress_data") as codec, \
                patch.object(runner, "run_worker") as worker, \
                patch.object(runner.subprocess, "run", side_effect=self.parent), self.assertRaises(RuntimeError):
            runner.run_next(self.study, {**EVENTS, "no_research_jobs_running": False})
        codec.assert_not_called()
        worker.assert_not_called()
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual(child["run_status"], "aborted")
        self.assertFalse(child["recording_checks_passed"])

    def test_worker_input_mutation_at_end_aborts_instead_of_aggregating(self):
        last = self.plan["schedules"]["1"][-1]
        def measure(request, paths):
            evidence = fixture_worker(request, paths)
            if request["request_id"] == last["request_id"]:
                paths["compress"].write_bytes(b"fixture mutation after final job")
            return evidence
        with self.assertRaisesRegex(ValueError, "changed before run ended"):
            self.run_fixture(measure)
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual(child["run_status"], "aborted")
        self.assertFalse(child["recording_checks_passed"])
        self.assertFalse((self.study / "run_01/measurements.csv").exists())

    def test_exclusive_lock_and_no_rerun_or_modified_plan(self):
        lock = self.study / ".active_run.json"
        lock.write_text("{}", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.run_fixture()
        self.assertEqual(lock.read_text(), "{}")
        lock.unlink()
        plan = copy.deepcopy(self.plan)
        plan["schedules"]["1"].pop()
        runner.common._save_metadata(self.study / "plan.json", plan)
        with self.assertRaisesRegex(ValueError, "fixed design"):
            self.run_fixture()
        self.assertFalse((self.study / "run_01").exists())

    def test_prior_raw_evidence_change_rejected(self):
        self.run_fixture()
        path = self.study / "run_01/memory_repeats.csv"
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.run_fixture()
        self.assertFalse((self.study / "run_02").exists())

    def test_parent_completion_cannot_claim_missing_jobs(self):
        self.run_fixture()
        child_path = self.study / "run_01/metadata.json"
        child = read_json(child_path)
        child["job_count"] -= 1
        runner.common._save_metadata(child_path, child)
        with self.assertRaisesRegex(ValueError, "counts/artifact"):
            runner._history(self.study, 1, self.plan)

    def test_reference_hash_difference_across_runs_remains_failure(self):
        self.run_fixture()
        self.now = "2026-10-14T00:31:00+00:00"
        original = runner.compressors.compress_data
        def changed(data, algorithm):
            compressed = original(data, algorithm)
            if algorithm == "gzip":
                # Modify only deterministic gzip header mtime; restored bytes match.
                return compressed[:4] + b'\x01\x00\x00\x00' + compressed[8:]
            return compressed
        with patch.object(runner.compressors, "compress_data", side_effect=changed):
            self.run_fixture()
        refs = read_csv(self.study / "run_02/references.csv")
        gzip = next(r for r in refs if r["algorithm"] == "gzip")
        self.assertEqual(gzip["status"], "preparation_failed")
        self.assertEqual(gzip["reference_roundtrip_verified"], "True")
        self.assertIn("between runs", gzip["error"])
        self.assertEqual(read_json(self.study / "run_02/metadata.json")["failed_repeat_count"], 20)

    def test_interrupt_preserves_flushed_rows_and_original_error(self):
        error = KeyboardInterrupt("original fixture")
        first = self.plan["schedules"]["1"][0]
        count = 10 if first["kind"] == "timing" else 1
        def measure(request, paths):
            if request["schedule_index"] == 1:
                raise error
            return fixture_worker(request, paths)
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.run_fixture(measure)
        self.assertIs(caught.exception, error)
        child = read_json(self.study / "run_01/metadata.json")
        top = read_json(self.study / "metadata.json")
        self.assertEqual((child["run_status"], top["run_status"]), ("interrupted", "interrupted"))
        self.assertEqual(child["repeat_count"], count)
        self.assertEqual(sum(len(read_csv(self.study / f"run_01/{k}_repeats.csv")) for k in ("memory", "timing")), count)
        with self.assertRaises(ValueError):
            self.run_fixture()

    def test_parent_crash_keeps_stdout_stderr_and_blocks_retry(self):
        def crash(command, **kwargs):
            kwargs["stdout"].write(b"partial output")
            kwargs["stderr"].write(b"fixture crash")
            return subprocess.CompletedProcess(command, 7)
        with patch.object(runner.subprocess, "run", side_effect=crash), self.assertRaises(FileNotFoundError):
            runner.run_next(self.study, EVENTS)
        top = read_json(self.study / "metadata.json")
        self.assertEqual(top["run_status"], "aborted")
        self.assertEqual(top["runs"][0]["return_code"], 7)
        self.assertEqual((self.study / "run_01_stdout.txt").read_bytes(), b"partial output")
        self.assertEqual((self.study / "run_01_stderr.txt").read_bytes(), b"fixture crash")

    def test_midrun_source_change_invalidates_completion(self):
        real_sources = runner._sources
        def sources():
            result = real_sources()
            if (self.study / "run_01/measurements.csv").exists():
                result["src/memory_stability_validation.py"] = "0" * 64
            return result
        with patch.object(runner, "_sources", side_effect=sources), self.assertRaises(RuntimeError):
            self.run_fixture()
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual(child["run_status"], "invalid_provenance_changed")
        self.assertFalse(child["provenance_unchanged"])

    def test_midrun_plan_change_invalidates_completion(self):
        def measure(request, paths):
            if request["schedule_index"] == 0:
                plan = read_json(self.study / "plan.json")
                plan["attempt_reason"] = "fixture midrun change"
                runner.common._save_metadata(self.study / "plan.json", plan)
            return fixture_worker(request, paths)
        with self.assertRaises(RuntimeError):
            self.run_fixture(measure)
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual(child["run_status"], "invalid_provenance_changed")
        self.assertFalse(child["provenance_unchanged"])

    def test_source_or_git_drift_before_launch_preserves_aborted_metadata(self):
        hashes = runner._sources()
        hashes["src/compressors.py"] = "0" * 64
        with patch.object(runner, "_sources", return_value=hashes), self.assertRaisesRegex(ValueError, "before launch"):
            self.run_fixture()
        metadata = read_json(self.study / "metadata.json")
        self.assertEqual(metadata["run_status"], "aborted")
        self.assertFalse(metadata["recording_checks_passed"])
        self.assertFalse((self.study / "run_01").exists())

    def test_final_metadata_failure_does_not_report_completed(self):
        real_save = runner.common._save_metadata
        def save(path, data):
            if path.parent.name == "run_01" and data.get("finalization_status") == "completed":
                raise OSError("fixture final save failure")
            real_save(path, data)
        with patch.object(runner.common, "_save_metadata", side_effect=save), self.assertRaises(OSError):
            self.run_fixture()
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual(child["run_status"], "finalizing")
        self.assertEqual(read_json(self.study / "metadata.json")["run_status"], "aborted")

    def test_midrun_checkpoint_failure_keeps_written_rows_and_stops_jobs(self):
        real_save = runner.common._save_metadata
        def save(path, data):
            if path.parent.name == "run_01" and data.get("job_count") == 2 and data["run_status"] == "running":
                raise OSError("fixture checkpoint storage failure")
            real_save(path, data)
        with patch.object(runner.common, "_save_metadata", side_effect=save), self.assertRaises(OSError):
            self.run_fixture()
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual(child["run_status"], "aborted")
        self.assertEqual(child["job_count"], 2)
        self.assertEqual(sum(len(read_csv(self.study / f"run_01/{k}_repeats.csv")) for k in ("memory", "timing")), child["repeat_count"])

    def test_secondary_finalization_error_does_not_replace_original(self):
        real_save = runner.common._save_metadata
        error = SystemExit("original fixture")
        def save(path, data):
            if path.parent.name == "run_01" and "finalization_status" in data:
                raise OSError("fixture persistent storage failure")
            real_save(path, data)
        with patch.object(runner.common, "_save_metadata", side_effect=save), self.assertRaises(SystemExit) as caught:
            self.run_fixture(lambda *_: (_ for _ in ()).throw(error))
        self.assertIs(caught.exception, error)
        self.assertIn("Finalization also failed", " ".join(error.__notes__))

    def test_claim_release_failure_is_recorded_and_preserves_original(self):
        real_unlink = Path.unlink
        error = KeyboardInterrupt("original fixture")
        def unlink(path, *args, **kwargs):
            if path == self.study / ".active_run.json":
                raise OSError("fixture claim release failure")
            return real_unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", unlink), self.assertRaises(KeyboardInterrupt) as caught:
            self.run_fixture(lambda *_: (_ for _ in ()).throw(error))
        self.assertIs(caught.exception, error)
        self.assertIn("Claim release also failed", " ".join(error.__notes__))
        metadata = read_json(self.study / "metadata.json")
        self.assertEqual(metadata["run_status"], "interrupted")
        self.assertEqual(metadata["finalization_errors"][-1]["stage"], "release_claim")
        self.assertTrue((self.study / ".active_run.json").exists())

    def test_claim_release_failure_after_finished_run_is_not_success(self):
        real_unlink = Path.unlink
        def unlink(path, *args, **kwargs):
            if path == self.study / ".active_run.json":
                raise OSError("fixture claim release failure")
            return real_unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", unlink), self.assertRaises(OSError):
            self.run_fixture()
        metadata = read_json(self.study / "metadata.json")
        self.assertEqual(metadata["run_status"], "finalization_failed")
        self.assertFalse(metadata["recording_checks_passed"])

    def test_summary_rejects_duplicate_unplanned_and_mismatched_keys(self):
        refs = runner._prepare(runner._saved_samples(self.study / "samples.csv", self.plan["samples"]), self.root)
        raw = {"memory": [], "timing": []}
        for job in self.plan["schedules"]["1"]:
            ref, paths = refs[(job["sample_id"], job["algorithm"])]
            request = {**ref, **job, "attempt_id": "fixture"}
            raw[job["kind"]].extend(runner._raw_rows(request, fixture_worker(request, paths)))
        for bad in ([*raw["memory"], raw["memory"][0]], [{**raw["memory"][0], "sample_id": "other"}],
                    [{**raw["memory"][0], "repeat_index": True}], [{**raw["memory"][0], "schedule_index": 999}]):
            with self.assertRaises(ValueError):
                runner.summarize(self.plan, 1, bad, raw["timing"])
        partial = runner.summarize(self.plan, 1, raw["memory"][:1], raw["timing"])
        self.assertTrue(all(r["verified"] is False for r in partial))

    def test_real_fresh_parent_cli_with_mocked_measurements(self):
        script = '''
import sys
from unittest.mock import patch
from src import memory_stability_validation as runner
sys.path.insert(0, str(runner.ROOT / 'tests'))
from test_memory_stability_validation import fixture_worker, fixture_environment, fixture_git
with patch.object(runner, 'CORE_SIZES', ()), patch.object(runner, 'TINY_SIZES', (64,)), patch.object(runner, 'FAMILIES', ('periodic_16',)), patch.object(runner, 'run_worker', side_effect=fixture_worker), patch.object(runner, '_environment', side_effect=fixture_environment), patch.object(runner.common, '_git_information', side_effect=fixture_git):
    raise SystemExit(runner.main(sys.argv[1:]))
'''
        real_run = subprocess.run
        def launch(command, **kwargs):
            return real_run([sys.executable, "-B", "-c", script, *command[4:]], **kwargs)
        with patch.object(runner.subprocess, "run", side_effect=launch):
            result = runner.run_next(self.study, EVENTS)
        child = read_json(self.study / "run_01/metadata.json")
        self.assertEqual(result["run_status"], "awaiting_next_run")
        self.assertNotEqual(child["environment"]["pid"], os.getpid())
        self.assertTrue(child["environment"]["bytecode_disabled"])


@unittest.skipUnless(sys.platform == "win32", "Windows temporary adapter smoke test")
class RealAdapterSmokeTests(unittest.TestCase):
    def test_real_memory_and_timing_worker_routes(self):
        with tempfile.TemporaryDirectory(prefix="stability_adapter_smoke_") as temporary:
            paths = {p: Path(temporary) / (p + ".bin") for p in runner.PHASES}
            data = b"ABCD" * 16
            paths["compress"].write_bytes(data)
            for algorithm in runner.ALGORITHMS:
                compressed = runner.compressors.compress_data(data, algorithm)
                self.assertEqual(runner.compressors.decompress_data(compressed, algorithm), data)
                paths["decompress"].write_bytes(compressed)
                request = dict(kind="timing", request_id="temporary-smoke", algorithm=algorithm,
                               original_size=len(data), compressed_size=len(compressed),
                               original_sha256=runner.common._digest(data), compressed_sha256=runner.common._digest(compressed))
                self.assertEqual(runner.run_worker(request, paths)["status"], "ok")
                for phase in runner.PHASES:
                    value, output = (data, compressed) if phase == "compress" else (compressed, data)
                    request.update(kind="memory", phase=phase, input_size=len(value), input_sha256=runner.common._digest(value),
                                   expected_output_sha256=runner.common._digest(output))
                    result = runner.run_worker(request, paths)
                    self.assertEqual(result["status"], "ok", result)
                    self.assertGreater(result["payload"]["peak_process_working_set_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
