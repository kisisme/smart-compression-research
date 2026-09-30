"""Read-only audit of completed runtime-baseline-v1 evidence.

This module intentionally does not import the runner, worker or compression code.
It regenerates input bytes and schedules, but never compresses or measures memory.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import random
import re
import statistics

ROOT = Path(__file__).resolve().parent.parent
DESIGN = "memory_runtime_baseline_v1"
METHOD = "windows_get_process_memory_info_peak_working_set"
SOURCES = (
    "src/memory_runtime_validation.py", "src/memory_runtime_worker.py",
    "src/memory_validation.py", "src/memory_benchmark.py", "src/compressors.py",
    "src/data_generator.py", "config/experiment_config.json", "requirements.txt",
    "research_log/memory_runtime_baseline_design.md",
)
ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
PHASES = ("compress", "decompress")
ARMS = ("import_only", "input_only", "codec")
SAMPLE_FIELDS = ("sample_id", "family", "size", "seed", "generation_parameters")
REFERENCE_FIELDS = (*SAMPLE_FIELDS, "algorithm", "input_sha256", "compressed_sha256",
                    "compressed_size", "reference_roundtrip_verified", "error")
REPEAT_FIELDS = ("attempt_id", "run_id", "round_index", "schedule_index", "request_id",
                 *SAMPLE_FIELDS, "algorithm", "phase", "arm", "input_size", "input_sha256",
                 "expected_output_sha256", "reference_roundtrip_verified", "peak_process_working_set_bytes",
                 "verified", "input_verified", "status", "error", "return_code", "stdout", "stderr")
GROUP = ("sample_id", "algorithm", "phase", "arm")
SUMMARY_FIELDS = (*GROUP, "expected_count", "recorded_count", "failed_count", "complete",
                  "median_bytes", "min_bytes", "max_bytes", "population_std_bytes", "cv")


class AuditError(ValueError):
    """Evidence does not satisfy the complete successful study contract."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def same(actual, expected, message):
    # JSON encoding also distinguishes bool/int and int/float, unlike Python ==.
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
    def finite_float(value):
        result = float(value)
        require(math.isfinite(result), f"Nonfinite JSON number: {value}")
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite_float)


def positive_int(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value) is not None,
            f"Invalid positive integer: {label}")
    return int(value)


def sha(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            f"Invalid SHA-256: {label}")
    return value


def fixed_plan(attempt_id, reason):
    require(isinstance(attempt_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", attempt_id),
            "Invalid attempt ID")
    require(isinstance(reason, str), "Invalid attempt reason")
    samples, hashes = [], {}
    for size in (64, 256, 1024, 4096, 16384):
        for family in ("zero_bytes", "periodic_16", "uniform_random"):
            index = len(samples)
            seed = 20260922 + index if family == "uniform_random" else None
            spec = dict(sample_id=f"runtime_{index:06d}", family=family, size=size, seed=seed,
                        generation_parameters=json.dumps(dict(family=family, size=size), sort_keys=True))
            samples.append(spec)
            data = (bytes(size) if family == "zero_bytes" else
                    (bytes(range(16)) * ((size + 15) // 16))[:size] if family == "periodic_16" else
                    random.Random(seed).randbytes(size))
            hashes[spec["sample_id"]] = digest(data)
    schedules = {}
    for run_id in (1, 2, 3):
        rng = random.Random(20260922 + run_id - 1)
        rows = []
        for round_index in range(1, 6):
            blocks = [(s["sample_id"], a, p) for s in samples for a in ALGORITHMS for p in PHASES]
            rng.shuffle(blocks)
            for sid, algorithm, phase in blocks:
                arms = list(ARMS)
                rng.shuffle(arms)
                for arm in arms:
                    index = len(rows)
                    rows.append(dict(run_id=run_id, round_index=round_index, schedule_index=index,
                                     sample_id=sid, algorithm=algorithm, phase=phase, arm=arm,
                                     request_id=f"{attempt_id}:{run_id}:{index}"))
        schedules[str(run_id)] = rows
    return dict(schema_version=1, design_id=DESIGN, attempt_id=attempt_id, attempt_reason=reason,
                measurement_status="validation_only", score_inclusion=False, samples=samples,
                schedules=schedules, base_seed=20260922, repeats=5, timeout_seconds=120, run_ids=[1, 2, 3]), hashes


def csv_strings(values):
    return {k: "" if v is None else str(v) for k, v in values.items()}


def audit(directory: Path) -> dict:
    directory = directory.resolve()
    snapshots = {}

    def read(path):
        path = path.resolve()
        if path not in snapshots:
            snapshots[path] = path.read_bytes()
        return snapshots[path]

    def load(name):
        result = parse_json(read(directory / name))
        require(isinstance(result, dict), f"Expected JSON object: {name}")
        return result

    def table(name, fields):
        reader = csv.DictReader(io.StringIO(read(directory / name).decode("utf-8"), newline=""), strict=True)
        require(reader.fieldnames == list(fields), f"CSV header mismatch: {name}")
        rows = list(reader)
        require(all(set(r) == set(fields) and all(isinstance(v, str) for v in r.values()) for r in rows),
                f"Missing or surplus CSV fields: {name}")
        return rows

    def manifest(record, names, base, label):
        require(isinstance(record, dict) and set(record) == set(names), f"Incomplete {label} manifest")
        for name in names:
            require(digest(read(base / name)) == sha(record[name], name), f"SHA-256 mismatch: {label}/{name}")

    plan = load("plan.json")
    expected, input_hashes = fixed_plan(plan["attempt_id"], plan["attempt_reason"])
    same({k: v for k, v in plan.items() if k not in ("config", "source_sha256")}, expected, "Fixed plan/schedule mismatch")
    manifest(plan["source_sha256"], SOURCES, ROOT, "source; use recorded checkout")
    config = parse_json(read(ROOT / "config/experiment_config.json"))
    same(plan["config"], config, "Plan config differs from source-hashed config")
    same(config["compression"], dict(gzip={"level": 9}, bz2={"level": 9}, lzma={"preset": 6}, zstd={"level": 3}),
         "Compression design changed")
    same(config["memory"], dict(status="validation_only", platform="win32", metric="peak_process_working_set_bytes",
                              backend="GetProcessMemoryInfo.PeakWorkingSetSize", unit="bytes",
                              isolation="fresh_subprocess_per_phase_repeat", repeats=5, aggregate="median",
                              combined="max_of_phase_medians"), "Memory design changed")
    samples = table("samples.csv", SAMPLE_FIELDS)
    same(samples, [csv_strings(s) for s in expected["samples"]], "Sample matrix differs from fixed plan")
    sample_by_id = {s["sample_id"]: s for s in samples}
    plan_hash = digest(read(directory / "plan.json"))

    def metadata(meta, count, names, base):
        for key, value in dict(schema_version=1, design_id=DESIGN, attempt_id=plan["attempt_id"],
                               measurement_status="validation_only", score_inclusion=False, run_status="completed",
                               run_status_before_finalization="completed", finalization_status="completed",
                               finalization_errors=[], provenance_unchanged=True, repeat_count=count,
                               failed_repeat_count=0, measurement_method=METHOD,
                               subprocess_options=["-B", "PYTHONDONTWRITEBYTECODE=1"]).items():
            same(meta[key], value, f"Metadata {key} mismatch at {base.name}")
        require(not meta.get("run_error"), "Recorded run error")
        same(meta["source_sha256"], plan["source_sha256"], "Metadata source hash mismatch")
        same(meta["source_sha256_at_end"], plan["source_sha256"], "Changed source hash")
        same(meta["config"], config, "Metadata config mismatch")
        manifest(meta["artifact_sha256"], names, base, "artifact")
        times = []
        for key in ("started_at_utc", "finished_at_utc"):
            require(isinstance(meta[key], str), "Invalid timestamp type")
            value = datetime.fromisoformat(meta[key])
            require(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "Expected UTC timestamp")
            times.append(value)
        require(times[0] <= times[1], "Reversed run timestamps")
        git = meta["git"]
        require(isinstance(git, dict) and isinstance(git.get("commit_hash"), str)
                and re.fullmatch(r"[0-9a-f]{40}", git["commit_hash"]), "Missing Git commit provenance")
        require(type(git.get("worktree_dirty")) is bool and isinstance(git.get("status_porcelain"), str)
                and git["worktree_dirty"] == bool(git["status_porcelain"]) and not git.get("error"), "Invalid Git status provenance")
        for env in (meta["environment"], meta["environment_at_end"]):
            require(isinstance(env, dict) and env.get("bytecode_disabled") is True, "Bytecode option missing")
            for key in ("pid", "total_physical_memory_bytes", "available_physical_memory_bytes", "logical_cpu_count", "python_pointer_bits"):
                require(type(env.get(key)) is int and env[key] > 0, f"Invalid environment {key}")
            require(env["available_physical_memory_bytes"] <= env["total_physical_memory_bytes"], "Invalid available memory")
            for key in ("python_version", "python_executable", "operating_system", "architecture"):
                require(isinstance(env.get(key), str) and env[key], f"Missing environment {key}")
            require(isinstance(env.get("processor"), str) and isinstance(env.get("package_versions"), dict)
                    and env["package_versions"] and all(isinstance(v, str) and v for v in env["package_versions"].values()),
                    "Missing package/processor provenance")
        stable = {k: v for k, v in meta["environment"].items() if k != "available_physical_memory_bytes"}
        same({k: v for k, v in meta["environment_at_end"].items() if k != "available_physical_memory_bytes"},
             stable, "Environment changed within run")
        return times

    top = load("metadata.json")
    names = ["plan.json", "samples.csv", *(name for i in (1, 2, 3) for name in
             (f"run_{i:02d}_stdout.txt", f"run_{i:02d}_stderr.txt", f"run_{i:02d}/metadata.json"))]
    outer_times = metadata(top, sum(map(len, expected["schedules"].values())), names, directory)
    same(top["runs"], [dict(run_id=i, return_code=0, run_status="completed") for i in (1, 2, 3)], "Parent completion records mismatch")
    require(top["analysis_status"] == "pending_independent_audit_and_diagnostics", "Unexpected analysis contract")
    reference_evidence, run_reports = {}, []
    previous_end = outer_times[0]
    for run_id in (1, 2, 3):
        prefix = f"run_{run_id:02d}"
        schedule = expected["schedules"][str(run_id)]
        meta = load(f"{prefix}/metadata.json")
        times = metadata(meta, len(schedule), ("references.csv", "repeats.csv", "summary.csv"), directory / prefix)
        require(previous_end <= times[0] <= times[1] <= outer_times[1], "Runs overlap or fall outside study timestamps")
        previous_end = times[1]
        same(meta["run_id"], run_id, "Wrong run ID")
        same(meta["planned_repeat_count"], len(schedule), "Wrong planned count")
        same(meta["repeat_status_counts"], {"ok": len(schedule)}, "Wrong status counts")
        require(meta["plan_sha256"] == meta["plan_sha256_at_end"] == plan_hash, "Plan hash mismatch")
        require(meta["git"]["commit_hash"] == top["git"]["commit_hash"], "Git commit changed between parents")
        for key in ("python_version", "python_executable", "operating_system", "architecture", "package_versions"):
            same(meta["environment"][key], top["environment"][key], f"Run environment differs: {key}")
        same(load(f"{prefix}_stdout.txt"), dict(run_status="completed", repeat_count=len(schedule), failed_repeat_count=0),
             "Parent stdout mismatch")
        # A successful worker or parent may write a warning to stderr. Preserve it
        # as evidence; the runner contract does not treat nonempty stderr as failure.
        references = table(f"{prefix}/references.csv", REFERENCE_FIELDS)
        expected_pairs = {(s["sample_id"], a) for s in samples for a in ALGORITHMS}
        by_pair = {(r["sample_id"], r["algorithm"]): r for r in references}
        require(len(references) == len(by_pair) == len(expected_pairs) and set(by_pair) == expected_pairs,
                "Duplicate/missing reference pairs")
        for pair, record in by_pair.items():
            same({k: record[k] for k in SAMPLE_FIELDS}, sample_by_id[pair[0]], "Reference sample mismatch")
            require(record["input_sha256"] == input_hashes[pair[0]], "Regenerated input hash mismatch")
            sha(record["compressed_sha256"], "compressed reference")
            positive_int(record["compressed_size"], "compressed reference size")
            require(record["reference_roundtrip_verified"] == "True" and record["error"] == "", "Failed reference preparation")
            evidence = (record["compressed_sha256"], record["compressed_size"])
            if run_id == 1:
                reference_evidence[pair] = evidence
            require(reference_evidence[pair] == evidence, "Compressed reference differs across runs")
        rows = table(f"{prefix}/repeats.csv", REPEAT_FIELDS)
        require(len(rows) == len(schedule), "Incomplete repeat matrix")
        grouped = defaultdict(list)
        for row, item in zip(rows, schedule):
            same({k: row[k] for k in item}, csv_strings(item), "Duplicate/missing/reordered schedule key")
            same({k: row[k] for k in SAMPLE_FIELDS}, sample_by_id[item["sample_id"]], "Repeat sample mismatch")
            ref = by_pair[(item["sample_id"], item["algorithm"])]
            compress = item["phase"] == "compress"
            expected_input = ref["input_sha256"] if compress else ref["compressed_sha256"]
            expected_output = ref["compressed_sha256"] if compress else ref["input_sha256"]
            input_size = ref["size"] if compress else ref["compressed_size"]
            require(row["attempt_id"] == plan["attempt_id"] and row["input_sha256"] == expected_input
                    and row["expected_output_sha256"] == expected_output and row["input_size"] == input_size,
                    "Phase input/output reference mismatch")
            require(row["status"] == "ok" and row["error"] == "" and row["return_code"] == "0"
                    and row["reference_roundtrip_verified"] == "True", "Failed/unverified repeat")
            arm = item["arm"]
            require(row["verified"] == ("True" if arm == "codec" else "")
                    and row["input_verified"] == ("True" if arm == "input_only" else ""), "Invalid arm null/boolean rule")
            peak = positive_int(row["peak_process_working_set_bytes"], "peak")
            payload = dict(schema_version=1, design_id=DESIGN, measurement_status="validation_only",
                           score_inclusion=False, measurement_method=METHOD, request_id=item["request_id"],
                           arm=arm, phase=item["phase"], algorithm=item["algorithm"], peak_process_working_set_bytes=peak,
                           observed_input_size=None if arm == "import_only" else int(input_size),
                           verified=True if arm == "codec" else None, input_verified=True if arm == "input_only" else None,
                           status="ok", error="")
            same(parse_json(row["stdout"]), payload, "Worker JSON differs from stored request/result")
            grouped[tuple(row[k] for k in GROUP)].append(peak)
        summaries = table(f"{prefix}/summary.csv", SUMMARY_FIELDS)
        keys = [tuple(r[k] for k in GROUP) for r in summaries]
        require(len(keys) == len(set(keys)) == len(grouped) and set(keys) == set(grouped), "Duplicate/missing summary groups")
        for row, key in zip(summaries, keys):
            require(row["expected_count"] == row["recorded_count"] == "5" and row["failed_count"] == "0"
                    and row["complete"] == "True", "Incomplete summary")
            values = grouped[key]
            require(len(values) == 5, "Wrong repeat count per group")
            expected_stats = dict(median_bytes=statistics.median(values), min_bytes=min(values), max_bytes=max(values),
                                  population_std_bytes=statistics.pstdev(values), cv=statistics.pstdev(values) / statistics.mean(values))
            for field, value in expected_stats.items():
                if field in ("median_bytes", "min_bytes", "max_bytes"):
                    require(positive_int(row[field], field) == value, f"Summary statistic mismatch: {field}")
                    continue
                actual = float(row[field])
                require(math.isfinite(actual) and math.isclose(actual, value, rel_tol=1e-12, abs_tol=1e-12),
                        f"Summary statistic mismatch: {field}")
        run_reports.append(dict(run_id=run_id, reference_count=len(references), repeat_count=len(rows), summary_count=len(summaries)))
    # Detect concurrent changes and bind the report to exactly the bytes audited.
    for path, data in snapshots.items():
        require(path.read_bytes() == data, f"Input changed during audit: {path}")
    return dict(audit_passed=True, audited_at_utc=datetime.now(timezone.utc).isoformat(),
                audit_scope="completed_runtime_baseline_v1_saved_evidence_consistency",
                design_id=DESIGN, attempt_id=plan["attempt_id"], measurement_status="validation_only", score_inclusion=False,
                measurement_commit=top["git"]["commit_hash"], audit_script_sha256=digest(Path(__file__).read_bytes()),
                sample_count=len(samples), runs=run_reports,
                input_sha256={p.relative_to(directory).as_posix(): digest(data) for p, data in snapshots.items() if p.is_relative_to(directory)},
                limitations=["No memory measurement, compression or restoration was rerun.",
                             "Round-trip flags are saved evidence, not independent restoration verification.",
                             "Compressed digests/sizes are checked for consistency, not recomputed.",
                             "Requires matching recorded source/config bytes; hashes are not authenticity signatures.",
                             "No paired/cross-run diagnostics or scientific acceptance decision; no memory score activation."])


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Optional new audit JSON; never overwrite")
    args = parser.parse_args(arguments)
    try:
        result = audit(args.experiment_dir)
        serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, csv.Error) as exc:
        parser.exit(1, f"Audit failed: {exc}\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
