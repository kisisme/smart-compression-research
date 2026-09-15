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
