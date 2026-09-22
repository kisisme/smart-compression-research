"""Worker contracts; mocked peaks are fixtures, real CLI calls are smoke tests.

All inputs/outputs are temporary. No study results or stored evidence are written.
"""

from __future__ import annotations

import copy
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

from src import memory_runtime_worker as worker


ROOT = Path(__file__).resolve().parent.parent


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class WorkerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="runtime_worker_fixture_")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "phase.bin"
        self.data = b"ABCD" * 16
        self.path.write_bytes(self.data)
        self.arguments = dict(request_id="fixture-request", arm="input_only", phase="compress",
                              algorithm="gzip", input_path=self.path,
                              input_sha256=digest(self.data), expected_output_sha256="a" * 64)
        for name, value in (("platform", "win32"), ("dont_write_bytecode", True)):
            patcher = patch.object(worker.sys, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.peak = patch.object(worker.memory_benchmark, "current_process_peak_working_set_bytes",
                                 return_value=123456).start()
        self.addCleanup(patch.stopall)

    def call(self, **changes) -> dict:
        return worker.measure_arm(**{**self.arguments, **changes})

    def cli_arguments(self, **changes) -> list[str]:
        values = {**self.arguments, **changes}
        return [part for key, value in values.items()
                for part in ("--input" if key == "input_path" else "--" + key.replace("_", "-"), str(value))]

    def test_import_only_never_reads_input_hashes_or_calls_codec(self) -> None:
        with patch.object(Path, "read_bytes", side_effect=AssertionError("input read")), \
                patch.object(worker, "_sha256", side_effect=AssertionError("hash called")), \
                patch.object(worker.compressors, "compress_data", side_effect=AssertionError("codec called")), \
                patch.object(worker.compressors, "decompress_data", side_effect=AssertionError("codec called")):
            for phase in worker.PHASES:
                result = self.call(arm="import_only", phase=phase, input_path=self.path.parent / "missing")
                self.assertEqual(result["status"], "ok")
                self.assertIsNone(result["observed_input_size"])
                self.assertIsNone(result["verified"])
                self.assertIsNone(result["input_verified"])

    def test_input_only_reads_actual_phase_input_and_never_calls_codec(self) -> None:
        compressed = worker.compressors.compress_data(self.data, "gzip")
        with patch.object(worker.compressors, "compress_data", side_effect=AssertionError("codec called")), \
                patch.object(worker.compressors, "decompress_data", side_effect=AssertionError("codec called")):
            for phase, data in (("compress", self.data), ("decompress", compressed)):
                self.path.write_bytes(data)
                result = self.call(phase=phase, input_sha256=digest(data))
                self.assertEqual(result["observed_input_size"], len(data))
                self.assertTrue(result["input_verified"])
                self.assertIsNone(result["verified"])
                self.assertEqual(result["status"], "ok")

    def test_codec_calls_only_selected_operation_once_for_all_algorithms(self) -> None:
        for algorithm in worker.ALGORITHMS:
            compressed = worker.compressors.compress_data(self.data, algorithm)
            for phase, data, expected in (("compress", self.data, compressed),
                                          ("decompress", compressed, self.data)):
                with self.subTest(algorithm=algorithm, phase=phase):
                    self.path.write_bytes(data)
                    selected = "compress_data" if phase == "compress" else "decompress_data"
                    other = "decompress_data" if phase == "compress" else "compress_data"
                    with patch.object(worker.compressors, selected,
                                      wraps=getattr(worker.compressors, selected)) as codec, \
                            patch.object(worker.compressors, other, side_effect=AssertionError("wrong codec")):
                        result = self.call(arm="codec", phase=phase, algorithm=algorithm,
                                           input_sha256=digest(data), expected_output_sha256=digest(expected))
                    codec.assert_called_once_with(data, algorithm)
                    self.assertTrue(result["verified"])
                    self.assertIsNone(result["input_verified"])
                    self.assertEqual(result["status"], "ok")

    def test_hash_failure_retains_peak_and_arm_specific_false(self) -> None:
        for arm, field in (("input_only", "input_verified"), ("codec", "verified")):
            with self.subTest(arm=arm):
                result = self.call(arm=arm, input_sha256="0" * 64, expected_output_sha256="0" * 64)
                self.assertEqual(result["status"], "verification_failed")
                self.assertIs(result[field], False)
                self.assertEqual(result["peak_process_working_set_bytes"], 123456)

    def test_wrong_restored_bytes_fail_output_verification(self) -> None:
        with patch.object(worker.compressors, "decompress_data", return_value=b"wrong"):
            result = self.call(arm="codec", phase="decompress", expected_output_sha256=digest(self.data))
        self.assertIs(result["verified"], False)
        self.assertEqual(result["status"], "verification_failed")

    def test_peak_follows_operation_and_digest_and_precedes_serialization(self) -> None:
        for arm in worker.ARMS:
            with self.subTest(arm=arm):
                events = []
                real_hash, real_dumps = worker._sha256, worker.json.dumps
                def hashed(data):
                    events.append("digest")
                    return real_hash(data)
                def peak():
                    events.append("peak")
                    return 123456
                def codec(data, algorithm):
                    events.append("codec")
                    return b"fixture output"
                def serialized(*args, **kwargs):
                    events.append("serialize")
                    return real_dumps(*args, **kwargs)
                with patch.object(worker, "_sha256", side_effect=hashed), \
                        patch.object(worker.compressors, "compress_data", side_effect=codec), \
                        patch.object(worker.memory_benchmark, "current_process_peak_working_set_bytes", side_effect=peak), \
                        patch.object(worker.json, "dumps", side_effect=serialized), redirect_stdout(io.StringIO()):
                    code = worker.main(self.cli_arguments(arm=arm, expected_output_sha256=digest(b"fixture output")))
                self.assertEqual(code, 0)
                prefix = {"import_only": [], "input_only": ["digest"], "codec": ["codec", "digest"]}[arm]
                self.assertEqual(events, prefix + ["peak", "serialize"])

    def test_invalid_requests_fail_before_input_or_peak(self) -> None:
        invalid = ({"request_id": " "}, {"arm": "invalid"}, {"phase": "invalid"},
                   {"algorithm": "invalid"}, {"input_sha256": "A" * 64},
                   {"input_sha256": "0" * 63}, {"expected_output_sha256": "g" * 64},
                   {"expected_output_sha256": None})
        with patch.object(Path, "read_bytes", side_effect=AssertionError("input read")):
            for changes in invalid:
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    self.call(**changes)
        self.peak.assert_not_called()

    def test_empty_or_missing_phase_input_is_rejected(self) -> None:
        self.path.write_bytes(b"")
        for arm in ("input_only", "codec"):
            with self.assertRaises(ValueError):
                self.call(arm=arm)
            with self.assertRaises(FileNotFoundError):
                self.call(arm=arm, input_path=self.path.parent / "missing")
        self.peak.assert_not_called()

    def test_environment_and_config_drift_rejected_before_measurement(self) -> None:
        with patch.object(worker.sys, "platform", "linux"), self.assertRaises(RuntimeError):
            self.call()
        with patch.object(worker.sys, "dont_write_bytecode", False), self.assertRaises(RuntimeError):
            self.call()
        changed = copy.deepcopy(worker.compressors._CONFIG)
        changed["compression"]["gzip"]["level"] = 1
        with patch.object(worker.memory_benchmark, "_load_config", return_value=changed):
            with self.assertRaises(ValueError):
                self.call()
            with patch.object(worker.compressors, "_CONFIG", changed), self.assertRaises(ValueError):
                self.call()
        self.peak.assert_not_called()

    def test_invalid_peak_or_backend_failure_has_no_success_cli_result(self) -> None:
        for bad in (0, -1, True, 1.5, None):
            self.peak.return_value = bad
            output = io.StringIO()
            with redirect_stdout(output):
                code = worker.main(self.cli_arguments())
            result = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "worker_failed")
            self.assertIsNone(result["peak_process_working_set_bytes"])
            self.assertIsNone(result["verified"])
        self.peak.side_effect = OSError("fixture backend failure")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(worker.main(self.cli_arguments()), 1)
        self.assertIn("fixture backend failure", json.loads(output.getvalue())["error"])

    def test_interrupt_is_not_converted_into_success_or_swallowed(self) -> None:
        for exception in (KeyboardInterrupt, SystemExit):
            with patch.object(worker.memory_benchmark, "current_process_peak_working_set_bytes",
                              side_effect=exception), redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(exception):
                    worker.main(self.cli_arguments())
            self.assertEqual(output.getvalue(), "")


@unittest.skipUnless(sys.platform == "win32", "Windows fresh-process smoke tests")
class WorkerCliSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="runtime_worker_smoke_")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "phase.bin"
        self.data = b"ABCD" * 16

    def invoke(self, arm, phase, algorithm, data, expected, optimization=None):
        self.path.write_bytes(data)
        command = [sys.executable, "-B"] + ([optimization] if optimization else [])
        command += ["-m", "src.memory_runtime_worker", "--request-id", "temporary-smoke",
                    "--arm", arm, "--phase", phase, "--algorithm", algorithm,
                    "--input", str(self.path if arm != "import_only" else self.path.parent / "missing"),
                    "--input-sha256", digest(data), "--expected-output-sha256", expected]
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                              text=True, encoding="utf-8", timeout=120)

    def test_fresh_workers_all_arms_algorithms_and_phases(self) -> None:
        for algorithm in worker.ALGORITHMS:
            compressed = worker.compressors.compress_data(self.data, algorithm)
            self.assertEqual(worker.compressors.decompress_data(compressed, algorithm), self.data)
            for phase, data, expected in (("compress", self.data, compressed),
                                          ("decompress", compressed, self.data)):
                for arm in worker.ARMS:
                    with self.subTest(algorithm=algorithm, phase=phase, arm=arm):
                        result = self.invoke(arm, phase, algorithm, data, digest(expected))
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, "")
                        payload = json.loads(result.stdout)
                        self.assertEqual((payload["request_id"], payload["arm"], payload["phase"], payload["algorithm"]),
                                         ("temporary-smoke", arm, phase, algorithm))
                        self.assertEqual(payload["design_id"], worker.DESIGN_ID)
                        self.assertEqual(payload["measurement_status"], "validation_only")
                        self.assertFalse(payload["score_inclusion"])
                        self.assertEqual(payload["status"], "ok")
                        self.assertIs(type(payload["peak_process_working_set_bytes"]), int)
                        self.assertGreater(payload["peak_process_working_set_bytes"], 0)
                        self.assertIs(payload["verified"], True if arm == "codec" else None)
                        self.assertIs(payload["input_verified"], True if arm == "input_only" else None)

    def test_digest_mismatch_remains_failure_under_optimization(self) -> None:
        for option in (None, "-O", "-OO"):
            result = self.invoke("codec", "compress", "gzip", self.data, "0" * 64, option)
            self.assertEqual(result.returncode, 2, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "verification_failed")
            self.assertIs(payload["verified"], False)
            self.assertGreater(payload["peak_process_working_set_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
