"""Finalize derived publication records and verify stored bytes; no measurements.

The publication initially embeds the validated pre-install checkpoint. Replace
that checkpoint with the verified installation result, preserving both versions.
This does not edit any raw CSV, sample, plan, or per-run measurement metadata.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import shutil
import sys

SESSION = Path(__file__).resolve().parent
ROOT = SESSION.parents[2]
sys.path.insert(0, str(ROOT))
from research_log import replace_memory_repeatability_run02 as t

record = t.read(SESSION / "replacement.json")
t.require(record["status"] == "installed_and_verified", "Installation has not completed")
study = Path(record["original_snapshot"]).parent.parent / "memory_repeatability_v1_20261019T124938284221Z_attempt02"
study = t.within_results(study)
plan = t.r._load_plan(study)
baseline = t.read(SESSION / "original_manifest.json")
t.require(t.tree_hashes(SESSION / "original_snapshot") == baseline, "Original archive differs")
t.require(not (study / t.LOCK).exists(), "Measurement claim still active")
runs = [t.validate_saved(study / f"run_{i:02d}", plan, i) for i in t.r.RUN_IDS]
old_run_02 = t.validate_saved(SESSION / "original_snapshot/run_02", plan, 2)
t.require(old_run_02["failed_repeat_count"] == record["original_failed_repeats"], "Original failures changed")
t.require(all(v["failed_repeat_count"] == 0 for v in runs), "Active measurements contain failures")
unchanged = {name: expected for name, expected in baseline.items()
             if any(name.startswith(f"run_{i:02d}/") for i in (1, 3, 4, 5, 6))}
t.require(all(t.digest(study / n) == expected for n, expected in unchanged.items()), "Other run changed")
t.require(t.r._sources() == plan["source_sha256"], "Frozen sources changed")
t.require(all(t.digest(ROOT / n) == expected for n, expected in record["adapter_sha256"].items()), "Adapter/design changed")

derived = ("run_02_replacement.json", "metadata.json", "collection_summary.json",
           "limited_record_check_run_02.json", "evidence_manifest.json")
checkpoint = SESSION / "publication_preinstall_checkpoint"
checkpoint.mkdir(exist_ok=False)
for name in derived:
    shutil.copy2(study / name, checkpoint / name)
    t.require(t.digest(study / name) == t.digest(checkpoint / name), "Checkpoint copy mismatch")
record = {**record, "record_scope": "Verified completed installation; pre-install checkpoint retained in session",
          "transaction_status_file": str(SESSION / "installation.json")}
t.save(study / "run_02_replacement.json", record)
for name in ("metadata.json", "collection_summary.json", "limited_record_check_run_02.json"):
    value = t.read(study / name)
    value["replacement"] = record
    value["replacement_record_finalized_at_utc"] = t.r.common._now()
    t.save(study / name, value)
manifest = t.read(study / "evidence_manifest.json")
manifest.update(replacement=record, generated_at_utc=t.r.common._now())
manifest["sha256"] = {n: value for n, value in t.tree_hashes(study).items() if n != "evidence_manifest.json"}
t.save(study / "evidence_manifest.json", manifest)
actual = t.tree_hashes(study)
actual.pop("evidence_manifest.json")
t.require(actual == manifest["sha256"], "Active manifest is incomplete or wrong")
coordinator = t.read(study / "metadata.json")
t.require(all(t.digest(study / n) == expected for n, expected in coordinator["artifact_sha256"].items()),
          "Coordinator artifact mismatch")
t.require(t.tree_hashes(SESSION / "original_snapshot") == baseline, "Archive changed during finalization")
t.require(all(t.digest(study / n) == expected for n, expected in unchanged.items()), "Other run changed during finalization")

totals = Counter()
for run in runs:
    totals.update(jobs=run["job_count"], memory_rows=run["raw"]["memory"]["rows"],
                  timing_rows=run["raw"]["timing"]["rows"], failed_repeats=run["failed_repeat_count"],
                  pairs=run["pair_count"], verified_pairs=run["normal_pair_count"])
summary = t.read(study / "collection_summary.json")
for field in ("jobs", "memory_rows", "timing_rows", "failed_repeats", "pairs"):
    t.require(summary["counts"][field] == totals[field], "Active summary count differs: " + field)
new_meta = t.read(study / "run_02/metadata.json")
local = timezone(timedelta(hours=9))
report = dict(report_type="post_replacement_limited_saved_record_verification_not_independent_protocol_audit",
    generated_at_utc=t.r.common._now(), saved_integrity_checks_passed=True,
    archive_file_count=len(baseline), archive_hashes_match=True,
    unchanged_other_run_file_count=len(unchanged), unchanged_other_run_hashes_match=True,
    active_manifest_file_count=len(actual), active_manifest_complete=True,
    original_run_02_failed_repeats=old_run_02["failed_repeat_count"],
    new_run_02=runs[1], active_totals=dict(totals), active_execution_order=summary["active_execution_order"],
    new_run_02_started_at_kst=datetime.fromisoformat(new_meta["started_at_utc"]).astimezone(local).isoformat(),
    new_run_02_finished_at_kst=datetime.fromisoformat(new_meta["finished_at_utc"]).astimezone(local).isoformat(),
    execution_commit=record["execution_git"]["commit_hash"], measurement_code_commit=plan["implementation_commit"],
    idle_sleep_inhibition_restored=record["idle_sleep_inhibition"]["restored"],
    power_event_query_result=record["power_events"], original_collection_success_claimed=False,
    independent_protocol_audit_performed=False, candidate_score_analysis_performed=False,
    memory_formally_adopted=False, score_inclusion=False)
t.save(SESSION / "post_replacement_verification.json", report)
print(json.dumps(report, ensure_ascii=False, indent=2))
