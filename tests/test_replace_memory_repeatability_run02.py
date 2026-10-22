"""Artificial fixtures for full-run replacement; never research measurements."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from research_log import replace_memory_repeatability_run02 as tool


def small_plan():
    plan = tool.r.build_plan("replacement_fixture")
    plan["samples"] = plan["samples"][:1]
    sample_id = plan["samples"][0]["sample_id"]
    for kind in plan["expected_keys"]:
        plan["expected_keys"][kind] = [k for k in plan["expected_keys"][kind] if k[0] == sample_id]
    for run_id, jobs in plan["schedules"].items():
        plan["schedules"][run_id] = [v for v in jobs if v["sample_id"] == sample_id]
        for index, job in enumerate(plan["schedules"][run_id]):
            job.update(schedule_index=index, request_id=f"replacement_fixture:{run_id}:{index}")
    plan["source_sha256"] = {"fixture_only.py": "a" * 64}
    return plan


def make_saved(directory, plan, run_id=2):
    directory.mkdir()
    sample = plan["samples"][0]
    refs = [dict(sample_id=sample["sample_id"], algorithm=a, original_size=sample["size"],
                 compressed_size=100, original_sha256="a" * 64, compressed_sha256="b" * 64,
                 reference_roundtrip_verified=True, status="ok", error="") for a in tool.r.ALGORITHMS]
    tool.r._write_csv(directory / "references.csv", tool.r.REFERENCE_FIELDS, refs)
    raw = {"memory": [], "timing": []}
    for job in plan["schedules"][str(run_id)]:
        pairs = [(job["phase"], job["repeat_index"])] if job["kind"] == "memory" else [
            (phase, index) for phase in tool.r.PHASES for index in range(1, 6)]
        for phase, index in pairs:
            compress = phase == "compress"
            row = dict(attempt_id=plan["attempt_id"], run_id=run_id, sample_id=sample["sample_id"],
                algorithm=job["algorithm"], phase=phase, repeat_index=index, schedule_index=job["schedule_index"],
                request_id=job["request_id"], started_at_utc="2026-10-22T00:00:00+00:00",
                finished_at_utc="2026-10-22T00:00:01+00:00", argv="[]", python_executable="fixture_python",
                subprocess_options=json.dumps(tool.r.OPTIONS), input_size=sample["size"] if compress else 100,
                input_sha256=("a" if compress else "b") * 64,
                expected_output_sha256=("b" if compress else "a") * 64,
                reference_roundtrip_verified=True, bundle_status="ok", verified=True, status="ok", error="",
                return_code=0, stdout="{}", stderr="", input_verified_before=True, input_verified_after=True,
                actual_output_sha256=("b" if compress else "a") * 64)
            if job["kind"] == "memory":
                row.update(measurement_method=tool.r.common.METHOD,
                           peak_process_working_set_bytes=1000 + index * 10 + (100 if compress else 0))
            else:
                row.update(timer="time.perf_counter_ns", elapsed_ns=index * 1_000_000 + (100 if compress else 0))
            raw[job["kind"]].append(row)
    for kind, fields in (("memory", tool.r.MEMORY_FIELDS), ("timing", tool.r.TIMING_FIELDS)):
        tool.r._write_csv(directory / f"{kind}_repeats.csv", fields, raw[kind])
    tool.r._write_csv(directory / "measurements.csv", tool.r.MEASUREMENT_FIELDS,
                      tool.r.summarize(plan, run_id, raw["memory"], raw["timing"]))
    meta = dict(run_id=run_id, finalization_status="completed", finalization_errors=[], provenance_unchanged=True,
        validity_issues=[], measurement_status="validation_only", score_inclusion=False,
        source_sha256=plan["source_sha256"], source_sha256_at_end=plan["source_sha256"],
        planned_source_sha256=plan["source_sha256"],
        memory_repeat_count=len(raw["memory"]), timing_repeat_count=len(raw["timing"]),
        repeat_count=len(raw["memory"]) + len(raw["timing"]), job_count=len(plan["schedules"][str(run_id)]),
        failed_repeat_count=0, run_status="completed", started_at_utc="2026-10-22T00:00:00+00:00",
        finished_at_utc="2026-10-22T00:01:00+00:00", git=dict(commit_hash="fixture_execution_head"))
    meta["artifact_sha256"] = {n: tool.digest(directory / n) for n in tool.ARTIFACTS}
    tool.save(directory / "metadata.json", meta)
    return raw


class SavedValueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "run_02"
        self.plan = small_plan()
        self.raw = make_saved(self.directory, self.plan)

    def rewrite(self, name, fields, rows):
        path = self.directory / name
        path.unlink()  # Only this test's temporary fixture.
        tool.r._write_csv(path, fields, rows)
        meta = tool.read(self.directory / "metadata.json")
        meta["artifact_sha256"][name] = tool.digest(path)
        tool.save(self.directory / "metadata.json", meta)

    def test_independent_medians_and_complete_schedule(self):
        with patch.object(tool.r, "run_worker", side_effect=AssertionError("No measurement allowed")), \
             patch.object(tool.r, "summarize", side_effect=AssertionError("Independent calculation required")):
            result = tool.validate_saved(self.directory, self.plan, 2)
        self.assertTrue(result["record_integrity_checks_passed"])
        self.assertEqual(result["normal_pair_count"], 4)
        self.assertEqual(result["failed_repeat_count"], 0)

    def test_hash_tampering_is_detected(self):
        with (self.directory / "memory_repeats.csv").open("a") as stream:
            stream.write("tampering\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            tool.validate_saved(self.directory, self.plan, 2)

    def test_rehashed_wrong_median_is_detected(self):
        values = tool.csv_rows(self.directory / "measurements.csv")
        values[0]["peak_memory_bytes"] = "1"
        self.rewrite("measurements.csv", tool.r.MEASUREMENT_FIELDS, values)
        with self.assertRaisesRegex(ValueError, "median/ratio"):
            tool.validate_saved(self.directory, self.plan, 2)

    def test_rehashed_duplicate_key_is_detected(self):
        values = tool.csv_rows(self.directory / "memory_repeats.csv")
        values[-1] = dict(values[0])
        self.rewrite("memory_repeats.csv", tool.r.MEMORY_FIELDS, values)
        with self.assertRaisesRegex(ValueError, "Duplicate/unplanned"):
            tool.validate_saved(self.directory, self.plan, 2)

    def test_rehashed_request_identity_is_detected(self):
        values = tool.csv_rows(self.directory / "timing_repeats.csv")
        values[0]["request_id"] = "wrong_execution"
        self.rewrite("timing_repeats.csv", tool.r.TIMING_FIELDS, values)
        with self.assertRaisesRegex(ValueError, "schedule identity"):
            tool.validate_saved(self.directory, self.plan, 2)

    def test_failed_rows_are_preserved_and_pairs_stay_null(self):
        failed = self.raw["memory"][0]
        failed.update(status="timeout", bundle_status="timeout", verified=None,
                      peak_process_working_set_bytes=None, error="fixture timeout", return_code=None)
        self.rewrite("memory_repeats.csv", tool.r.MEMORY_FIELDS, self.raw["memory"])
        self.rewrite("measurements.csv", tool.r.MEASUREMENT_FIELDS,
            tool.r.summarize(self.plan, 2, self.raw["memory"], self.raw["timing"]))
        meta = tool.read(self.directory / "metadata.json")
        meta.update(failed_repeat_count=1, run_status="completed_with_failures")
        tool.save(self.directory / "metadata.json", meta)
        result = tool.validate_saved(self.directory, self.plan, 2)
        self.assertEqual(result["failed_repeat_count"], 1)
        self.assertEqual(result["failed_pair_count"], 1)
        self.assertEqual(result["preserved_failed_records"][0]["status"], "timeout")


class PreservationTests(unittest.TestCase):
    def test_publication_updates_manifest_and_keeps_actual_replacement_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            study, session = root / "study", root / "session"
            study.mkdir()
            session.mkdir()
            plan = small_plan()
            plan["implementation_commit"] = "fixture_original_measurement_head"
            runs = []
            for i in range(1, 7):
                directory = study / f"run_{i:02d}"
                make_saved(directory, plan, i)
                meta = tool.read(directory / "metadata.json")
                meta.update(started_at_utc=f"2026-10-22T0{i}:00:00+00:00",
                            finished_at_utc=f"2026-10-22T0{i}:01:00+00:00")
                tool.save(directory / "metadata.json", meta)
                runs.append(tool.validate_saved(directory, plan, i))
            coordinator = dict(runs=[dict(run_id=i) for i in range(1, 7)],
                artifact_sha256={f"run_{i:02d}/metadata.json": tool.digest(study / f"run_{i:02d}/metadata.json")
                                 for i in range(1, 7)})
            tool.save(study / "metadata.json", coordinator)
            make_saved(session / "new_run_02", plan)
            meta = tool.read(session / "new_run_02/metadata.json")
            meta.update(started_at_utc="2026-10-22T07:00:00+00:00", finished_at_utc="2026-10-22T07:01:00+00:00")
            tool.save(session / "new_run_02/metadata.json", meta)
            runs[1] = tool.validate_saved(session / "new_run_02", plan, 2)
            tool.save(session / "preflight.json", dict(fixture=True))
            record = dict(original_failed_repeats=3, original_snapshot="fixture_archive", observations={}, power_events=[])
            unchanged = tool.tree_hashes(study / "run_03")
            publication, summary = tool.prepare_publication(study, session, plan, record, runs)
            tool.publish_files(study, publication, session)
            self.assertEqual(summary["active_execution_order"], [1, 3, 4, 5, 6, 2])
            self.assertFalse(summary["original_collection_all_repeats_successful"])
            self.assertEqual(tool.tree_hashes(study / "run_03"), unchanged)
            manifest = tool.read(study / "evidence_manifest.json")["sha256"]
            self.assertTrue(all(tool.digest(study / n) == expected for n, expected in manifest.items()))
            coordinator = tool.read(study / "metadata.json")
            self.assertEqual(coordinator["run_status"], "completed_after_run_replacement")
            self.assertFalse(coordinator["recording_checks_passed"])
            self.assertEqual(coordinator["runs"][1]["started_at_utc"], "2026-10-22T07:00:00+00:00")
            self.assertEqual(coordinator["artifact_sha256"]["run_02/metadata.json"],
                             tool.digest(study / "run_02/metadata.json"))

    def test_archive_is_complete_and_ignores_only_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            study = root / "study"
            study.mkdir()
            (study / "run_02").mkdir()
            (study / "run_02/raw.csv").write_bytes(b"original\r\n")
            (study / tool.LOCK).write_text("own claim")
            manifest = tool.archive(study, root / "archive")
            self.assertEqual(manifest, {"run_02/raw.csv": tool.digest(study / "run_02/raw.csv")})
            self.assertEqual(tool.tree_hashes(root / "archive"), manifest)

    def test_publication_retains_displaced_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            study, prepared, session = (root / n for n in ("study", "publication", "session"))
            for directory in (study, prepared, session):
                directory.mkdir()
            (study / "old.json").write_text("original")
            (prepared / "old.json").write_text("new")
            tool.publish_files(study, prepared, session)
            self.assertEqual((study / "old.json").read_text(), "new")
            self.assertEqual((session / "displaced_active_files/old.json").read_text(), "original")
            self.assertEqual(tool.read(session / "installation.json")["status"], "installed")

    def test_failed_install_restores_original_without_deleting_new(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            study, prepared, session = (root / n for n in ("study", "publication", "session"))
            for directory in (study, prepared, session):
                directory.mkdir()
            (study / "a.json").write_text("original a")
            (study / "b.json").write_text("original b")
            (prepared / "a.json").write_text("new a")
            (prepared / "b.json").write_text("new b")
            real_replace = os.replace
            def replace(source, destination):
                if source == prepared / "b.json":
                    raise PermissionError("fixture install failure")
                return real_replace(source, destination)
            with patch.object(tool.os, "replace", side_effect=replace), self.assertRaises(PermissionError):
                tool.publish_files(study, prepared, session)
            self.assertEqual((study / "a.json").read_text(), "original a")
            self.assertEqual((study / "b.json").read_text(), "original b")
            self.assertEqual((session / "rolled_back_new_files/a.json").read_text(), "new a")
            self.assertEqual((prepared / "b.json").read_text(), "new b")
            self.assertEqual(tool.read(session / "installation.json")["status"], "rolled_back")

    def test_sleep_inhibition_is_released_on_measurement_error(self):
        api = Mock(side_effect=[0x80000000, 0x80000001])
        with self.assertRaisesRegex(RuntimeError, "fixture worker error"):
            with tool.awake(api) as record:
                raise RuntimeError("fixture worker error")
        self.assertTrue(record["restored"])
        self.assertEqual([call.args[0] for call in api.call_args_list], [0x80000001, 0x80000000])

    def test_failed_sleep_request_never_enters_measurement(self):
        api = Mock(return_value=0)
        entered = False
        with self.assertRaisesRegex(ValueError, "sleep inhibition"):
            with tool.awake(api):
                entered = True
        self.assertFalse(entered)

    def test_paths_cannot_escape_results(self):
        for path in (tool.ROOT, tool.ROOT / "data/results", tool.ROOT / "data/results/../../src"):
            with self.assertRaisesRegex(ValueError, "inside project"):
                tool.within_results(path)


if __name__ == "__main__":
    unittest.main()
