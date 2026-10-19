"""Collect memory_repeatability_v1 using ordered runs without clock windows.

Frozen additive adaptation of memory_stability_validation at commit 82041e8.
The study protocol is distinct; existing timing-worker wire protocol is reused.
CLI init prepares a NEW study; run executes only its next ordered full run.
No clock/day/gap restriction, sleep, job retry or interrupted-run resumption.
Actual timestamps and environment/events remain recorded. No cross-day claim,
independent audit, candidate labels or scientific adoption is produced here.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import csv
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
import tempfile
import uuid

from src import compressors, data_generator, memory_benchmark
from src import memory_validation as common
from src import memory_stability_timing_worker as timing_worker

ROOT = common.ROOT
DESIGN_ID = "memory_repeatability_v1"
TIMING_WORKER_DESIGN_ID = "memory_stability_v1"
ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
PHASES = ("compress", "decompress")
CORE_SIZES = (16384, 65536, 262144, 1048576)
GENERATORS = ("random", "small_alphabet", "repeated_pattern", "long_runs", "structured", "mixed")
REPLICATES = (0, 1, 2)
TINY_SIZES = (64, 256, 1024, 4096)
FAMILIES = ("zero_bytes", "periodic_16", "uniform_random")
RUN_IDS = (1, 2, 3, 4, 5, 6)
SEED, SCHEDULE_SEED, REPEATS, TIMEOUT = 20261007, 20262007, 5, 120
SEOUL = timezone(timedelta(hours=9), "Asia/Seoul")
DESIGN_PATH = "research_log/memory_repeatability_validation_design.md"
SOURCE_PATHS = (
    "src/memory_repeatability_validation.py", "src/memory_stability_timing_worker.py",
    "src/memory_benchmark.py", "src/memory_validation.py", "src/compressors.py",
    "src/data_generator.py", "config/experiment_config.json", "requirements.txt", DESIGN_PATH,
)
WEIGHTS = {
    "archive": {"size": .65, "compress": .10, "decompress": .10, "memory": .15},
    "balanced": {"size": .40, "compress": .20, "decompress": .20, "memory": .20},
    "fast_access": {"size": .20, "compress": .20, "decompress": .45, "memory": .15},
}
CRITERIA = {
    "delta": .01, "epsilon": .005, "w_memory_max": .20,
    "memory_span_limit_expression": "epsilon / (2 * w_memory_max)",
    "memory_span_limit": .005 / (2 * .20),
    "memory_span_expression": "ln(max_r M_ra / min_r M_ra)",
    "transfer_regret_expression": "S_q(t, A_q(r)) - min_a S_q(t,a)",
    "timing_aggregate": "median(elapsed_ns) / 1000000",
    "memory_aggregate": "max(median(compress), median(decompress))",
    "tie_order": list(ALGORITHMS), "score_epsilon": None,
    "execution_policy": "ordered_nonoverlapping_runs_without_clock_day_or_gap_limits",
    "interpretation_scope": "observed_repeated_runs_in_recorded_environment_not_cross_day_validation",
    "timezone": "Asia/Seoul",
}
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
ENVIRONMENT_KEYS = ("python_version", "python_executable", "operating_system", "architecture",
                    "python_pointer_bits", "processor", "logical_cpu_count",
                    "total_physical_memory_bytes", "package_versions")
EVENT_FIELDS = ("power_mode", "manual_reboot_since_previous_run", "concurrent_activity",
                "os_update_events", "other_events", "no_research_jobs_running")
OPTIONS = ["-B", "PYTHONDONTWRITEBYTECODE=1"]


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _same(left, right) -> bool:
    return _json(left) == _json(right)


def strict_json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def floating(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("Nonfinite JSON number")
        return parsed
    def constant(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")
    return json.loads(text, object_pairs_hook=pairs, parse_float=floating, parse_constant=constant)


def _read_json(path):
    return strict_json(path.read_text(encoding="utf-8"))


def _sources():
    return {name: common._digest((ROOT / name).read_bytes()) for name in SOURCE_PATHS}


def _check_config():
    if sys.platform != "win32" or not sys.dont_write_bytecode:
        raise RuntimeError("Requires Windows and python -B")
    timing_worker._check_configuration()
    config = memory_benchmark._load_config()
    repeats, _ = memory_benchmark._memory_config(config)
    if (not _same(config, compressors._CONFIG) or not _same(config, data_generator._CONFIG)
            or repeats != REPEATS or config["sample_sizes"] != [16384, 65536, 262144, 1048576]):
        raise ValueError("Loaded configuration differs from the fixed stability design")
    return config


def _environment():
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                    *((name, ctypes.c_ulonglong) for name in (
                        "total_physical", "available_physical", "total_pagefile", "available_pagefile",
                        "total_virtual", "available_virtual", "available_extended_virtual"))]
    state = MemoryStatus()
    state.length = ctypes.sizeof(state)
    api = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
    api.argtypes, api.restype = (ctypes.POINTER(MemoryStatus),), wintypes.BOOL
    if not api(ctypes.byref(state)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {**common._environment(), "available_physical_memory_bytes": state.available_physical,
            "memory_load_percent": state.load, "pid": os.getpid(),
            "bytecode_disabled": sys.dont_write_bytecode}


def _fixed_environment(environment):
    return {key: environment[key] for key in ENVIRONMENT_KEYS}


def _check_events(events):
    if not isinstance(events, dict) or set(events) != set(EVENT_FIELDS):
        raise ValueError(f"Events require exactly {EVENT_FIELDS}")
    for name in EVENT_FIELDS:
        if name in ("manual_reboot_since_previous_run", "no_research_jobs_running"):
            if type(events[name]) is not bool:
                raise TypeError(f"Event {name} must be boolean")
        elif not isinstance(events[name], str) or not events[name].strip():
            raise ValueError(f"Event {name} must be a nonempty description (use 'none' when applicable)")
    return events


def build_plan(attempt_id: str, reason: str = "") -> dict:
    if not isinstance(attempt_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", attempt_id):
        raise ValueError("attempt_id must be 1-64 ASCII letters, digits, underscores or hyphens")
    if not isinstance(reason, str):
        raise TypeError("Attempt reason must be a string")
    samples = []
    for size in CORE_SIZES:
        for generator in GENERATORS:
            for replicate in REPLICATES:
                index = len(samples)
                samples.append(dict(sample_id=f"stability_{index:06d}", stratum="core", generator=generator,
                                    family=None, replicate_index=replicate, size=size, seed=SEED + index))
    for size in TINY_SIZES:
        for family in FAMILIES:
            index = len(samples)
            samples.append(dict(sample_id=f"stability_{index:06d}", stratum="tiny", generator=None,
                                family=family, replicate_index=None, size=size,
                                seed=SEED + index if family == "uniform_random" else None))
    keys = [(s["sample_id"], a, p, i) for s in samples for a in ALGORITHMS for p in PHASES for i in range(1, REPEATS + 1)]
    schedules = {}
    for run_id in RUN_IDS:
        jobs = [dict(kind="memory", sample_id=s, algorithm=a, phase=p, repeat_index=i) for s, a, p, i in keys]
        jobs += [dict(kind="timing", sample_id=s["sample_id"], algorithm=a, phase=None, repeat_index=None)
                 for s in samples for a in ALGORITHMS]
        random.Random(SCHEDULE_SEED + run_id).shuffle(jobs)
        schedules[str(run_id)] = [{**job, "run_id": run_id, "schedule_index": index,
                                  "request_id": f"{attempt_id}:{run_id}:{index}"} for index, job in enumerate(jobs)]
    return dict(schema_version=1, design_id=DESIGN_ID, attempt_id=attempt_id, attempt_reason=reason,
                measurement_status="validation_only", score_inclusion=False, samples=samples,
                schedules=schedules, expected_keys={"memory": keys, "timing": keys},
                base_seed=SEED, schedule_seed=SCHEDULE_SEED, repeats=REPEATS, timeout_seconds=TIMEOUT,
                run_ids=list(RUN_IDS), candidate_weights=WEIGHTS, criteria=CRITERIA,
                subprocess_options=OPTIONS, timing_worker_design_id=TIMING_WORKER_DESIGN_ID)


def generate_input(spec):
    if spec["stratum"] == "core":
        sample = data_generator.generate_sample(spec["generator"], spec["size"], spec["seed"])
        return sample.data, sample.parameters
    size, family = spec["size"], spec["family"]
    if family == "zero_bytes":
        data = bytes(size)
    elif family == "periodic_16":
        data = (bytes(range(16)) * ((size + 15) // 16))[:size]
    elif family == "uniform_random":
        data = random.Random(spec["seed"]).randbytes(size)
    else:
        raise ValueError("Unknown tiny family")
    return data, {"family": family, "size": size}


def _sample_records(specs):
    rows, first = [], {}
    for spec in specs:
        row = {**spec, "generation_parameters": None, "input_sha256": None,
               "duplicate_of": None, "status": "preparation_failed", "error": ""}
        try:
            data, parameters = generate_input(spec)
            if not isinstance(data, bytes) or len(data) != spec["size"] or not data:
                raise ValueError("Generated input has wrong type/size")
            sha = common._digest(data)
            row.update(generation_parameters=_json(parameters), input_sha256=sha,
                       duplicate_of=first.get(sha), status="ok")
            first.setdefault(sha, spec["sample_id"])
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows


def _write_csv(path, fields, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        stream.flush()
        for row in rows:
            writer.writerow(row)
            stream.flush()


def _read_csv(path, fields):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(fields):
            raise ValueError("CSV schema differs from contract")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError("Malformed CSV row")
        return rows


def _saved_samples(path, specs):
    rows = _read_csv(path, SAMPLE_FIELDS)
    if len(rows) != len(specs):
        raise ValueError("Sample count differs from plan")
    restored = []
    for row, spec in zip(rows, specs):
        if any(row[key] != ("" if value is None else str(value)) for key, value in spec.items()):
            raise ValueError("Sample identity differs from fixed input specification")
        restored.append({**spec, **{key: row[key] or None for key in ("generation_parameters", "input_sha256", "duplicate_of")},
                         "status": row["status"], "error": row["error"]})
    return restored


def _prepare(samples, directory, previous_references=None):
    refs = {}
    for sample in samples:
        data, error = None, sample["error"]
        try:
            if sample["status"] != "ok":
                raise ValueError(error or "Saved input preparation failed")
            data, parameters = generate_input(sample)
            if (not isinstance(data, bytes) or len(data) != sample["size"]
                    or common._digest(data) != sample["input_sha256"]
                    or _json(parameters) != sample["generation_parameters"]):
                raise ValueError("Regenerated input differs from saved sample")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        for algorithm in ALGORITHMS:
            record = dict(sample_id=sample["sample_id"], algorithm=algorithm, original_size=sample["size"],
                          compressed_size=None, original_sha256=sample["input_sha256"], compressed_sha256=None,
                          reference_roundtrip_verified=None, status="preparation_failed", error=error)
            paths = {}
            try:
                if error:
                    raise ValueError(error)
                compressed = compressors.compress_data(data, algorithm)
                if not isinstance(compressed, bytes) or not compressed:
                    raise ValueError("Reference compressed output must be nonempty bytes")
                record.update(compressed_size=len(compressed), compressed_sha256=common._digest(compressed),
                              reference_roundtrip_verified=compressors.decompress_data(compressed, algorithm) == data)
                if record["reference_roundtrip_verified"] is not True:
                    raise ValueError("Reference restored bytes differ from original")
                if previous_references is not None:
                    previous = previous_references[(sample["sample_id"], algorithm)]
                    for key in ("original_size", "compressed_size", "original_sha256", "compressed_sha256"):
                        if previous[key] != str(record[key]):
                            raise ValueError("Reference differs between runs")
                    if previous["status"] != "ok" or previous["reference_roundtrip_verified"] != "True":
                        raise ValueError("Earlier reference preparation failed")
                for phase, value in (("compress", data), ("decompress", compressed)):
                    path = directory / f"{sample['sample_id']}_{algorithm}_{phase}.bin"
                    with path.open("xb") as stream:
                        stream.write(value)
                    if path.read_bytes() != value:
                        raise OSError("Prepared file differs from reference bytes")
                    paths[phase] = path
                record.update(status="ok", error="")
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            refs[(sample["sample_id"], algorithm)] = record, paths
    return refs


def _digest_valid(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _positive_int(value):
    return type(value) is int and value > 0


def _require_identity(payload, expected):
    if not isinstance(payload, dict):
        raise ValueError("Worker response must be an object")
    for key, value in expected.items():
        if key not in payload or not _same(payload[key], value):
            raise ValueError(f"Worker identity/contract mismatch: {key}")


def _validate_memory(payload, request, code):
    _require_identity(payload, {"operation": request["phase"], "algorithm": request["algorithm"]})
    if set(payload) != {"operation", "algorithm", "peak_process_working_set_bytes", "verified"}:
        raise ValueError("Memory response fields differ from contract")
    if not _positive_int(payload["peak_process_working_set_bytes"]) or type(payload["verified"]) is not bool:
        raise ValueError("Memory requires positive integer peak and boolean verification")
    if code != (0 if payload["verified"] else 2):
        raise ValueError("Memory exit code and verification disagree")


def _validate_timing(payload, request, code):
    identities = dict(schema_version=1, design_id=TIMING_WORKER_DESIGN_ID, measurement_status="validation_only", score_inclusion=False,
                      request_id=request["request_id"], algorithm=request["algorithm"], timer="time.perf_counter_ns")
    _require_identity(payload, identities)
    if set(payload) != {*identities, "original_size", "compressed_size", "original_sha256", "compressed_sha256", "records", "status", "error"}:
        raise ValueError("Timing response fields differ from contract")
    status = payload["status"]
    if status not in ("ok", "verification_failed", "worker_failed") or code != {"ok": 0, "verification_failed": 2, "worker_failed": 1}[status]:
        raise ValueError("Timing status/exit code mismatch")
    if not isinstance(payload["error"], str) or bool(payload["error"]) != (status != "ok"):
        raise ValueError("Timing error/status mismatch")
    for key in ("original_size", "compressed_size", "original_sha256", "compressed_sha256"):
        value = payload[key]
        if value is None and status == "worker_failed":
            continue
        if not _same(value, request[key]):
            raise ValueError(f"Timing input mismatch: {key}")
    records = payload["records"]
    keys = [(p, i) for p in PHASES for i in range(1, REPEATS + 1)]
    if not isinstance(records, list) or len(records) > len(keys) or (status != "worker_failed" and len(records) != len(keys)):
        raise ValueError("Timing record count differs from contract")
    for index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != {"phase", "repeat_index", "elapsed_ns", "actual_output_sha256", "verified", "status", "error"}:
            raise ValueError("Timing record schema differs from contract")
        _require_identity(record, {"phase": keys[index][0], "repeat_index": keys[index][1]})
        rstatus, value, verified, digest = (record[k] for k in ("status", "elapsed_ns", "verified", "actual_output_sha256"))
        if not isinstance(record["error"], str) or bool(record["error"]) != (rstatus != "ok"):
            raise ValueError("Timing record error/status mismatch")
        expected_digest = request["compressed_sha256"] if record["phase"] == "compress" else request["original_sha256"]
        if rstatus in ("ok", "verification_failed"):
            if not _positive_int(value) or type(verified) is not bool or verified != (rstatus == "ok") or not _digest_valid(digest):
                raise ValueError("Invalid successful/verification-failed timing record")
            if verified and digest != expected_digest:
                raise ValueError("Verified timing output digest differs from reference")
        elif rstatus == "worker_failed":
            if (status != "worker_failed" or index != len(records) - 1 or (value is not None and type(value) is not int)
                    or (verified is not None and type(verified) is not bool) or (digest is not None and not _digest_valid(digest))):
                raise ValueError("Invalid partial failed timing record")
        else:
            raise ValueError("Unknown timing record status")
    if status == "ok" and any(r["status"] != "ok" for r in records):
        raise ValueError("Successful timing bundle contains failure")
    if status == "verification_failed" and not any(r["status"] == "verification_failed" for r in records):
        raise ValueError("Timing bundle claims failure without failed verification")
    if status == "worker_failed" and records and records[-1]["status"] != "worker_failed":
        raise ValueError("Failed timing bundle lacks terminal failed record")


def _text(value):
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


def run_worker(request, paths):
    """Launch once, checking immutable phase inputs before and after even failures."""
    timing = request["kind"] == "timing"
    if timing:
        command = [sys.executable, "-B", "-m", "src.memory_stability_timing_worker",
                   "--request-id", request["request_id"], "--algorithm", request["algorithm"],
                   "--original", str(paths["compress"]), "--reference-compressed", str(paths["decompress"]),
                   "--original-sha256", request["original_sha256"], "--compressed-sha256", request["compressed_sha256"]]
        checks = [(paths[p], request["original_size" if p == "compress" else "compressed_size"],
                   request["original_sha256" if p == "compress" else "compressed_sha256"]) for p in PHASES]
    else:
        command = [sys.executable, "-B", "-m", "src.memory_benchmark", "worker",
                   "--operation", request["phase"], "--algorithm", request["algorithm"],
                   "--input", str(paths[request["phase"]]), "--expected-sha256", request["expected_output_sha256"]]
        checks = [(paths[request["phase"]], request["input_size"], request["input_sha256"])]
    evidence = dict(status="worker_failed", error="", return_code=None, stdout="", stderr="", payload=None,
                    argv=_json(command), python_executable=sys.executable, subprocess_options=_json(OPTIONS),
                    started_at_utc=common._now(), finished_at_utc=None,
                    input_verified_before=False, input_verified_after=False)
    def check():
        for path, size, digest in checks:
            data = path.read_bytes()
            if len(data) != size or common._digest(data) != digest:
                raise ValueError("Phase input changed or differs from request")
    try:
        check()
        evidence["input_verified_before"] = True
        original_exception = None
        try:
            completed = subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                       capture_output=True, timeout=TIMEOUT)
            evidence.update(return_code=completed.returncode, stdout=_text(completed.stdout), stderr=_text(completed.stderr))
            try:
                payload = strict_json(evidence["stdout"])
                if evidence["stderr"]:
                    raise ValueError("Worker stderr is not empty")
                if timing:
                    _validate_timing(payload, request, completed.returncode)
                    status, error = payload["status"], payload["error"]
                else:
                    _validate_memory(payload, request, completed.returncode)
                    status = "ok" if payload["verified"] else "verification_failed"
                    error = "" if payload["verified"] else "Memory output SHA-256 mismatch"
                evidence.update(status=status, error=error, payload=payload)
            except (ValueError, TypeError, KeyError) as exc:
                evidence.update(status="invalid_result" if completed.returncode in (0, 1, 2) else "worker_failed",
                                error=f"{type(exc).__name__}: {exc}")
        except subprocess.TimeoutExpired as exc:
            evidence.update(status="timeout", error=str(exc), stdout=_text(exc.stdout), stderr=_text(exc.stderr))
        except OSError as exc:
            evidence["error"] = f"{type(exc).__name__}: {exc}"
        except BaseException as exc:
            original_exception = exc
            raise
        finally:
            try:
                check()
                evidence["input_verified_after"] = True
            except BaseException as exc:
                if original_exception is None:
                    raise
                original_exception.add_note(f"Input verification after worker also failed: {type(exc).__name__}: {exc}")
    except (OSError, ValueError) as exc:
        previous_error = evidence["error"]
        evidence.update(status="input_changed", error=f"{type(exc).__name__}: {exc}"
                        + (f"; previous worker error: {previous_error}" if previous_error else ""))
    finally:
        evidence["finished_at_utc"] = common._now()
    return evidence


def _raw_rows(request, evidence):
    timing = request["kind"] == "timing"
    keys = [(p, i) for p in PHASES for i in range(1, REPEATS + 1)] if timing else [(request["phase"], request["repeat_index"])]
    payload = evidence.get("payload")
    records = {(r["phase"], r["repeat_index"]): r for r in payload["records"]} if timing and payload is not None else {}
    rows = []
    for phase, index in keys:
        compress = phase == "compress"
        row = {key: request[key] for key in ("attempt_id", "run_id", "sample_id", "algorithm", "schedule_index", "request_id", "reference_roundtrip_verified")}
        row.update({key: evidence[key] for key in ("argv", "python_executable", "subprocess_options", "started_at_utc", "finished_at_utc", "return_code", "stdout", "stderr", "input_verified_before", "input_verified_after")})
        row.update(phase=phase, repeat_index=index, input_size=request["original_size" if compress else "compressed_size"],
                   input_sha256=request["original_sha256" if compress else "compressed_sha256"],
                   expected_output_sha256=request["compressed_sha256" if compress else "original_sha256"],
                   bundle_status=evidence["status"], status=evidence["status"], error=evidence["error"],
                   verified=None, actual_output_sha256=None)
        if timing:
            row.update(timer="time.perf_counter_ns", elapsed_ns=None)
            record = records.get((phase, index))
            if record is not None:
                row.update({k: record[k] for k in ("elapsed_ns", "actual_output_sha256", "verified", "status", "error")})
                if evidence["status"] not in ("ok", "verification_failed", "worker_failed"):
                    row.update(status=evidence["status"], error=evidence["error"])
            elif payload is not None:
                row.update(status="missing_record", error="Worker did not execute this planned repeat")
        else:
            row.update(measurement_method=common.METHOD, peak_process_working_set_bytes=None)
            if payload is not None:
                row.update(peak_process_working_set_bytes=payload["peak_process_working_set_bytes"], verified=payload["verified"])
        rows.append(row)
    return rows


def summarize(plan, run_id, memory_rows, timing_rows):
    groups = {}
    for kind, rows in (("memory", memory_rows), ("timing", timing_rows)):
        expected = {}
        for job in plan["schedules"][str(run_id)]:
            if job["kind"] != kind:
                continue
            keys = [(p, i) for p in PHASES for i in range(1, REPEATS + 1)] if kind == "timing" else [(job["phase"], job["repeat_index"])]
            for phase, index in keys:
                expected[(job["sample_id"], job["algorithm"], phase, index)] = job
        seen, grouped = set(), defaultdict(list)
        for row in rows:
            if (type(row["repeat_index"]) is not int or not 1 <= row["repeat_index"] <= REPEATS
                    or type(row["run_id"]) is not int or type(row["schedule_index"]) is not int):
                raise ValueError("Raw identity indices must be integers, not booleans")
            key = tuple(row[k] for k in ("sample_id", "algorithm", "phase", "repeat_index"))
            if key in seen or key not in expected:
                raise ValueError("Duplicate or unplanned raw repeat")
            job = expected[key]
            if any(not _same(row[k], job[k]) for k in ("run_id", "request_id", "schedule_index")) or row["attempt_id"] != plan["attempt_id"]:
                raise ValueError("Raw repeat differs from saved schedule")
            seen.add(key)
            grouped[key[:2]].append(row)
        groups[kind] = grouped
    output = []
    for sample in plan["samples"]:
        for algorithm in ALGORITHMS:
            row = dict.fromkeys(MEASUREMENT_FIELDS)
            row.update(sample_id=sample["sample_id"], algorithm=algorithm, verified=False)
            memory, timing = (groups[kind][(sample["sample_id"], algorithm)] for kind in ("memory", "timing"))
            valid = lambda r: (r["status"] == r["bundle_status"] == "ok" and r["verified"] is True
                               and r["reference_roundtrip_verified"] is True
                               and r["input_verified_before"] is True and r["input_verified_after"] is True)
            row["failed_repeat_count"] = REPEATS * 4 - sum(valid(r) for r in memory + timing)
            if len(memory) == len(timing) == REPEATS * 2 and all(valid(r) for r in memory + timing):
                if any(not _positive_int(r["peak_process_working_set_bytes"]) for r in memory) or any(not _positive_int(r["elapsed_ns"]) for r in timing):
                    raise ValueError("Successful repeats require positive integer measurements")
                original = {r["input_size"] for r in memory if r["phase"] == "compress"}
                compressed = {r["input_size"] for r in memory if r["phase"] == "decompress"}
                if (len(original) != 1 or len(compressed) != 1 or not all(_positive_int(v) for v in original | compressed)
                        or any(r["input_size"] != next(iter(original if r["phase"] == "compress" else compressed)) for r in timing)):
                    raise ValueError("Inconsistent phase input sizes")
                row.update(verified=True, compression_ratio=next(iter(compressed)) / next(iter(original)))
                for phase in PHASES:
                    prefix = "compression" if phase == "compress" else "decompression"
                    row[prefix + "_time_ms"] = statistics.median(r["elapsed_ns"] for r in timing if r["phase"] == phase) / 1_000_000
                    row[prefix + "_peak_memory_bytes"] = statistics.median(r["peak_process_working_set_bytes"] for r in memory if r["phase"] == phase)
                row["peak_memory_bytes"] = max(row["compression_peak_memory_bytes"], row["decompression_peak_memory_bytes"])
            output.append(row)
    return output


def schedule_issues(run_id, start, previous):
    """Keep order and non-overlap; actual gaps/dates are descriptive evidence."""
    if type(run_id) is not int or run_id not in RUN_IDS or len(previous) != run_id - 1:
        raise ValueError("Invalid run order/history")
    now = datetime.fromisoformat(start)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Run timestamp must have timezone")
    prior_end = None
    for index, record in enumerate(previous, 1):
        if record.get("run_id") != index or type(record.get("run_id")) is not int:
            raise ValueError("Invalid previous run order")
        begin = datetime.fromisoformat(record["started_at_utc"])
        end = datetime.fromisoformat(record["finished_at_utc"])
        if begin.tzinfo is None or end.tzinfo is None or begin.utcoffset() is None or end.utcoffset() is None:
            raise ValueError("History timestamps must have timezone")
        if end < begin or (prior_end is not None and begin < prior_end):
            raise ValueError("Invalid/overlapping history timestamps")
        prior_end = end
    return ["run_overlaps_previous"] if prior_end is not None and now < prior_end else []


def _git_for_attempt(study=None):
    info = common._git_information()
    if info.get("commit_hash") is None or type(info.get("worktree_dirty")) is not bool:
        raise RuntimeError("Cannot establish Git provenance")
    allowed = None
    if study is not None:
        try:
            allowed = study.resolve().relative_to(ROOT.resolve()).as_posix() + "/"
        except ValueError:
            pass
    for line in info.get("status_porcelain", "").splitlines():
        if allowed is None or line != "?? " + allowed:
            raise RuntimeError("Worktree contains changes outside this new attempt")
    return info


def _metadata(plan):
    return dict(schema_version=1, design_id=DESIGN_ID, attempt_id=plan["attempt_id"],
                measurement_status="validation_only", score_inclusion=False, run_status="running",
                started_at_utc=common._now(), source_sha256=_sources(), environment=_environment(),
                planned_source_sha256=plan["source_sha256"],
                subprocess_options=OPTIONS, config=_check_config(), repeat_count=0, failed_repeat_count=0,
                validity_issues=[], analysis_status="pending_independent_audit_and_analysis",
                technical_validity_status="pending_independent_audit")


def _finalize(path, metadata, artifacts, immutable):
    status = metadata["run_status"]
    metadata.update(finished_at_utc=common._now(), run_status_before_finalization=status,
                    finalization_status="in_progress", finalization_errors=[], artifact_sha256={},
                    source_sha256_at_end=None, environment_at_end=None, immutable_sha256_at_end={},
                    provenance_unchanged=None)
    if status in ("initialized", "awaiting_next_run", "completed", "completed_with_failures"):
        metadata["run_status"] = "finalizing"
    failures = []
    def attempt(stage, action):
        try:
            action()
        except BaseException as exc:
            failures.append(exc)
            metadata["finalization_errors"].append(dict(stage=stage, error=f"{type(exc).__name__}: {exc}"))
    attempt("terminal_checkpoint", lambda: common._save_metadata(path, metadata))
    attempt("environment_at_end", lambda: metadata.update(environment_at_end=_environment()))
    attempt("source_sha256_at_end", lambda: metadata.update(source_sha256_at_end=_sources()))
    for name, (artifact, digest) in immutable.items():
        attempt(f"immutable:{name}", lambda a=artifact, n=name: metadata["immutable_sha256_at_end"].update({n: common._digest(a.read_bytes())}))
    metadata["provenance_unchanged"] = (metadata["source_sha256_at_end"] == metadata["source_sha256"] == metadata["planned_source_sha256"]
                                       and all(metadata["immutable_sha256_at_end"].get(n) == digest for n, (_, digest) in immutable.items()))
    if metadata["environment_at_end"] is not None and not _same(_fixed_environment(metadata["environment"]), _fixed_environment(metadata["environment_at_end"])):
        metadata["validity_issues"].append("environment_changed_during_operation")
    for artifact in artifacts:
        name = artifact.relative_to(path.parent).as_posix()
        attempt(f"artifact:{name}", lambda a=artifact, n=name: metadata["artifact_sha256"].update({n: common._digest(a.read_bytes())}))
    metadata["finalization_status"] = "failed" if failures else "completed"
    metadata["run_status"] = ("finalization_failed" if failures and metadata["run_status"] == "finalizing" else
                              "invalid_provenance_changed" if metadata["run_status"] == "finalizing" and not metadata["provenance_unchanged"] else status)
    metadata["recording_checks_passed"] = (metadata["run_status"] in ("initialized", "awaiting_next_run", "completed")
                                           and metadata["provenance_unchanged"] is True and not metadata["validity_issues"]
                                           and not metadata["failed_repeat_count"] and not metadata.get("failed_sample_count", 0) and not failures)
    attempt("final_metadata_save", lambda: common._save_metadata(path, metadata))
    if failures:
        failures[0].add_note("Finalization errors: " + _json(metadata["finalization_errors"]))
        raise failures[0]


def _finish(path, metadata, artifacts, immutable, original_error):
    try:
        _finalize(path, metadata, artifacts, immutable)
    except BaseException as exc:
        if original_error is None:
            raise
        original_error.add_note(f"Finalization also failed: {type(exc).__name__}: {exc}")
        for note in getattr(exc, "__notes__", ()):
            original_error.add_note(note)


def initialize(*, attempt_id, reason="", results_root=None):
    _check_config()
    git = _git_for_attempt()
    plan = build_plan(attempt_id, reason)
    if sys.platform != "win32" or not sys.dont_write_bytecode:
        raise RuntimeError("Requires Windows and python -B")
    stamp = datetime.fromisoformat(common._now()).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = Path(results_root) if results_root is not None else ROOT / "data/results"
    destination = (root / f"{DESIGN_ID}_{stamp}_{attempt_id}").absolute()
    plan.update(config=_check_config(), source_sha256=_sources(), design_sha256=_sources()[DESIGN_PATH],
                implementation_commit=git["commit_hash"], git=git, created_at_utc=common._now(),
                environment=_environment())
    destination.mkdir(parents=True, exist_ok=False)
    path = destination / "metadata.json"
    metadata = {**_metadata(plan), "git": git, "runs": [], "study_dir": str(destination),
                "attempt_started_at_utc": common._now(), "environment_at_initialization": plan["environment"],
                "memory_repeat_count": 0, "timing_repeat_count": 0, "job_count": 0,
                "planned_run_count": len(RUN_IDS), "planned_memory_repeat_count": len(plan["expected_keys"]["memory"]) * len(RUN_IDS),
                "planned_timing_repeat_count": len(plan["expected_keys"]["timing"]) * len(RUN_IDS)}
    artifacts, immutable, original_error = [], {}, None
    try:
        common._save_metadata(path, metadata)
        if _sources() != plan["source_sha256"] or not _same(_check_config(), plan["config"]):
            raise ValueError("Source/config changed while creating the plan")
        samples = _sample_records(plan["samples"])
        samples_path = destination / "samples.csv"
        _write_csv(samples_path, SAMPLE_FIELDS, samples)
        artifacts.append(samples_path)
        plan["samples_sha256"] = common._digest(samples_path.read_bytes())
        with (destination / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_json(plan) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        artifacts.append(destination / "plan.json")
        with (destination / ".gitattributes").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("* -text\n")
        artifacts.append(destination / ".gitattributes")
        immutable = {p.name: (p, common._digest(p.read_bytes())) for p in artifacts}
        metadata.update(run_status="initialized", sample_count=len(samples),
                        failed_sample_count=sum(s["status"] != "ok" for s in samples),
                        immutable_sha256={n: digest for n, (_, digest) in immutable.items()})
    except BaseException as exc:
        original_error = exc
        metadata.update(run_status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "aborted", run_error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _finish(path, metadata, artifacts, immutable, original_error)
    return metadata


def _load_plan(study):
    plan = _read_json(study / "plan.json")
    canonical = build_plan(plan["attempt_id"], plan["attempt_reason"])
    if any(not _same(plan.get(key), value) for key, value in canonical.items()):
        raise ValueError("Saved plan differs from fixed design")
    if plan["samples_sha256"] != common._digest((study / "samples.csv").read_bytes()):
        raise ValueError("Saved samples changed")
    return plan


def _history(study, count, plan):
    previous = []
    for run_id in RUN_IDS[:count]:
        child = _read_json(study / f"run_{run_id:02d}/metadata.json")
        _require_identity(child, dict(schema_version=1, design_id=DESIGN_ID, attempt_id=plan["attempt_id"],
                                      run_id=run_id, measurement_status="validation_only", score_inclusion=False,
                                      planned_source_sha256=plan["source_sha256"], source_sha256=plan["source_sha256"],
                                      source_sha256_at_end=plan["source_sha256"], config=plan["config"],
                                      planned_memory_repeat_count=len(plan["expected_keys"]["memory"]),
                                      planned_timing_repeat_count=len(plan["expected_keys"]["timing"])))
        if child["run_status"] not in ("completed", "completed_with_failures") or child["finalization_status"] != "completed" or child["provenance_unchanged"] is not True or child["finalization_errors"]:
            raise ValueError("Earlier run did not complete; cannot resume this attempt")
        for key in ("memory_repeat_count", "timing_repeat_count", "repeat_count", "failed_repeat_count", "job_count"):
            if type(child[key]) is not int or child[key] < 0:
                raise ValueError("Parent counts must be nonnegative integers")
        if (child["memory_repeat_count"] != child["planned_memory_repeat_count"]
                or child["timing_repeat_count"] != child["planned_timing_repeat_count"]
                or child["repeat_count"] != child["memory_repeat_count"] + child["timing_repeat_count"]
                or child["job_count"] != len(plan["schedules"][str(run_id)])
                or child["failed_repeat_count"] > child["repeat_count"]
                or child["run_status"] != ("completed_with_failures" if child["failed_repeat_count"] else "completed")
                or set(child["artifact_sha256"]) != {"references.csv", "memory_repeats.csv", "timing_repeats.csv", "measurements.csv"}):
            raise ValueError("Parent completion counts/artifact manifest differ from plan")
        for name, digest in child["artifact_sha256"].items():
            if common._digest((study / f"run_{run_id:02d}" / name).read_bytes()) != digest:
                raise ValueError("Earlier run artifact changed")
        previous.append(child)
    return previous


def run_one(study, run_id, token):
    """Internal fresh parent. Coordinator owns the exclusive attempt lock."""
    study = Path(study).absolute()
    claim = _read_json(study / ".active_run.json")
    if claim.get("token") != token or type(run_id) is not int or claim.get("run_id") != run_id or run_id not in RUN_IDS:
        raise ValueError("Run does not hold the coordinator claim")
    plan = _load_plan(study)
    previous = _history(study, run_id - 1, plan)
    directory = study / f"run_{run_id:02d}"
    directory.mkdir(exist_ok=False)
    metadata = {**_metadata(plan), "run_id": run_id, "git": _git_for_attempt(study), "operator_events": claim["events"],
                "planned_memory_repeat_count": len(plan["expected_keys"]["memory"]),
                "planned_timing_repeat_count": len(plan["expected_keys"]["timing"]),
                "memory_repeat_count": 0, "timing_repeat_count": 0, "job_count": 0, "repeat_status_counts": {}}
    metadata["validity_issues"] = schedule_issues(run_id, metadata["started_at_utc"], previous)
    if not claim["events"]["no_research_jobs_running"]:
        metadata["validity_issues"].append("operator_reports_concurrent_research_jobs")
    if not _same(_fixed_environment(plan["environment"]), _fixed_environment(metadata["environment"])):
        metadata["validity_issues"].append("environment_differs_from_plan")
    immutable = {name: (study / name, common._digest((study / name).read_bytes())) for name in ("plan.json", "samples.csv", ".gitattributes")}
    path = directory / "metadata.json"
    artifacts, original_error = [], None
    memory_rows, timing_rows, counts = [], [], Counter()
    try:
        common._save_metadata(path, metadata)
        if "run_overlaps_previous" in metadata["validity_issues"]:
            raise ValueError("A run cannot overlap a preceding run")
        if not claim["events"]["no_research_jobs_running"]:
            raise RuntimeError("Operator reports concurrent research jobs; this run cannot start")
        if plan["source_sha256"] != _sources() or not _same(plan["config"], _check_config()) or metadata["git"]["commit_hash"] != plan["implementation_commit"]:
            raise ValueError("Study source/config/commit changed before run")
        samples = _saved_samples(study / "samples.csv", plan["samples"])
        old_refs = None
        if previous:
            old_refs = {(r["sample_id"], r["algorithm"]): r for r in _read_csv(study / "run_01/references.csv", REFERENCE_FIELDS)}
        with tempfile.TemporaryDirectory(prefix="stability_phase_inputs_") as temporary:
            references = _prepare(samples, Path(temporary), old_refs)
            reference_path = directory / "references.csv"
            artifacts.append(reference_path)
            _write_csv(reference_path, REFERENCE_FIELDS, (r for r, _ in references.values()))
            with ExitStack() as stack:
                writers = {}
                for kind, fields in (("memory", MEMORY_FIELDS), ("timing", TIMING_FIELDS)):
                    artifact = directory / f"{kind}_repeats.csv"
                    artifacts.append(artifact)
                    stream = stack.enter_context(artifact.open("x", encoding="utf-8", newline=""))
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    stream.flush()
                    writers[kind] = writer, stream
                for job in plan["schedules"][str(run_id)]:
                    reference, paths = references[(job["sample_id"], job["algorithm"])]
                    request = {**reference, **job, "attempt_id": plan["attempt_id"]}
                    if job["kind"] == "memory":
                        compress = job["phase"] == "compress"
                        request.update(input_size=reference["original_size" if compress else "compressed_size"],
                                       input_sha256=reference["original_sha256" if compress else "compressed_sha256"],
                                       expected_output_sha256=reference["compressed_sha256" if compress else "original_sha256"])
                    if reference["status"] != "ok":
                        evidence = dict(status="preparation_failed", error=reference["error"], return_code=None, stdout="", stderr="", payload=None,
                                        argv=None, python_executable=sys.executable, subprocess_options=_json(OPTIONS),
                                        started_at_utc=common._now(), finished_at_utc=common._now(), input_verified_before=False, input_verified_after=False)
                    else:
                        evidence = run_worker(request, paths)
                    rows = _raw_rows(request, evidence)
                    writer, stream = writers[job["kind"]]
                    for row in rows:
                        writer.writerow(row)
                        stream.flush()
                        (memory_rows if job["kind"] == "memory" else timing_rows).append(row)
                        counts[row["status"]] += 1
                    metadata.update(job_count=metadata["job_count"] + 1, memory_repeat_count=len(memory_rows),
                                    timing_repeat_count=len(timing_rows), repeat_count=len(memory_rows) + len(timing_rows),
                                    failed_repeat_count=sum(r["status"] != "ok" or r["bundle_status"] != "ok" for r in memory_rows + timing_rows),
                                    repeat_status_counts=dict(counts))
                    common._save_metadata(path, metadata)
            for reference, paths in references.values():
                if reference["status"] == "ok":
                    for phase, input_path in paths.items():
                        value = input_path.read_bytes()
                        if (len(value) != reference["original_size" if phase == "compress" else "compressed_size"]
                                or common._digest(value) != reference["original_sha256" if phase == "compress" else "compressed_sha256"]):
                            raise ValueError("Prepared phase input changed before run ended")
            measurements = directory / "measurements.csv"
            artifacts.append(measurements)
            _write_csv(measurements, MEASUREMENT_FIELDS, summarize(plan, run_id, memory_rows, timing_rows))
        metadata["run_status"] = "completed_with_failures" if metadata["failed_repeat_count"] else "completed"
    except BaseException as exc:
        original_error = exc
        metadata.update(run_status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "aborted", run_error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _finish(path, metadata, artifacts, immutable, original_error)
    return metadata


def run_next(study, events):
    study = Path(study).absolute()
    events = _check_events(events)
    lock = study / ".active_run.json"
    # A stale claim is retained after forced process termination; never steal it.
    with lock.open("x", encoding="utf-8") as stream:
        token = uuid.uuid4().hex
        stream.write(_json({"token": token, "pid": os.getpid()}))
        stream.flush()
    try:
        plan = _load_plan(study)
        metadata = _read_json(study / "metadata.json")
        if metadata["run_status"] not in ("initialized", "awaiting_next_run") or metadata["finalization_status"] != "completed" or metadata["provenance_unchanged"] is not True:
            raise ValueError("Attempt is not ready for a new scheduled run")
        for name, digest in metadata["artifact_sha256"].items():
            if common._digest((study / name).read_bytes()) != digest:
                raise ValueError("Stored attempt artifact changed")
        run_id = len(metadata["runs"]) + 1
        if run_id not in RUN_IDS:
            raise ValueError("No additional runs are permitted")
        _history(study, run_id - 1, plan)
        common._save_metadata(lock, dict(token=token, pid=os.getpid(), run_id=run_id, events=events))
        metadata.update(started_at_utc=common._now(), source_sha256=_sources(), environment=_environment(),
                        run_status="running", active_run_id=run_id)
        artifacts = [study / name for name in metadata["artifact_sha256"]]
        immutable = {name: (study / name, digest) for name, digest in metadata["immutable_sha256"].items()}
        path = study / "metadata.json"
        original_error = None
        try:
            common._save_metadata(path, metadata)
            metadata["git"] = _git_for_attempt(study)
            if plan["source_sha256"] != _sources() or not _same(plan["config"], _check_config()) or metadata["git"]["commit_hash"] != plan["implementation_commit"]:
                raise ValueError("Study source/config/commit changed before launch")
            outpath, errpath = (study / f"run_{run_id:02d}_{name}.txt" for name in ("stdout", "stderr"))
            artifacts.extend((outpath, errpath))
            record = dict(run_id=run_id, return_code=None, run_status="not_loaded", operator_events=events)
            metadata["runs"].append(record)
            with outpath.open("xb") as out, errpath.open("xb") as err:
                completed = subprocess.run([sys.executable, "-B", "-m", "src.memory_repeatability_validation", "_run",
                                            "--study-dir", str(study), "--run-id", str(run_id), "--token", token],
                                           cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, stdout=out, stderr=err)
            record["return_code"] = completed.returncode
            child_path = study / f"run_{run_id:02d}/metadata.json"
            artifacts.append(child_path)
            child = _read_json(child_path)
            record.update(run_status=child["run_status"], started_at_utc=child["started_at_utc"], finished_at_utc=child["finished_at_utc"])
            if child["run_status"] not in ("completed", "completed_with_failures") or completed.returncode != (0 if child["run_status"] == "completed" else 1):
                raise RuntimeError("Parent did not finish; preserve attempt and start a new one")
            _history(study, run_id, plan)
            parent_stdout = strict_json(outpath.read_text(encoding="utf-8"))
            _require_identity(parent_stdout, {k: child[k] for k in ("run_status", "repeat_count", "failed_repeat_count", "run_id")})
            if errpath.read_bytes():
                raise ValueError("Parent stderr is not empty")
            metadata["repeat_count"] += child["repeat_count"]
            metadata["memory_repeat_count"] += child["memory_repeat_count"]
            metadata["timing_repeat_count"] += child["timing_repeat_count"]
            metadata["job_count"] += child["job_count"]
            metadata["failed_repeat_count"] += child["failed_repeat_count"]
            metadata["validity_issues"].extend(f"run_{run_id:02d}:{issue}" for issue in child["validity_issues"])
            metadata["run_status"] = ("completed_with_failures" if metadata["failed_repeat_count"] else "completed") if run_id == RUN_IDS[-1] else "awaiting_next_run"
        except BaseException as exc:
            original_error = exc
            metadata.update(run_status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "aborted", run_error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            _finish(path, metadata, artifacts, immutable, original_error)
        return metadata
    finally:
        # This invocation created the claim; no study evidence is removed.
        original_exception = sys.exception()
        try:
            lock.unlink()
        except BaseException as exc:
            if "metadata" in locals() and "path" in locals():
                metadata.setdefault("finalization_errors", []).append(dict(stage="release_claim", error=f"{type(exc).__name__}: {exc}"))
                metadata["finalization_status"] = "failed"
                metadata["recording_checks_passed"] = False
                if metadata["run_status"] in ("awaiting_next_run", "completed", "completed_with_failures"):
                    metadata["run_status"] = "finalization_failed"
                try:
                    common._save_metadata(path, metadata)
                except BaseException as save_error:
                    exc.add_note(f"Saving claim release failure also failed: {type(save_error).__name__}: {save_error}")
            if original_exception is None:
                raise
            original_exception.add_note(f"Claim release also failed: {type(exc).__name__}: {exc}")
            for note in getattr(exc, "__notes__", ()):
                original_exception.add_note(note)


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create immutable plan; do not measure")
    init.add_argument("--attempt-id", required=True)
    init.add_argument("--reason", default="")
    init.add_argument("--results-root", type=Path)
    run = commands.add_parser("run", help="Launch only the next ordered run; no clock, date or gap limit")
    run.add_argument("--study-dir", type=Path, required=True)
    run.add_argument("--events-file", type=Path, required=True)
    child = commands.add_parser("_run", help=argparse.SUPPRESS)
    child.add_argument("--study-dir", type=Path, required=True)
    child.add_argument("--run-id", type=int, choices=RUN_IDS, required=True)
    child.add_argument("--token", required=True)
    args = parser.parse_args(arguments)
    if args.command == "init":
        result = initialize(attempt_id=args.attempt_id, reason=args.reason, results_root=args.results_root)
        print(_json({"study_dir": result["study_dir"], "run_status": result["run_status"]}))
    elif args.command == "run":
        result = run_next(args.study_dir, _read_json(args.events_file))
        print(_json({k: result[k] for k in ("run_status", "repeat_count", "failed_repeat_count")}))
    else:
        result = run_one(args.study_dir, args.run_id, args.token)
        print(_json({k: result[k] for k in ("run_status", "repeat_count", "failed_repeat_count", "run_id")}))
    return 0 if result["run_status"] in ("initialized", "awaiting_next_run", "completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
