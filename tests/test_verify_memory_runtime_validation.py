"""Full-sized synthetic evidence, with artificial peaks; never research data."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_log import verify_memory_runtime_validation as audit
from src import memory_runtime_validation as runner


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, payload):
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path, data):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


@unittest.skipUnless(sys.platform == "win32", "Fixture uses the Windows runner environment record")
class RuntimeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="runtime_audit_artificial_fixture_")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.original = cls.root / "original"

        def worker(request, path):
            peak = 10000 + request["round_index"] * 100 + request["run_id"] * 10 + runner.worker.ARMS.index(request["arm"])
            payload = runner.worker._response(request["request_id"], request["arm"], request["phase"], request["algorithm"])
            payload.update(status="ok", peak_process_working_set_bytes=peak,
                           observed_input_size=None if request["arm"] == "import_only" else request["input_size"],
                           verified=True if request["arm"] == "codec" else None,
                           input_verified=True if request["arm"] == "input_only" else None)
            return {**{k: payload[k] for k in ("status", "error", "verified", "input_verified", "peak_process_working_set_bytes")},
                    "return_code": 0, "stdout": json.dumps(payload), "stderr": ""}

        def parent(command, **kwargs):
            result = runner.run_one(cls.original, int(command[-1]))
            kwargs["stdout"].write(json.dumps({k: result[k] for k in ("run_status", "repeat_count", "failed_repeat_count")}).encode())
            return subprocess.CompletedProcess(command, 0)

        git = dict(commit_hash="a" * 40, worktree_dirty=True, status_porcelain="?? artificial_fixture\n")
        with patch.object(runner, "run_worker", side_effect=worker), \
                patch.object(runner.subprocess, "run", side_effect=parent), \
                patch.object(runner.common, "_git_information", return_value=git):
            result = runner.run_study(cls.original, attempt_id="artificial_fixture", reason="test only; synthetic peaks")
        if result["run_status"] != "completed":
            raise RuntimeError("Fixture setup failed")

    def setUp(self):
        self.directory = self.root / self._testMethodName
        shutil.copytree(self.original, self.directory)

    def reseal(self):
        # Tests deliberately refresh hashes after corrupting semantics, to prove
        # the audit checks more than manifest equality. Never used on real data.
        for run_id in (1, 2, 3):
            path = self.directory / f"run_{run_id:02d}/metadata.json"
            meta = load(path)
            meta["artifact_sha256"] = {name: audit.digest((path.parent / name).read_bytes()) for name in
                                       ("references.csv", "repeats.csv", "summary.csv")}
            save(path, meta)
        path = self.directory / "metadata.json"
        meta = load(path)
        meta["artifact_sha256"] = {name: audit.digest((self.directory / name).read_bytes()) for name in meta["artifact_sha256"]}
        save(path, meta)

    def corrupt_table(self, relative, edit):
        path = self.directory / relative
        data = rows(path)
        edit(data)
        write_rows(path, data)
        self.reseal()

    def rejected(self):
        with self.assertRaises((audit.AuditError, ValueError, KeyError, TypeError)):
            audit.audit(self.directory)

    def test_success_recalculates_full_matrix_without_runner_or_codec_and_preserves_bytes(self):
        before = {p.relative_to(self.directory): p.read_bytes() for p in self.directory.rglob("*") if p.is_file()}
        with patch.object(runner, "build_plan", side_effect=AssertionError("runner plan called")), \
                patch.object(runner, "generate_input", side_effect=AssertionError("runner generator called")), \
                patch.object(runner, "summarize", side_effect=AssertionError("runner summary called")), \
                patch.object(runner, "run_worker", side_effect=AssertionError("measurement called")), \
                patch.object(runner.compressors, "compress_data", side_effect=AssertionError("codec called")), \
                patch.object(runner.compressors, "decompress_data", side_effect=AssertionError("codec called")):
            report = audit.audit(self.directory)
        self.assertIs(report["audit_passed"], True)
        self.assertIs(report["score_inclusion"], False)
        self.assertEqual(report["sample_count"], 15)
        self.assertEqual(report["runs"], [dict(run_id=i, reference_count=60, repeat_count=1800, summary_count=360) for i in (1, 2, 3)])
        self.assertEqual({p.relative_to(self.directory): p.read_bytes() for p in self.directory.rglob("*") if p.is_file()}, before)
        for name, checksum in report["input_sha256"].items():
            self.assertEqual(hashlib.sha256((self.directory / name).read_bytes()).hexdigest(), checksum)

    def test_all_incomplete_failure_finalization_states_are_rejected(self):
        path = self.directory / "run_01/metadata.json"
        original = load(path)
        for state in ("running", "interrupted", "aborted", "finalizing", "finalization_failed", "completed_with_failures", "invalid_provenance_changed"):
            with self.subTest(state=state):
                save(path, {**original, "run_status": state})
                self.reseal()
                self.rejected()
        path = self.directory / "metadata.json"
        meta = load(path)
        meta["run_status"] = "running"
        save(path, meta)
        self.rejected()

    def test_metadata_types_counts_finalization_and_provenance(self):
        path = self.directory / "run_01/metadata.json"
        original = load(path)
        changes = ({"schema_version": True}, {"score_inclusion": 0}, {"failed_repeat_count": False},
                   {"repeat_count": 1799}, {"planned_repeat_count": 1}, {"repeat_status_counts": {"ok": 1}},
                   {"finalization_status": "in_progress"}, {"finalization_errors": [{"error": "failure"}]},
                   {"provenance_unchanged": False}, {"run_error": "hidden failure"},
                   {"plan_sha256_at_end": "0" * 64}, {"source_sha256_at_end": {}}, {"finished_at_utc": "invalid"},
                   {"git": {"commit_hash": None}}, {"environment_at_end": {}}, {"run_id": True})
        for change in changes:
            with self.subTest(change=change):
                save(path, {**original, **change})
                self.reseal()
                self.rejected()

    def test_artifact_and_source_hash_manifest_cannot_be_bypassed(self):
        path = self.directory / "run_01/repeats.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        self.rejected()
        self.reseal()
        meta_path = self.directory / "metadata.json"
        meta = load(meta_path)
        del meta["artifact_sha256"]["run_01/metadata.json"]
        save(meta_path, meta)
        self.rejected()
        plan = load(self.directory / "plan.json")
        plan["source_sha256"]["src/memory_runtime_validation.py"] = "0" * 64
        save(self.directory / "plan.json", plan)
        self.rejected()

    def test_plan_schedule_reduction_reordering_and_typed_fields_are_rejected(self):
        path = self.directory / "plan.json"
        original = path.read_bytes()
        for kind in ("missing", "duplicate", "reorder", "seed", "bool", "extra"):
            with self.subTest(kind=kind):
                plan = json.loads(original)
                schedule = plan["schedules"]["1"]
                if kind == "missing":
                    schedule.pop()
                elif kind == "duplicate":
                    schedule[1] = schedule[0]
                elif kind == "reorder":
                    schedule[0], schedule[1] = schedule[1], schedule[0]
                elif kind == "seed":
                    plan["base_seed"] += 1
                elif kind == "bool":
                    plan["run_ids"][0] = True
                else:
                    plan["extra"] = "unexpected"
                save(path, plan)
                self.rejected()

    def test_missing_duplicate_and_reordered_raw_rows_even_with_new_hashes(self):
        path = self.directory / "run_01/repeats.csv"
        original = rows(path)
        for kind in ("missing", "duplicate", "reorder"):
            data = [dict(r) for r in original]
            if kind == "missing":
                data.pop()
            elif kind == "duplicate":
                data[1] = data[0]
            else:
                data[0], data[1] = data[1], data[0]
            write_rows(path, data)
            self.reseal()
            self.rejected()

    def test_arm_rules_hashes_phase_input_and_failures_are_checked(self):
        path = self.directory / "run_01/repeats.csv"
        original = path.read_bytes()
        changes = ({"verified": "False"}, {"input_verified": "False"}, {"status": "timeout"},
                   {"return_code": "2"}, {"error": "failure"}, {"reference_roundtrip_verified": "False"},
                   {"peak_process_working_set_bytes": "0"}, {"peak_process_working_set_bytes": "nan"},
                   {"input_size": "1"}, {"input_sha256": "0" * 64}, {"expected_output_sha256": "0" * 64},
                   {"attempt_id": "other"}, {"family": "other"})
        for change in changes:
            with self.subTest(change=change):
                path.write_bytes(original)
                self.corrupt_table("run_01/repeats.csv", lambda data: data[0].update(change))
                self.rejected()

    def test_worker_json_identity_types_nulls_and_duplicates_are_checked(self):
        path = self.directory / "run_01/repeats.csv"
        original = path.read_bytes()
        for change in ({"request_id": "other"}, {"schema_version": True}, {"score_inclusion": 0},
                       {"peak_process_working_set_bytes": True}, {"observed_input_size": 1},
                       {"algorithm": "other"}, {"arm": "other"}, {"verified": 1}, {"extra": "value"}):
            path.write_bytes(original)
            def edit(data):
                payload = json.loads(data[0]["stdout"])
                payload.update(change)
                data[0]["stdout"] = json.dumps(payload)
            self.corrupt_table("run_01/repeats.csv", edit)
            self.rejected()
        for invalid in ('{"status":"ok","status":"ok"}', '{"value":NaN}', '[]', 'not JSON'):
            path.write_bytes(original)
            self.corrupt_table("run_01/repeats.csv", lambda data: data[0].update(stdout=invalid))
            self.rejected()

    def test_reference_hash_roundtrip_size_and_cross_run_consistency(self):
        path = self.directory / "run_02/references.csv"
        original = path.read_bytes()
        for change in ({"input_sha256": "0" * 64}, {"reference_roundtrip_verified": "False"},
                       {"compressed_size": "0"}, {"compressed_sha256": "invalid"},
                       {"compressed_sha256": "b" * 64}, {"error": "failure"}):
            path.write_bytes(original)
            self.corrupt_table("run_02/references.csv", lambda data: data[0].update(change))
            self.rejected()
        path.write_bytes(original)
        self.corrupt_table("run_02/references.csv", lambda data: data.__setitem__(1, data[0]))
        self.rejected()

    def test_summary_independent_statistics_and_group_completeness(self):
        path = self.directory / "run_01/summary.csv"
        original = path.read_bytes()
        for field in ("median_bytes", "min_bytes", "max_bytes", "population_std_bytes", "cv"):
            for value in ("999999", "nan", "inf", ""):
                path.write_bytes(original)
                self.corrupt_table("run_01/summary.csv", lambda data: data[0].update({field: value}))
                self.rejected()
        for change in ({"recorded_count": "4"}, {"failed_count": "1"}, {"complete": "False"}):
            path.write_bytes(original)
            self.corrupt_table("run_01/summary.csv", lambda data: data[0].update(change))
            self.rejected()
        path.write_bytes(original)
        self.corrupt_table("run_01/summary.csv", lambda data: data.__setitem__(1, data[0]))
        self.rejected()

    def test_csv_duplicate_header_extra_columns_and_truncated_rows(self):
        path = self.directory / "samples.csv"
        original = path.read_text(encoding="utf-8")
        for text in (original.replace("family", "sample_id", 1), original.replace("generation_parameters\n", "generation_parameters,extra\n", 1),
                     original + "partial\n"):
            path.write_text(text, encoding="utf-8")
            self.reseal()
            self.rejected()

    def test_duplicate_json_keys_and_nonfinite_metadata_are_rejected(self):
        path = self.directory / "metadata.json"
        original = path.read_text(encoding="utf-8")
        for prefix in ('"score_inclusion":false,', '"unexpected":NaN,', '"unexpected":1e999,'):
            path.write_text("{" + prefix + original[1:], encoding="utf-8")
            self.rejected()

    def test_parent_stdout_environment_and_run_time_order(self):
        path = self.directory / "run_02/metadata.json"
        original = path.read_bytes()
        for kind in ("overlap", "environment", "end_environment", "parent_record"):
            with self.subTest(kind=kind):
                meta = json.loads(original)
                if kind == "overlap":
                    meta["started_at_utc"] = load(self.directory / "metadata.json")["started_at_utc"]
                elif kind == "environment":
                    meta["environment"]["python_version"] = "other"
                    meta["environment_at_end"]["python_version"] = "other"
                elif kind == "end_environment":
                    meta["environment_at_end"]["pid"] += 1
                else:
                    save(self.directory / "run_02_stdout.txt", dict(run_status="completed", repeat_count=1, failed_repeat_count=0))
                save(path, meta)
                self.reseal()
                self.rejected()

    def test_concurrent_input_change_is_rejected(self):
        target = (self.directory / "samples.csv").resolve()
        real_read = Path.read_bytes
        calls = 0
        def changed(path):
            nonlocal calls
            data = real_read(path)
            if path.resolve() == target:
                calls += 1
                if calls > 1:
                    return data + b"changed after validation"
            return data
        with patch.object(Path, "read_bytes", changed):
            with self.assertRaisesRegex(audit.AuditError, "Input changed during audit"):
                audit.audit(self.directory)

    def test_cli_optimized_modes_fail_closed_and_output_is_exclusive(self):
        base = [sys.executable, "-B"]
        for optimization in ([], ["-O"], ["-OO"]):
            command = [*base, *optimization, "-m", "research_log.verify_memory_runtime_validation", "--experiment-dir", str(self.directory)]
            result = subprocess.run(command, cwd=runner.ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["audit_passed"])
        output = self.directory / "audit.json"
        command = [*base, "-m", "research_log.verify_memory_runtime_validation", "--experiment-dir", str(self.directory), "--output", str(output)]
        result = subprocess.run(command, cwd=runner.ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = output.read_bytes()
        result = subprocess.run(command, cwd=runner.ROOT, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(output.read_bytes(), saved)
        meta = load(self.directory / "metadata.json")
        meta["run_status"] = "interrupted"
        save(self.directory / "metadata.json", meta)
        for optimization in ([], ["-O"], ["-OO"]):
            bad_output = self.directory / ("failed" + "".join(optimization) + ".json")
            result = subprocess.run([*base, *optimization, "-m", "research_log.verify_memory_runtime_validation",
                                     "--experiment-dir", str(self.directory), "--output", str(bad_output)],
                                    cwd=runner.ROOT, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertFalse(bad_output.exists())


if __name__ == "__main__":
    unittest.main()
