"""Failure-aware limited saved-record checks for Run 2; not the pending protocol audit.
Uses saved files and independent median calculations, without codec calls.
Run only after collector exits; output is exclusive and never overwrites.
"""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

STUDY = Path(__file__).resolve().parent
PROJECT = STUDY.parents[2]
failures = []
checks = Counter()

def require(condition, name):
    checks[name] += 1
    if not condition:
        failures.append(name)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def rows(name):
    with (STUDY / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))

def close(left, right):
    return math.isfinite(left) and math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)

plan = read_json(STUDY / "plan.json")
coordinator = read_json(STUDY / "metadata.json")
parent = read_json(STUDY / "run_02/metadata.json")
require(coordinator["run_status"] == "awaiting_next_run", "coordinator_awaiting_next")
raw_failure_rows = []
for kind in ("memory", "timing"):
    for row in rows(f"run_02/{kind}_repeats.csv"):
        if row["status"] != "ok" or row["bundle_status"] != "ok" or row["verified"] != "True":
            raw_failure_rows.append({"kind": kind, **row})
run_successful = not raw_failure_rows
require(parent["run_status"] == ("completed" if run_successful else "completed_with_failures"),
        "parent_status_matches_raw_failures")
require(len(coordinator["runs"]) == 2, "exactly_two_runs")
require(not (STUDY / ".active_run.json").exists(), "claim_released")
require(not (STUDY / "run_03").exists(), "run_03_not_started")
require((STUDY / "run_02_stderr.txt").read_bytes() == b"", "parent_stderr_empty")
require(plan["collector_revision"] == parent["collector_revision"] == coordinator["collector_revision"] == 2,
        "collector_revision")
require(plan["design_id"] == parent["design_id"] == coordinator["design_id"] == "memory_repeatability_v1",
        "design_id")
require(plan["metadata_io_policy"]["measurement_job_retry"] is False, "no_job_retry")
require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT).decode().strip()
        == plan["implementation_commit"], "head_matches_plan")
for metadata, label in ((parent, "parent"), (coordinator, "coordinator")):
    require(metadata["measurement_status"] == "validation_only" and metadata["score_inclusion"] is False,
            label + "_validation_only")
    require(metadata["finalization_status"] == "completed" and not metadata["finalization_errors"],
            label + "_finalization")
    require(metadata["recording_checks_passed"] is run_successful and metadata["provenance_unchanged"] is True
            and not metadata["validity_issues"], label + "_recording_flags")
    multiplier = 1 if label == "parent" else 2
    require(metadata["failed_repeat_count"] == len(raw_failure_rows) and metadata["job_count"] == 3696 * multiplier
            and metadata["memory_repeat_count"] == metadata["timing_repeat_count"] == 3360 * multiplier
            and metadata["repeat_count"] == 6720 * multiplier, label + "_counts")
    for path, expected in metadata["source_sha256"].items():
        require(digest(PROJECT / path) == expected, label + "_source_hash")
    require(metadata["source_sha256"] == metadata["source_sha256_at_end"]
            == metadata["planned_source_sha256"] == plan["source_sha256"], label + "_source_invariance")
    base = STUDY / "run_02" if label == "parent" else STUDY
    for path, expected in metadata["artifact_sha256"].items():
        require(digest(base / path) == expected, label + "_artifact_hash")
    require(metadata["immutable_sha256_at_end"] == coordinator["immutable_sha256"], label + "_immutable_manifest")
    for path, expected in metadata["immutable_sha256_at_end"].items():
        # Both parent and coordinator bind plan/samples at the study root.
        require(digest(STUDY / path) == expected, label + "_immutable_hash")

samples = rows("samples.csv")
sample_map = {row["sample_id"]: row for row in samples}
require(len(samples) == len(sample_map) == 84 and all(row["status"] == "ok" for row in samples),
        "samples_complete")
references = rows("run_02/references.csv")
reference_map = {(row["sample_id"], row["algorithm"]): row for row in references}
require(len(references) == len(reference_map) == 336, "references_complete")
for row in references:
    sample = sample_map[row["sample_id"]]
    require(row["status"] == "ok" and row["reference_roundtrip_verified"] == "True" and not row["error"],
            "reference_verified")
    require(row["original_sha256"] == sample["input_sha256"]
            and int(row["original_size"]) == int(sample["size"]) and int(row["compressed_size"]) > 0,
            "reference_sample_identity")

raw = {}
groups = {}
raw_stats = {}
schedule = plan["schedules"]["2"]
require(len(schedule) == 3696, "schedule_size")
for kind, filename, metric in (
        ("memory", "run_02/memory_repeats.csv", "peak_process_working_set_bytes"),
        ("timing", "run_02/timing_repeats.csv", "elapsed_ns")):
    values = rows(filename)
    raw[kind] = values
    expected = {tuple(key) for key in plan["expected_keys"][kind]}
    keys = [(row["sample_id"], row["algorithm"], row["phase"], int(row["repeat_index"])) for row in values]
    require(len(values) == len(set(keys)) == 3360 and set(keys) == expected, kind + "_complete_unique_keys")
    grouped = defaultdict(list)
    for row in values:
        ref = reference_map[(row["sample_id"], row["algorithm"])]
        compress = row["phase"] == "compress"
        job = schedule[int(row["schedule_index"])]
        require(job["kind"] == kind and job["sample_id"] == row["sample_id"]
                and job["algorithm"] == row["algorithm"] and job["request_id"] == row["request_id"]
                and row["run_id"] == "2" and row["attempt_id"] == plan["attempt_id"], kind + "_job_identity")
        if kind == "memory":
            require(job["phase"] == row["phase"] and job["repeat_index"] == int(row["repeat_index"]),
                    "memory_phase_identity")
        valid = row["status"] == row["bundle_status"] == "ok" and row["verified"] == "True"
        require(row["reference_roundtrip_verified"] == row["input_verified_before"]
                == row["input_verified_after"] == "True", kind + "_reference_input_flags")
        if valid:
            require(not row["error"] and row["return_code"] == "0", kind + "_successful_status")
        else:
            require(row["status"] == row["bundle_status"] == "timeout" and row["error"]
                    and row["verified"] == "" and row["return_code"] == "" and row[metric] == "",
                    kind + "_timeout_preserved_not_normal_measurement")
        require(row["input_sha256"] == ref["original_sha256" if compress else "compressed_sha256"]
                and row["expected_output_sha256"] == ref["compressed_sha256" if compress else "original_sha256"]
                and row["input_size"] == ref["original_size" if compress else "compressed_size"],
                kind + "_input_identity")
        if valid:
            require(int(row[metric]) > 0, kind + "_positive_measurement")
        if kind == "timing" and valid:
            require(row["timer"] == "time.perf_counter_ns"
                    and row["actual_output_sha256"] == row["expected_output_sha256"], "timing_output_digest")
        grouped[(row["sample_id"], row["algorithm"], row["phase"])].append(int(row[metric]) if valid else None)
    require(len(grouped) == 672 and all(len(values) == 5 for values in grouped.values()), kind + "_phase_groups")
    groups[kind] = grouped
    raw_stats[kind] = dict(rows=len(values), status_counts=dict(Counter(row["status"] for row in values)),
                           verified_counts=dict(Counter(row["verified"] for row in values)))
observed_jobs = {int(row["schedule_index"]) for values in raw.values() for row in values}
require(observed_jobs == set(range(3696)), "all_scheduled_jobs_recorded")

measurements = rows("run_02/measurements.csv")
pairs = [(row["sample_id"], row["algorithm"]) for row in measurements]
require(len(measurements) == len(set(pairs)) == 336 and set(pairs) == set(reference_map), "all_pairs_complete")
failed_pair_count = 0
for row in measurements:
    key = (row["sample_id"], row["algorithm"])
    failed_count = sum(value is None for kind in ("memory", "timing")
                       for phase in ("compress", "decompress") for value in groups[kind][(*key, phase)])
    if failed_count:
        failed_pair_count += 1
        require(row["verified"] == "False" and int(row["failed_repeat_count"]) == failed_count,
                "failed_pair_flag_and_count")
        require(all(row[field] == "" for field in ("compression_ratio", "compression_time_ms",
                    "decompression_time_ms", "compression_peak_memory_bytes",
                    "decompression_peak_memory_bytes", "peak_memory_bytes")), "failed_pair_numeric_values_null")
        continue
    ref = reference_map[key]
    require(row["verified"] == "True" and row["failed_repeat_count"] == "0", "pair_verified")
    require(close(float(row["compression_ratio"]), int(ref["compressed_size"]) / int(ref["original_size"])),
            "pair_ratio")
    peaks = []
    for phase, prefix in (("compress", "compression"), ("decompress", "decompression")):
        peak = statistics.median(groups["memory"][(*key, phase)])
        elapsed_ms = statistics.median(groups["timing"][(*key, phase)]) / 1_000_000
        require(close(float(row[prefix + "_peak_memory_bytes"]), peak), "pair_memory_median")
        require(close(float(row[prefix + "_time_ms"]), elapsed_ms), "pair_timing_median_ns_to_ms")
        peaks.append(peak)
    require(close(float(row["peak_memory_bytes"]), max(peaks)), "pair_memory_phase_max")
started = datetime.fromisoformat(parent["started_at_utc"])
finished = datetime.fromisoformat(parent["finished_at_utc"])
require(started.tzinfo is not None and finished >= started, "parent_timestamps")

previous = read_json(STUDY / "run_01/metadata.json")
previous_finished = datetime.fromisoformat(previous["finished_at_utc"])
require(started >= previous_finished, "ordered_nonoverlapping_runs")
require(previous["run_status"] == "completed" and previous["source_sha256"] == parent["source_sha256"],
        "previous_run_source_consistency")
require(rows("run_01/references.csv") == references, "reference_outputs_identical_across_runs")
context = read_json(STUDY / "operator_context_run_02.json")
prior_preserved = {}
for name, expected in context["prior_evidence_sha256"].items():
    # The coordinator intentionally updates its live metadata on each run.
    if name == "metadata.json":
        continue
    prior_preserved[name] = digest(STUDY / name) == expected
    require(prior_preserved[name], "prior_run_evidence_unchanged")


power_events = read_json(STUDY / "windows_power_events_run_02.json")
power_observations = []
for failed in raw_failure_rows:
    begin = datetime.fromisoformat(failed["started_at_utc"])
    end = datetime.fromisoformat(failed["finished_at_utc"])
    nearby = [event for event in power_events if event["Id"] in (506,507)
              and begin.timestamp()-5 <= datetime.fromisoformat(event["time_created_utc"]).timestamp()
              <= end.timestamp()+5]
    power_observations.append(dict(schedule_index=int(failed["schedule_index"]),
        worker_wall_seconds=(end-begin).total_seconds(), nearby_modern_standby_events=nearby))

evidence_hashes = {path.relative_to(STUDY).as_posix(): digest(path)
                   for path in sorted(STUDY.rglob("*")) if path.is_file()}
report = dict(schema_version=1, report_type="limited_saved_record_check_not_independent_protocol_audit",
              generated_at_utc=datetime.now(timezone.utc).isoformat(), run_id=2,
              study_dir=str(STUDY), measurement_commit=plan["implementation_commit"],
              collector_revision=plan["collector_revision"], record_integrity_checks_passed=not failures, run_successful=run_successful,
              complete_successful_matrix=run_successful, candidate_admissible=False,
              failed_repeat_count=len(raw_failure_rows), failed_pair_count=failed_pair_count,
              failed_raw_records=raw_failure_rows,
              check_counts=dict(checks), failures=failures, raw=raw_stats,
              pair_count=len(measurements), job_count=parent["job_count"],
              started_at_utc=parent["started_at_utc"], finished_at_utc=parent["finished_at_utc"],
              duration_seconds=(finished-started).total_seconds(),
              gap_since_previous_seconds=(started-previous_finished).total_seconds(),
              prior_evidence_preserved=prior_preserved,
              power_observations=power_observations,
              diagnosis_scope="Windows logged Modern Standby entry/exit overlapping long timeout windows; this supports a standby contribution, not a measured codec decompression failure or a proven cause for every delay.",
              metadata_save_retry_events=parent.get("metadata_save_retry_events", []),
              coordinator_metadata_save_retry_events=coordinator.get("metadata_save_retry_events", []),
              artifact_sha256_at_check=evidence_hashes,
              independent_protocol_audit_performed=False, candidate_analysis_performed=False,
              formal_four_metric_transition=False, remaining_runs=[3,4,5,6],
              next_run_clock_window_required=False)
with (STUDY / "limited_record_check_run_02.json").open("x", encoding="utf-8", newline="\n") as stream:
    stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
print(json.dumps({key: report[key] for key in (
    "record_integrity_checks_passed", "run_successful", "failed_repeat_count", "failed_pair_count", "failures", "raw", "pair_count", "job_count", "duration_seconds",
    "metadata_save_retry_events", "measurement_commit")}, ensure_ascii=False))
raise SystemExit(0 if not failures else 1)
