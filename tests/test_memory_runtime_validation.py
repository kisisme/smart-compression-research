"""Artificial peak fixtures and temporary smoke inputs; no research measurements."""
from __future__ import annotations

from collections import Counter
import copy
import csv
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src import memory_runtime_validation as runner


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def fixture_result(request, path):
    # Deliberately artificial bytes, unrelated to any backend measurement.
    peak = {"import_only": 300, "input_only": 200, "codec": 100}[request["arm"]] + request["round_index"]
    return dict(peak_process_working_set_bytes=peak, verified=True if request["arm"] == "codec" else None,
                input_verified=True if request["arm"] == "input_only" else None,
                status="ok", error="", return_code=0, stdout="artificial fixture", stderr="")


class PlanTests(unittest.TestCase):
    def test_full_schedule_matches_independent_block_shuffle_and_covers_keys(self):
        plan = runner.build_plan("fixture")
        self.assertEqual(plan, runner.build_plan("fixture"))
        self.assertEqual(len(plan["samples"]), 15)
        for run_id in (1, 2, 3):
            rows = plan["schedules"][str(run_id)]
            expected_keys = {(round_index, s["sample_id"], a, p, arm)
                             for round_index in range(1, 6) for s in plan["samples"]
                             for a in runner.worker.ALGORITHMS for p in runner.worker.PHASES
                             for arm in runner.worker.ARMS}
            keys = [(r["round_index"], r["sample_id"], r["algorithm"], r["phase"], r["arm"]) for r in rows]
            self.assertEqual(len(keys), 1800)
            self.assertEqual(set(keys), expected_keys)
            self.assertEqual(len(set(r["request_id"] for r in rows)), len(rows))
            self.assertEqual([r["schedule_index"] for r in rows], list(range(len(rows))))
            rng = random.Random(20260922 + run_id - 1)
            expected = []
            for round_index in range(1, 6):
                blocks = [(s["sample_id"], a, p) for s in plan["samples"]
                          for a in ("gzip", "bz2", "lzma", "zstd") for p in ("compress", "decompress")]
                rng.shuffle(blocks)
                for block in blocks:
                    arms = ["import_only", "input_only", "codec"]
                    rng.shuffle(arms)
                    expected.extend((round_index, *block, arm) for arm in arms)
            self.assertEqual(keys, expected)
        self.assertNotEqual(plan["schedules"]["1"], plan["schedules"]["2"])

    def test_generated_bytes_seeds_and_attempt_ids(self):
        for index, spec in enumerate(runner.build_plan("fixture")["samples"]):
            data = runner.generate_input(spec)
            self.assertEqual(len(data), spec["size"])
            self.assertEqual(data, runner.generate_input(spec))
            if spec["family"] == "zero_bytes":
                self.assertEqual(set(data), {0})
                self.assertIsNone(spec["seed"])
            elif spec["family"] == "periodic_16":
                self.assertEqual(data[:32], bytes(range(16)) * 2)
                self.assertIsNone(spec["seed"])
            else:
                self.assertEqual(spec["seed"], 20260922 + index)
                self.assertEqual(data, random.Random(spec["seed"]).randbytes(spec["size"]))
        for invalid in ("", "../escape", "with space", None):
            with self.assertRaises(ValueError):
                runner.build_plan(invalid)


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.request = dict(request_id="fixture:1:0", arm="codec", algorithm="gzip", phase="compress",
                            input_size=64, input_sha256="a" * 64, expected_output_sha256="b" * 64)

    def payload(self, arm="codec", status="ok"):
        payload = runner.worker._response(self.request["request_id"], arm, "compress", "gzip")
        payload.update(status=status, error="" if status == "ok" else "SHA-256 mismatch",
                       peak_process_working_set_bytes=123, observed_input_size=None if arm == "import_only" else 64,
                       verified=(status == "ok") if arm == "codec" else None,
                       input_verified=(status == "ok") if arm == "input_only" else None)
        return payload

    def call(self, payload, code=0):
        evidence = json.dumps(payload)
        completed = subprocess.CompletedProcess([], code, evidence.encode(), b"fixture stderr")
        with patch.object(runner.subprocess, "run", return_value=completed) as invoked:
            result = runner.run_worker(self.request, Path("phase.bin"))
        self.assertEqual(result["stdout"], evidence)
        self.assertEqual(result["stderr"], "fixture stderr")
        self.assertEqual(result["return_code"], code)
        self.assertEqual(invoked.call_args.kwargs["timeout"], 120)
        self.assertEqual(invoked.call_args.args[0][:4], [sys.executable, "-B", "-m", "src.memory_runtime_worker"])
        return result

    def test_all_arm_success_and_hash_failure_contracts(self):
        for arm in runner.worker.ARMS:
            self.request["arm"] = arm
            self.assertEqual(self.call(self.payload(arm))["status"], "ok")
            if arm != "import_only":
                result = self.call(self.payload(arm, "verification_failed"), 2)
                self.assertEqual(result["status"], "verification_failed")
                self.assertEqual(result["peak_process_working_set_bytes"], 123)
                self.assertIs(result["verified" if arm == "codec" else "input_verified"], False)

    def test_invalid_identity_type_size_and_null_rules_keep_evidence(self):
        valid = self.payload()
        changes = ({"schema_version": True}, {"score_inclusion": 0}, {"design_id": "other"},
                   {"measurement_status": "official"}, {"measurement_method": "other"},
                   {"request_id": "other"}, {"arm": "input_only"}, {"phase": "decompress"},
                   {"algorithm": "zstd"}, {"observed_input_size": 63}, {"observed_input_size": True},
                   {"peak_process_working_set_bytes": 0}, {"peak_process_working_set_bytes": True},
                   {"peak_process_working_set_bytes": float("nan")}, {"verified": 1},
                   {"input_verified": False}, {"error": "contradiction"}, {"status": []})
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(self.call({**valid, **change})["status"], "invalid_result")
        for key in valid:
            payload = dict(valid)
            del payload[key]
            self.assertEqual(self.call(payload)["status"], "invalid_result", key)
        self.assertEqual(self.call([])["status"], "invalid_result")
        self.assertEqual(self.call(valid, 2)["status"], "invalid_result")
        self.assertEqual(self.call(valid, 7)["status"], "worker_failed")

    def test_timeout_crash_invalid_json_and_interrupt(self):
        timeout = subprocess.TimeoutExpired([], 120, output=b"partial", stderr=b"detail")
        with patch.object(runner.subprocess, "run", side_effect=timeout):
            result = runner.run_worker(self.request, Path("unused"))
        self.assertEqual((result["status"], result["stdout"], result["stderr"]), ("timeout", "partial", "detail"))
        self.assertIsNone(result["return_code"])
        for code, status in ((0, "invalid_result"), (7, "worker_failed")):
            with patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], code, b"not json", b"crash")):
                result = runner.run_worker(self.request, Path("unused"))
            self.assertEqual(result["status"], status)
            self.assertEqual(result["stdout"], "not json")
        for error in (KeyboardInterrupt, SystemExit):
            with patch.object(runner.subprocess, "run", side_effect=error), self.assertRaises(error):
                runner.run_worker(self.request, Path("unused"))
        with patch.object(runner.subprocess, "run", side_effect=OSError("fixture spawn failure")):
            self.assertEqual(runner.run_worker(self.request, Path("unused"))["status"], "worker_failed")

    def test_structured_worker_failure_and_its_invalid_variants(self):
        payload = runner.worker._response(self.request["request_id"], "codec", "compress", "gzip")
        payload["error"] = "fixture backend failure"
        self.assertEqual(self.call(payload, 1)["status"], "worker_failed")
        for change in ({"verified": False}, {"peak_process_working_set_bytes": 12}, {"error": ""}):
            self.assertEqual(self.call({**payload, **change}, 1)["status"], "invalid_result")


@unittest.skipUnless(sys.platform == "win32", "Windows study runner")
class RunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="runtime_runner_artificial_fixture_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "study"
        for name, value in (("SIZES", (64,)), ("FAMILIES", ("periodic_16",))):
            patcher = patch.object(runner, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for owner, name in ((runner, "_environment"), (runner.common, "_git_information")):
            patcher = patch.object(owner, name, return_value={"artificial_fixture": True})
            patcher.start()
            self.addCleanup(patcher.stop)
        self.plan = {**runner.build_plan("fixture"), "source_sha256": runner._sources(), "config": runner._check_config()}

    def prepare_plan(self):
        self.output.mkdir()
        runner.common._save_metadata(self.output / "plan.json", self.plan)

    def run_fixture(self, effect=fixture_result):
        self.prepare_plan()
        with patch.object(runner, "run_worker", side_effect=effect):
            return runner.run_one(self.output, 1)

    def test_preparation_finishes_before_workers_and_actual_phase_inputs_are_used(self):
        real_prepare = runner._prepare
        prepared = []
        seen = []
        def prepare(*args):
            refs = real_prepare(*args)
            prepared.extend(refs)
            return refs
        def measure(request, path):
            self.assertEqual(len(prepared), 4)
            data = path.read_bytes()
            self.assertEqual(runner.common._digest(data), request["input_sha256"])
            self.assertEqual(len(data), request["input_size"])
            operation = runner.compressors.compress_data if request["phase"] == "compress" else runner.compressors.decompress_data
            self.assertEqual(runner.common._digest(operation(data, request["algorithm"])), request["expected_output_sha256"])
            self.assertTrue(request["reference_roundtrip_verified"])
            seen.append(request["request_id"])
            return fixture_result(request, path)
        with patch.object(runner, "_prepare", side_effect=prepare):
            metadata = self.run_fixture(measure)
        self.assertEqual(seen, [r["request_id"] for r in self.plan["schedules"]["1"]])
        self.assertEqual(metadata["run_status"], "completed")
        self.assertEqual(metadata["finalization_status"], "completed")
        self.assertFalse(metadata["score_inclusion"])
        directory = self.output / "run_01"
        rows = read_csv(directory / "repeats.csv")
        self.assertEqual(len(rows), 120)
        for row in rows:
            self.assertEqual(row["verified"], "True" if row["arm"] == "codec" else "")
            self.assertEqual(row["input_verified"], "True" if row["arm"] == "input_only" else "")
        for summary in read_csv(directory / "summary.csv"):
            values = [int(r["peak_process_working_set_bytes"]) for r in rows
                      if all(r[k] == summary[k] for k in runner.GROUP_FIELDS)]
            self.assertEqual(float(summary["median_bytes"]), statistics.median(values))
            self.assertAlmostEqual(float(summary["cv"]), statistics.pstdev(values) / statistics.mean(values))
        for name, digest in metadata["artifact_sha256"].items():
            self.assertEqual(runner.common._digest((directory / name).read_bytes()), digest)

    def test_failure_rows_continue_and_only_affected_group_loses_aggregate(self):
        failed_id = self.plan["schedules"]["1"][1]["request_id"]
        def measure(request, path):
            if request["request_id"] == failed_id:
                return runner._empty_result("timeout", "artificial timeout")
            return fixture_result(request, path)
        metadata = self.run_fixture(measure)
        self.assertEqual(metadata["run_status"], "completed_with_failures")
        self.assertEqual(metadata["failed_repeat_count"], 1)
        rows = read_csv(self.output / "run_01/repeats.csv")
        self.assertEqual(len(rows), 120)
        self.assertEqual(rows[1]["status"], "timeout")
        incomplete = [r for r in read_csv(self.output / "run_01/summary.csv") if r["complete"] == "False"]
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0]["median_bytes"], "")

    def test_reference_or_generation_failure_records_every_planned_key(self):
        for failure in ("reference", "generation"):
            with self.subTest(failure=failure):
                self.output = self.root / failure
                self.prepare_plan()
                target = (patch.object(runner.compressors, "decompress_data", return_value=b"wrong")
                          if failure == "reference" else patch.object(runner, "generate_input", side_effect=ValueError("fixture generation")))
                with target, patch.object(runner, "run_worker") as worker:
                    metadata = runner.run_one(self.output, 1)
                worker.assert_not_called()
                self.assertEqual(metadata["failed_repeat_count"], 120)
                rows = read_csv(self.output / "run_01/repeats.csv")
                self.assertEqual({r["status"] for r in rows}, {"preparation_failed"})
                self.assertEqual({r["reference_roundtrip_verified"] for r in rows}, {"False" if failure == "reference" else ""})
                self.assertTrue(all(r["median_bytes"] == "" for r in read_csv(self.output / "run_01/summary.csv")))

    def test_existing_paths_and_modified_plan_are_rejected(self):
        self.prepare_plan()
        original = (self.output / "plan.json").read_bytes()
        with self.assertRaises(FileExistsError):
            runner.run_study(self.output, attempt_id="fixture")
        self.assertEqual((self.output / "plan.json").read_bytes(), original)
        (self.output / "run_01").mkdir()
        sentinel = self.output / "run_01/user.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            runner.run_one(self.output, 1)
        self.assertEqual(sentinel.read_bytes(), b"keep")
        plan = copy.deepcopy(self.plan)
        plan["schedules"]["1"].pop()
        runner.common._save_metadata(self.output / "plan.json", plan)
        with self.assertRaisesRegex(ValueError, "fixed design"):
            runner.run_one(self.output, 2)
        self.assertFalse((self.output / "run_02").exists())

    def test_interrupt_flushes_previous_rows_and_preserves_original_exception(self):
        for kind in (KeyboardInterrupt, SystemExit, RuntimeError):
            self.output = self.root / kind.__name__
            self.prepare_plan()
            error = kind("original fixture")
            first = self.plan["schedules"]["1"][0]
            with patch.object(runner, "run_worker", side_effect=[fixture_result(first, None), error]):
                with self.assertRaises(kind) as caught:
                    runner.run_one(self.output, 1)
            self.assertIs(caught.exception, error)
            metadata = read_json(self.output / "run_01/metadata.json")
            self.assertEqual(metadata["run_status"], "aborted" if kind is RuntimeError else "interrupted")
            self.assertEqual(metadata["repeat_count"], 1)
            self.assertEqual(len(read_csv(self.output / "run_01/repeats.csv")), 1)
            self.assertIn("Finalization also failed", " ".join(error.__notes__))
            self.assertFalse((self.output / "run_01/summary.csv").exists())

    def test_source_drift_invalidates_success(self):
        self.prepare_plan()
        original = runner._sources
        def sources():
            hashes = original()
            if (self.output / "run_01/summary.csv").exists():
                hashes["src/memory_runtime_validation.py"] = "0" * 64
            return hashes
        with patch.object(runner, "_sources", side_effect=sources), patch.object(runner, "run_worker", side_effect=fixture_result):
            metadata = runner.run_one(self.output, 1)
        self.assertEqual(metadata["run_status"], "invalid_provenance_changed")
        self.assertFalse(metadata["provenance_unchanged"])

    def test_plan_change_during_execution_invalidates_success(self):
        self.prepare_plan()
        def measure(request, path):
            if request["schedule_index"] == 0:
                plan = read_json(self.output / "plan.json")
                plan["attempt_reason"] = "fixture mid-run edit"
                runner.common._save_metadata(self.output / "plan.json", plan)
            return fixture_result(request, path)
        with patch.object(runner, "run_worker", side_effect=measure):
            metadata = runner.run_one(self.output, 1)
        self.assertEqual(metadata["run_status"], "invalid_provenance_changed")
        self.assertNotEqual(metadata["plan_sha256"], metadata["plan_sha256_at_end"])

    def test_summary_rejects_duplicates_unplanned_and_mismatched_keys(self):
        schedule = self.plan["schedules"]["1"]
        rows = [{**r, "reference_roundtrip_verified": True, **fixture_result(r, None)} for r in schedule]
        for invalid in ([*rows, rows[0]], [{**rows[0], "request_id": "unplanned"}],
                        [{**rows[0], "round_index": 9}]):
            with self.assertRaises(ValueError):
                runner.summarize(schedule, invalid)
        partial = runner.summarize(schedule, rows[:1])
        self.assertTrue(all(r["complete"] is False and r["median_bytes"] is None for r in partial))
        rows[0]["verified"] = 1 if rows[0]["arm"] == "codec" else False
        self.assertEqual(sum(not r["complete"] for r in runner.summarize(schedule, rows)), 1)

    def test_final_save_failure_never_leaves_completed_and_secondary_errors_do_not_mask(self):
        real_save = runner.common._save_metadata
        for fail_at in ("in_progress", "completed", "persistent"):
            self.output = self.root / fail_at
            self.prepare_plan()
            original = KeyboardInterrupt("original fixture")
            def save(path, payload):
                if "finalization_status" in payload and (fail_at == "persistent" or payload["finalization_status"] == fail_at):
                    raise OSError("fixture save failure")
                real_save(path, payload)
            with patch.object(runner.common, "_save_metadata", side_effect=save), \
                    patch.object(runner, "run_worker", side_effect=original if fail_at == "persistent" else fixture_result):
                with self.assertRaises(KeyboardInterrupt if fail_at == "persistent" else OSError) as caught:
                    runner.run_one(self.output, 1)
            metadata = read_json(self.output / "run_01/metadata.json")
            self.assertNotEqual(metadata["run_status"], "completed")
            if fail_at == "persistent":
                self.assertIs(caught.exception, original)
                self.assertIn("Finalization also failed", " ".join(original.__notes__))

    def test_coordinator_launches_separate_parents_sequentially_and_keeps_failures(self):
        calls = []
        def child(command, **kwargs):
            run_id = int(command[-1])
            calls.append(run_id)
            self.assertEqual(command[:4], [sys.executable, "-B", "-m", "src.memory_runtime_validation"])
            self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
            result = runner.run_one(self.output, run_id)
            kwargs["stdout"].write(b"artificial parent fixture\n")
            return subprocess.CompletedProcess(command, 0 if result["run_status"] == "completed" else 1)
        def measure(request, path):
            if request["run_id"] == 2 and request["schedule_index"] == 0:
                return runner._empty_result("worker_failed", "fixture failure")
            return fixture_result(request, path)
        with patch.object(runner.subprocess, "run", side_effect=child), patch.object(runner, "run_worker", side_effect=measure):
            metadata = runner.run_study(self.output, attempt_id="fixture")
        self.assertEqual(calls, [1, 2, 3])
        self.assertEqual(metadata["run_status"], "completed_with_failures")
        self.assertEqual(metadata["failed_repeat_count"], 1)
        self.assertEqual(metadata["repeat_count"], 360)
        self.assertFalse((self.output / "diagnostic_summary.json").exists())
        self.assertEqual(metadata["analysis_status"], "pending_independent_audit_and_diagnostics")

    def test_coordinator_parent_crash_stops_attempt_and_keeps_stdout(self):
        def crash(command, **kwargs):
            kwargs["stdout"].write(b"partial parent output")
            kwargs["stderr"].write(b"fixture crash")
            return subprocess.CompletedProcess(command, 7)
        with patch.object(runner.subprocess, "run", side_effect=crash) as launched:
            with self.assertRaises(FileNotFoundError):
                runner.run_study(self.output, attempt_id="fixture")
        self.assertEqual(launched.call_count, 1)
        self.assertEqual((self.output / "run_01_stdout.txt").read_bytes(), b"partial parent output")
        metadata = read_json(self.output / "metadata.json")
        self.assertEqual(metadata["run_status"], "aborted")
        self.assertEqual(metadata["runs"][0]["return_code"], 7)

    def test_three_real_parent_processes_with_artificial_worker_fixture(self):
        # Child CLI and file contracts are real; only the matrix and worker peaks
        # are patched in each temporary child. This is not a baseline experiment.
        script = '''
import sys
from unittest.mock import patch
from src import memory_runtime_validation as runner
sys.path.insert(0, str(runner.ROOT / "tests"))
from test_memory_runtime_validation import fixture_result
with patch.object(runner, "SIZES", (64,)), patch.object(runner, "FAMILIES", ("periodic_16",)), patch.object(runner, "run_worker", side_effect=fixture_result):
    raise SystemExit(runner.main(sys.argv[1:]))
'''
        real_run = subprocess.run
        def launch(command, **kwargs):
            return real_run([sys.executable, "-B", "-c", script, *command[4:]], **kwargs)
        with patch.object(runner.subprocess, "run", side_effect=launch):
            result = runner.run_study(self.output, attempt_id="fixture")
        self.assertEqual(result["run_status"], "completed")
        parents = [read_json(self.output / f"run_{run_id:02d}/metadata.json") for run_id in (1, 2, 3)]
        self.assertEqual(len({p["environment"]["pid"] for p in parents}), 3)
        self.assertTrue(all(p["environment"]["bytecode_disabled"] for p in parents))
        self.assertTrue(all(p["finalization_status"] == "completed" for p in parents))
        for run_id in (1, 2, 3):
            self.assertEqual(read_json(self.output / f"run_{run_id:02d}_stdout.txt")["run_status"], "completed")


@unittest.skipUnless(sys.platform == "win32", "Windows temporary adapter smoke test")
class AdapterSmokeTests(unittest.TestCase):
    def test_real_worker_adapter_for_each_arm_and_phase(self):
        with tempfile.TemporaryDirectory(prefix="runtime_adapter_smoke_") as temporary:
            original = b"ABCD" * 16
            compressed = runner.compressors.compress_data(original, "gzip")
            for phase, data, output in (("compress", original, compressed), ("decompress", compressed, original)):
                path = Path(temporary) / "input.bin"
                path.write_bytes(data)
                for arm in runner.worker.ARMS:
                    request = dict(request_id="temporary-smoke", arm=arm, algorithm="gzip", phase=phase,
                                   input_size=len(data), input_sha256=runner.common._digest(data),
                                   expected_output_sha256=runner.common._digest(output))
                    result = runner.run_worker(request, path)
                    self.assertEqual(result["status"], "ok", result)
                    self.assertEqual(result["return_code"], 0)


if __name__ == "__main__":
    unittest.main()
