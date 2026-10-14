"""Read-only, independent audit of completed memory_stability_v1 evidence.

No runner, worker, compressors or scoring imports. Only the source-checked pure
data generator is used, after provenance validation. No codecs or measurements
are executed. Success concerns stored consistency, not scientific adoption.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path, PureWindowsPath
import random
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
DESIGN = "memory_stability_v1"
DESIGN_PATH = "research_log/memory_stability_validation_design.md"
SOURCES = ("src/memory_stability_validation.py", "src/memory_stability_timing_worker.py",
           "src/memory_benchmark.py", "src/memory_validation.py", "src/compressors.py",
           "src/data_generator.py", "config/experiment_config.json", "requirements.txt", DESIGN_PATH)
ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
PHASES = ("compress", "decompress")
RUNS = (1, 2, 3, 4, 5, 6)
METHOD = "windows_get_process_memory_info_peak_working_set"
TIMER = "time.perf_counter_ns"
OPTIONS = ["-B", "PYTHONDONTWRITEBYTECODE=1"]
SEOUL = timezone(timedelta(hours=9))
WEIGHTS = {"archive": dict(size=.65, compress=.10, decompress=.10, memory=.15),
           "balanced": dict(size=.40, compress=.20, decompress=.20, memory=.20),
           "fast_access": dict(size=.20, compress=.20, decompress=.45, memory=.15)}
CRITERIA = dict(delta=.01, epsilon=.005, w_memory_max=.20,
                memory_span_limit_expression="epsilon / (2 * w_memory_max)",
                memory_span_limit=.005 / (2 * .20),
                memory_span_expression="ln(max_r M_ra / min_r M_ra)",
                transfer_regret_expression="S_q(t, A_q(r)) - min_a S_q(t,a)",
                timing_aggregate="median(elapsed_ns) / 1000000",
                memory_aggregate="max(median(compress), median(decompress))",
                tie_order=list(ALGORITHMS), score_epsilon=None,
                day_offsets_hours=[0, 24, 48], first_run_tolerance_minutes=60,
                second_run_gap_minutes=[30, 90], timezone="Asia/Seoul")
SAMPLE_FIELDS = ("sample_id", "stratum", "generator", "family", "replicate_index", "size", "seed",
                 "generation_parameters", "input_sha256", "duplicate_of", "status", "error")
REFERENCE_FIELDS = ("sample_id", "algorithm", "original_size", "compressed_size", "original_sha256",
                    "compressed_sha256", "reference_roundtrip_verified", "status", "error")
RAW_FIELDS = ("attempt_id", "run_id", "sample_id", "algorithm", "phase", "repeat_index",
              "schedule_index", "request_id", "started_at_utc", "finished_at_utc", "argv",
              "python_executable", "subprocess_options", "input_size", "input_sha256",
              "expected_output_sha256", "reference_roundtrip_verified", "bundle_status",
              "verified", "status", "error", "return_code", "stdout", "stderr",
              "input_verified_before", "input_verified_after", "actual_output_sha256")
MEMORY_FIELDS = (*RAW_FIELDS, "measurement_method", "peak_process_working_set_bytes")
TIMING_FIELDS = (*RAW_FIELDS, "timer", "elapsed_ns")
MEASUREMENT_FIELDS = ("sample_id", "algorithm", "verified", "failed_repeat_count", "compression_ratio",
                      "compression_time_ms", "decompression_time_ms", "compression_peak_memory_bytes",
                      "decompression_peak_memory_bytes", "peak_memory_bytes")
ENV_KEYS = ("python_version", "python_executable", "operating_system", "architecture", "python_pointer_bits",
            "processor", "logical_cpu_count", "total_physical_memory_bytes", "package_versions")
EVENT_KEYS = ("power_mode", "manual_reboot_since_previous_run", "concurrent_activity", "os_update_events",
              "other_events", "no_research_jobs_running")
IMMUTABLE = ("plan.json", "samples.csv", ".gitattributes")
ARTIFACTS = ("references.csv", "memory_repeats.csv", "timing_repeats.csv", "measurements.csv")


class AuditError(ValueError):
    """Stored evidence does not satisfy the complete successful contract."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def same(actual, expected, message):
    require(json.dumps(actual, sort_keys=True, allow_nan=False) ==
            json.dumps(expected, sort_keys=True, allow_nan=False), message)


def parse_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise AuditError(f"Nonfinite JSON value: {value}")
    def floating(value):
        result = float(value)
        require(math.isfinite(result), "Nonfinite JSON number")
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid, parse_float=floating)


def positive_int(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value), f"Invalid integer: {label}")
    return int(value)


def sha(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), f"Invalid hash: {label}")
    return value


def timestamp(value):
    require(isinstance(value, str), "Timestamp must be a string")
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None and result.utcoffset() == timedelta(0), "Timestamp must be UTC")
    return result


def csv_strings(record):
    return {key: "" if value is None else str(value) for key, value in record.items()}


def fixed_plan(attempt_id, reason):
    require(isinstance(attempt_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", attempt_id),
            "Invalid attempt ID")
    require(isinstance(reason, str), "Invalid reason")
    samples = []
    for size in (16384, 65536, 262144, 1048576):
        for generator in ("random", "small_alphabet", "repeated_pattern", "long_runs", "structured", "mixed"):
            for replicate in range(3):
                index = len(samples)
                samples.append(dict(sample_id=f"stability_{index:06d}", stratum="core", generator=generator,
                                    family=None, replicate_index=replicate, size=size, seed=20261007 + index))
    for size in (64, 256, 1024, 4096):
        for family in ("zero_bytes", "periodic_16", "uniform_random"):
            index = len(samples)
            samples.append(dict(sample_id=f"stability_{index:06d}", stratum="tiny", generator=None,
                                family=family, replicate_index=None, size=size,
                                seed=20261007 + index if family == "uniform_random" else None))
    keys = [[s["sample_id"], a, p, i] for s in samples for a in ALGORITHMS for p in PHASES for i in range(1, 6)]
    schedules = {}
    for run_id in RUNS:
        jobs = [dict(kind="memory", sample_id=s, algorithm=a, phase=p, repeat_index=i) for s, a, p, i in keys]
        jobs.extend(dict(kind="timing", sample_id=s["sample_id"], algorithm=a, phase=None, repeat_index=None)
                    for s in samples for a in ALGORITHMS)
        random.Random(20262007 + run_id).shuffle(jobs)
        schedules[str(run_id)] = [{**job, "run_id": run_id, "schedule_index": index,
                                  "request_id": f"{attempt_id}:{run_id}:{index}"} for index, job in enumerate(jobs)]
    return dict(schema_version=1, design_id=DESIGN, attempt_id=attempt_id, attempt_reason=reason,
                measurement_status="validation_only", score_inclusion=False, samples=samples,
                schedules=schedules, expected_keys=dict(memory=keys, timing=keys),
                base_seed=20261007, schedule_seed=20262007, repeats=5, timeout_seconds=120,
                run_ids=list(RUNS), candidate_weights=WEIGHTS, criteria=CRITERIA, subprocess_options=OPTIONS)


def generated_samples(specs, config):
    # Import only after the caller has checked the recorded source/config bytes.
    from src import data_generator
    require(Path(data_generator.__file__).resolve() == (ROOT / "src/data_generator.py").resolve(),
            "Generator loaded from a different checkout")
    same(data_generator._CONFIG, config, "Generator's loaded config differs from recorded config")
    rows, first = [], {}
    for spec in specs:
        if spec["stratum"] == "core":
            sample = data_generator.generate_sample(spec["generator"], spec["size"], spec["seed"])
            data, parameters = sample.data, sample.parameters
        else:
            size, family = spec["size"], spec["family"]
            data = (bytes(size) if family == "zero_bytes" else
                    (bytes(range(16)) * ((size + 15) // 16))[:size] if family == "periodic_16" else
                    random.Random(spec["seed"]).randbytes(size))
            parameters = dict(family=family, size=size)
        require(type(data) is bytes and len(data) == spec["size"], "Regenerated input type/size mismatch")
        checksum = digest(data)
        rows.append(csv_strings({**spec, "generation_parameters": json.dumps(parameters, sort_keys=True,
                                                                            ensure_ascii=False, allow_nan=False),
                                 "input_sha256": checksum, "duplicate_of": first.get(checksum), "status": "ok", "error": ""}))
        first.setdefault(checksum, spec["sample_id"])
    return rows


def environment(env):
    require(isinstance(env, dict) and env.get("bytecode_disabled") is True, "Missing bytecode environment option")
    for key in ("pid", "python_pointer_bits", "logical_cpu_count", "total_physical_memory_bytes", "available_physical_memory_bytes"):
        require(type(env.get(key)) is int and env[key] > 0, f"Invalid environment {key}")
    require(env["python_pointer_bits"] in (32, 64), "Invalid pointer width")
    require(env["available_physical_memory_bytes"] <= env["total_physical_memory_bytes"], "Invalid available memory")
    require(type(env.get("memory_load_percent")) is int and 0 <= env["memory_load_percent"] <= 100, "Invalid memory load")
    for key in ("python_version", "python_executable", "operating_system", "architecture"):
        require(isinstance(env.get(key), str) and env[key], f"Missing environment {key}")
    require("windows" in env["operating_system"].lower() and PureWindowsPath(env["python_executable"]).is_absolute(),
            "Expected recorded Windows environment")
    require(isinstance(env.get("processor"), str), "Invalid processor")
    packages = env.get("package_versions")
    require(isinstance(packages, dict) and packages and
            all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in packages.items()), "Invalid packages")
    return {key: env[key] for key in ENV_KEYS}


def events(record):
    require(isinstance(record, dict) and set(record) == set(EVENT_KEYS), "Invalid operator event fields")
    for key in EVENT_KEYS:
        if key in ("manual_reboot_since_previous_run", "no_research_jobs_running"):
            require(type(record[key]) is bool, f"Event {key} must be boolean")
        else:
            require(isinstance(record[key], str) and record[key].strip(), f"Empty event {key}")
    require(record["no_research_jobs_running"] is True, "Concurrent research jobs reported")


def git_record(record, commit, study_dir, clean=False):
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit), "Invalid implementation commit")
    require(isinstance(record, dict) and not record.get("error"), "Invalid Git provenance")
    same(record.get("commit_hash"), commit, "Git commit mismatch")
    require(type(record.get("worktree_dirty")) is bool and isinstance(record.get("status_porcelain"), str), "Invalid Git status")
    status = record["status_porcelain"]
    require(record["worktree_dirty"] == bool(status), "Git dirty flag/status mismatch")
    if clean or not status:
        require(not status, "Initialization requires clean Git state")
        return
    root = PureWindowsPath(str(ROOT))
    try:
        allowed = PureWindowsPath(study_dir).relative_to(root).as_posix() + "/"
    except ValueError as exc:
        raise AuditError("Git changes outside recorded attempt") from exc
    require(status.splitlines() == ["?? " + allowed], "Git changes outside recorded attempt")


def check_schedule(run_id, start, previous):
    if run_id in (3, 5):
        first = previous[0][0]
        require(abs((start - first - timedelta(days=run_id // 2)).total_seconds()) <= 3600,
                "First run outside daily window")
        require(start.astimezone(SEOUL).date() == first.astimezone(SEOUL).date() + timedelta(days=run_id // 2),
                "Nonconsecutive local date")
    elif run_id % 2 == 0:
        require(1800 <= (start - previous[-1][1]).total_seconds() <= 5400, "Second run outside gap window")
        require(start.astimezone(SEOUL).date() == previous[-1][0].astimezone(SEOUL).date(), "Second run on another local date")


def audit(directory: Path) -> dict:
    require(sys.dont_write_bytecode, "Run audit with python -B to preserve read-only inputs")
    directory = Path(directory).resolve()
    require(not (directory / ".active_run.json").exists(), "Active or stale run claim")
    snapshots = {}
    def read(path):
        path = Path(path).resolve()
        if path not in snapshots:
            snapshots[path] = path.read_bytes()
        return snapshots[path]
    def load(name):
        value = parse_json(read(directory / name))
        require(isinstance(value, dict), f"Expected object: {name}")
        return value
    def table(name, fields):
        reader = csv.DictReader(io.StringIO(read(directory / name).decode("utf-8"), newline=""), strict=True)
        require(reader.fieldnames == list(fields), f"Wrong CSV header: {name}")
        rows = list(reader)
        require(all(set(row) == set(fields) and all(isinstance(v, str) for v in row.values()) for row in rows),
                f"Missing/surplus CSV fields: {name}")
        return rows
    def manifest(record, names, base, label):
        require(isinstance(record, dict) and set(record) == set(names), f"Incomplete {label} manifest")
        for name in names:
            require(digest(read(base / name)) == sha(record[name], name), f"Hash mismatch: {label}/{name}")

    read(Path(__file__))
    plan = load("plan.json")
    expected = fixed_plan(plan["attempt_id"], plan["attempt_reason"])
    extras = ("config", "source_sha256", "design_sha256", "implementation_commit", "git", "created_at_utc",
              "environment", "samples_sha256")
    same({k: v for k, v in plan.items() if k not in extras}, expected, "Fixed plan/schedule/key mismatch")
    require(set(plan) == set(expected) | set(extras), "Incomplete plan provenance")
    manifest(plan["source_sha256"], SOURCES, ROOT, "source; use recorded checkout")
    require(plan["design_sha256"] == plan["source_sha256"][DESIGN_PATH], "Design hash mismatch")
    config = parse_json(read(ROOT / "config/experiment_config.json"))
    same(plan["config"], config, "Plan config mismatch")
    same(config["compression"], dict(gzip={"level": 9}, bz2={"level": 9}, lzma={"preset": 6}, zstd={"level": 3}), "Changed codecs")
    same(config["timing"], dict(repeats=5, timer=TIMER, aggregate="median"), "Changed timing")
    same(config["memory"], dict(status="validation_only", platform="win32", metric="peak_process_working_set_bytes",
                              backend="GetProcessMemoryInfo.PeakWorkingSetSize", unit="bytes",
                              isolation="fresh_subprocess_per_phase_repeat", repeats=5, aggregate="median",
                              combined="max_of_phase_medians"), "Changed memory")
    same(config["sample_sizes"], [16384, 65536, 262144, 1048576], "Changed sample sizes")
    same(config["selection_modes"], dict(archive=dict(compression_ratio=.70, compression_time=.15, decompression_time=.15),
                                       balanced=dict(compression_ratio=.50, compression_time=.25, decompression_time=.25),
                                       fast_access=dict(compression_ratio=.30, compression_time=.20, decompression_time=.50)),
         "Official three-metric weights changed")
    fixed_env = environment(plan["environment"])
    created = timestamp(plan["created_at_utc"])
    samples = table("samples.csv", SAMPLE_FIELDS)
    same(samples, generated_samples(expected["samples"], config), "Regenerated sample/hash/parameters/duplicates mismatch")
    require(digest(read(directory / "samples.csv")) == sha(plan["samples_sha256"], "samples"), "Samples hash mismatch")
    require(read(directory / ".gitattributes") == b"* -text\n", "Evidence preservation attributes mismatch")
    immutable = {n: digest(read(directory / n)) for n in IMMUTABLE}
    by_sample = {s["sample_id"]: s for s in samples}
    top = load("metadata.json")
    study_dir = top["study_dir"]
    require(isinstance(study_dir, str) and PureWindowsPath(study_dir).is_absolute(), "Invalid recorded study path")
    git_record(plan["git"], plan["implementation_commit"], study_dir, clean=True)
    total_each = len(expected["expected_keys"]["memory"])
    jobs_each = len(expected["schedules"]["1"])
    top_artifacts = [*IMMUTABLE, *(n for i in RUNS for n in
                     (f"run_{i:02d}_stdout.txt", f"run_{i:02d}_stderr.txt", f"run_{i:02d}/metadata.json"))]

    def metadata(meta, base, names, factor):
        identities = dict(schema_version=1, design_id=DESIGN, attempt_id=plan["attempt_id"],
                          measurement_status="validation_only", score_inclusion=False, run_status="completed",
                          run_status_before_finalization="completed", finalization_status="completed", finalization_errors=[],
                          provenance_unchanged=True, recording_checks_passed=True, validity_issues=[],
                          analysis_status="pending_independent_audit_and_analysis", technical_validity_status="pending_independent_audit",
                          repeat_count=2 * total_each * factor, failed_repeat_count=0,
                          memory_repeat_count=total_each * factor, timing_repeat_count=total_each * factor,
                          job_count=jobs_each * factor, planned_memory_repeat_count=total_each * factor,
                          planned_timing_repeat_count=total_each * factor, subprocess_options=OPTIONS,
                          config=config, source_sha256=plan["source_sha256"], planned_source_sha256=plan["source_sha256"],
                          source_sha256_at_end=plan["source_sha256"], immutable_sha256_at_end=immutable)
        for key, value in identities.items():
            same(meta[key], value, f"Metadata mismatch: {base.name}/{key}")
        require(not meta.get("run_error"), "Recorded run error")
        git_record(meta["git"], plan["implementation_commit"], study_dir)
        same(environment(meta["environment"]), fixed_env, "Environment differs from plan")
        same(environment(meta["environment_at_end"]), fixed_env, "Environment changed at end")
        manifest(meta["artifact_sha256"], names, base, "artifact")
        start, end = timestamp(meta["started_at_utc"]), timestamp(meta["finished_at_utc"])
        require(start <= end, "Reversed metadata timestamps")
        return start, end

    top_start, top_end = metadata(top, directory, top_artifacts, len(RUNS))
    for key, value in dict(planned_run_count=6, sample_count=len(samples), failed_sample_count=0,
                           active_run_id=6, immutable_sha256=immutable, environment_at_initialization=plan["environment"]).items():
        same(top[key], value, f"Study metadata mismatch: {key}")
    attempt_start = timestamp(top["attempt_started_at_utc"])
    require(created <= attempt_start <= top_start <= top_end, "Invalid attempt/coordinator timestamps")
    same(top["immutable_sha256"], immutable, "Immutable manifest mismatch")
    require(isinstance(top["runs"], list) and len(top["runs"]) == 6, "Incomplete run records")
    require({p.name for p in directory.iterdir() if p.is_dir() and p.name.startswith("run_")} ==
            {f"run_{i:02d}" for i in RUNS}, "Missing/extra run directories")
    reports, prior_times, first_refs = [], [], None
    for run_id in RUNS:
        prefix = f"run_{run_id:02d}"
        meta = load(f"{prefix}/metadata.json")
        start, end = metadata(meta, directory / prefix, ARTIFACTS, 1)
        same(meta["run_id"], run_id, "Wrong run ID")
        same(meta["repeat_status_counts"], {"ok": 2 * total_each}, "Wrong repeat status counts")
        events(meta["operator_events"])
        same(top["runs"][run_id - 1], dict(run_id=run_id, return_code=0, run_status="completed",
                                         operator_events=meta["operator_events"], started_at_utc=meta["started_at_utc"],
                                         finished_at_utc=meta["finished_at_utc"]), "Coordinator run record mismatch")
        same(load(f"{prefix}_stdout.txt"), dict(run_id=run_id, run_status="completed", repeat_count=2 * total_each,
                                             failed_repeat_count=0), "Parent stdout mismatch")
        require(read(directory / f"{prefix}_stderr.txt") == b"", "Parent stderr present")
        require(attempt_start <= start <= end <= top_end and (not prior_times or prior_times[-1][1] <= start),
                "Runs overlap/outside attempt")
        check_schedule(run_id, start, prior_times)
        if run_id == 6:
            require(top_start <= start, "Last coordinator starts after parent")
        prior_times.append((start, end))

        refs = table(f"{prefix}/references.csv", REFERENCE_FIELDS)
        pairs = [(s["sample_id"], a) for s in samples for a in ALGORITHMS]
        same([(r["sample_id"], r["algorithm"]) for r in refs], pairs, "Duplicate/missing/reordered references")
        for row in refs:
            sample = by_sample[row["sample_id"]]
            require(row["status"] == "ok" and row["error"] == "" and row["reference_roundtrip_verified"] == "True",
                    "Failed/unverified reference")
            require(row["original_size"] == sample["size"] and row["original_sha256"] == sample["input_sha256"], "Reference input mismatch")
            positive_int(row["compressed_size"], "compressed size")
            sha(row["compressed_sha256"], "compressed reference")
        if first_refs is None:
            first_refs = refs
        same(refs, first_refs, "Reference differs across runs")
        by_pair = {(r["sample_id"], r["algorithm"]): r for r in refs}
        raw = {"memory": table(f"{prefix}/memory_repeats.csv", MEMORY_FIELDS),
               "timing": table(f"{prefix}/timing_repeats.csv", TIMING_FIELDS)}
        for kind in raw:
            require(len(raw[kind]) == total_each, f"Incomplete {kind} matrix")
        cursors = dict(memory=0, timing=0)
        grouped = defaultdict(list)
        input_paths = {}
        temporary_parent = None
        previous_end = start
        for job in expected["schedules"][str(run_id)]:
            kind = job["kind"]
            count = 1 if kind == "memory" else 10
            bundle = raw[kind][cursors[kind]:cursors[kind] + count]
            cursors[kind] += count
            first = bundle[0]
            ref = by_pair[(job["sample_id"], job["algorithm"])]
            keys = [(job["phase"], job["repeat_index"])] if kind == "memory" else [(p, i) for p in PHASES for i in range(1, 6)]
            begin, finish = timestamp(first["started_at_utc"]), timestamp(first["finished_at_utc"])
            require(previous_end <= begin <= finish <= end, "Jobs overlap/reorder/outside run")
            previous_end = finish
            command = parse_json(first["argv"])
            require(isinstance(command, list) and all(isinstance(a, str) for a in command), "Invalid argv")
            def phase_path(path, phase):
                nonlocal temporary_parent
                value = PureWindowsPath(path)
                require(value.is_absolute() and value.name == f"{job['sample_id']}_{job['algorithm']}_{phase}.bin", "Wrong phase path")
                if temporary_parent is None:
                    temporary_parent = value.parent
                require(value.parent == temporary_parent, "Phase directories differ within run")
                key = (job["sample_id"], job["algorithm"], phase)
                input_paths.setdefault(key, path)
                require(input_paths[key] == path, "Phase path changed within run")
                return path
            executable = fixed_env["python_executable"]
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
            records = []
            for row, (phase, index) in zip(bundle, keys):
                identities = dict(attempt_id=plan["attempt_id"], run_id=run_id, sample_id=job["sample_id"], algorithm=job["algorithm"],
                                  phase=phase, repeat_index=index, schedule_index=job["schedule_index"], request_id=job["request_id"],
                                  input_size=ref["original_size" if phase == "compress" else "compressed_size"],
                                  input_sha256=ref["original_sha256" if phase == "compress" else "compressed_sha256"],
                                  expected_output_sha256=ref["compressed_sha256" if phase == "compress" else "original_sha256"],
                                  reference_roundtrip_verified=True, bundle_status="ok", verified=True, status="ok", error="", return_code=0,
                                  stderr="", input_verified_before=True, input_verified_after=True, python_executable=executable)
                same({k: row[k] for k in identities}, csv_strings(identities), "Failed/unverified/mismatched raw repeat")
                for key in ("argv", "stdout", "subprocess_options", "started_at_utc", "finished_at_utc"):
                    require(row[key] == first[key], "Timing bundle evidence differs between rows")
                same(parse_json(row["subprocess_options"]), OPTIONS, "Missing subprocess bytecode options")
                value = positive_int(row["peak_process_working_set_bytes" if kind == "memory" else "elapsed_ns"], kind)
                if kind == "memory":
                    require(row["measurement_method"] == METHOD and row["actual_output_sha256"] == "", "Memory method/digest contract mismatch")
                else:
                    require(row["timer"] == TIMER and row["actual_output_sha256"] == identities["expected_output_sha256"], "Timing timer/output hash mismatch")
                    records.append(dict(phase=phase, repeat_index=index, elapsed_ns=value, actual_output_sha256=row["actual_output_sha256"],
                                        verified=True, status="ok", error=""))
                grouped[(job["sample_id"], job["algorithm"], kind, phase)].append(value)
            if kind == "memory":
                payload = dict(operation=job["phase"], algorithm=job["algorithm"], peak_process_working_set_bytes=value, verified=True)
            else:
                payload = dict(schema_version=1, design_id=DESIGN, measurement_status="validation_only", score_inclusion=False,
                               request_id=job["request_id"], algorithm=job["algorithm"], timer=TIMER, records=records, status="ok", error="",
                               original_size=int(ref["original_size"]), compressed_size=int(ref["compressed_size"]),
                               original_sha256=ref["original_sha256"], compressed_sha256=ref["compressed_sha256"])
            same(parse_json(first["stdout"]), payload, "Worker JSON differs from raw/request/reference")
        summaries = table(f"{prefix}/measurements.csv", MEASUREMENT_FIELDS)
        same([(r["sample_id"], r["algorithm"]) for r in summaries], pairs, "Duplicate/missing/reordered measurements")
        for row in summaries:
            sid, algorithm = row["sample_id"], row["algorithm"]
            ref = by_pair[(sid, algorithm)]
            require(row["verified"] == "True" and row["failed_repeat_count"] == "0", "Failed measurement pair")
            values = {}
            for kind in ("memory", "timing"):
                for phase in PHASES:
                    group = grouped[(sid, algorithm, kind, phase)]
                    require(len(group) == 5, "Incomplete phase group")
                    values[kind, phase] = statistics.median(group)
            calculated = dict(compression_ratio=int(ref["compressed_size"]) / int(ref["original_size"]),
                              compression_time_ms=values["timing", "compress"] / 1000000,
                              decompression_time_ms=values["timing", "decompress"] / 1000000,
                              compression_peak_memory_bytes=values["memory", "compress"],
                              decompression_peak_memory_bytes=values["memory", "decompress"],
                              peak_memory_bytes=max(values["memory", "compress"], values["memory", "decompress"]))
            for field, value in calculated.items():
                if "memory" in field:
                    require(positive_int(row[field], field) == value, f"Incorrect median/max: {field}")
                else:
                    actual = float(row[field])
                    require(math.isfinite(actual) and actual > 0 and actual == value, f"Incorrect ratio/time: {field}")
        reports.append(dict(run_id=run_id, reference_count=len(refs), memory_repeat_count=len(raw["memory"]),
                            timing_repeat_count=len(raw["timing"]), job_count=jobs_each, measurement_count=len(summaries)))
    for path, data in snapshots.items():
        require(path.read_bytes() == data, f"Evidence/source changed during audit: {path}")
    require(not (directory / ".active_run.json").exists(), "Run claim appeared during audit")
    return dict(audit_passed=True, audited_at_utc=datetime.now(timezone.utc).isoformat(),
                audit_scope="completed_memory_stability_v1_saved_evidence_consistency", design_id=DESIGN,
                attempt_id=plan["attempt_id"], measurement_status="validation_only", score_inclusion=False,
                measurement_commit=plan["implementation_commit"], audit_script_sha256=digest(snapshots[Path(__file__).resolve()]),
                source_sha256=plan["source_sha256"], sample_count=len(samples), runs=reports,
                input_sha256={p.relative_to(directory).as_posix(): digest(data) for p, data in snapshots.items() if p.is_relative_to(directory)},
                limitations=["No memory/timing measurement, compression or restoration was rerun.",
                             "Round-trip flags and compressed sizes/hashes are saved evidence, not independent restoration verification.",
                             "Requires matching recorded source/config bytes; hashes do not authenticate evidence.",
                             "Operator events and reported environment are consistency checks, not independent certification.",
                             "No candidate labels, stability/regret analysis, scientific acceptance decision or official four-metric activation."])


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Optional new JSON report; never overwrite")
    args = parser.parse_args(arguments)
    try:
        report = audit(args.experiment_dir)
        serialized = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(serialized)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, csv.Error) as exc:
        parser.exit(1, f"Audit failed: {exc}\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
