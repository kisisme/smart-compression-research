"""Timing contract fixtures and temporary CLI smoke tests, not study results."""

from __future__ import annotations

import copy
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src import memory_stability_timing_worker as worker


ROOT = Path(__file__).resolve().parent.parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


class TimingContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="stability_timing_fixture_")
        self.addCleanup(temporary.cleanup)
        self.original = Path(temporary.name) / "original.bin"
        self.reference = Path(temporary.name) / "compressed.bin"
        self.data = b"ABCD" * 16
        self.compressed = worker.compressors.compress_data(self.data, "gzip")
        self.original.write_bytes(self.data)
        self.reference.write_bytes(self.compressed)
        self.arguments = dict(request_id="fixture", algorithm="gzip", original=self.original,
                              reference_compressed=self.reference,
                              original_sha256=digest(self.data), compressed_sha256=digest(self.compressed))
        for owner, name, value in ((worker.sys, "platform", "win32"),
                                   (worker.sys, "dont_write_bytecode", True)):
            patcher = patch.object(owner, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(worker.time, "perf_counter_ns", side_effect=range(100, 1000, 7))
        self.clock = patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, **changes):
        return worker.measure_timing(**{**self.arguments, **changes})

    def cli_args(self, **changes):
        return [part for key, value in {**self.arguments, **changes}.items()
                for part in ("--" + key.replace("_", "-"), str(value))]

    def test_all_algorithms_have_ten_verified_raw_records(self):
        for algorithm in worker.ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                compressed = worker.compressors.compress_data(self.data, algorithm)
                self.reference.write_bytes(compressed)
                with patch.object(worker.compressors, "compress_data",
                                  wraps=worker.compressors.compress_data) as compress, \
                        patch.object(worker.compressors, "decompress_data",
                                     wraps=worker.compressors.decompress_data) as decompress:
                    result = self.call(algorithm=algorithm, compressed_sha256=digest(compressed))
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["design_id"], "memory_stability_v1")
                self.assertEqual(result["measurement_status"], "validation_only")
                self.assertIs(result["score_inclusion"], False)
                self.assertEqual(result["original_size"], len(self.data))
                self.assertEqual(result["compressed_size"], len(compressed))
                self.assertEqual(result["original_sha256"], digest(self.data))
                self.assertEqual(result["compressed_sha256"], digest(compressed))
                self.assertEqual([(r["phase"], r["repeat_index"]) for r in result["records"]],
                                 [(p, i) for p in ("compress", "decompress") for i in range(1, 6)])
                for record in result["records"]:
                    expected = compressed if record["phase"] == "compress" else self.data
                    self.assertEqual(record["elapsed_ns"], 7)
                    self.assertIs(type(record["elapsed_ns"]), int)
                    self.assertIs(record["verified"], True)
                    self.assertEqual(record["actual_output_sha256"], digest(expected))
                    self.assertEqual((record["status"], record["error"]), ("ok", ""))
                self.assertEqual(compress.call_count, 5)
                self.assertEqual(decompress.call_count, 5)
                self.assertEqual(compress.call_args.args, (self.data, algorithm))
                self.assertEqual(decompress.call_args.args, (compressed, algorithm))

    def test_file_reads_hashes_and_serialization_are_outside_timed_calls(self):
        events = []
        real_read, real_hash, real_json = Path.read_bytes, worker._sha256, json.dumps
        def read(path):
            events.append("read")
            return real_read(path)
        def hashed(data):
            events.append("hash")
            return real_hash(data)
        def timed():
            events.append("timer")
            return len(events)
        def compress(data, algorithm):
            events.append("compress")
            return self.compressed
        def decompress(data, algorithm):
            events.append("decompress")
            return self.data
        def serialized(*args, **kwargs):
            events.append("serialize")
            return real_json(*args, **kwargs)
        with patch.object(Path, "read_bytes", read), \
                patch.object(worker, "_sha256", side_effect=hashed), \
                patch.object(worker.time, "perf_counter_ns", side_effect=timed), \
                patch.object(worker.compressors, "compress_data", side_effect=compress), \
                patch.object(worker.compressors, "decompress_data", side_effect=decompress), \
                patch.object(worker.json, "dumps", side_effect=serialized), redirect_stdout(io.StringIO()):
            self.assertEqual(worker.main(self.cli_args()), 0)
        self.assertEqual(events, ["read", "hash", "read", "hash"]
                         + ["timer", "compress", "timer", "hash"] * 5
                         + ["timer", "decompress", "timer", "hash"] * 5 + ["serialize"])

    def test_all_compressed_outputs_remain_live_during_decompression(self):
        released = []
        class TrackedBytes(bytes):
            def __del__(self):
                released.append(True)
        def decompress(data, algorithm):
            gc.collect()
            self.assertEqual(released, [])
            return self.data
        with patch.object(worker.compressors, "compress_data", side_effect=lambda *_: TrackedBytes(self.compressed)), \
                patch.object(worker.compressors, "decompress_data", side_effect=decompress):
            self.assertEqual(self.call()["status"], "ok")
        gc.collect()
        self.assertEqual(len(released), 5)

    def test_output_byte_mismatch_continues_and_cli_returns_two(self):
        for phase in ("compress", "decompress"):
            with self.subTest(phase=phase):
                name = "compress_data" if phase == "compress" else "decompress_data"
                with patch.object(worker.compressors, name, return_value=b"wrong") as codec:
                    output = io.StringIO()
                    with redirect_stdout(output):
                        code = worker.main(self.cli_args())
                result = json.loads(output.getvalue())
                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "verification_failed")
                self.assertEqual(len(result["records"]), 10)
                self.assertEqual(codec.call_count, 5)
                bad = [r for r in result["records"] if r["phase"] == phase]
                self.assertTrue(all(r["verified"] is False and r["status"] == "verification_failed" for r in bad))
                self.assertTrue(all(r["actual_output_sha256"] == digest(b"wrong") for r in bad))

    def test_matching_output_digest_cannot_replace_exact_bytes_verification(self):
        def hash_fixture(data):
            return digest(self.compressed) if data == b"wrong" else digest(data)
        with patch.object(worker, "_sha256", side_effect=hash_fixture), \
                patch.object(worker.compressors, "compress_data", return_value=b"wrong"):
            result = self.call()
        self.assertEqual(result["status"], "verification_failed")
        self.assertIs(result["records"][0]["verified"], False)

    def test_invalid_requests_rejected_before_reads_or_codec(self):
        invalid = ({"request_id": " "}, {"algorithm": "invalid"},
                   {"original_sha256": "A" * 64}, {"compressed_sha256": "g" * 64},
                   {"original_sha256": None}, {"compressed_sha256": "0" * 63})
        with patch.object(Path, "read_bytes", side_effect=AssertionError("read")) as read, \
                patch.object(worker.compressors, "compress_data", side_effect=AssertionError("codec")) as codec:
            for changes in invalid:
                result = self.call(**changes)
                self.assertEqual(result["status"], "worker_failed")
                self.assertEqual(result["records"], [])
                self.assertIsNone(result["original_size"])
            read.assert_not_called()
            codec.assert_not_called()
        self.clock.assert_not_called()

    def test_input_hash_mismatch_rejected_before_timing(self):
        for field in ("original_sha256", "compressed_sha256"):
            with self.subTest(field=field), \
                    patch.object(worker.compressors, "compress_data", side_effect=AssertionError("codec")) as codec:
                result = self.call(**{field: "0" * 64})
                self.assertEqual(result["status"], "worker_failed")
                self.assertEqual(result["records"], [])
                self.assertIn("Input SHA-256 mismatch", result["error"])
                codec.assert_not_called()
        self.clock.assert_not_called()

    def test_missing_or_empty_inputs_preserve_only_observed_sizes_and_hashes(self):
        missing = self.original.parent / "missing"
        with patch.object(worker.compressors, "compress_data", side_effect=AssertionError("codec")) as codec:
            result = self.call(original=missing)
            self.assertIsNone(result["original_size"])
            self.assertIsNone(result["compressed_sha256"])
            self.assertEqual(result["status"], "worker_failed")
            result = self.call(reference_compressed=missing)
            self.assertEqual(result["original_sha256"], digest(self.data))
            self.assertIsNone(result["compressed_size"])
            for path in (self.original, self.reference):
                saved = path.read_bytes()
                path.write_bytes(b"")
                result = self.call()
                self.assertEqual(result["status"], "worker_failed")
                self.assertEqual(result["records"], [])
                field = "original_size" if path == self.original else "compressed_size"
                self.assertEqual(result[field], 0)
                path.write_bytes(saved)
            codec.assert_not_called()
        self.clock.assert_not_called()

    def test_environment_and_configuration_drift_rejected_before_reads(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("read")) as read:
            for name, value in (("platform", "linux"), ("dont_write_bytecode", False)):
                with patch.object(worker.sys, name, value):
                    self.assertEqual(self.call()["status"], "worker_failed")
            for section, key, value in (("timing", "repeats", 4), ("timing", "timer", "time.time"),
                                         ("timing", "aggregate", "mean"), ("compression", "gzip", {"level": 1})):
                changed = copy.deepcopy(worker.compressors._CONFIG)
                changed[section][key] = value
                with patch.object(worker.compressors, "_load_config", return_value=changed):
                    self.assertEqual(self.call()["status"], "worker_failed")
                    with patch.object(worker.compressors, "_CONFIG", changed):
                        self.assertEqual(self.call()["status"], "worker_failed")
            with patch.object(worker.compressors, "_GZIP_LEVEL", 1):
                self.assertEqual(self.call()["status"], "worker_failed")
            read.assert_not_called()
        self.clock.assert_not_called()

    def test_codec_failure_preserves_completed_and_failed_records(self):
        for phase in ("compress", "decompress"):
            name = "compress_data" if phase == "compress" else "decompress_data"
            expected = self.compressed if phase == "compress" else self.data
            with self.subTest(phase=phase), \
                    patch.object(worker.compressors, name, side_effect=[expected, expected, RuntimeError("fixture failure")]) as codec:
                result = self.call()
            count = 3 if phase == "compress" else 8
            self.assertEqual(len(result["records"]), count)
            self.assertEqual(codec.call_count, 3)
            self.assertEqual(result["status"], "worker_failed")
            self.assertTrue(all(r["status"] == "ok" for r in result["records"][:-1]))
            last = result["records"][-1]
            self.assertEqual((last["phase"], last["repeat_index"], last["status"]), (phase, 3, "worker_failed"))
            self.assertIsNone(last["elapsed_ns"])
            self.assertIsNone(last["verified"])
            self.assertIn("fixture failure", result["error"])

    def test_invalid_timer_values_stop_without_fabricating_remaining_records(self):
        for pair in ((10, 10), (10, 9), (True, 10), (10, False), (1.5, 10),
                     (10, float("nan")), (10, float("inf")), (None, 10)):
            with self.subTest(pair=pair), patch.object(worker.time, "perf_counter_ns", side_effect=pair):
                result = self.call()
            self.assertEqual(result["status"], "worker_failed")
            self.assertEqual(len(result["records"]), 1)
            self.assertEqual(result["records"][0]["status"], "worker_failed")
            json.dumps(result, allow_nan=False)
        with patch.object(worker.time, "perf_counter_ns", side_effect=[10, OSError("timer failure")]):
            result = self.call()
        self.assertEqual(result["status"], "worker_failed")
        self.assertIsNone(result["records"][0]["elapsed_ns"])

    def test_nonbytes_codec_output_and_unexpected_codec_exception_fail_cli(self):
        for behavior in ({"return_value": bytearray(b"wrong")},
                         {"side_effect": LookupError("unexpected codec failure")}):
            with patch.object(worker.compressors, "compress_data", **behavior), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(worker.main(self.cli_args()), 1)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "worker_failed")
            self.assertEqual(len(result["records"]), 1)
            self.assertIsNone(result["records"][0]["verified"])

    def test_interrupts_propagate_without_success_json(self):
        for exception in (KeyboardInterrupt, SystemExit):
            with patch.object(worker.compressors, "compress_data", side_effect=exception), \
                    redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(exception):
                    worker.main(self.cli_args())
            self.assertEqual(output.getvalue(), "")


@unittest.skipUnless(sys.platform == "win32", "Windows temporary subprocess smoke tests")
class TimingCliSmokeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="stability_timing_smoke_")
        self.addCleanup(temporary.cleanup)
        self.original = Path(temporary.name) / "original.bin"
        self.reference = Path(temporary.name) / "compressed.bin"
        self.data = b"ABCD" * 16
        self.original.write_bytes(self.data)

    def invoke(self, algorithm="gzip", optimization=None, reference=None, expected_original=None, extra=None):
        compressed = worker.compressors.compress_data(self.data, algorithm)
        self.reference.write_bytes(compressed if reference is None else reference)
        actual_reference = self.reference.read_bytes()
        command = [sys.executable, "-B"] + ([optimization] if optimization else [])
        command += ["-m", "src.memory_stability_timing_worker", "--request-id", "temporary-smoke",
                    "--algorithm", algorithm, "--original", str(self.original),
                    "--reference-compressed", str(self.reference),
                    "--original-sha256", digest(self.data) if expected_original is None else expected_original,
                    "--compressed-sha256", digest(actual_reference)] + (extra or [])
        completed = subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                   capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(self.original.read_bytes(), self.data)
        self.assertEqual(self.reference.read_bytes(), actual_reference)
        return completed

    def test_fresh_process_all_algorithms_success_schema(self):
        expected_fields = {"schema_version", "design_id", "measurement_status", "score_inclusion",
                           "request_id", "algorithm", "timer", "original_size", "compressed_size",
                           "original_sha256", "compressed_sha256", "records", "status", "error"}
        for algorithm in worker.ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                completed = self.invoke(algorithm)
                self.assertEqual((completed.returncode, completed.stderr), (0, ""))
                result = json.loads(completed.stdout)
                self.assertEqual(set(result), expected_fields)
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["request_id"], "temporary-smoke")
                self.assertEqual(result["algorithm"], algorithm)
                self.assertEqual(len(result["records"]), 10)
                self.assertIs(result["score_inclusion"], False)
                for record in result["records"]:
                    self.assertEqual(set(record), {"phase", "repeat_index", "elapsed_ns", "actual_output_sha256",
                                                   "verified", "status", "error"})
                    self.assertIs(type(record["elapsed_ns"]), int)
                    self.assertGreater(record["elapsed_ns"], 0)
                    self.assertIs(record["verified"], True)

    def test_failures_remain_failures_under_optimization(self):
        for option in (None, "-O", "-OO"):
            with self.subTest(option=option):
                rejected = self.invoke(optimization=option, expected_original="0" * 64)
                self.assertEqual(rejected.returncode, 1, rejected.stderr)
                result = json.loads(rejected.stdout)
                self.assertEqual(result["status"], "worker_failed")
                self.assertEqual(result["records"], [])
                # Valid gzip data and matching input hash, but wrong reference bytes.
                wrong = worker.compressors.compress_data(b"other original", "gzip")
                failed = self.invoke(optimization=option, reference=wrong)
                self.assertEqual(failed.returncode, 2, failed.stderr)
                result = json.loads(failed.stdout)
                self.assertEqual(result["status"], "verification_failed")
                self.assertEqual(len(result["records"]), 10)
                self.assertTrue(all(r["verified"] is False for r in result["records"]))
                invalid = self.invoke(optimization=option, reference=b"not gzip")
                self.assertEqual(invalid.returncode, 1, invalid.stderr)
                result = json.loads(invalid.stdout)
                self.assertEqual(result["status"], "worker_failed")
                self.assertEqual(len(result["records"]), 6)
                self.assertEqual(result["records"][-1]["status"], "worker_failed")

    def test_argument_parsing_failure_has_no_success_response(self):
        completed = self.invoke(extra=["--algorithm", "invalid"])
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("invalid choice", completed.stderr)


if __name__ == "__main__":
    unittest.main()
