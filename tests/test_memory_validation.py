"""Failure-path fixtures below are artificial and are never research measurements."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src import memory_benchmark as benchmark
from src import memory_validation as validation


def fixture_result(peak: int = 100) -> benchmark.MemoryWorkerResult:
    return benchmark.MemoryWorkerResult(peak, True, "ok", "", 0, "fixture worker output", "")


def read_rows(directory: Path, filename: str) -> list[dict]:
    with (directory / filename).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class MemoryWorkerEvidenceTests(unittest.TestCase):
    def worker_reply(self, payload: object, code: int = 0) -> benchmark.MemoryWorkerResult:
        completed = subprocess.CompletedProcess([], code, json.dumps(payload), "fixture stderr")
        with patch.object(benchmark.subprocess, "run", return_value=completed):
            return benchmark.run_memory_worker("compress", "gzip", Path("unused.bin"), "0" * 64)

    def test_invalid_results_keep_original_worker_evidence(self) -> None:
        valid = {"operation": "compress", "algorithm": "gzip",
                 "peak_process_working_set_bytes": 100, "verified": True}
        for payload in ([], {**valid, "peak_process_working_set_bytes": 0},
                        {**valid, "peak_process_working_set_bytes": True},
                        {**valid, "operation": "decompress"},
                        {**valid, "algorithm": "zstd"}, {**valid, "verified": "True"}):
            with self.subTest(payload=payload):
                result = self.worker_reply(payload)
                self.assertEqual(result.status, "invalid_result")
                self.assertEqual(json.loads(result.stdout), payload)
                self.assertEqual(result.stderr, "fixture stderr")
        self.assertEqual(self.worker_reply({**valid, "peak_process_working_set_bytes": 0})
                         .peak_process_working_set_bytes, 0)
        self.assertEqual(self.worker_reply(valid, code=2).status, "invalid_result")

    def test_digest_failure_is_distinct_from_worker_crash(self) -> None:
        payload = {"operation": "compress", "algorithm": "gzip",
                   "peak_process_working_set_bytes": 123, "verified": False}
        result = self.worker_reply(payload, code=2)
        self.assertEqual(result.status, "verification_failed")
        self.assertFalse(result.verified)
        self.assertEqual(result.peak_process_working_set_bytes, 123)
        crashed = self.worker_reply(payload, code=7)
        self.assertEqual(crashed.status, "worker_failed")
        self.assertEqual(crashed.return_code, 7)
        self.assertEqual(json.loads(crashed.stdout), payload)

    def test_timeout_and_invalid_json_are_retained(self) -> None:
        timeout = subprocess.TimeoutExpired(["fixture"], 120, output=b"partial", stderr=b"timeout detail")
        with patch.object(benchmark.subprocess, "run", side_effect=timeout):
            result = benchmark.run_memory_worker("compress", "gzip", Path("unused.bin"), "0" * 64)
        self.assertEqual((result.status, result.stdout, result.stderr),
                         ("timeout", "partial", "timeout detail"))
        self.assertIsNone(result.peak_process_working_set_bytes)
        with patch.object(benchmark.subprocess, "run",
                          return_value=subprocess.CompletedProcess([], 0, "not JSON", "")):
            result = benchmark.run_memory_worker("compress", "gzip", Path("unused.bin"), "0" * 64)
        self.assertEqual((result.status, result.stdout), ("invalid_result", "not JSON"))


class AtomicMetadataTests(unittest.TestCase):
    def test_failed_serialization_sync_or_replace_preserves_previous_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="atomic_metadata_fixture_") as directory:
            path = Path(directory) / "metadata.json"
            original = b'{"status": "previous fixture"}\n'
            path.write_bytes(original)
            with self.assertRaises(ValueError):
                validation._save_metadata(path, {"invalid": float("nan")})
            self.assertEqual(path.read_bytes(), original)
            for operation in ("fsync", "replace"):
                with self.subTest(operation=operation):
                    with patch.object(validation.os, operation, side_effect=OSError("fixture storage failure")):
                        with self.assertRaisesRegex(OSError, "fixture storage failure"):
                            validation._save_metadata(path, {"status": "new fixture"})
                    self.assertEqual(path.read_bytes(), original)
                    self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_replace_receives_complete_json_beside_untouched_previous_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="atomic_metadata_fixture_") as directory:
            path = Path(directory) / "metadata.json"
            original = b'{"status": "previous fixture"}\n'
            path.write_bytes(original)
            payload = {"status": "new fixture", "text": "검증"}
            replace = validation.os.replace

            def inspect(source, destination):
                self.assertEqual(Path(source).parent, path.parent)
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(json.loads(Path(source).read_text(encoding="utf-8")), payload)
                replace(source, destination)

            with patch.object(validation.os, "replace", side_effect=inspect):
                validation._save_metadata(path, payload)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)
            self.assertEqual(list(Path(directory).iterdir()), [path])


@unittest.skipUnless(sys.platform == "win32", "Windows validation runner")
class MemoryValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="memory_validation_test_fixture_")
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "new_run"
        self.spec = {"sample_id": "fixture_000000", "generator": "random", "size": 64, "seed": 1}
        for target, value in (("build_validation_plan", [self.spec]),
                              ("_environment", {"test_fixture": True}),
                              ("_git_information", {"test_fixture": True})):
            patcher = patch.object(validation, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(validation, "ALGORITHMS", ("gzip",))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_successful_run_saves_raw_values_correct_aggregates_and_hashes(self) -> None:
        peaks = [10, 20, 30, 40, 50, 50, 60, 70, 80, 90]
        with patch.object(benchmark, "run_memory_worker", side_effect=[fixture_result(p) for p in peaks]):
            result = validation.run_validation(self.output)
        self.assertEqual(result["run_status"], "completed")
        self.assertEqual(result["finalization_status"], "completed")
        self.assertEqual(result["finalization_errors"], [])
        self.assertEqual(result["repeat_count"], 10)
        self.assertEqual(result["failed_repeat_count"], 0)
        rows = read_rows(self.output, "memory_repeats.csv")
        self.assertEqual([int(row["peak_process_working_set_bytes"]) for row in rows], peaks)
        self.assertTrue(all(row["reference_roundtrip_verified"] == "True" for row in rows))
        summary, = read_rows(self.output, "memory_summary.csv")
        self.assertEqual(float(summary["compression_peak_memory_bytes"]), 30)
        self.assertEqual(float(summary["decompression_peak_memory_bytes"]), 70)
        self.assertEqual(float(summary["peak_memory_bytes"]), 70)
        self.assertAlmostEqual(float(summary["compress_cv"]), statistics.pstdev(peaks[:5]) / 30)
        for name, digest in result["artifact_sha256"].items():
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), digest)
        self.assertFalse(result["score_inclusion"])

    def test_mid_run_failures_are_saved_and_remaining_repeats_continue(self) -> None:
        replies = [fixture_result() for _ in range(10)]
        replies[1] = benchmark.MemoryWorkerResult(0, True, "invalid_result", "zero peak", 0, "raw zero", "")
        replies[3] = benchmark.MemoryWorkerResult(150, False, "verification_failed", "digest mismatch", 2, "raw", "")
        replies[6] = benchmark.MemoryWorkerResult(None, None, "worker_failed", "crashed", 7, "partial", "traceback")
        with patch.object(benchmark, "run_memory_worker", side_effect=replies) as worker:
            result = validation.run_validation(self.output)
        self.assertEqual(worker.call_count, 10)
        self.assertEqual(result["run_status"], "completed_with_failures")
        self.assertEqual(result["failed_repeat_count"], 3)
        rows = read_rows(self.output, "memory_repeats.csv")
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[1]["peak_process_working_set_bytes"], "0")
        self.assertEqual(rows[3]["verified"], "False")
        self.assertEqual(rows[6]["stderr"], "traceback")
        self.assertEqual(rows[-1]["status"], "ok")
        summary, = read_rows(self.output, "memory_summary.csv")
        self.assertEqual(summary["verified"], "False")
        self.assertEqual(summary["peak_memory_bytes"], "")
        self.assertEqual(summary["compression_peak_memory_bytes"], "")

    def test_existing_directory_is_rejected_without_changing_results(self) -> None:
        self.output.mkdir()
        existing = self.output / "memory_repeats.csv"
        existing.write_bytes(b"existing user result\n")
        with patch.object(benchmark, "run_memory_worker") as worker:
            with self.assertRaises(FileExistsError):
                validation.run_validation(self.output)
        worker.assert_not_called()
        self.assertEqual(existing.read_bytes(), b"existing user result\n")
        self.assertEqual(list(self.output.iterdir()), [existing])

    def test_failed_reference_roundtrip_never_launches_workers(self) -> None:
        with patch.object(validation.compressors, "decompress_data", return_value=b"wrong"), \
                patch.object(benchmark, "run_memory_worker") as worker:
            result = validation.run_validation(self.output)
        worker.assert_not_called()
        self.assertEqual(result["failed_repeat_count"], 10)
        rows = read_rows(self.output, "memory_repeats.csv")
        self.assertTrue(all(row["status"] == "preparation_failed" for row in rows))
        self.assertTrue(all(row["reference_roundtrip_verified"] == "False" for row in rows))
        self.assertTrue(all(row["peak_process_working_set_bytes"] == "" for row in rows))

    def test_failed_generation_is_recorded(self) -> None:
        with patch.object(validation, "generate_sample", side_effect=ValueError("fixture failure")), \
                patch.object(benchmark, "run_memory_worker") as worker:
            result = validation.run_validation(self.output)
        worker.assert_not_called()
        self.assertEqual(result["failed_sample_count"], 1)
        sample, = read_rows(self.output, "samples.csv")
        self.assertEqual(sample["status"], "generation_failed")
        self.assertIn("fixture failure", sample["error"])
        self.assertEqual(len(read_rows(self.output, "memory_repeats.csv")), 10)

    def test_interruption_keeps_completed_repeats_and_marks_partial_run(self) -> None:
        with patch.object(benchmark, "run_memory_worker", side_effect=[fixture_result(), KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                validation.run_validation(self.output)
        metadata = json.loads((self.output / "memory_validation_metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["run_status"], "interrupted")
        self.assertEqual(metadata["repeat_count"], 1)
        self.assertEqual(len(read_rows(self.output, "memory_repeats.csv")), 1)
        self.assertEqual(read_rows(self.output, "memory_summary.csv"), [])


    def test_original_exception_survives_hash_and_persistent_save_failures(self) -> None:
        sources = validation._source_hashes()
        replace = validation.os.replace
        for kind in (RuntimeError, KeyboardInterrupt, SystemExit):
            for failure in ("hash", "save"):
                with self.subTest(kind=kind, failure=failure):
                    self.output = Path(self.temporary.name) / f"{kind.__name__}_{failure}"
                    original = kind("fixture original failure")

                    def fail_terminal_saves(source, destination):
                        payload = json.loads(Path(source).read_text(encoding="utf-8"))
                        if "finalization_status" in payload:
                            raise PermissionError("fixture persistent save failure")
                        replace(source, destination)

                    with patch.object(benchmark, "run_memory_worker", side_effect=[fixture_result(), original]), \
                            patch.object(validation, "_source_hashes", side_effect=[
                                sources, OSError("fixture hash failure") if failure == "hash" else sources]), \
                            patch.object(validation.os, "replace", side_effect=(
                                fail_terminal_saves if failure == "save" else replace)):
                        with self.assertRaises(kind) as caught:
                            validation.run_validation(self.output)
                    self.assertIs(caught.exception, original)
                    self.assertIn("Finalization also failed", " ".join(original.__notes__))
                    metadata = json.loads((self.output / "memory_validation_metadata.json").read_text())
                    if failure == "hash":
                        self.assertEqual(metadata["run_status"], "aborted" if kind is RuntimeError else "interrupted")
                        self.assertEqual(metadata["run_error"], f"{kind.__name__}: fixture original failure")
                        self.assertEqual(metadata["finalization_status"], "failed")
                        self.assertEqual(metadata["repeat_count"], 1)
                        self.assertEqual(len(metadata["artifact_sha256"]), 3)
                    else:
                        self.assertEqual(metadata["run_status"], "running")
                        self.assertIn("final_metadata_save", " ".join(original.__notes__))
                    self.assertEqual(len(read_rows(self.output, "memory_repeats.csv")), 1)
                    self.assertEqual(read_rows(self.output, "memory_summary.csv"), [])
                    self.assertEqual(list(self.output.glob("*.tmp")), [])

    def test_hash_failures_are_independent_and_cli_cannot_report_success(self) -> None:
        sources = validation._source_hashes()
        read_bytes = Path.read_bytes
        source_error = OSError("fixture source hash failure")
        csv_before = {}

        def end_source_hashes():
            saved = json.loads((self.output / "memory_validation_metadata.json").read_text())
            self.assertEqual(saved["run_status"], "finalizing")
            self.assertEqual(saved["finalization_status"], "in_progress")
            self.assertTrue(saved["finished_at_utc"])
            self.assertEqual(saved["repeat_status_counts"], {"ok": 10})
            csv_before.update({p.name: read_bytes(p) for p in self.output.glob("*.csv")})
            raise source_error

        def hashes():
            if not self.output.exists():
                return sources
            return end_source_hashes()

        def fail_one_csv(path):
            if path == self.output / "memory_repeats.csv":
                raise PermissionError("fixture artifact read failure")
            return read_bytes(path)

        with patch.object(benchmark, "run_memory_worker", return_value=fixture_result()), \
                patch.object(validation, "_source_hashes", side_effect=hashes), \
                patch.object(Path, "read_bytes", fail_one_csv):
            with self.assertRaises(OSError) as caught:
                validation.main(["--output-dir", str(self.output)])
        self.assertIs(caught.exception, source_error)
        saved = json.loads((self.output / "memory_validation_metadata.json").read_text())
        self.assertEqual(saved["run_status"], "finalization_failed")
        self.assertEqual(saved["run_status_before_finalization"], "completed")
        self.assertIsNone(saved["source_sha256_at_end"])
        self.assertIsNone(saved["provenance_unchanged"])
        self.assertEqual([e["stage"] for e in saved["finalization_errors"]],
                         ["source_sha256_at_end", "artifact_sha256:memory_repeats.csv"])
        self.assertEqual(set(saved["artifact_sha256"]), {"samples.csv", "memory_summary.csv"})
        self.assertEqual({p.name: p.read_bytes() for p in self.output.glob("*.csv")}, csv_before)

    def test_terminal_or_final_save_failure_never_leaves_completed_metadata(self) -> None:
        replace = validation.os.replace
        for failed_status in ("in_progress", "completed"):
            with self.subTest(failed_status=failed_status):
                self.output = Path(self.temporary.name) / failed_status

                def fail_selected_save(source, destination):
                    payload = json.loads(Path(source).read_text())
                    if payload.get("finalization_status") == failed_status:
                        raise PermissionError("fixture replace failure")
                    replace(source, destination)

                with patch.object(benchmark, "run_memory_worker", return_value=fixture_result()), \
                        patch.object(validation.os, "replace", side_effect=fail_selected_save):
                    with self.assertRaises(PermissionError) as caught:
                        validation.run_validation(self.output)
                saved = json.loads((self.output / "memory_validation_metadata.json").read_text())
                if failed_status == "in_progress":
                    self.assertEqual(saved["run_status"], "finalization_failed")
                    self.assertEqual(saved["finalization_errors"][0]["stage"], "terminal_checkpoint")
                else:
                    self.assertEqual(saved["run_status"], "finalizing")
                    self.assertEqual(saved["finalization_status"], "in_progress")
                    self.assertIn("final_metadata_save", " ".join(caught.exception.__notes__))
                self.assertEqual(saved["repeat_count"], 10)
                self.assertEqual(len(read_rows(self.output, "memory_repeats.csv")), 10)

    def test_source_change_still_invalidates_an_otherwise_complete_run(self) -> None:
        sources = validation._source_hashes()
        changed = {**sources, "src/memory_validation.py": "0" * 64}
        with patch.object(benchmark, "run_memory_worker", return_value=fixture_result()), \
                patch.object(validation, "_source_hashes", side_effect=[sources, changed]):
            result = validation.run_validation(self.output)
        self.assertEqual(result["run_status"], "invalid_provenance_changed")
        self.assertFalse(result["provenance_unchanged"])
        self.assertEqual(result["finalization_status"], "completed")


class ValidationPlanTests(unittest.TestCase):
    def test_fixed_matrix_and_seeds_cover_all_existing_generators_and_sizes(self) -> None:
        plan = validation.build_validation_plan(20260915)
        self.assertEqual(len(plan), len(validation.SAMPLE_SIZES) * len(validation.GENERATOR_NAMES))
        self.assertEqual(len({spec["sample_id"] for spec in plan}), len(plan))
        self.assertEqual([spec["seed"] for spec in plan], list(range(20260915, 20260915 + len(plan))))
        self.assertEqual(Counter((spec["generator"], spec["size"]) for spec in plan),
                         Counter((generator, size) for generator in validation.GENERATOR_NAMES
                                 for size in validation.SAMPLE_SIZES))
        with self.assertRaises(TypeError):
            validation.build_validation_plan(True)

    def test_duplicate_repeat_is_rejected_instead_of_aggregated(self) -> None:
        spec = {"sample_id": "fixture", "generator": "random", "size": 64, "seed": 1, "algorithm": "gzip"}
        rows = [{**spec, "phase": "compress", "repeat_index": 1} for _ in range(10)]
        with self.assertRaises(ValueError):
            validation.summarize_pair(rows, 5)


if __name__ == "__main__":
    unittest.main()
