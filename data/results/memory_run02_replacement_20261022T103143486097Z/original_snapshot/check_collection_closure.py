"""Limited collection closure checks; NOT the pending independent protocol audit.
Reads saved evidence only; no worker, codec, score, label or model execution.
Run after Run 6 exits and before changing the frozen measurement HEAD.
"""
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

STUDY = Path(__file__).resolve().parent
PROJECT = STUDY.parents[2]
issues = []
checks = Counter()

def require(condition, name):
    checks[name] += 1
    if not condition:
        issues.append(name)

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))

plan = load(STUDY / "plan.json")
coordinator = load(STUDY / "metadata.json")
require(not (STUDY / ".active_run.json").exists(), "claim_released")
require(not (STUDY / "run_07").exists(), "no_unplanned_run")
require(len(coordinator["runs"]) == 6 and plan["run_ids"] == list(range(1, 7)), "six_planned_runs")
require(plan["measurement_status"] == "validation_only" and plan["score_inclusion"] is False,
        "validation_only")
require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT).decode().strip()
        == plan["implementation_commit"], "measurement_head_at_closure")
for name, expected in plan["source_sha256"].items():
    require(digest(PROJECT / name) == expected, "source_hash")
require(digest(STUDY / "samples.csv") == plan["samples_sha256"], "samples_hash")
samples = rows(STUDY / "samples.csv")
require(len(samples) == len(plan["samples"]) == 84 and all(row["status"] == "ok" for row in samples),
        "sample_matrix")
expected_reference = rows(STUDY / "run_01/references.csv")
require(len(expected_reference) == 336, "reference_count")
require(coordinator["finalization_status"] == "completed" and not coordinator["finalization_errors"]
        and coordinator["provenance_unchanged"] is True, "coordinator_finalization")
for name, expected in coordinator["artifact_sha256"].items():
    require(digest(STUDY / name) == expected, "coordinator_artifact_hash")

runs = []
totals = Counter()
previous_end = None
failures_preserved = []
historical_checkpoint_checks = []
flag_fields = ("verified", "reference_roundtrip_verified", "input_verified_before", "input_verified_after")
for run_id in range(1, 7):
    directory = STUDY / f"run_{run_id:02d}"
    metadata = load(directory / "metadata.json")
    report = load(STUDY / f"limited_record_check_run_{run_id:02d}.json")
    require(report.get("record_integrity_checks_passed", report.get("limited_checks_passed")) is True,
            f"run_{run_id}_saved_limited_check")
    require(metadata["finalization_status"] == "completed" and not metadata["finalization_errors"]
            and metadata["provenance_unchanged"] is True and not metadata["validity_issues"],
            f"run_{run_id}_finalization")
    require(metadata["source_sha256"] == metadata["source_sha256_at_end"]
            == metadata["planned_source_sha256"] == plan["source_sha256"], f"run_{run_id}_source")
    for name, expected in metadata["artifact_sha256"].items():
        require(digest(directory / name) == expected, f"run_{run_id}_artifact_hash")
    require(rows(directory / "references.csv") == expected_reference, f"run_{run_id}_same_reference")
    # Old reports bind their own coordinator checkpoint, which the coordinator
    # intentionally updates later. All other bound files must remain unchanged.
    checked = 0
    for name, expected in report["artifact_sha256_at_check"].items():
        if name == "metadata.json" and run_id < 6:
            continue
        require(digest(STUDY / name) == expected, f"run_{run_id}_historical_evidence_hash")
        checked += 1
    historical_checkpoint_checks.append(dict(run_id=run_id, checked_files=checked,
        mutable_coordinator_checkpoint_excluded=run_id < 6))
    started = datetime.fromisoformat(metadata["started_at_utc"])
    ended = datetime.fromisoformat(metadata["finished_at_utc"])
    require(started.tzinfo is not None and ended >= started
            and (previous_end is None or started >= previous_end), f"run_{run_id}_chronology")
    gap = None if previous_end is None else (started-previous_end).total_seconds()
    previous_end = ended
    failed_rows = []
    kind_stats = {}
    for kind in ("memory", "timing"):
        records = rows(directory / f"{kind}_repeats.csv")
        keys = [(row["sample_id"], row["algorithm"], row["phase"], int(row["repeat_index"]))
                for row in records]
        expected_keys = {tuple(key) for key in plan["expected_keys"][kind]}
        require(len(records) == len(set(keys)) == len(expected_keys) == 3360
                and set(keys) == expected_keys, f"run_{run_id}_{kind}_complete_keys")
        bad = [row for row in records if row["status"] != "ok" or row["bundle_status"] != "ok"
               or any(row[field] != "True" for field in flag_fields)]
        failed_rows += [dict(kind=kind, **row) for row in bad]
        kind_stats[kind] = dict(rows=len(records),
            status_counts=dict(Counter(row["status"] for row in records)),
            verified_counts=dict(Counter(row["verified"] for row in records)))
        totals[kind + "_rows"] += len(records)
        require(metadata[kind + "_repeat_count"] == len(records), f"run_{run_id}_{kind}_counts")
    failed_pairs = rows(directory / "measurements.csv")
    require(len(failed_pairs) == 336, f"run_{run_id}_pair_count")
    normal_pairs = sum(row["verified"] == "True" for row in failed_pairs)
    for row in failed_pairs:
        if row["verified"] != "True":
            require(row["verified"] == "False" and int(row["failed_repeat_count"]) > 0
                    and all(row[field] == "" for field in (
                        "compression_ratio", "compression_time_ms", "decompression_time_ms",
                        "compression_peak_memory_bytes", "decompression_peak_memory_bytes",
                        "peak_memory_bytes")), f"run_{run_id}_failed_pair_null")
    require(metadata["failed_repeat_count"] == len(failed_rows), f"run_{run_id}_failure_count")
    expected_status = "completed_with_failures" if failed_rows else "completed"
    require(metadata["run_status"] == expected_status
            and metadata["recording_checks_passed"] is (not failed_rows), f"run_{run_id}_status")
    require(metadata["job_count"] == len(plan["schedules"][str(run_id)]) == 3696
            and metadata["repeat_count"] == 6720, f"run_{run_id}_jobs")
    require((STUDY / f"run_{run_id:02d}_stderr.txt").read_bytes() == b"", f"run_{run_id}_stderr_empty")
    totals["jobs"] += metadata["job_count"]
    totals["raw_rows"] += metadata["repeat_count"]
    totals["failed_repeats"] += len(failed_rows)
    totals["pairs"] += len(failed_pairs)
    totals["normal_pairs"] += normal_pairs
    totals["failed_pairs"] += len(failed_pairs)-normal_pairs
    failures_preserved += [dict(run_id=run_id, **row) for row in failed_rows]
    runs.append(dict(run_id=run_id, run_status=metadata["run_status"],
        job_count=metadata["job_count"], raw=kind_stats, pair_count=len(failed_pairs),
        normal_pair_count=normal_pairs, failed_pair_count=len(failed_pairs)-normal_pairs,
        failed_repeat_count=len(failed_rows), started_at_utc=metadata["started_at_utc"],
        finished_at_utc=metadata["finished_at_utc"], duration_seconds=(ended-started).total_seconds(),
        gap_since_previous_seconds=gap, metadata_save_retry_event_count=len(
            metadata.get("metadata_save_retry_events", []))))
require(coordinator["failed_repeat_count"] == totals["failed_repeats"]
        and coordinator["job_count"] == totals["jobs"] and coordinator["repeat_count"] == totals["raw_rows"]
        and coordinator["memory_repeat_count"] == totals["memory_rows"]
        and coordinator["timing_repeat_count"] == totals["timing_rows"], "coordinator_total_counts")
expected_status = "completed_with_failures" if totals["failed_repeats"] else "completed"
require(coordinator["run_status"] == expected_status
        and coordinator["recording_checks_passed"] is (totals["failed_repeats"] == 0), "terminal_status")
summary = dict(schema_version=1, report_type="limited_saved_collection_closure_not_protocol_audit",
    generated_at_utc=datetime.now(timezone.utc).isoformat(), study_dir=str(STUDY),
    measurement_commit=plan["implementation_commit"], run_count=len(runs), input_sample_count=len(samples),
    collection_execution_finished=True, limited_record_integrity_checks_passed=not issues,
    all_repeats_successful=totals["failed_repeats"] == 0, collector_final_status=coordinator["run_status"],
    counts=dict(totals), runs=runs, preserved_failed_records=failures_preserved,
    historical_report_hash_checks=historical_checkpoint_checks, checks=dict(checks), issues=issues,
    validation_only=True, score_inclusion=False, independent_protocol_audit_performed=False,
    candidate_score_analysis_performed=False, memory_formally_adopted=False,
    limits=["A finished collection with failures is not a complete successful matrix.",
            "Previous coordinator checkpoints in historical reports are intentionally mutable.",
            "Per-run saved-record checks are not the pending independent protocol audit.",
            "No failed repeat was retried, substituted or admitted as a normal result."])
with (STUDY / "collection_summary.json").open("x", encoding="utf-8", newline="\n") as stream:
    stream.write(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
print(json.dumps({name:summary[name] for name in (
    "limited_record_integrity_checks_passed", "issues", "collector_final_status",
    "all_repeats_successful", "run_count", "input_sample_count", "counts", "measurement_commit")},
    ensure_ascii=False))
raise SystemExit(0 if not issues else 1)

