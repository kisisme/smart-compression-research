"""Artificial full-size replacement evidence; peaks/ns/events/Git are NOT research data.

Only fixture preparation uses codecs. Audits must never execute producers/codecs.
"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import copy
from datetime import datetime, timedelta, timezone
import json
import io
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from research_log import verify_memory_repeatability_validation as audit
from research_log import replace_memory_repeatability_run02 as publisher
from src import memory_repeatability_validation as runner
import test_verify_memory_stability_validation as fixture

load, save, rows, write_rows = fixture.load, fixture.save, fixture.rows, fixture.write_rows


def seal_collection(root):
    for i in range(1, 7):
        path = root / f"run_{i:02d}/metadata.json"
        meta = load(path)
        meta["artifact_sha256"] = {n: audit.digest((path.parent / n).read_bytes()) for n in audit.ARTIFACTS}
        save(path, meta)
    top = load(root / "metadata.json")
    top["artifact_sha256"] = {n: audit.digest((root / n).read_bytes()) for n in top["artifact_sha256"]}
    save(root / "metadata.json", top)


def seal_original_manifest(root):
    files = {p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size, sha256=audit.digest(p.read_bytes()))
             for p in root.rglob("*") if p.is_file() and p.name != "evidence_manifest.json"}
    save(root / "evidence_manifest.json", dict(manifest_self_excluded=True, files=files,
         file_count=len(files), total_bytes=sum(v["bytes"] for v in files.values())))


def typed_rows(values):
    result = []
    ints = {"run_id", "repeat_index", "schedule_index", "input_size", "return_code", "peak_process_working_set_bytes", "elapsed_ns"}
    bools = {"reference_roundtrip_verified", "verified", "input_verified_before", "input_verified_after"}
    for row in values:
        value = dict(row)
        for key in ints & set(value):
            value[key] = int(value[key]) if value[key] else None
        for key in bools & set(value):
            value[key] = {"True": True, "False": False, "": None}[value[key]]
        result.append(value)
    return result


@unittest.skipUnless(sys.platform == "win32", "Full fixture records Windows paths")
class RepeatabilityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Share only the artificial fixture builder, not old audit acceptance logic.
        with patch.object(fixture, "runner", runner), patch.object(fixture, "audit", audit):
            fixture.StabilityAuditTests.setUpClass.__func__(cls)
        plan = load(cls.original / "plan.json")
        for i in range(1, 7):
            directory = cls.original / f"run_{i:02d}"
            values = rows(directory / "timing_repeats.csv")
            cache = {}
            for value in values:
                if value["stdout"] not in cache:
                    payload = json.loads(value["stdout"])
                    payload["design_id"] = runner.TIMING_WORKER_DESIGN_ID
                    cache[value["stdout"]] = json.dumps(payload)
                value["stdout"] = cache[value["stdout"]]
            write_rows(directory / "timing_repeats.csv", runner.TIMING_FIELDS, values)
            meta = load(directory / "metadata.json")
            meta.update(collector_revision=2, metadata_io_policy=runner.METADATA_IO_POLICY)
            save(directory / "metadata.json", meta)
        top = load(cls.original / "metadata.json")
        top.update(collector_revision=2, metadata_io_policy=runner.METADATA_IO_POLICY)
        save(cls.original / "metadata.json", top)
        fresh = cls.root / "fresh_run_02_artificial"
        shutil.copytree(cls.original / "run_02", fresh)
        # Three operational timeouts on distinct pairs, including partial stdout.
        memory = rows(cls.original / "run_02/memory_repeats.csv")
        chosen = set()
        for row in memory:
            key = row["sample_id"], row["algorithm"]
            if len(chosen) == 3:
                break
            if key in chosen:
                continue
            chosen.add(key)
            row.update(status="timeout", bundle_status="timeout", verified="", peak_process_working_set_bytes="",
                       return_code="", error="Artificial command timed out after 120 seconds")
            if len(chosen) == 1:
                row["stdout"] = ""
        write_rows(cls.original / "run_02/memory_repeats.csv", runner.MEMORY_FIELDS, memory)
        timing = rows(cls.original / "run_02/timing_repeats.csv")
        write_rows(cls.original / "run_02/measurements.csv", runner.MEASUREMENT_FIELDS,
                   runner.summarize(plan, 2, typed_rows(memory), typed_rows(timing)))
        meta = load(cls.original / "run_02/metadata.json")
        meta.update(run_status="completed_with_failures", run_status_before_finalization="completed_with_failures",
                    failed_repeat_count=3, recording_checks_passed=False,
                    repeat_status_counts=dict(Counter(v["status"] for v in memory + timing)))
        save(cls.original / "run_02/metadata.json", meta)
        save(cls.original / "run_02_stdout.txt", {k: meta[k] for k in ("run_id", "run_status", "repeat_count", "failed_repeat_count")})
        top = load(cls.original / "metadata.json")
        top.update(run_status="completed_with_failures", run_status_before_finalization="completed_with_failures",
                   failed_repeat_count=3, recording_checks_passed=False)
        top["runs"][1].update(return_code=1, run_status="completed_with_failures")
        save(cls.original / "metadata.json", top)
        seal_collection(cls.original)
        old_checks = [publisher.validate_saved(cls.original / f"run_{i:02d}", plan, i) for i in range(1, 7)]
        count = dict(memory_rows=20160, timing_rows=20160, jobs=22176, raw_rows=40320,
                     failed_repeats=3, pairs=2016, normal_pairs=2013, failed_pairs=3)
        save(cls.original / "collection_summary.json", dict(counts=count, run_count=6, all_repeats_successful=False,
             runs=old_checks, collector_final_status="completed_with_failures", preserved_failed_records=old_checks[1]["preserved_failed_records"]))
        # The real installation replaces every pre-existing publication file.
        # Retain the same file presence contract in the artificial original.
        for name in ("collection_completion.md", "run_02_completion.md"):
            (cls.original / name).write_text("ARTIFICIAL original completion\n", encoding="utf-8")
        for name in ("limited_record_check_run_02.json", "operator_context_run_02.json"):
            save(cls.original / name, dict(artificial_fixture=True))
        save(cls.original / "operator_events_run_02.json", fixture.EVENTS)
        save(cls.original / "windows_power_events_run_02.json", [])
        seal_original_manifest(cls.original)
        cls.template = cls.root / "template"
        cls.active = cls.template / "active"
        session = cls.template / "replacement"
        session.mkdir(parents=True)
        shutil.copytree(cls.original, cls.active)
        publisher.archive(cls.active, session / "original_snapshot")
        save(session / "original_manifest.json", publisher.tree_hashes(session / "original_snapshot"))
        shutil.copytree(fresh, session / "new_run_02")
        start = datetime.fromisoformat(top["finished_at_utc"]) + timedelta(hours=1)
        old_start = datetime.fromisoformat(load(fresh / "metadata.json")["started_at_utc"])
        shift = start - old_start
        new_meta = load(session / "new_run_02/metadata.json")
        new_meta["started_at_utc"] = start.isoformat()
        new_meta["finished_at_utc"] = (datetime.fromisoformat(new_meta["finished_at_utc"]) + shift).isoformat()
        end = datetime.fromisoformat(new_meta["finished_at_utc"])
        for kind, fields in (("memory", runner.MEMORY_FIELDS), ("timing", runner.TIMING_FIELDS)):
            values = rows(session / "new_run_02" / f"{kind}_repeats.csv")
            for value in values:
                for key in ("started_at_utc", "finished_at_utc"):
                    value[key] = (datetime.fromisoformat(value[key]) + shift).isoformat()
            write_rows(session / "new_run_02" / f"{kind}_repeats.csv", fields, values)
        pid = plan["environment"]["pid"]
        observation = dict(observed_at_utc=(start - timedelta(seconds=1)).isoformat(), ac_line_status=1, battery_percent=80,
            boot_at=(start - timedelta(minutes=30)).isoformat(), observation_scope="ARTIFICIAL FIXTURE ONLY",
            python_processes=[dict(ProcessId=pid, ParentProcessId=pid+1, Name="python.exe", CommandLine="python -B " + audit.ADAPTER_PATH)])
        after = {**observation, "observed_at_utc": (end + timedelta(seconds=1)).isoformat()}
        execution_git = dict(commit_hash="b" * 40, worktree_dirty=False, status_porcelain="")
        new_meta.pop("operator_events")
        new_meta.update(git=execution_git, execution_amendment=audit.AMENDMENT,
            execution_role="replacement_of_logical_run_02_after_run_06", measurement_code_commit=plan["implementation_commit"],
            operator_observations=dict(before=observation))
        new_meta["artifact_sha256"] = {n: audit.digest((session / "new_run_02" / n).read_bytes()) for n in audit.ARTIFACTS}
        save(session / "new_run_02/metadata.json", new_meta)
        new_check = publisher.validate_saved(session / "new_run_02", plan, 2)
        record = dict(amendment_id=audit.AMENDMENT, status="validated_ready_to_install", session_dir=str(session),
            original_snapshot=str(session / "original_snapshot"), execution_git=execution_git,
            adapter_sha256={n: audit.digest((audit.ROOT / n).read_bytes()) for n in (audit.ADAPTER_PATH, audit.AMENDMENT_PATH)},
            original_measurement_code_commit=plan["implementation_commit"], original_failed_repeats=3,
            observations=dict(before=observation, after=after), validation_only=True, score_inclusion=False,
            idle_sleep_inhibition=dict(api="SetThreadExecutionState", requested_flags=0x80000001, previous_flags=0x80000000,
                acquired_at_utc=(start - timedelta(microseconds=1)).isoformat(), released_at_utc=(end + timedelta(microseconds=1)).isoformat(), restored=True),
            power_events=[], new_run_summary=new_check, actual_active_execution_order=[1,3,4,5,6,2],
            original_collection_status="completed_with_failures", independent_protocol_audit_performed=False)
        preflight = {k: record[k] for k in ("amendment_id", "session_dir", "original_snapshot", "execution_git", "adapter_sha256",
            "original_measurement_code_commit", "original_failed_repeats", "validation_only", "score_inclusion")}
        preflight.update(status="preparing", environment=plan["environment"], observations=dict(before=observation),
            plan_sha256=audit.digest((cls.active / "plan.json").read_bytes()), original_runs=old_checks,
            actual_active_order_after_replacement=[1,3,4,5,6,2], user_instruction="ARTIFICIAL authorization fixture")
        save(session / "preflight.json", preflight)
        save(session / "new_run_saved_check.json", new_check)
        save(session / "power_events.json", [])
        active_checks = [new_check if v["run_id"] == 2 else v for v in old_checks]
        publication, _ = publisher.prepare_publication(cls.active, session, plan, record, active_checks)
        publisher.publish_files(cls.active, publication, session)
        checkpoint = session / "publication_preinstall_checkpoint"
        checkpoint.mkdir()
        for name in ("run_02_replacement.json", "metadata.json", "collection_summary.json", "limited_record_check_run_02.json", "evidence_manifest.json"):
            shutil.copy2(cls.active / name, checkpoint / name)
        record.update(status="installed_and_verified", finished_at_utc=runner.common._now(),
                      unchanged_other_run_files=True, original_snapshot_hashes_verified=True)
        save(session / "replacement.json", record)
        final = {**record, "record_scope": "Artificial verified installation", "transaction_status_file": str(session / "installation.json")}
        save(cls.active / "run_02_replacement.json", final)
        for name in ("metadata.json", "collection_summary.json", "limited_record_check_run_02.json", "evidence_manifest.json"):
            value = load(cls.active / name)
            value["replacement"] = final
            save(cls.active / name, value)
        value = load(cls.active / "evidence_manifest.json")
        value["sha256"] = {n:v for n,v in publisher.tree_hashes(cls.active).items() if n != "evidence_manifest.json"}
        save(cls.active / "evidence_manifest.json", value)
        save(session / "post_replacement_verification.json", dict(saved_integrity_checks_passed=True,
            archive_file_count=len(publisher.tree_hashes(session / "original_snapshot")), archive_hashes_match=True,
            unchanged_other_run_file_count=25, unchanged_other_run_hashes_match=True,
            active_manifest_file_count=len(publisher.tree_hashes(cls.active))-1, active_manifest_complete=True,
            original_run_02_failed_repeats=3, new_run_02=new_check, active_execution_order=[1,3,4,5,6,2],
            execution_commit=execution_git["commit_hash"], measurement_code_commit=plan["implementation_commit"],
            idle_sleep_inhibition_restored=True, power_event_query_result=[], original_collection_success_claimed=False,
            independent_protocol_audit_performed=False, candidate_score_analysis_performed=False,
            memory_formally_adopted=False, score_inclusion=False,
            active_totals=dict(jobs=22176,memory_rows=20160,timing_rows=20160,failed_repeats=0,pairs=2016,verified_pairs=2016)))
        # A valid baseline is mandatory before negative mutations can count.
        with patch.object(audit, "generated_samples", return_value=cls.canonical_samples):
            cls.valid_report = audit.audit(cls.active, session)
            if cls.valid_report["audit_passed"] is not True:
                raise RuntimeError("Artificial baseline did not pass")

    def setUp(self):
        self.case = self.root / self._testMethodName
        shutil.copytree(self.template, self.case)
        self.addCleanup(shutil.rmtree, self.case)
        self.directory, self.session = self.case / "active", self.case / "replacement"
        if self._testMethodName not in {"test_full_success_is_read_only_and_independent", "test_mutation_during_audit_is_rejected"}:
            self.addCleanup(patch.stopall)
            patch.object(audit, "generated_samples", return_value=self.canonical_samples).start()

    def rejected(self, expression=None):
        with self.assertRaisesRegex(audit.AuditError, expression or ".+"):
            audit.audit(self.directory, self.session)

    def reseal_active(self):
        seal_collection(self.directory)
        for name in audit.ARTIFACTS + ("metadata.json",):
            shutil.copy2(self.directory / "run_02" / name, self.session / "new_run_02" / name)
        value = load(self.directory / "evidence_manifest.json")
        value["sha256"] = {n:v for n,v in publisher.tree_hashes(self.directory).items() if n != "evidence_manifest.json"}
        save(self.directory / "evidence_manifest.json", value)

    def reseal_archive(self):
        root = self.session / "original_snapshot"
        seal_collection(root)
        seal_original_manifest(root)
        save(self.session / "original_manifest.json", publisher.tree_hashes(root))

    def test_full_success_is_read_only_and_independent(self):
        before = publisher.tree_hashes(self.case)
        prohibited = AssertionError("Audit called producer/codec/old audit")
        with patch.object(runner, "run_worker", side_effect=prohibited), \
             patch.object(runner, "summarize", side_effect=prohibited), \
             patch.object(runner, "build_plan", side_effect=prohibited), \
             patch.object(publisher, "validate_saved", side_effect=prohibited), \
             patch.object(publisher, "execute", side_effect=prohibited), \
             patch.object(runner.compressors, "compress_data", side_effect=prohibited), \
             patch.object(runner.compressors, "decompress_data", side_effect=prohibited), \
             patch.object(audit.base, "audit", side_effect=prohibited):
            report = audit.audit(self.directory, self.session)
        self.assertTrue(report["audit_passed"])
        self.assertEqual(report["active_counts"]["failed_repeats"], 0)
        self.assertEqual(report["original_counts"]["failed_repeats"], 3)
        self.assertEqual(report["active_execution_order"], [1,3,4,5,6,2])
        self.assertFalse(report["score_inclusion"])
        self.assertEqual(before, publisher.tree_hashes(self.case))

    def test_old_three_day_auditor_still_rejects_new_protocol(self):
        with self.assertRaises(audit.AuditError):
            audit.base.audit(self.directory)

    def test_fixed_plan_policy_and_regenerated_samples_cannot_change(self):
        path = self.directory / "plan.json"
        original = load(path)
        for change in (dict(collector_revision=1), dict(base_seed=0), dict(design_id="memory_stability_v1")):
            save(path, {**original, **change})
            self.rejected("Fixed plan/schedule/key mismatch")
        save(path, original)
        path = self.directory / "samples.csv"
        values = rows(path)
        values[0]["duplicate_of"] = values[1]["sample_id"]
        write_rows(path, runner.SAMPLE_FIELDS, values)
        self.rejected("Regenerated sample/hash/parameters/duplicates mismatch")

    def test_rehashed_boolean_count_and_invalid_metadata_retry_are_rejected(self):
        path = self.directory / "run_02/metadata.json"
        original = load(path)
        for change in (dict(repeat_count=True), dict(metadata_save_retry_events=[dict(occurred_at_utc=original["started_at_utc"],
            target="measurements.csv", failed_attempt=1, winerror=5, error="ARTIFICIAL bad retry")]),
            dict(metadata_save_retry_events=[dict(occurred_at_utc=original["started_at_utc"], target="metadata.json",
                  failed_attempt=2, winerror=5, error="ARTIFICIAL omitted first failure")])):
            save(path, {**original, **change})
            self.reseal_active()
            self.rejected("Metadata mismatch|Invalid metadata-only retry evidence|Metadata retry chain is incomplete")
        save(path, original)

    def test_sleep_evidence_rejects_resume_and_failed_restore(self):
        record = load(self.directory / "run_02_replacement.json")
        meta = load(self.directory / "run_02/metadata.json")
        preflight = load(self.session / "preflight.json")
        old_end = audit.timestamp(load(self.session / "original_snapshot/metadata.json")["finished_at_utc"])
        for change in (dict(idle_sleep_inhibition={**record["idle_sleep_inhibition"],"restored":False}),
                       dict(power_events=[dict(Id=506,ProviderName="Microsoft-Windows-Kernel-Power",Message="ARTIFICIAL sleep",
                                               time_created_utc=meta["started_at_utc"])])):
            with self.assertRaisesRegex(audit.AuditError, "Sleep inhibition|Sleep/resume"):
                audit.check_observations({**record,**change},meta,preflight,old_end)

    def test_source_change_during_audit_is_rejected_without_editing_real_source(self):
        source = audit.ROOT / "src/data_generator.py"
        original = Path.read_bytes
        seen = 0
        def read(path):
            nonlocal seen
            data = original(path)
            if path == source:
                seen += 1
                if seen > 1:
                    return data + b"\n# artificial race fixture\n"
            return data
        with patch.object(Path, "read_bytes", read):
            self.rejected("Evidence/source changed during audit")

    def test_report_write_failure_removes_only_its_new_output(self):
        output = self.case / "failed_write.json"
        report = copy.deepcopy(self.valid_report)
        report["evidence_directories"] = dict(active=str(self.directory),replacement=str(self.session))
        with patch.object(audit,"audit",return_value=report), patch.object(audit.os,"fsync",side_effect=OSError("ARTIFICIAL fsync failure")), \
             redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            audit.main(["--experiment-dir",str(self.directory),"--replacement-dir",str(self.session),"--output",str(output)])
        self.assertFalse(output.exists())

    def test_input_change_during_report_write_rejects_and_removes_output(self):
        output = self.case / "changed_during_write.json"
        report = copy.deepcopy(self.valid_report)
        report["evidence_directories"] = dict(active=str(self.directory),replacement=str(self.session))
        def change(_):
            path = self.directory / "samples.csv"
            path.write_bytes(path.read_bytes()+b"\n")
        with patch.object(audit,"audit",return_value=report), patch.object(audit.os,"fsync",side_effect=change), \
             redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            audit.main(["--experiment-dir",str(self.directory),"--replacement-dir",str(self.session),"--output",str(output)])
        self.assertFalse(output.exists())

    def test_csv_schema_and_nonfinite_metric_are_rejected_after_rehash(self):
        path = self.directory / "run_02/measurements.csv"
        original = path.read_bytes()
        path.write_bytes(original.replace(b"compression_ratio,",b"wrong_header,",1))
        self.reseal_active()
        self.rejected("Wrong CSV header")
        path.write_bytes(original)
        values = rows(path)
        values[0]["compression_ratio"] = "nan"
        write_rows(path, runner.MEASUREMENT_FIELDS, values)
        self.reseal_active()
        self.rejected("Incorrect ratio/median/max")

    def test_rehashed_wrong_median_is_rejected(self):
        path = self.directory / "run_02/measurements.csv"
        values = rows(path)
        values[0]["peak_memory_bytes"] = "1"
        write_rows(path, runner.MEASUREMENT_FIELDS, values)
        self.reseal_active()
        self.rejected("Incorrect ratio/median/max")

    def test_rehashed_raw_value_and_stdout_disagreement_is_rejected(self):
        path = self.directory / "run_02/memory_repeats.csv"
        values = rows(path)
        values[0]["peak_process_working_set_bytes"] = "42"
        write_rows(path, runner.MEMORY_FIELDS, values)
        self.reseal_active()
        self.rejected("Worker stdout/raw/request mismatch")

    def test_rehashed_job_reorder_is_rejected(self):
        path = self.directory / "run_02/memory_repeats.csv"
        values = rows(path)
        values[0], values[1] = values[1], values[0]
        write_rows(path, runner.MEMORY_FIELDS, values)
        self.reseal_active()
        self.rejected("Wrong phase path|Worker argv/request mismatch|Raw identity/reference/input mismatch")

    def test_original_manifest_and_preflight_history_are_required(self):
        path = self.session / "original_snapshot/evidence_manifest.json"
        original = path.read_bytes()
        path.unlink()
        save(self.session / "original_manifest.json", publisher.tree_hashes(self.session / "original_snapshot"))
        self.rejected("Original evidence manifest is missing")
        path.write_bytes(original)
        save(self.session / "original_manifest.json", publisher.tree_hashes(self.session / "original_snapshot"))
        preflight = load(self.session / "preflight.json")
        preflight["original_runs"][1]["failed_repeat_count"] = 0
        save(self.session / "preflight.json", preflight)
        self.rejected("Preflight original history differs")

    def test_rehashed_worker_wire_protocol_is_not_study_id(self):
        path = self.directory / "run_02/timing_repeats.csv"
        values = rows(path)
        payload = json.loads(values[0]["stdout"])
        payload["design_id"] = runner.DESIGN_ID
        for row in values[:10]:
            row["stdout"] = json.dumps(payload)
        write_rows(path, runner.TIMING_FIELDS, values)
        self.reseal_active()
        self.rejected("Worker stdout/raw/request mismatch")

    def test_timeout_partial_stdout_is_never_admitted_as_a_peak(self):
        root = self.session / "original_snapshot"
        path = root / "run_02/memory_repeats.csv"
        values = rows(path)
        row = next(v for v in values if v["status"] == "timeout" and v["stdout"])
        row["peak_process_working_set_bytes"] = str(json.loads(row["stdout"])["peak_process_working_set_bytes"])
        write_rows(path, runner.MEMORY_FIELDS, values)
        self.reseal_archive()
        self.rejected("Timeout was altered/admitted as normal")

    def test_archived_failed_pair_must_remain_blank(self):
        root = self.session / "original_snapshot"
        path = root / "run_02/measurements.csv"
        values = rows(path)
        next(v for v in values if v["verified"] == "False")["compression_ratio"] = "0.5"
        write_rows(path, runner.MEASUREMENT_FIELDS, values)
        self.reseal_archive()
        self.rejected("Failed pair metrics must be blank")

    def test_other_run_and_staging_cannot_change(self):
        for relative in ("original_snapshot/run_03/references.csv", "new_run_02/metadata.json"):
            path = self.session / relative
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            self.rejected()
            path.write_bytes(original)

    def test_manifest_traversal_and_missing_archive_are_rejected(self):
        path = self.session / "original_manifest.json"
        value = load(path)
        value["../outside"] = "a"*64
        save(path, value)
        self.rejected()

    def test_original_status_and_physical_order_cannot_be_rewritten(self):
        path = self.directory / "metadata.json"
        original = load(path)
        for change in (dict(recording_checks_passed=True), dict(original_collection_status="completed"),
                       dict(active_execution_order=[1,2,3,4,5,6])):
            save(path, {**original, **change})
            self.reseal_active()
            self.rejected()
        save(path, original)

    def test_claim_extra_run_and_duplicate_json_are_rejected(self):
        claim = self.directory / ".active_run.json"
        claim.write_text("{}")
        self.rejected()
        claim.unlink()
        extra = self.directory / "run_07"
        extra.mkdir()
        self.rejected()
        extra.rmdir()
        (self.session / "replacement.json").write_text('{"status":"installed","status":"installed"}')
        self.rejected()

    def test_mutation_during_audit_is_rejected(self):
        original = audit.generated_samples
        def mutate(*args):
            value = original(*args)
            path = self.directory / "samples.csv"
            path.write_bytes(path.read_bytes() + b"\n")
            return value
        with patch.object(audit, "generated_samples", side_effect=mutate):
            self.rejected()

    def test_new_file_during_audit_is_rejected(self):
        def mutate(*args):
            (self.session / "late_file.json").write_text("{}")
            return self.canonical_samples
        with patch.object(audit, "generated_samples", side_effect=mutate):
            self.rejected()

    def test_cli_blocks_producer_imports_and_preserves_existing_output(self):
        guard = '''import importlib.abc,sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'src.memory_repeatability_validation','src.memory_stability_validation','src.memory_stability_timing_worker','src.memory_validation','src.memory_benchmark','src.compressors','src.scoring','research_log.replace_memory_repeatability_run02'}:
            raise RuntimeError('Prohibited import: '+fullname)
sys.meta_path.insert(0,Guard())
from research_log.verify_memory_repeatability_validation import main
raise SystemExit(main(sys.argv[1:]))
'''
        output = self.case / "audit.json"
        command = [sys.executable, "-B", "-c", guard, "--experiment-dir", str(self.directory),
                   "--replacement-dir", str(self.session), "--output", str(output)]
        result = subprocess.run(command, cwd=audit.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(load(output)["audit_passed"])
        before = output.read_bytes()
        result = subprocess.run(command, cwd=audit.ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(output.read_bytes(), before)

    def test_cli_rejects_bad_evidence_under_optimization_and_output_in_inputs(self):
        path = self.session / "original_manifest.json"
        value = load(path)
        value["samples.csv"] = "0"*64
        save(path, value)
        for flag in (None, "-O", "-OO"):
            output = self.case / f"invalid_{flag}.json"
            command = [sys.executable, "-B", *([flag] if flag else []), "-m", "research_log.verify_memory_repeatability_validation",
                       "--experiment-dir", str(self.directory), "--replacement-dir", str(self.session), "--output", str(output)]
            result = subprocess.run(command, cwd=audit.ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertFalse(output.exists())
        with self.assertRaises(SystemExit):
            audit.main(["--experiment-dir",str(self.directory),"--replacement-dir",str(self.session),
                        "--output",str(self.directory / "new_report.json")])
        self.assertFalse((self.directory / "new_report.json").exists())


if __name__ == "__main__":
    unittest.main()
