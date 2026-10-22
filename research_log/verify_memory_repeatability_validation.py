"""Read-only audit of repeatability evidence and an authorized full Run 2 replacement.

The original three-day auditor remains unchanged. Its pure JSON, input-generation,
and schema utilities are shared; neither its audit nor any producer is called.
No runner, replacement adapter, worker, codec, scoring, or measurement imports.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import statistics
import sys

from research_log import verify_memory_stability_validation as base

ROOT = base.ROOT
DESIGN = "memory_repeatability_v1"
WORKER_DESIGN = "memory_stability_v1"
DESIGN_PATH = "research_log/memory_repeatability_validation_design.md"
AMENDMENT = "memory_repeatability_run02_replacement_v1"
AMENDMENT_PATH = "research_log/memory_run02_replacement_amendment.md"
ADAPTER_PATH = "research_log/replace_memory_repeatability_run02.py"
SOURCES = ("src/memory_repeatability_validation.py", *base.SOURCES[1:-1], DESIGN_PATH)
ALGORITHMS, PHASES, RUNS = base.ALGORITHMS, base.PHASES, base.RUNS
IMMUTABLE, ARTIFACTS = base.IMMUTABLE, base.ARTIFACTS
SAMPLE_FIELDS, REFERENCE_FIELDS = base.SAMPLE_FIELDS, base.REFERENCE_FIELDS
MEMORY_FIELDS, TIMING_FIELDS, MEASUREMENT_FIELDS = base.MEMORY_FIELDS, base.TIMING_FIELDS, base.MEASUREMENT_FIELDS
OPTIONS, TIMER, METHOD = base.OPTIONS, base.TIMER, base.METHOD
AuditError, require = base.AuditError, base.require
digest, parse_json, timestamp, positive_int, sha = base.digest, base.parse_json, base.timestamp, base.positive_int, base.sha
generated_samples = base.generated_samples
IO_POLICY = dict(max_save_attempts=5, retry_winerrors=[5, 32, 33], backoff_seconds=[.05, .10, .15, .20],
                 windows_read_share=["read", "write", "delete"], measurement_job_retry=False)
PUBLICATION = ("collection_completion.md", "collection_summary.json", "evidence_manifest.json",
               "limited_record_check_run_02.json", "metadata.json", "operator_context_run_02.json",
               "operator_events_run_02.json", "run_02", "run_02_completion.md", "run_02_replacement.json",
               "run_02_stderr.txt", "run_02_stdout.txt", "windows_power_events_run_02.json")


def same(actual, expected, message):
    if isinstance(actual, bytes) or isinstance(expected, bytes):
        require(type(actual) is type(expected) is bytes and actual == expected, message)
    else:
        base.same(actual, expected, message)


def fixed_plan(attempt_id, reason):
    plan = base.fixed_plan(attempt_id, reason)
    criteria = {k: v for k, v in plan["criteria"].items()
                if k not in ("day_offsets_hours", "first_run_tolerance_minutes", "second_run_gap_minutes")}
    criteria.update(execution_policy="ordered_nonoverlapping_runs_without_clock_day_or_gap_limits",
                    interpretation_scope="observed_repeated_runs_in_recorded_environment_not_cross_day_validation")
    return {**plan, "design_id": DESIGN, "timing_worker_design_id": WORKER_DESIGN,
            "collector_revision": 2, "metadata_io_policy": IO_POLICY, "criteria": criteria}


def relative_name(name):
    require(isinstance(name, str) and name and "\\" not in name, "Unsafe manifest path")
    path = PurePosixPath(name)
    require(not path.is_absolute() and all(p not in (".", "..") for p in path.parts)
            and path.as_posix() == name and not PureWindowsPath(name).drive, "Unsafe manifest path")
    return name


class Evidence:
    """Snapshot every input byte; detect edits, new files, symlinks, and claims."""
    def __init__(self, *roots):
        self.roots = [Path(p).resolve() for p in roots]
        require(len(set(self.roots)) == len(self.roots)
                and not any(a != b and a.is_relative_to(b) for a in self.roots for b in self.roots),
                "Evidence roots overlap")
        self.snapshots = {}
        self.inventories = {root: self.inventory(root) for root in self.roots}
        self.directory_inventories = {root: self.directories(root) for root in self.roots}
        for root, names in self.inventories.items():
            for name in names:
                self.read(root / name)

    @staticmethod
    def inventory(root):
        require(root.is_dir(), "Evidence directory missing")
        paths = list(root.rglob("*"))
        require(not any(p.is_symlink() or p.is_junction() for p in paths), "Linked evidence is not supported")
        require(not any(p.name == ".active_run.json" for p in paths), "Active or stale run claim")
        return {p.relative_to(root).as_posix() for p in paths if p.is_file()}

    @staticmethod
    def directories(root):
        return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()}

    def read(self, path):
        path = Path(path).resolve()
        if path not in self.snapshots:
            self.snapshots[path] = path.read_bytes()
        return self.snapshots[path]

    def load(self, path):
        value = parse_json(self.read(path))
        require(isinstance(value, dict), f"Expected JSON object: {path}")
        return value

    def table(self, path, fields):
        reader = csv.DictReader(io.StringIO(self.read(path).decode("utf-8"), newline=""), strict=True)
        require(reader.fieldnames == list(fields), f"Wrong CSV header: {path}")
        rows = list(reader)
        require(all(set(row) == set(fields) and all(isinstance(v, str) for v in row.values()) for row in rows),
                f"Missing/surplus CSV fields: {path}")
        return rows

    def tree(self, root):
        root = Path(root).resolve()
        return {path.relative_to(root).as_posix(): digest(data) for path, data in self.snapshots.items()
                if path.is_relative_to(root)}

    def manifest(self, record, names, root, label):
        require(isinstance(record, dict) and set(record) == set(names), f"Incomplete {label} manifest")
        for name in names:
            relative_name(name)
            require(digest(self.read(root / name)) == sha(record[name], name), f"Hash mismatch: {label}/{name}")

    def unchanged(self):
        for root, names in self.inventories.items():
            require(self.inventory(root) == names, "Evidence inventory/claim changed during audit")
            require(self.directories(root) == self.directory_inventories[root], "Evidence directories changed during audit")
        for path, data in self.snapshots.items():
            require(path.read_bytes() == data, f"Evidence/source changed during audit: {path}")


def check_plan(e, directory):
    plan = e.load(directory / "plan.json")
    canonical = fixed_plan(plan["attempt_id"], plan["attempt_reason"])
    extras = ("config", "source_sha256", "design_sha256", "implementation_commit", "git", "created_at_utc",
              "environment", "samples_sha256")
    same({k: v for k, v in plan.items() if k not in extras}, canonical, "Fixed plan/schedule/key mismatch")
    require(set(plan) == set(canonical) | set(extras), "Incomplete plan provenance")
    e.manifest(plan["source_sha256"], SOURCES, ROOT, "measurement source")
    same(plan["design_sha256"], plan["source_sha256"][DESIGN_PATH], "Design hash mismatch")
    config = parse_json(e.read(ROOT / "config/experiment_config.json"))
    same(plan["config"], config, "Plan config mismatch")
    same(config["compression"], dict(gzip={"level": 9}, bz2={"level": 9}, lzma={"preset": 6}, zstd={"level": 3}), "Changed codecs")
    same(config["timing"], dict(repeats=5, timer=TIMER, aggregate="median"), "Changed timing")
    same(config["memory"], dict(status="validation_only", platform="win32", metric="peak_process_working_set_bytes",
         backend="GetProcessMemoryInfo.PeakWorkingSetSize", unit="bytes", isolation="fresh_subprocess_per_phase_repeat",
         repeats=5, aggregate="median", combined="max_of_phase_medians"), "Changed memory definition")
    same(config["sample_sizes"], [16384, 65536, 262144, 1048576], "Changed input sizes")
    same(config["selection_modes"], dict(archive=dict(compression_ratio=.70, compression_time=.15, decompression_time=.15),
         balanced=dict(compression_ratio=.50, compression_time=.25, decompression_time=.25),
         fast_access=dict(compression_ratio=.30, compression_time=.20, decompression_time=.50)), "Official weights changed")
    base.environment(plan["environment"])
    timestamp(plan["created_at_utc"])
    samples = e.table(directory / "samples.csv", SAMPLE_FIELDS)
    same(samples, generated_samples(canonical["samples"], config), "Regenerated sample/hash/parameters/duplicates mismatch")
    same(digest(e.read(directory / "samples.csv")), sha(plan["samples_sha256"], "samples"), "Samples hash mismatch")
    require(e.read(directory / ".gitattributes") == b"* -text\n", "Preservation attributes differ")
    return plan, samples


def check_metadata(e, meta, directory, plan, immutable, commit, *, factor=1, failed=0, replacement=False):
    count = len(plan["expected_keys"]["memory"])
    status = "completed_with_failures" if failed else "completed"
    identities = dict(schema_version=1, design_id=DESIGN, collector_revision=2, metadata_io_policy=IO_POLICY,
        attempt_id=plan["attempt_id"], measurement_status="validation_only", score_inclusion=False,
        run_status=status, run_status_before_finalization=status, finalization_status="completed", finalization_errors=[],
        provenance_unchanged=True, recording_checks_passed=failed == 0, validity_issues=[],
        analysis_status="pending_independent_audit_and_analysis", technical_validity_status="pending_independent_audit",
        repeat_count=2 * count * factor, failed_repeat_count=failed, memory_repeat_count=count * factor,
        timing_repeat_count=count * factor, job_count=len(plan["schedules"]["1"]) * factor,
        planned_memory_repeat_count=count * factor, planned_timing_repeat_count=count * factor,
        subprocess_options=OPTIONS, config=plan["config"], source_sha256=plan["source_sha256"],
        planned_source_sha256=plan["source_sha256"], source_sha256_at_end=plan["source_sha256"],
        immutable_sha256_at_end=immutable)
    for key, value in identities.items():
        same(meta[key], value, f"Metadata mismatch: {directory.name}/{key}")
    require(not meta.get("run_error"), "Recorded parent error")
    base.git_record(meta["git"], commit, meta.get("study_dir", ""), clean=replacement)
    same(base.environment(meta["environment"]), base.environment(plan["environment"]), "Environment differs from plan")
    same(base.environment(meta["environment_at_end"]), base.environment(plan["environment"]), "Environment changed at end")
    start, end = timestamp(meta["started_at_utc"]), timestamp(meta["finished_at_utc"])
    require(start <= end, "Reversed run timestamps")
    previous_retry = None
    for retry in meta.get("metadata_save_retry_events", []):
        require(set(retry) == {"occurred_at_utc", "target", "failed_attempt", "winerror", "error"}
                and retry["target"] == "metadata.json" and type(retry["failed_attempt"]) is int
                and 1 <= retry["failed_attempt"] < IO_POLICY["max_save_attempts"]
                and type(retry["winerror"]) is int and retry["winerror"] in IO_POLICY["retry_winerrors"]
                and isinstance(retry["error"], str) and retry["error"], "Invalid metadata-only retry evidence")
        require(start <= timestamp(retry["occurred_at_utc"]), "Metadata retry precedes operation")
        if previous_retry is not None:
            require(timestamp(previous_retry["occurred_at_utc"]) <= timestamp(retry["occurred_at_utc"]), "Metadata retries reorder")
        if retry["failed_attempt"] != 1:
            require(previous_retry is not None and retry["failed_attempt"] == previous_retry["failed_attempt"] + 1,
                    "Metadata retry chain is incomplete")
        previous_retry = retry
    return start, end


def check_run(e, root, run_id, plan, samples, *, failed_allowed=False, execution_commit=None):
    """Recompute bundle identities, raw verification, medians, and failed-pair nulls."""
    prefix = root / f"run_{run_id:02d}"
    meta = e.load(prefix / "metadata.json")
    immutable = {n: digest(e.read(root / n)) for n in IMMUTABLE}
    failed = meta["failed_repeat_count"]
    require(type(failed) is int and failed >= 0 and (failed_allowed or failed == 0), "Unexpected failed repeats")
    for key, value in dict(run_id=run_id).items():
        same(meta[key], value, "Wrong run ID")
    # Original Git status is scoped to the original recorded study path.
    recorded_study = e.load(root / "metadata.json")["study_dir"]
    check_meta = {**meta, "study_dir": recorded_study}
    start, end = check_metadata(e, check_meta, prefix, plan, immutable,
        execution_commit or plan["implementation_commit"], failed=failed, replacement=execution_commit is not None)
    if execution_commit is None:
        base.events(meta["operator_events"])
    else:
        same(meta["execution_amendment"], AMENDMENT, "Replacement amendment mismatch")
        same(meta["execution_role"], "replacement_of_logical_run_02_after_run_06", "Wrong replacement role")
        same(meta["measurement_code_commit"], plan["implementation_commit"], "Original code commit mismatch")
    e.manifest(meta["artifact_sha256"], ARTIFACTS, prefix, "run artifact")
    refs = e.table(prefix / "references.csv", REFERENCE_FIELDS)
    pairs = [(s["sample_id"], a) for s in samples for a in ALGORITHMS]
    same([(v["sample_id"], v["algorithm"]) for v in refs], pairs, "Reference pair order/matrix differs")
    by_sample = {v["sample_id"]: v for v in samples}
    for ref in refs:
        sample = by_sample[ref["sample_id"]]
        require(ref["status"] == "ok" and ref["error"] == "" and ref["reference_roundtrip_verified"] == "True", "Unverified reference")
        same(ref["original_size"], sample["size"], "Reference size mismatch")
        same(ref["original_sha256"], sample["input_sha256"], "Reference input hash mismatch")
        positive_int(ref["compressed_size"], "compressed size")
        sha(ref["compressed_sha256"], "reference")
    by_pair = {(v["sample_id"], v["algorithm"]): v for v in refs}
    raw = dict(memory=e.table(prefix / "memory_repeats.csv", MEMORY_FIELDS),
               timing=e.table(prefix / "timing_repeats.csv", TIMING_FIELDS))
    require(all(len(rows) == len(plan["expected_keys"][kind]) for kind, rows in raw.items()), "Incomplete repeat matrix")
    cursors = dict(memory=0, timing=0)
    grouped, bad_pairs, failures = defaultdict(list), Counter(), []
    temporary_parent, paths, previous_end = None, {}, start
    for job in plan["schedules"][str(run_id)]:
        kind = job["kind"]
        keys = [(job["phase"], job["repeat_index"])] if kind == "memory" else [(p, i) for p in PHASES for i in range(1, 6)]
        bundle = raw[kind][cursors[kind]:cursors[kind] + len(keys)]
        cursors[kind] += len(keys)
        first = bundle[0]
        ref = by_pair[job["sample_id"], job["algorithm"]]
        begin, finish = timestamp(first["started_at_utc"]), timestamp(first["finished_at_utc"])
        require(previous_end <= begin <= finish <= end, "Jobs overlap/reorder/outside parent")
        previous_end = finish
        command = parse_json(first["argv"])
        require(isinstance(command, list) and all(isinstance(v, str) for v in command), "Invalid worker argv")
        def phase_path(path, phase):
            nonlocal temporary_parent
            value = PureWindowsPath(path)
            require(value.is_absolute() and value.name == f"{job['sample_id']}_{job['algorithm']}_{phase}.bin", "Wrong phase path")
            if temporary_parent is None:
                temporary_parent = value.parent
            require(value.parent == temporary_parent, "Phase input directories differ")
            key = job["sample_id"], job["algorithm"], phase
            paths.setdefault(key, path)
            same(paths[key], path, "Phase input path changed")
            return path
        executable = plan["environment"]["python_executable"]
        if kind == "memory":
            require(len(command) == 13, "Wrong memory argv length")
            path = phase_path(command[10], job["phase"])
            expected_command = [executable, "-B", "-m", "src.memory_benchmark", "worker", "--operation", job["phase"],
                "--algorithm", job["algorithm"], "--input", path, "--expected-sha256",
                ref["compressed_sha256" if job["phase"] == "compress" else "original_sha256"]]
        else:
            require(len(command) == 16, "Wrong timing argv length")
            original, compressed = phase_path(command[9], "compress"), phase_path(command[11], "decompress")
            expected_command = [executable, "-B", "-m", "src.memory_stability_timing_worker", "--request-id", job["request_id"],
                "--algorithm", job["algorithm"], "--original", original, "--reference-compressed", compressed,
                "--original-sha256", ref["original_sha256"], "--compressed-sha256", ref["compressed_sha256"]]
        same(command, expected_command, "Worker argv/request mismatch")
        timed_out = first["status"] == "timeout"
        require(not timed_out or failed_allowed and kind == "memory", "Only archived memory timeouts may be retained")
        records = []
        for row, (phase, index) in zip(bundle, keys):
            identities = dict(attempt_id=plan["attempt_id"], run_id=run_id, sample_id=job["sample_id"], algorithm=job["algorithm"],
                phase=phase, repeat_index=index, schedule_index=job["schedule_index"], request_id=job["request_id"],
                input_size=ref["original_size" if phase == "compress" else "compressed_size"],
                input_sha256=ref["original_sha256" if phase == "compress" else "compressed_sha256"],
                expected_output_sha256=ref["compressed_sha256" if phase == "compress" else "original_sha256"],
                reference_roundtrip_verified=True, stderr="", input_verified_before=True, input_verified_after=True,
                python_executable=executable)
            same({k: row[k] for k in identities}, base.csv_strings(identities), "Raw identity/reference/input mismatch")
            for key in ("argv", "stdout", "subprocess_options", "started_at_utc", "finished_at_utc"):
                same(row[key], first[key], "Inconsistent bundle evidence")
            same(parse_json(row["subprocess_options"]), OPTIONS, "Wrong worker bytecode options")
            if kind == "memory":
                require(row["measurement_method"] == METHOD and row["actual_output_sha256"] == "", "Wrong memory method/digest contract")
            if timed_out:
                require(row["bundle_status"] == "timeout" and row["return_code"] == row["verified"] == row["peak_process_working_set_bytes"] == ""
                        and "timed out after 120 seconds" in row["error"], "Timeout was altered/admitted as normal")
                bad_pairs[job["sample_id"], job["algorithm"]] += 1
                failures.append(dict(kind=kind, **row))
                # Partial stdout is diagnostic evidence, never an accepted peak.
                if row["stdout"]:
                    payload = parse_json(row["stdout"])
                    require(set(payload) == {"operation", "algorithm", "peak_process_working_set_bytes", "verified"}
                            and payload["operation"] == phase and payload["algorithm"] == job["algorithm"]
                            and type(payload["verified"]) is bool and type(payload["peak_process_working_set_bytes"]) is int
                            and payload["peak_process_working_set_bytes"] > 0, "Invalid partial timeout stdout")
                continue
            same({k: row[k] for k in ("status", "bundle_status", "verified", "error", "return_code")},
                 dict(status="ok", bundle_status="ok", verified="True", error="", return_code="0"), "Failed/unverified raw repeat")
            value = positive_int(row["peak_process_working_set_bytes" if kind == "memory" else "elapsed_ns"], kind)
            if kind == "timing":
                require(row["timer"] == TIMER and row["actual_output_sha256"] == identities["expected_output_sha256"], "Wrong timing verification")
                records.append(dict(phase=phase, repeat_index=index, elapsed_ns=value,
                    actual_output_sha256=row["actual_output_sha256"], verified=True, status="ok", error=""))
            grouped[job["sample_id"], job["algorithm"], kind, phase].append(value)
        if timed_out:
            continue
        if kind == "memory":
            payload = dict(operation=job["phase"], algorithm=job["algorithm"], peak_process_working_set_bytes=value, verified=True)
        else:
            payload = dict(schema_version=1, design_id=WORKER_DESIGN, measurement_status="validation_only", score_inclusion=False,
                request_id=job["request_id"], algorithm=job["algorithm"], timer=TIMER, records=records, status="ok", error="",
                original_size=int(ref["original_size"]), compressed_size=int(ref["compressed_size"]),
                original_sha256=ref["original_sha256"], compressed_sha256=ref["compressed_sha256"])
        same(parse_json(first["stdout"]), payload, "Worker stdout/raw/request mismatch")
    same(meta["failed_repeat_count"], len(failures), "Failure count mismatch")
    same(meta["repeat_status_counts"], dict(Counter(v["status"] for rows in raw.values() for v in rows)), "Status count mismatch")
    summaries = e.table(prefix / "measurements.csv", MEASUREMENT_FIELDS)
    same([(v["sample_id"], v["algorithm"]) for v in summaries], pairs, "Measurement pair order/matrix differs")
    for row in summaries:
        sid, algorithm = row["sample_id"], row["algorithm"]
        bad = bad_pairs[sid, algorithm]
        require(row["verified"] == str(bad == 0) and row["failed_repeat_count"] == str(bad), "Pair verification mismatch")
        if bad:
            require(all(row[n] == "" for n in MEASUREMENT_FIELDS[4:]), "Failed pair metrics must be blank")
            continue
        values = {}
        for kind in raw:
            for phase in PHASES:
                vals = grouped[sid, algorithm, kind, phase]
                require(len(vals) == 5, "Incomplete phase repeats")
                values[kind, phase] = statistics.median(vals)
        ref = by_pair[sid, algorithm]
        expected = dict(compression_ratio=int(ref["compressed_size"]) / int(ref["original_size"]),
            compression_time_ms=values["timing", "compress"] / 1000000,
            decompression_time_ms=values["timing", "decompress"] / 1000000,
            compression_peak_memory_bytes=values["memory", "compress"],
            decompression_peak_memory_bytes=values["memory", "decompress"],
            peak_memory_bytes=max(values["memory", "compress"], values["memory", "decompress"]))
        for field, value in expected.items():
            actual = positive_int(row[field], field) if "memory" in field else float(row[field])
            require(math.isfinite(actual) and actual > 0 and actual == value, f"Incorrect ratio/median/max: {field}")
    return dict(run_id=run_id, start=meta["started_at_utc"], end=meta["finished_at_utc"],
        reference_count=len(refs), memory_repeat_count=len(raw["memory"]), timing_repeat_count=len(raw["timing"]),
        job_count=len(plan["schedules"][str(run_id)]), measurement_count=len(summaries),
        failed_repeat_count=len(failures), verified_pair_count=len(summaries) - len(bad_pairs),
        failed_pair_count=len(bad_pairs), metadata_save_retry_event_count=len(meta.get("metadata_save_retry_events", [])),
        preserved_failed_records=failures, raw={kind: dict(rows=len(rows),
            status_counts=dict(Counter(v["status"] for v in rows)),
            verified_counts=dict(Counter(v["verified"] for v in rows))) for kind, rows in raw.items()})


def run_summary(run):
    return dict(run_id=run["run_id"], run_status="completed_with_failures" if run["failed_repeat_count"] else "completed",
        job_count=run["job_count"], raw=run["raw"], pair_count=run["measurement_count"],
        normal_pair_count=run["verified_pair_count"], failed_pair_count=run["failed_pair_count"],
        failed_repeat_count=run["failed_repeat_count"], started_at_utc=run["start"], finished_at_utc=run["end"],
        duration_seconds=(timestamp(run["end"]) - timestamp(run["start"])).total_seconds(),
        preserved_failed_records=run["preserved_failed_records"], record_integrity_checks_passed=True)


def collection_counts(runs):
    return dict(memory_rows=sum(v["memory_repeat_count"] for v in runs),
        timing_rows=sum(v["timing_repeat_count"] for v in runs), jobs=sum(v["job_count"] for v in runs),
        raw_rows=sum(v["memory_repeat_count"] + v["timing_repeat_count"] for v in runs),
        failed_repeats=sum(v["failed_repeat_count"] for v in runs), pairs=sum(v["measurement_count"] for v in runs),
        normal_pairs=sum(v["verified_pair_count"] for v in runs), failed_pairs=sum(v["failed_pair_count"] for v in runs))


def check_summary(summary, runs):
    same(summary["counts"], collection_counts(runs), "Collection summary counts mismatch")
    same(summary["run_count"], len(RUNS), "Summary run count mismatch")
    same(summary["all_repeats_successful"], not any(v["failed_repeat_count"] for v in runs), "Summary success mismatch")
    require(len(summary["runs"]) == len(RUNS), "Summary run matrix incomplete")
    for run, record in zip(runs, summary["runs"]):
        expected = run_summary(run)
        for key in ("run_id", "run_status", "job_count", "raw", "pair_count", "normal_pair_count",
                    "failed_pair_count", "failed_repeat_count", "started_at_utc", "finished_at_utc", "duration_seconds"):
            same(record[key], expected[key], "Summary run value mismatch: " + key)


def check_observations(record, new_meta, preflight, original_end):
    before, after = record["observations"]["before"], record["observations"]["after"]
    start, end = timestamp(new_meta["started_at_utc"]), timestamp(new_meta["finished_at_utc"])
    require(original_end <= timestamp(before["observed_at_utc"]) <= start <= end <= timestamp(after["observed_at_utc"]),
            "Replacement observation/execution chronology mismatch")
    same(before["boot_at"], after["boot_at"], "Reboot during replacement")
    require(timestamp(before["boot_at"]) <= timestamp(before["observed_at_utc"]), "Boot timestamp is in the future")
    for observation in (before, after):
        require(type(observation["ac_line_status"]) is int and observation["ac_line_status"] in (0, 1, 255)
                and type(observation["battery_percent"]) is int
                and (0 <= observation["battery_percent"] <= 100 or observation["battery_percent"] == 255)
                and isinstance(observation["observation_scope"], str) and observation["observation_scope"], "Invalid power observation")
        require(isinstance(observation["python_processes"], list), "Missing process observation")
    pid = preflight["environment"]["pid"]
    own = [v for v in before["python_processes"] if v["ProcessId"] == pid]
    require(len(own) == 1, "Measurement parent absent from preflight")
    require(all(type(v["ProcessId"]) is int and type(v["ParentProcessId"]) is int and v["Name"] == "python.exe"
                and isinstance(v["CommandLine"], str) and ADAPTER_PATH in v["CommandLine"].replace("\\", "/")
                and v["ProcessId"] in (pid, own[0]["ParentProcessId"]) for v in before["python_processes"]),
            "Other Python work in preflight")
    sleep = record["idle_sleep_inhibition"]
    require(sleep["api"] == "SetThreadExecutionState" and type(sleep["requested_flags"]) is int
            and sleep["requested_flags"] == 0x80000001 and type(sleep["previous_flags"]) is int
            and sleep["previous_flags"] != 0 and sleep["restored"] is True
            and timestamp(before["observed_at_utc"]) <= timestamp(sleep["acquired_at_utc"]) <= start
            and end <= timestamp(sleep["released_at_utc"]) <= timestamp(after["observed_at_utc"]), "Sleep inhibition evidence mismatch")
    require(isinstance(record["power_events"], list), "Missing power event query result")
    for event in record["power_events"]:
        require(type(event["Id"]) is int and isinstance(event["Message"], str)
                and start <= timestamp(event["time_created_utc"]) <= end, "Invalid power event")
        require(not (event["ProviderName"] == "Microsoft-Windows-Kernel-Power" and event["Id"] in (42, 107, 506, 507)
                     or event["ProviderName"] == "Microsoft-Windows-Power-Troubleshooter" and event["Id"] == 1),
                "Sleep/resume during replacement")


def audit(directory: Path, replacement_directory: Path) -> dict:
    require(sys.dont_write_bytecode, "Run audit with python -B")
    directory, session = Path(directory).resolve(), Path(replacement_directory).resolve()
    e = Evidence(directory, session)
    for path in (Path(__file__), Path(base.__file__)):
        e.read(path)
    plan, samples = check_plan(e, directory)
    original = session / "original_snapshot"
    original_tree = e.tree(original)
    old_manifest = e.load(session / "original_manifest.json")
    e.manifest(old_manifest, original_tree, original, "original snapshot")
    for name in IMMUTABLE:
        same(e.read(directory / name), e.read(original / name), "Original plan/input changed during replacement")
    immutable = {n: digest(e.read(directory / n)) for n in IMMUTABLE}
    for root in (directory, original):
        require({p.name for p in root.iterdir() if p.is_dir() and p.name.startswith("run_")} ==
                {f"run_{i:02d}" for i in RUNS}, "Missing/extra run directories")
    top = e.load(directory / "metadata.json")
    old_top = e.load(original / "metadata.json")
    base.git_record(plan["git"], plan["implementation_commit"], old_top["study_dir"], clean=True)
    old_runs = [check_run(e, original, i, plan, samples, failed_allowed=i == 2) for i in RUNS]
    require(old_runs[1]["failed_repeat_count"] > 0, "Archived Run 2 failures are missing")
    total_failed = sum(v["failed_repeat_count"] for v in old_runs)
    top_start, top_end = check_metadata(e, old_top, original, plan, immutable, plan["implementation_commit"], factor=6, failed=total_failed)
    top_artifacts = [*IMMUTABLE, *(n for i in RUNS for n in
                     (f"run_{i:02d}_stdout.txt", f"run_{i:02d}_stderr.txt", f"run_{i:02d}/metadata.json"))]
    e.manifest(old_top["artifact_sha256"], top_artifacts, original, "original coordinator")
    for key, value in dict(planned_run_count=6, sample_count=len(samples), failed_sample_count=0, active_run_id=6,
                           immutable_sha256=immutable, environment_at_initialization=plan["environment"]).items():
        same(old_top[key], value, "Original coordinator mismatch: " + key)
    attempt_start = timestamp(old_top["attempt_started_at_utc"])
    require(timestamp(plan["created_at_utc"]) <= attempt_start <= top_start <= top_end, "Invalid original coordinator chronology")
    require(len(old_top["runs"]) == 6, "Original coordinator history incomplete")
    previous_end = attempt_start
    for run in old_runs:
        i = run["run_id"]
        meta = e.load(original / f"run_{i:02d}/metadata.json")
        require(previous_end <= timestamp(run["start"]) <= timestamp(run["end"]) <= top_end, "Original run order/overlap mismatch")
        previous_end = timestamp(run["end"])
        expected = dict(run_id=i, return_code=1 if run["failed_repeat_count"] else 0,
            run_status=meta["run_status"], operator_events=meta["operator_events"],
            started_at_utc=run["start"], finished_at_utc=run["end"])
        same(old_top["runs"][i - 1], expected, "Original coordinator run record mismatch")
        same(e.load(original / f"run_{i:02d}_stdout.txt"),
             {k: meta[k] for k in ("run_id", "run_status", "repeat_count", "failed_repeat_count")}, "Original parent stdout mismatch")
        require(e.read(original / f"run_{i:02d}_stderr.txt") == b"", "Original parent stderr present")
    require(top_start <= timestamp(old_runs[-1]["start"]), "Last original coordinator started after parent")
    original_summary = e.load(original / "collection_summary.json")
    check_summary(original_summary, old_runs)
    same(original_summary["collector_final_status"], "completed_with_failures", "Original failure status was changed")
    same(original_summary["preserved_failed_records"], old_runs[1]["preserved_failed_records"], "Original failure details changed")
    require(original / "evidence_manifest.json" in e.snapshots, "Original evidence manifest is missing")
    if original / "evidence_manifest.json" in e.snapshots:
        old_evidence = e.load(original / "evidence_manifest.json")
        require(old_evidence["manifest_self_excluded"] is True, "Invalid original manifest scope")
        expected_names = set(original_tree) - {"evidence_manifest.json"}
        require(set(old_evidence["files"]) == expected_names, "Incomplete original evidence manifest")
        for name, entry in old_evidence["files"].items():
            relative_name(name)
            data = e.read(original / name)
            same(entry, dict(bytes=len(data), sha256=digest(data)), "Original evidence size/hash differs")
        same(old_evidence["file_count"], len(expected_names), "Original file count differs")
        same(old_evidence["total_bytes"], sum(len(e.read(original / n)) for n in expected_names), "Original byte count differs")

    session_record = e.load(session / "replacement.json")
    active_record = e.load(directory / "run_02_replacement.json")
    require(set(active_record) == set(session_record) | {"record_scope", "transaction_status_file"}, "Incomplete active replacement record")
    same({k: active_record[k] for k in session_record}, session_record, "Active/session replacement records disagree")
    for key, value in dict(amendment_id=AMENDMENT, status="installed_and_verified", validation_only=True,
        score_inclusion=False, original_measurement_code_commit=plan["implementation_commit"], original_failed_repeats=total_failed,
        original_collection_status="completed_with_failures", independent_protocol_audit_performed=False,
        unchanged_other_run_files=True, original_snapshot_hashes_verified=True, actual_active_execution_order=[1, 3, 4, 5, 6, 2]).items():
        same(active_record[key], value, "Replacement record mismatch: " + key)
    recorded_session = PureWindowsPath(active_record["session_dir"])
    require(recorded_session.is_absolute() and PureWindowsPath(active_record["original_snapshot"]) == recorded_session / "original_snapshot"
            and PureWindowsPath(active_record["transaction_status_file"]) == recorded_session / "installation.json", "Recorded replacement paths disagree")
    e.manifest(active_record["adapter_sha256"], (ADAPTER_PATH, AMENDMENT_PATH), ROOT, "replacement source")
    commit = active_record["execution_git"]["commit_hash"]
    base.git_record(active_record["execution_git"], commit, old_top["study_dir"], clean=True)
    require(commit != plan["implementation_commit"], "Replacement and original execution commits were conflated")
    preflight = e.load(session / "preflight.json")
    for key in ("amendment_id", "session_dir", "original_snapshot", "execution_git", "adapter_sha256",
                "original_measurement_code_commit", "original_failed_repeats", "validation_only", "score_inclusion"):
        same(preflight[key], active_record[key], "Preflight/replacement mismatch: " + key)
    same(preflight["status"], "preparing", "Invalid preflight checkpoint")
    same(preflight["plan_sha256"], digest(e.read(directory / "plan.json")), "Preflight plan mismatch")
    same(preflight["actual_active_order_after_replacement"], [1, 3, 4, 5, 6, 2], "Preflight execution order differs")
    same(base.environment(preflight["environment"]), base.environment(plan["environment"]), "Preflight environment differs")
    same(preflight["observations"]["before"], active_record["observations"]["before"], "Preflight observations differ")
    same(preflight["original_runs"], [run_summary(run) for run in old_runs], "Preflight original history differs from archived raw values")
    require(isinstance(preflight["user_instruction"], str) and preflight["user_instruction"], "Missing user authorization record")
    for name in ARTIFACTS + ("metadata.json",):
        same(e.read(directory / "run_02" / name), e.read(session / "new_run_02" / name), "New staging/active Run 2 differ")
    new_run = check_run(e, directory, 2, plan, samples, execution_commit=commit)
    new_meta = e.load(directory / "run_02/metadata.json")
    same(active_record["new_run_summary"], run_summary(new_run), "Replacement summary differs from audited raw values")
    same(e.load(session / "new_run_saved_check.json"), run_summary(new_run), "Staging saved-check disagrees")
    same(new_meta["operator_observations"], preflight["observations"], "New parent observations differ")
    check_observations(active_record, new_meta, preflight, top_end)
    same(parse_json(e.read(session / "power_events.json")), active_record["power_events"], "Power query evidence differs")
    same(parse_json(e.read(directory / "windows_power_events_run_02.json")), active_record["power_events"], "Active power evidence differs")
    same(e.load(directory / "operator_context_run_02.json"), preflight, "Active preflight context differs")
    same(e.load(directory / "operator_events_run_02.json"), dict(execution_amendment=AMENDMENT,
         report_scope="Observed snapshots, no new user activity confirmation", observations=active_record["observations"]), "Active observation report differs")
    same(e.load(directory / "run_02_stdout.txt"), {k: new_meta[k] for k in ("run_id", "run_status", "repeat_count", "failed_repeat_count")},
         "Replacement generated summary disagrees")
    require(e.read(directory / "run_02_stderr.txt") == b"", "Replacement summary stderr is not empty")
    active_runs = [new_run if v["run_id"] == 2 else v for v in old_runs]
    for run in active_runs:
        root = directory / f"run_{run['run_id']:02d}"
        same(e.read(root / "references.csv"), e.read(original / "run_01/references.csv"), "Reference inputs differ across runs")
        if run["run_id"] != 2:
            for name in ARTIFACTS + ("metadata.json",):
                same(e.read(root / name), e.read(original / root.name / name), "An unrelated run was changed")
    order = sorted(active_runs, key=lambda v: timestamp(v["start"]))
    same([v["run_id"] for v in order], [1, 3, 4, 5, 6, 2], "Actual active execution order differs")
    require(all(timestamp(a["end"]) <= timestamp(b["start"]) for a, b in zip(order, order[1:])), "Active runs overlap")

    # Retain original coordinator history verbatim except explicitly derived publication fields.
    changed = {"run_status", "active_run_id", "failed_repeat_count", "replacement", "recording_checks_passed",
        "replacement_record_integrity_checks_passed", "technical_validity_status", "original_collection_status",
        "original_collection_failed_repeat_count", "active_execution_order", "original_schedule_order_preserved",
        "active_all_repeats_successful", "replacement_finalized_at_utc", "historical_metadata_scope", "runs",
        "artifact_sha256", "replacement_record_finalized_at_utc"}
    same({k: v for k, v in top.items() if k not in changed}, {k: v for k, v in old_top.items() if k not in changed},
         "Original coordinator history was rewritten")
    for key, value in dict(run_status="completed_after_run_replacement", active_run_id=2, failed_repeat_count=0,
        recording_checks_passed=False, replacement_record_integrity_checks_passed=True,
        technical_validity_status="pending_amendment_specific_independent_audit", original_collection_status="completed_with_failures",
        original_collection_failed_repeat_count=total_failed, active_execution_order=[1, 3, 4, 5, 6, 2],
        original_schedule_order_preserved=False, active_all_repeats_successful=True, replacement=active_record).items():
        same(top[key], value, "Active coordinator mismatch: " + key)
    e.manifest(top["artifact_sha256"], top_artifacts, directory, "active coordinator")
    require(len(top["runs"]) == 6, "Active coordinator run matrix incomplete")
    for i in RUNS:
        expected_record = (dict(run_id=2, return_code=0, run_status="completed", started_at_utc=new_run["start"],
            finished_at_utc=new_run["end"], execution_amendment=AMENDMENT, execution_commit=commit,
            parent_output_scope="Summary generated by replacement adapter; original stdout in snapshot")
            if i == 2 else old_top["runs"][i - 1])
        same(top["runs"][i - 1], expected_record, "Active coordinator run record mismatch")
    summary = e.load(directory / "collection_summary.json")
    check_summary(summary, active_runs)
    for key, value in dict(collector_final_status="completed_after_run_replacement", original_collection_all_repeats_successful=False,
        active_execution_order=[1, 3, 4, 5, 6, 2], original_schedule_order_preserved=False, validation_only=True,
        score_inclusion=False, independent_protocol_audit_performed=False, candidate_score_analysis_performed=False,
        memory_formally_adopted=False, measurement_code_commit=plan["implementation_commit"],
        replacement_execution_commit=commit, input_sample_count=len(samples), replacement=active_record).items():
        same(summary[key], value, "Active summary mismatch: " + key)
    saved_check = e.load(directory / "limited_record_check_run_02.json")
    for key, value in run_summary(new_run).items():
        same(saved_check[key], value, "Active limited check differs from audited raw")
    same(saved_check["replacement"], active_record, "Limited check replacement record differs")
    active_manifest = e.load(directory / "evidence_manifest.json")
    same(active_manifest["replacement"], active_record, "Manifest replacement record differs")
    e.manifest(active_manifest["sha256"], set(e.tree(directory)) - {"evidence_manifest.json"}, directory, "active evidence")

    installation = e.load(session / "installation.json")
    same(installation["status"], "installed", "Replacement installation is incomplete")
    changes = installation["changes"]
    same([v["name"] for v in changes], list(PUBLICATION), "Installation path list differs")
    require(timestamp(new_run["end"]) <= timestamp(installation["started_at_utc"])
            <= timestamp(installation["finished_at_utc"]) <= timestamp(active_record["finished_at_utc"]), "Installation chronology differs")
    displaced_names = set()
    for entry in changes:
        name = relative_name(entry["name"])
        require(entry["new_installed"] is True and entry["old_moved"] is (name != "run_02_replacement.json"), "Installation movement flags differ")
        if entry["old_moved"]:
            names = [n for n in original_tree if n == name or n.startswith(name + "/")]
            require(names, "Displaced original is missing")
            for n in names:
                same(e.read(original / n), e.read(session / "displaced_active_files" / n), "Displaced original differs from snapshot")
            displaced_names.update(names)
    require(set(e.tree(session / "displaced_active_files")) == displaced_names, "Incomplete displaced-file archive")
    checkpoint = session / "publication_preinstall_checkpoint"
    checkpoint_names = ("run_02_replacement.json", "metadata.json", "collection_summary.json", "limited_record_check_run_02.json", "evidence_manifest.json")
    require(set(e.tree(checkpoint)) == set(checkpoint_names), "Missing pre-install publication checkpoint")
    preinstall_record = e.load(checkpoint / "run_02_replacement.json")
    same(preinstall_record["status"], "validated_ready_to_install", "Invalid pre-install checkpoint state")
    for key, value in preinstall_record.items():
        if key != "status":
            same(active_record[key], value, "Pre-install/final replacement record mismatch")
    for name in checkpoint_names[1:]:
        same(e.load(checkpoint / name)["replacement"], preinstall_record, "Nested pre-install record differs")
    closure = e.load(session / "post_replacement_verification.json")
    for key, value in dict(saved_integrity_checks_passed=True, archive_file_count=len(original_tree), archive_hashes_match=True,
        unchanged_other_run_file_count=5 * len(ARTIFACTS + ("metadata.json",)), unchanged_other_run_hashes_match=True,
        active_manifest_file_count=len(e.tree(directory)) - 1, active_manifest_complete=True,
        original_run_02_failed_repeats=total_failed, new_run_02=run_summary(new_run), active_execution_order=[1, 3, 4, 5, 6, 2],
        execution_commit=commit, measurement_code_commit=plan["implementation_commit"], idle_sleep_inhibition_restored=True,
        power_event_query_result=active_record["power_events"], original_collection_success_claimed=False,
        independent_protocol_audit_performed=False, candidate_score_analysis_performed=False,
        memory_formally_adopted=False, score_inclusion=False).items():
        same(closure[key], value, "Closure report differs from audited evidence: " + key)
    totals = collection_counts(active_runs)
    same(closure["active_totals"], dict(jobs=totals["jobs"], memory_rows=totals["memory_rows"], timing_rows=totals["timing_rows"],
         failed_repeats=0, pairs=totals["pairs"], verified_pairs=totals["normal_pairs"]), "Closure totals differ")
    e.unchanged()
    return dict(audit_passed=True, audited_at_utc=datetime.now(timezone.utc).isoformat(),
        audit_scope="memory_repeatability_v1_with_authorized_full_run_02_replacement_saved_evidence_consistency",
        design_id=DESIGN, amendment_id=AMENDMENT, attempt_id=plan["attempt_id"],
        measurement_status="validation_only", score_inclusion=False, original_measurement_commit=plan["implementation_commit"],
        replacement_execution_commit=commit, sample_count=len(samples), active_counts=totals, runs=active_runs,
        original_counts=collection_counts(old_runs), original_collection_successful=False,
        original_failed_records=old_runs[1]["preserved_failed_records"],
        active_execution_order=[1, 3, 4, 5, 6, 2], original_schedule_order_preserved=False,
        archived_file_count=len(original_tree), metadata_only_retry_events=new_run["metadata_save_retry_event_count"],
        evidence_directories=dict(active=str(directory), replacement=str(session)),
        input_sha256=dict(active=e.tree(directory), replacement=e.tree(session)),
        input_directory_names=dict(active=sorted(e.directory_inventories[directory]), replacement=sorted(e.directory_inventories[session])),
        audit_source_sha256={p.relative_to(ROOT).as_posix(): digest(data) for p, data in e.snapshots.items() if p.is_relative_to(ROOT)
                             and not any(p.is_relative_to(root) for root in (directory, session))},
        limitations=["Saved evidence consistency only; codecs, measurements, and restoration were not rerun.",
            "Original failures remain failures; replacement changes the physical run order and execution HEAD.",
            "Hashes and recorded Git/environment/event fields do not independently authenticate execution or continuous conditions.",
            "No cross-day stability proof, candidate score/regret analysis, memory adoption, or official four-metric activation."])


def recheck_report_inputs(report):
    for label, names in report["input_sha256"].items():
        root = Path(report["evidence_directories"][label])
        require(Evidence.inventory(root) == set(names), "Evidence inventory changed before report publication")
        require(Evidence.directories(root) == set(report["input_directory_names"][label]), "Evidence directories changed before report publication")
        for name, checksum in names.items():
            require(digest((root / relative_name(name)).read_bytes()) == checksum, "Evidence changed before report publication")
    for name, checksum in report["audit_source_sha256"].items():
        require(digest((ROOT / relative_name(name)).read_bytes()) == checksum, "Source changed before report publication")


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--replacement-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="New JSON report outside evidence roots; never overwrite")
    args = parser.parse_args(arguments)
    created = False
    try:
        if args.output:
            require(not any(args.output.resolve().is_relative_to(p.resolve()) for p in (args.experiment_dir, args.replacement_dir)),
                    "Report output must be outside input evidence")
            require(not args.output.exists(), "Report output already exists")
        report = audit(args.experiment_dir, args.replacement_dir)
        serialized = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        recheck_report_inputs(report)
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                created = True
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            recheck_report_inputs(report)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, csv.Error, IndexError) as exc:
        if created:
            args.output.unlink(missing_ok=True)
        parser.exit(1, f"Audit failed: {exc}\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
