"""Persist the fixed runtime-baseline study, without scores or scientific approval.

The coordinator starts three sequential fresh parent processes. Each parent first
prepares every reference, then runs the saved schedule with fresh workers.
Derived cross-run diagnostics and independent audit are separate follow-up work.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys
import tempfile

from src import compressors, memory_benchmark
from src import memory_runtime_worker as worker
from src import memory_validation as common

ROOT = common.ROOT
SIZES = (64, 256, 1024, 4096, 16384)
FAMILIES = ("zero_bytes", "periodic_16", "uniform_random")
RUN_IDS = (1, 2, 3)
REPEATS = 5
SEED = 20260922
TIMEOUT = 120
SOURCE_PATHS = (
    "src/memory_runtime_validation.py", "src/memory_runtime_worker.py",
    "src/memory_validation.py", "src/memory_benchmark.py", "src/compressors.py",
    "src/data_generator.py", "config/experiment_config.json", "requirements.txt",
    "research_log/memory_runtime_baseline_design.md",
)
SAMPLE_FIELDS = ("sample_id", "family", "size", "seed", "generation_parameters")
REFERENCE_FIELDS = (*SAMPLE_FIELDS, "algorithm", "input_sha256", "compressed_sha256",
                    "compressed_size", "reference_roundtrip_verified", "error")
RESULT_FIELDS = ("peak_process_working_set_bytes", "verified", "input_verified",
                 "status", "error", "return_code", "stdout", "stderr")
REPEAT_FIELDS = ("attempt_id", "run_id", "round_index", "schedule_index", "request_id",
                 *SAMPLE_FIELDS, "algorithm", "phase", "arm", "input_size", "input_sha256",
                 "expected_output_sha256", "reference_roundtrip_verified", *RESULT_FIELDS)
GROUP_FIELDS = ("sample_id", "algorithm", "phase", "arm")
SUMMARY_FIELDS = (*GROUP_FIELDS, "expected_count", "recorded_count", "failed_count", "complete",
                  "median_bytes", "min_bytes", "max_bytes", "population_std_bytes", "cv")


def _sources() -> dict:
    return {name: common._digest((ROOT / name).read_bytes()) for name in SOURCE_PATHS}


def _environment() -> dict:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                    *((name, ctypes.c_ulonglong) for name in (
                        "total_physical", "available_physical", "total_pagefile",
                        "available_pagefile", "total_virtual", "available_virtual",
                        "available_extended_virtual"))]
    state = MemoryStatus()
    state.length = ctypes.sizeof(state)
    api = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
    api.argtypes, api.restype = (ctypes.POINTER(MemoryStatus),), wintypes.BOOL
    if not api(ctypes.byref(state)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {**common._environment(), "available_physical_memory_bytes": state.available_physical,
            "pid": os.getpid(), "bytecode_disabled": sys.dont_write_bytecode}


def _check_config() -> dict:
    if sys.platform != "win32" or not sys.dont_write_bytecode:
        raise RuntimeError("Requires Windows and python -B")
    config = memory_benchmark._load_config()
    repeats, status = memory_benchmark._memory_config(config)
    if (config != compressors._CONFIG or repeats != REPEATS or status != "validation_only"
            or config["compression"] != worker.EXPECTED_COMPRESSION):
        raise ValueError("Configuration differs from the fixed baseline design")
    return config


def build_plan(attempt_id: str, reason: str = "") -> dict:
    if not isinstance(attempt_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", attempt_id):
        raise ValueError("attempt_id must be 1-64 ASCII letters, digits, underscores or hyphens")
    samples = []
    for size in SIZES:
        for family in FAMILIES:
            index = len(samples)
            samples.append(dict(sample_id=f"runtime_{index:06d}", family=family, size=size,
                                seed=SEED + index if family == "uniform_random" else None,
                                generation_parameters=json.dumps({"family": family, "size": size}, sort_keys=True)))
    schedules = {}
    for run_id in RUN_IDS:
        rng = random.Random(SEED + run_id - 1)
        schedule = []
        for round_index in range(1, REPEATS + 1):
            blocks = [(s["sample_id"], a, p) for s in samples
                      for a in worker.ALGORITHMS for p in worker.PHASES]
            rng.shuffle(blocks)
            for sample_id, algorithm, phase in blocks:
                arms = list(worker.ARMS)
                rng.shuffle(arms)
                for arm in arms:
                    index = len(schedule)
                    schedule.append(dict(run_id=run_id, round_index=round_index,
                                         schedule_index=index, sample_id=sample_id,
                                         algorithm=algorithm, phase=phase, arm=arm,
                                         request_id=f"{attempt_id}:{run_id}:{index}"))
        schedules[str(run_id)] = schedule
    return dict(schema_version=1, design_id=worker.DESIGN_ID, attempt_id=attempt_id,
                attempt_reason=reason, measurement_status="validation_only", score_inclusion=False,
                samples=samples, schedules=schedules, base_seed=SEED, repeats=REPEATS,
                timeout_seconds=TIMEOUT, run_ids=list(RUN_IDS))


def generate_input(spec: dict) -> bytes:
    size = spec["size"]
    if spec["family"] == "zero_bytes":
        return bytes(size)
    if spec["family"] == "periodic_16":
        return (bytes(range(16)) * ((size + 15) // 16))[:size]
    if spec["family"] == "uniform_random":
        return random.Random(spec["seed"]).randbytes(size)
    raise ValueError("Unknown input family")


def _write_csv(path: Path, fields: tuple, rows) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        stream.flush()
        for row in rows:
            writer.writerow(row)
            stream.flush()


def _prepare(samples: list[dict], directory: Path):
    references = {}
    for spec in samples:
        data, generation_error = None, ""
        try:
            data = generate_input(spec)
            if len(data) != spec["size"] or not data:
                raise ValueError("Generated input has wrong size")
        except Exception as exc:
            generation_error = f"{type(exc).__name__}: {exc}"
        for algorithm in worker.ALGORITHMS:
            record = {**spec, "algorithm": algorithm, "input_sha256": None,
                      "compressed_sha256": None, "compressed_size": None,
                      "reference_roundtrip_verified": None, "error": generation_error}
            paths = {}
            try:
                if generation_error:
                    raise ValueError(generation_error)
                record["input_sha256"] = common._digest(data)
                compressed = compressors.compress_data(data, algorithm)
                record.update(compressed_sha256=common._digest(compressed), compressed_size=len(compressed),
                              reference_roundtrip_verified=compressors.decompress_data(compressed, algorithm) == data)
                if record["reference_roundtrip_verified"] is not True:
                    raise ValueError("Reference round-trip verification failed")
                for phase, value in (("compress", data), ("decompress", compressed)):
                    path = directory / f"{spec['sample_id']}_{algorithm}_{phase}.bin"
                    path.write_bytes(value)
                    if path.read_bytes() != value:
                        raise OSError("Prepared phase input differs from reference")
                    paths[phase] = path
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            references[(spec["sample_id"], algorithm)] = (record, paths)
    return references


def _text(value) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")


def _empty_result(status: str, error: str) -> dict:
    return dict(peak_process_working_set_bytes=None, verified=None, input_verified=None,
                status=status, error=error, return_code=None, stdout="", stderr="")


def _validate_response(payload, request: dict, return_code: int) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Worker response must be an object")
    constants = dict(schema_version=1, design_id=worker.DESIGN_ID,
                     measurement_status="validation_only", score_inclusion=False,
                     measurement_method=common.METHOD,
                     **{key: request[key] for key in ("request_id", "arm", "phase", "algorithm")})
    for key, expected in constants.items():
        if key not in payload or type(payload[key]) is not type(expected) or payload[key] != expected:
            raise ValueError(f"Worker identity/contract mismatch: {key}")
    for key in ("peak_process_working_set_bytes", "observed_input_size", "verified", "input_verified", "status", "error"):
        if key not in payload:
            raise ValueError(f"Missing worker field: {key}")
    status = payload["status"]
    if not isinstance(status, str) or not isinstance(payload["error"], str):
        raise ValueError("Invalid worker status/error type")
    if status == "worker_failed":
        if (return_code != 1 or not payload["error"] or any(payload[k] is not None for k in
                ("peak_process_working_set_bytes", "observed_input_size", "verified", "input_verified"))):
            raise ValueError("Invalid worker failure response")
        return
    if status not in ("ok", "verification_failed") or return_code != (0 if status == "ok" else 2):
        raise ValueError("Worker status/exit code mismatch")
    peak = payload["peak_process_working_set_bytes"]
    if type(peak) is not int or peak <= 0:
        raise ValueError("Peak must be a positive integer")
    arm = request["arm"]
    size = payload["observed_input_size"]
    if arm == "import_only":
        if size is not None or status != "ok":
            raise ValueError("Invalid import control result")
    elif type(size) is not int or size != request["input_size"]:
        raise ValueError("Phase input size mismatch")
    for key, active_arm in (("verified", "codec"), ("input_verified", "input_only")):
        expected = (status == "ok") if arm == active_arm else None
        if payload[key] is not expected:
            raise ValueError(f"Invalid arm verification: {key}")
    if (status == "ok" and payload["error"]) or (status != "ok" and not payload["error"]):
        raise ValueError("Worker error/status mismatch")


def run_worker(request: dict, input_path: Path) -> dict:
    result = _empty_result("worker_failed", "")
    command = [sys.executable, "-B", "-m", "src.memory_runtime_worker", "--input", str(input_path)]
    for key in ("request_id", "arm", "phase", "algorithm", "input_sha256", "expected_output_sha256"):
        command.extend(("--" + key.replace("_", "-"), str(request[key])))
    try:
        completed = subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                   capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        result.update(status="timeout", error=str(exc), stdout=_text(exc.stdout), stderr=_text(exc.stderr))
        return result
    except OSError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    result.update(return_code=completed.returncode, stdout=_text(completed.stdout), stderr=_text(completed.stderr))
    try:
        payload = json.loads(result["stdout"])
        _validate_response(payload, request, completed.returncode)
        result.update({key: payload[key] for key in ("peak_process_working_set_bytes", "verified", "input_verified", "status", "error")})
    except (ValueError, TypeError) as exc:
        result.update(status="invalid_result" if completed.returncode in (0, 1, 2) else "worker_failed",
                      error=f"{type(exc).__name__}: {exc}")
    return result


def summarize(schedule: list[dict], rows: list[dict]) -> list[dict]:
    planned = {r["request_id"]: r for r in schedule}
    seen = set()
    grouped = defaultdict(list)
    for row in rows:
        identity = row["request_id"]
        if identity in seen or identity not in planned:
            raise ValueError("Duplicate or unplanned repeat")
        if any(row[k] != planned[identity][k] for k in (*GROUP_FIELDS, "round_index", "schedule_index", "run_id")):
            raise ValueError("Repeat differs from schedule")
        seen.add(identity)
        grouped[tuple(row[k] for k in GROUP_FIELDS)].append(row)
    summaries = []
    for key in dict.fromkeys(tuple(r[k] for k in GROUP_FIELDS) for r in schedule):
        group = grouped[key]
        valid = [r for r in group if r["status"] == "ok" and r["reference_roundtrip_verified"] is True
                 and r["verified"] is (True if r["arm"] == "codec" else None)
                 and r["input_verified"] is (True if r["arm"] == "input_only" else None)]
        complete = len(valid) == len(group) == REPEATS
        summary = dict.fromkeys(SUMMARY_FIELDS)
        summary.update(zip(GROUP_FIELDS, key))
        summary.update(expected_count=REPEATS, recorded_count=len(group),
                       failed_count=len(group) - len(valid), complete=complete)
        if complete:
            values = [r["peak_process_working_set_bytes"] for r in valid]
            if any(type(v) is not int or v <= 0 for v in values):
                raise ValueError("Successful repeats require positive integer peaks")
            summary.update(median_bytes=statistics.median(values), min_bytes=min(values), max_bytes=max(values),
                           population_std_bytes=statistics.pstdev(values),
                           cv=statistics.pstdev(values) / statistics.mean(values))
        summaries.append(summary)
    return summaries


def _metadata(plan: dict) -> dict:
    return dict(schema_version=1, design_id=worker.DESIGN_ID, attempt_id=plan["attempt_id"],
                measurement_status="validation_only", score_inclusion=False, run_status="running",
                started_at_utc=common._now(), source_sha256=_sources(), git=common._git_information(),
                environment=_environment(), config=_check_config(), measurement_method=common.METHOD,
                subprocess_options=["-B", "PYTHONDONTWRITEBYTECODE=1"],
                repeat_count=0, failed_repeat_count=0)


def _finalize(path: Path, metadata: dict, artifacts: list[Path]) -> None:
    original_status = metadata["run_status"]
    finished = original_status in ("completed", "completed_with_failures")
    metadata.update(finished_at_utc=common._now(), run_status_before_finalization=original_status,
                    finalization_status="in_progress", finalization_errors=[], artifact_sha256={},
                    source_sha256_at_end=None, provenance_unchanged=None)
    if finished:
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
    if metadata["source_sha256_at_end"] is not None:
        metadata["provenance_unchanged"] = metadata["source_sha256"] == metadata["source_sha256_at_end"]
    if "plan_sha256" in metadata:
        metadata["plan_sha256_at_end"] = None
        attempt("plan_sha256_at_end", lambda: metadata.update(
            plan_sha256_at_end=common._digest((path.parent.parent / "plan.json").read_bytes())))
        metadata["provenance_unchanged"] = (metadata["provenance_unchanged"] is True
                                            and metadata["plan_sha256"] == metadata["plan_sha256_at_end"])
    for artifact in artifacts:
        name = artifact.relative_to(path.parent).as_posix()
        attempt(f"artifact_sha256:{name}", lambda a=artifact, n=name:
                metadata["artifact_sha256"].update({n: common._digest(a.read_bytes())}))
    metadata["finalization_status"] = "failed" if failures else "completed"
    metadata["run_status"] = ("finalization_failed" if finished and failures else
                              "invalid_provenance_changed" if finished and not metadata["provenance_unchanged"] else original_status)
    attempt("final_metadata_save", lambda: common._save_metadata(path, metadata))
    if failures:
        failures[0].add_note("Finalization errors: " + json.dumps(metadata["finalization_errors"]))
        raise failures[0]


def _finish_preserving_error(path, metadata, artifacts, original_error):
    try:
        _finalize(path, metadata, artifacts)
    except BaseException as exc:
        if original_error is None:
            raise
        original_error.add_note(f"Finalization also failed: {type(exc).__name__}: {exc}")
        for note in getattr(exc, "__notes__", ()):
            original_error.add_note(note)


def run_one(study_dir: Path, run_id: int) -> dict:
    """Internal child-parent entry point; no reduced matrix is exposed by the CLI."""
    _check_config()
    study_dir = study_dir.absolute()
    plan = json.loads((study_dir / "plan.json").read_text(encoding="utf-8"))
    expected = build_plan(plan["attempt_id"], plan["attempt_reason"])
    if any(plan.get(k) != v for k, v in expected.items()) or run_id not in RUN_IDS:
        raise ValueError("Saved plan differs from fixed design")
    if plan["source_sha256"] != _sources() or plan["config"] != _check_config():
        raise ValueError("Study provenance changed before run")
    directory = study_dir / f"run_{run_id:02d}"
    directory.mkdir(exist_ok=False)
    metadata = {**_metadata(plan), "run_id": run_id,
                "plan_sha256": common._digest((study_dir / "plan.json").read_bytes())}
    path = directory / "metadata.json"
    artifacts = [directory / name for name in ("references.csv", "repeats.csv", "summary.csv")]
    rows, counts, original_error = [], Counter(), None
    schedule = plan["schedules"][str(run_id)]
    metadata["planned_repeat_count"] = len(schedule)
    try:
        common._save_metadata(path, metadata)
        with tempfile.TemporaryDirectory(prefix="runtime_baseline_inputs_") as temporary:
            references = _prepare(plan["samples"], Path(temporary))
            _write_csv(artifacts[0], REFERENCE_FIELDS, (record for record, _ in references.values()))
            with artifacts[1].open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=REPEAT_FIELDS)
                writer.writeheader()
                stream.flush()
                for item in schedule:
                    record, paths = references[(item["sample_id"], item["algorithm"])]
                    compress = item["phase"] == "compress"
                    row = {**{k: record[k] for k in SAMPLE_FIELDS}, **item, "attempt_id": plan["attempt_id"],
                           "input_size": record["size"] if compress else record["compressed_size"],
                           "input_sha256": record["input_sha256"] if compress else record["compressed_sha256"],
                           "expected_output_sha256": record["compressed_sha256"] if compress else record["input_sha256"],
                           "reference_roundtrip_verified": record["reference_roundtrip_verified"]}
                    result = (_empty_result("preparation_failed", record["error"]) if record["error"]
                              else run_worker(row, paths[item["phase"]]))
                    row.update(result)
                    writer.writerow(row)
                    stream.flush()
                    rows.append(row)
                    counts[row["status"]] += 1
                    metadata.update(repeat_count=len(rows), failed_repeat_count=len(rows) - counts["ok"],
                                    repeat_status_counts=dict(counts))
            _write_csv(artifacts[2], SUMMARY_FIELDS, summarize(schedule, rows))
        metadata["run_status"] = "completed_with_failures" if metadata["failed_repeat_count"] else "completed"
    except BaseException as exc:
        original_error = exc
        metadata.update(run_status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "aborted",
                        run_error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _finish_preserving_error(path, metadata, artifacts, original_error)
    return metadata


def run_study(output_dir: Path, *, attempt_id: str, reason: str = "") -> dict:
    config = _check_config()
    plan = {**build_plan(attempt_id, reason), "config": config, "source_sha256": _sources()}
    destination = output_dir.absolute()
    destination.mkdir(parents=True, exist_ok=False)
    path = destination / "metadata.json"
    metadata = {**_metadata(plan), "runs": [], "analysis_status": "pending_independent_audit_and_diagnostics"}
    original_error = None
    artifacts = [destination / "plan.json", destination / "samples.csv"]
    try:
        common._save_metadata(path, metadata)
        common._save_metadata(artifacts[0], plan)
        _write_csv(artifacts[1], SAMPLE_FIELDS, plan["samples"])
        for run_id in RUN_IDS:
            stdout_path = destination / f"run_{run_id:02d}_stdout.txt"
            stderr_path = destination / f"run_{run_id:02d}_stderr.txt"
            artifacts.extend((stdout_path, stderr_path))
            with stdout_path.open("xb") as out, stderr_path.open("xb") as err:
                result = subprocess.run([sys.executable, "-B", "-m", "src.memory_runtime_validation",
                                         "--study-dir", str(destination), "--run-id", str(run_id)],
                                        cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                        stdout=out, stderr=err)
            run_record = dict(run_id=run_id, return_code=result.returncode, run_status="metadata_not_loaded")
            metadata["runs"].append(run_record)
            common._save_metadata(path, metadata)
            run_path = destination / f"run_{run_id:02d}" / "metadata.json"
            artifacts.append(run_path)
            child = json.loads(run_path.read_text(encoding="utf-8"))
            run_record["run_status"] = child["run_status"]
            metadata["repeat_count"] += child["repeat_count"]
            metadata["failed_repeat_count"] += child["failed_repeat_count"]
            if child["run_status"] not in ("completed", "completed_with_failures") or result.returncode != (0 if child["run_status"] == "completed" else 1):
                raise RuntimeError(f"Run {run_id} did not complete; preserve this attempt and start a new one")
            common._save_metadata(path, metadata)
        metadata["run_status"] = "completed_with_failures" if metadata["failed_repeat_count"] else "completed"
    except BaseException as exc:
        original_error = exc
        metadata.update(run_status="interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "aborted",
                        run_error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _finish_preserving_error(path, metadata, artifacts, original_error)
    return metadata


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--attempt-id")
    parser.add_argument("--reason", default="")
    parser.add_argument("--study-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--run-id", type=int, choices=RUN_IDS, help=argparse.SUPPRESS)
    args = parser.parse_args(arguments)
    if args.study_dir is not None:
        if args.run_id is None or args.output_dir is not None or args.attempt_id is not None or args.reason:
            parser.error("Internal child requires only --study-dir and --run-id")
        result = run_one(args.study_dir, args.run_id)
    else:
        if args.output_dir is None or args.attempt_id is None or args.run_id is not None:
            parser.error("Specify --output-dir and --attempt-id")
        result = run_study(args.output_dir, attempt_id=args.attempt_id, reason=args.reason)
    print(json.dumps({k: result[k] for k in ("run_status", "repeat_count", "failed_repeat_count")}))
    return 0 if result["run_status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
