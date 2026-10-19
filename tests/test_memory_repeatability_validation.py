"""Exercise the frozen collector contract with the new no-window protocol.

Reuse the previous contract fixtures/tests in isolation, binding their helpers
to the new runner only for this test module. Peaks/ns/Git/times are artificial.
Actual temporary worker smoke inputs are not research measurements.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import unittest

from src import memory_repeatability_validation as runner
from src import memory_stability_validation as original_runner
import test_memory_stability_validation as fixtures


def setUpModule():
    global _runner_patch, _timing_patch
    original_payload = fixtures.timing_payload

    def payload(*args, **kwargs):
        value = original_payload(*args, **kwargs)
        value["design_id"] = runner.TIMING_WORKER_DESIGN_ID
        return value

    _runner_patch = patch.object(fixtures, "runner", runner)
    _timing_patch = patch.object(fixtures, "timing_payload", payload)
    _runner_patch.start()
    _timing_patch.start()


def tearDownModule():
    _timing_patch.stop()
    _runner_patch.stop()


class PlanTests(fixtures.PlanTests):
    def test_protocol_identity_worker_identity_and_numerical_policy(self):
        plan = runner.build_plan("fixture")
        self.assertEqual(plan["design_id"], "memory_repeatability_v1")
        self.assertEqual(plan["timing_worker_design_id"], "memory_stability_v1")
        self.assertEqual(plan["collector_revision"], 2)
        self.assertFalse(plan["metadata_io_policy"]["measurement_job_retry"])
        self.assertNotEqual(runner.DESIGN_PATH, original_runner.DESIGN_PATH)
        self.assertIn("src/memory_repeatability_validation.py", runner.SOURCE_PATHS)
        self.assertNotIn("src/memory_stability_validation.py", runner.SOURCE_PATHS)
        self.assertNotIn("day_offsets_hours", plan["criteria"])
        self.assertNotIn("second_run_gap_minutes", plan["criteria"])
        for field in ("delta", "epsilon", "w_memory_max", "memory_span_limit", "tie_order", "score_epsilon"):
            self.assertEqual(plan["criteria"][field], original_runner.CRITERIA[field])
        self.assertEqual(plan["candidate_weights"], original_runner.WEIGHTS)

    def test_schedule_windows_boundaries_and_local_dates(self):
        start = datetime(2026, 10, 19, 14, 59, tzinfo=timezone.utc)
        end = start + timedelta(minutes=2)
        history = [dict(run_id=1, started_at_utc=start.isoformat(), finished_at_utc=end.isoformat())]
        self.assertEqual(runner.schedule_issues(1, start.isoformat(), []), [])
        for after in (timedelta(0), timedelta(minutes=1), timedelta(hours=4), timedelta(days=10)):
            self.assertEqual(runner.schedule_issues(2, (end + after).isoformat(), history), [])
        self.assertEqual(runner.schedule_issues(2, (end - timedelta(microseconds=1)).isoformat(), history),
                         ["run_overlaps_previous"])
        self.assertIn("second_run_outside_gap_window", original_runner.schedule_issues(2, end.isoformat(), history))
        for run_id, prior in ((True, []), (2, []), (7, history), (1, history)):
            with self.assertRaises(ValueError):
                runner.schedule_issues(run_id, end.isoformat(), prior)
        with self.assertRaises(ValueError):
            runner.schedule_issues(1, "2026-10-19T00:00:00", [])
        for changed in ({**history[0], "run_id": True},
                        {**history[0], "finished_at_utc": start.isoformat(), "started_at_utc": end.isoformat()},
                        {**history[0], "finished_at_utc": "2026-10-19T00:00:00"}):
            with self.assertRaises(ValueError):
                runner.schedule_issues(2, end.isoformat(), [changed])


class AdapterTests(fixtures.AdapterTests):
    def test_worker_wire_protocol_is_distinct_from_study_identity(self):
        payload = fixtures.timing_payload(self.request)
        self.assertEqual(self.call(payload)["status"], "ok")
        payload["design_id"] = runner.DESIGN_ID
        self.assertEqual(self.call(payload)["status"], "invalid_result")

    def test_response_validation_remains_active_under_optimization(self):
        script = '''
from src import memory_repeatability_validation as runner
request = dict(phase='compress', algorithm='gzip')
try:
    runner._validate_memory(dict(operation='compress', algorithm='gzip', peak_process_working_set_bytes=True, verified=True), request, 0)
except ValueError:
    pass
else:
    raise SystemExit('boolean peak accepted')
try:
    runner.strict_json('{"a":1,"a":2}')
except ValueError:
    pass
else:
    raise SystemExit('duplicate JSON accepted')
'''
        for flag in (None, "-O", "-OO"):
            result = subprocess.run([sys.executable, "-B", *([flag] if flag else []), "-c", script],
                                    cwd=runner.ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class RunnerTests(fixtures.RunnerTests):
    def parent(self, command, **kwargs):
        run_id = int(command[command.index("--run-id") + 1])
        token = command[command.index("--token") + 1]
        self.assertEqual(command[:5], [sys.executable, "-B", "-m", "src.memory_repeatability_validation", "_run"])
        self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        result = runner.run_one(self.study, run_id, token)
        kwargs["stdout"].write(runner._json({k: result[k] for k in
                                           ("run_status", "repeat_count", "failed_repeat_count", "run_id")}).encode())
        return subprocess.CompletedProcess(command, 0 if result["run_status"] == "completed" else 1)

    def test_schedule_violation_and_environment_drift_are_recorded(self):
        self.run_fixture()
        self.now = "2026-10-19T00:01:00+00:00"  # Several days later is allowed.
        env = fixtures.fixture_environment()
        env["processor"] = "changed fixture CPU"
        with patch.object(runner, "_environment", return_value=env):
            result = self.run_fixture()
        self.assertEqual(result["validity_issues"], ["run_02:environment_differs_from_plan"])
        self.assertFalse(result["recording_checks_passed"])

    def test_adjacent_same_day_runs_are_complete_without_waiting(self):
        for _ in range(6):
            result = self.run_fixture()
        self.assertEqual(result["run_status"], "completed")
        self.assertEqual(result["validity_issues"], [])
        self.assertTrue(result["recording_checks_passed"])
        self.assertEqual(len(result["runs"]), 6)

    def test_overlap_aborts_before_workers_and_preserves_failure(self):
        self.run_fixture()
        self.now = "2026-10-13T23:59:59+00:00"
        with patch.object(runner, "run_worker") as worker, \
             patch.object(runner.subprocess, "run", side_effect=self.parent), self.assertRaises(ValueError):
            runner.run_next(self.study, fixtures.EVENTS)
        worker.assert_not_called()
        meta = fixtures.read_json(self.study / "run_02/metadata.json")
        self.assertEqual(meta["run_status"], "aborted")
        self.assertEqual(meta["validity_issues"], ["run_overlaps_previous"])

    def test_old_study_cannot_be_loaded_as_new_protocol(self):
        plan = fixtures.read_json(self.study / "plan.json")
        plan["design_id"] = original_runner.DESIGN_ID
        runner.common._save_metadata(self.study / "plan.json", plan)
        with self.assertRaisesRegex(ValueError, "fixed design"):
            self.run_fixture()
        self.assertFalse((self.study / "run_01").exists())

    def test_real_fresh_parent_cli_with_mocked_measurements(self):
        script = '''
import sys
from unittest.mock import patch
from src import memory_repeatability_validation as runner
sys.path.insert(0, str(runner.ROOT / 'tests'))
import test_memory_stability_validation as fixtures
fixtures.runner = runner
original_payload = fixtures.timing_payload
def payload(*args, **kwargs):
    value = original_payload(*args, **kwargs)
    value['design_id'] = runner.TIMING_WORKER_DESIGN_ID
    return value
fixtures.timing_payload = payload
with patch.object(runner, 'CORE_SIZES', ()), patch.object(runner, 'TINY_SIZES', (64,)), patch.object(runner, 'FAMILIES', ('periodic_16',)), patch.object(runner, 'run_worker', side_effect=fixtures.fixture_worker), patch.object(runner, '_environment', side_effect=fixtures.fixture_environment), patch.object(runner.common, '_git_information', side_effect=fixtures.fixture_git):
    raise SystemExit(runner.main(sys.argv[1:]))
'''
        real_run = subprocess.run

        def launch(command, **kwargs):
            return real_run([sys.executable, "-B", "-c", script, *command[4:]], **kwargs)

        with patch.object(runner.subprocess, "run", side_effect=launch):
            result = runner.run_next(self.study, fixtures.EVENTS)
        child = fixtures.read_json(self.study / "run_01/metadata.json")
        self.assertEqual(result["run_status"], "awaiting_next_run")
        self.assertEqual(child["design_id"], runner.DESIGN_ID)
        self.assertNotEqual(child["environment"]["pid"], os.getpid())
        self.assertTrue(child["environment"]["bytecode_disabled"])


class RealAdapterSmokeTests(fixtures.RealAdapterSmokeTests):
    pass


@unittest.skipUnless(sys.platform == "win32", "Actual Windows file-sharing fixtures")
class MetadataIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="repeatability_io_fixture_")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "metadata.json"
        self.path.write_text('{"version":1}\n', encoding="utf-8")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.kernel.CloseHandle.restype = wintypes.BOOL

    def deny_delete(self):
        handle = self.kernel.CreateFileW(str(self.path), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def test_actual_shared_reader_contention_recovers_after_close(self):
        with runner._open_shared_text(self.path) as reader:
            self.assertEqual(runner.strict_json(reader.read()), {"version": 1})
            with patch.object(runner.time, "sleep", side_effect=lambda delay: reader.close()) as sleep:
                runner._save_metadata(self.path, {"version": 2})
            self.assertEqual(sleep.call_count, 1)
        self.assertEqual(runner._read_json(self.path)["version"], 2)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_read_handle_closed_before_parsing_snapshot(self):
        parse = runner.strict_json

        def parse_after_replace(text):
            with patch.object(runner.time, "sleep") as sleep:
                runner._save_metadata(self.path, {"version": 2})
            sleep.assert_not_called()
            return parse(text)

        with patch.object(runner, "strict_json", side_effect=parse_after_replace):
            self.assertEqual(runner._read_json(self.path), {"version": 1})
        self.assertEqual(runner._read_json(self.path), {"version": 2})

    def test_actual_blocked_replace_then_release_recovers_without_worker(self):
        handle = self.deny_delete()
        try:
            with self.assertRaises(OSError) as caught:
                runner.common._save_metadata(self.path, {"version": 2})
            self.assertIn(caught.exception.winerror, (5, 32, 33))
            self.assertEqual(runner._read_json(self.path), {"version": 1})

            def release(delay):
                nonlocal handle
                self.assertEqual(delay, .05)
                self.assertTrue(self.kernel.CloseHandle(handle))
                handle = None

            metadata = {"version": 2}
            with patch.object(runner.time, "sleep", side_effect=release) as sleep, \
                 patch.object(runner, "run_worker") as worker:
                runner._save_metadata(self.path, metadata)
            sleep.assert_called_once()
            worker.assert_not_called()
            saved = runner._read_json(self.path)
            self.assertEqual(saved["version"], 2)
            self.assertEqual(len(saved["metadata_save_retry_events"]), 1)
            self.assertEqual(saved["metadata_save_retry_events"][0]["failed_attempt"], 1)
            self.assertEqual(list(self.path.parent.glob("*.tmp")), [])
        finally:
            if handle is not None:
                self.kernel.CloseHandle(handle)

    def test_persistent_actual_lock_aborts_at_bound_preserving_original(self):
        handle = self.deny_delete()
        first = []
        real_save = runner.common._save_metadata

        def save(*args):
            try:
                return real_save(*args)
            except OSError as exc:
                first.append(exc)
                raise

        metadata = {"version": 2}
        try:
            with patch.object(runner.common, "_save_metadata", side_effect=save) as writer, \
                 patch.object(runner.time, "sleep") as sleep, \
                 patch.object(runner, "run_worker") as worker, self.assertRaises(OSError) as caught:
                runner._save_metadata(self.path, metadata)
            self.assertIs(caught.exception, first[0])
            self.assertEqual(writer.call_count, 5)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [.05, .10, .15, .20])
            self.assertEqual(len(metadata["metadata_save_retry_events"]), 5)
            worker.assert_not_called()
            self.assertEqual(runner._read_json(self.path), {"version": 1})
            self.assertEqual(list(self.path.parent.glob("*.tmp")), [])
        finally:
            self.kernel.CloseHandle(handle)

    def test_other_errors_interrupts_and_nonfinite_json_are_not_retried(self):
        for error in (OSError("fixture non-Windows I/O error"), ValueError("fixture validation"),
                      KeyboardInterrupt(), SystemExit(23)):
            with self.subTest(error=type(error).__name__), \
                 patch.object(runner.common, "_save_metadata", side_effect=error) as save, \
                 patch.object(runner.time, "sleep") as sleep, self.assertRaises(type(error)) as caught:
                runner._save_metadata(self.path, {"version": 2})
            self.assertIs(caught.exception, error)
            save.assert_called_once()
            sleep.assert_not_called()
        with patch.object(runner.time, "sleep") as sleep, self.assertRaises(ValueError):
            runner._save_metadata(self.path, {"version": float("nan")})
        sleep.assert_not_called()
        self.assertEqual(runner._read_json(self.path), {"version": 1})

    def test_shared_reader_keeps_strict_json_validation(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}'):
            self.path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                runner._read_json(self.path)


if __name__ == "__main__":
    unittest.main()
