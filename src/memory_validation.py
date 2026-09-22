"""Persist a validation-only memory matrix; never generate selection scores."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
import csv
import ctypes
from ctypes import wintypes
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib import metadata as package_metadata
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile

from src import compressors, memory_benchmark
from src.data_generator import GENERATOR_NAMES, SAMPLE_SIZES, generate_sample


ROOT = Path(__file__).resolve().parent.parent
ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
PHASES = ("compress", "decompress")
METHOD = "windows_get_process_memory_info_peak_working_set"
SOURCE_PATHS = (
    "src/memory_validation.py", "src/memory_benchmark.py", "src/compressors.py",
    "src/data_generator.py", "config/experiment_config.json", "requirements.txt",
)
SAMPLE_FIELDS = (
    "sample_id", "generator", "size", "seed", "generation_parameters",
    "input_sha256", "status", "error",
)
REPEAT_FIELDS = (
    "sample_id", "generator", "size", "seed", "algorithm", "phase", "repeat_index",
    "measurement_method", "expected_sha256", "reference_roundtrip_verified",
    "peak_process_working_set_bytes", "verified", "status", "error",
    "return_code", "stdout", "stderr",
)
SUMMARY_FIELDS = (
    "sample_id", "generator", "size", "seed", "algorithm", "verified",
    "failed_repeat_count", "compression_peak_memory_bytes",
    "decompression_peak_memory_bytes", "peak_memory_bytes",
    *(f"{phase}_{stat}" for phase in PHASES
      for stat in ("min_bytes", "max_bytes", "population_std_bytes", "cv")),
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_hashes() -> dict[str, str]:
    return {name: _digest((ROOT / name).read_bytes()) for name in SOURCE_PATHS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_metadata(path: Path, metadata: dict) -> None:
    """Replace only this run's metadata, after a complete same-directory write."""
    serialized = json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix=f".{path.name}.",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException as exc:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                exc.add_note(f"Metadata temporary cleanup failed: {cleanup_error}")
        raise


def _finalize_metadata(path: Path, metadata: dict, counts: Counter) -> None:
    """Persist terminal evidence before hashes; never publish premature success.

    Each finalization step gets one attempt. Secondary errors are recorded and
    re-raised after the final save attempt, including KeyboardInterrupt/SystemExit.
    Process termination and persistent storage failure cannot guarantee a save.
    """
    run_status = metadata["run_status"]
    finished_run = run_status in ("completed", "completed_with_failures")
    metadata.update(finished_at_utc=_now(), repeat_status_counts=dict(counts),
                    run_status_before_finalization=run_status,
                    finalization_status="in_progress", finalization_errors=[],
                    source_sha256_at_end=None, provenance_unchanged=None,
                    artifact_sha256={})
    if finished_run:
        metadata["run_status"] = "finalizing"
    failures = []

    def record(stage: str, exc: BaseException) -> None:
        failures.append(exc)
        metadata["finalization_errors"].append(
            {"stage": stage, "error": f"{type(exc).__name__}: {exc}"})
        metadata["finalization_status"] = "failed"
        if finished_run:
            metadata["run_status"] = "finalization_failed"

    try:
        _save_metadata(path, metadata)
    except BaseException as exc:
        record("terminal_checkpoint", exc)
    try:
        metadata["source_sha256_at_end"] = _source_hashes()
        metadata["provenance_unchanged"] = metadata["source_sha256_at_end"] == metadata["source_sha256"]
    except BaseException as exc:
        record("source_sha256_at_end", exc)
    for name in ("samples.csv", "memory_repeats.csv", "memory_summary.csv"):
        try:
            metadata["artifact_sha256"][name] = _digest((path.parent / name).read_bytes())
        except BaseException as exc:
            record(f"artifact_sha256:{name}", exc)
    if not failures:
        metadata["finalization_status"] = "completed"
        metadata["run_status"] = (
            "invalid_provenance_changed" if finished_run and not metadata["provenance_unchanged"]
            else run_status)
    try:
        _save_metadata(path, metadata)
    except BaseException as exc:
        record("final_metadata_save", exc)
    if failures:
        failures[0].add_note("Finalization errors: " + json.dumps(metadata["finalization_errors"]))
        raise failures[0]


def _git_information() -> dict:
    prefix = ["git", "-c", f"safe.directory={ROOT.as_posix()}",
              "--no-optional-locks", "-C", str(ROOT)]
    try:
        commit = subprocess.run([*prefix, "rev-parse", "HEAD"], check=True,
                                capture_output=True, text=True)
        status = subprocess.run([*prefix, "status", "--porcelain"], check=True,
                                capture_output=True, text=True)
        if commit.stderr or status.stderr:
            raise RuntimeError(commit.stderr + status.stderr)
        return {"commit_hash": commit.stdout.strip(), "worktree_dirty": bool(status.stdout),
                "status_porcelain": status.stdout}
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        return {"commit_hash": None, "worktree_dirty": None, "error": str(exc)}


def _environment() -> dict:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                    *((name, ctypes.c_ulonglong) for name in (
                        "total_physical", "available_physical", "total_pagefile",
                        "available_pagefile", "total_virtual", "available_virtual",
                        "available_extended_virtual"))]

    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalMemoryStatusEx.argtypes = (ctypes.POINTER(MemoryStatus),)
    kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError(ctypes.get_last_error())
    packages = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            name = line.split("==", 1)[0].strip()
            packages[name] = package_metadata.version(name)
    return {
        "python_version": platform.python_version(), "python_executable": sys.executable,
        "operating_system": platform.platform(), "architecture": platform.machine(),
        "python_pointer_bits": ctypes.sizeof(ctypes.c_void_p) * 8,
        "processor": platform.processor(), "logical_cpu_count": os.cpu_count(),
        "total_physical_memory_bytes": memory.total_physical, "package_versions": packages,
    }


def build_validation_plan(base_seed: int) -> list[dict]:
    """One sample per existing generator and configured size, in fixed order."""
    if isinstance(base_seed, bool) or not isinstance(base_seed, int):
        raise TypeError("Base seed must be an integer")
    return [
        {"sample_id": f"memory_{index:06d}", "generator": generator,
         "size": size, "seed": base_seed + index}
        for index, (size, generator) in enumerate(
            (size, generator) for size in SAMPLE_SIZES for generator in GENERATOR_NAMES
        )
    ]


def summarize_pair(rows: list[dict], repeats: int) -> dict:
    """Only fully verified pairs receive aggregates; failed raw values stay in CSV."""
    summary = {key: rows[0][key] for key in ("sample_id", "generator", "size", "seed", "algorithm")}
    expected_keys = {(phase, repeat) for phase in PHASES for repeat in range(1, repeats + 1)}
    actual_keys = {(row["phase"], row["repeat_index"]) for row in rows}
    if len(rows) != len(expected_keys) or actual_keys != expected_keys:
        raise ValueError("Incomplete or duplicate phase/repeat keys")
    failed = sum(row["status"] != "ok" or row["verified"] is not True
                 or row["reference_roundtrip_verified"] is not True for row in rows)
    summary.update(verified=failed == 0, failed_repeat_count=failed)
    if failed:
        return summary
    medians = {}
    for phase in PHASES:
        values = [row["peak_process_working_set_bytes"] for row in rows if row["phase"] == phase]
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("Verified repeats must have positive integer memory values")
        medians[phase] = statistics.median(values)
        summary.update({
            f"{phase}_min_bytes": min(values), f"{phase}_max_bytes": max(values),
            f"{phase}_population_std_bytes": statistics.pstdev(values),
            f"{phase}_cv": statistics.pstdev(values) / statistics.mean(values),
        })
    summary.update(compression_peak_memory_bytes=medians["compress"],
                   decompression_peak_memory_bytes=medians["decompress"],
                   peak_memory_bytes=max(medians.values()))
    return summary


def _measure_pair(spec: dict, data: bytes | None, algorithm: str, preparation_error: str):
    """Yield every planned attempt, including explicit unrun preparation failures."""
    repeats = memory_benchmark._MEMORY_REPEATS
    with tempfile.TemporaryDirectory(prefix="memory_validation_") as directory:
        original_path = Path(directory) / "original.bin"
        compressed_path = Path(directory) / "compressed.bin"
        expected = {phase: "" for phase in PHASES}
        reference_verified = None
        try:
            if preparation_error:
                raise RuntimeError(preparation_error)
            compressed = compressors.compress_data(data, algorithm)
            reference_verified = compressors.decompress_data(compressed, algorithm) == data
            if not reference_verified:
                raise RuntimeError("Reference round-trip verification failed")
            original_path.write_bytes(data)
            compressed_path.write_bytes(compressed)
            expected = {"compress": _digest(compressed), "decompress": _digest(data)}
        except Exception as exc:
            preparation_error = f"{type(exc).__name__}: {exc}"
        for phase in PHASES:
            for repeat_index in range(1, repeats + 1):
                if preparation_error:
                    result = memory_benchmark.MemoryWorkerResult(
                        None, None, "preparation_failed", preparation_error, None, "", "",
                    )
                else:
                    result = memory_benchmark.run_memory_worker(
                        phase, algorithm, original_path if phase == "compress" else compressed_path,
                        expected[phase],
                    )
                yield {**spec, "algorithm": algorithm, "phase": phase, "repeat_index": repeat_index,
                       "measurement_method": METHOD, "expected_sha256": expected[phase],
                       "reference_roundtrip_verified": reference_verified, **asdict(result)}


def run_validation(output_dir: str | Path, *, base_seed: int = 20260915) -> dict:
    """Run the fixed matrix into a new directory, flushing each raw row immediately."""
    if sys.platform != "win32":
        raise RuntimeError("Memory validation requires the Windows backend")
    plan = build_validation_plan(base_seed)
    config = json.loads((ROOT / "config/experiment_config.json").read_text(encoding="utf-8"))
    repeats, status = memory_benchmark._memory_config(config)
    if repeats != 5 or repeats != memory_benchmark._MEMORY_REPEATS:
        raise ValueError("Validation requires five repeats in both config and loaded module")
    if config != compressors._CONFIG or tuple(config["sample_sizes"]) != SAMPLE_SIZES:
        raise ValueError("Configuration changed since module import; start a fresh process")
    metadata = {
        "schema_version": 1, "measurement_status": status, "run_status": "running",
        "started_at_utc": _now(), "official_score_protocol": "research_protocol_v2.md",
        "score_inclusion": False, "base_seed": base_seed, "sample_plan": plan,
        "algorithm_order": list(ALGORITHMS), "phase_order": list(PHASES),
        "repeats_per_phase": repeats, "measurement_method": METHOD,
        "execution_order": "sample, algorithm, phase, repeat; sequential fresh worker processes",
        "config": config, "source_sha256": _source_hashes(),
        "git": _git_information(), "environment": _environment(),
        "planned_sample_count": len(plan), "planned_pair_count": len(plan) * len(ALGORITHMS),
        "planned_repeat_count": len(plan) * len(ALGORITHMS) * len(PHASES) * repeats,
        "sample_count": 0, "pair_count": 0, "repeat_count": 0,
        "failed_sample_count": 0, "failed_pair_count": 0, "failed_repeat_count": 0,
        "limitations": [
            "Whole-process lifetime peak includes runtime, libraries, input and output.",
            "Fixed execution order and one seed per generator/size; no population inference.",
            "Tiny-file runtime baseline and cross-run stability remain unvalidated.",
            "No timing, selection score, labels, model training or official four-metric transition.",
        ],
    }
    destination = Path(output_dir).absolute()
    destination.mkdir(parents=True, exist_ok=False)
    metadata_path = destination / "memory_validation_metadata.json"

    def save_metadata() -> None:
        _save_metadata(metadata_path, metadata)

    save_metadata()
    counts = Counter()
    run_error = None
    try:
        with ExitStack() as stack:
            writers = {}
            for filename, fields in (("samples.csv", SAMPLE_FIELDS), ("memory_repeats.csv", REPEAT_FIELDS),
                                     ("memory_summary.csv", SUMMARY_FIELDS)):
                stream = stack.enter_context((destination / filename).open("x", encoding="utf-8", newline=""))
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                stream.flush()
                writers[filename] = (writer, stream)

            def write(filename: str, row: dict) -> None:
                writer, stream = writers[filename]
                writer.writerow(row)
                stream.flush()

            for spec in plan:
                data, preparation_error = None, ""
                sample_row = {**spec, "status": "ok", "error": ""}
                try:
                    sample = generate_sample(spec["generator"], spec["size"], spec["seed"])
                    data = sample.data
                    sample_row.update(generation_parameters=json.dumps(sample.parameters, sort_keys=True),
                                      input_sha256=_digest(data))
                except Exception as exc:
                    preparation_error = f"{type(exc).__name__}: {exc}"
                    sample_row.update(status="generation_failed", error=preparation_error)
                    metadata["failed_sample_count"] += 1
                write("samples.csv", sample_row)
                metadata["sample_count"] += 1
                for algorithm in ALGORITHMS:
                    rows = []
                    for row in _measure_pair(spec, data, algorithm, preparation_error):
                        write("memory_repeats.csv", row)
                        rows.append(row)
                        counts[row["status"]] += 1
                        metadata["repeat_count"] += 1
                        metadata["failed_repeat_count"] += row["status"] != "ok"
                    summary = summarize_pair(rows, repeats)
                    write("memory_summary.csv", summary)
                    metadata["pair_count"] += 1
                    metadata["failed_pair_count"] += not summary["verified"]
                    save_metadata()
                print(f"{spec['sample_id']} {spec['generator']} {spec['size']} bytes: saved", flush=True)
        metadata["run_status"] = "completed_with_failures" if metadata["failed_pair_count"] else "completed"
    except BaseException as exc:
        run_error = exc
        metadata["run_status"] = "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "aborted"
        metadata["run_error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        try:
            _finalize_metadata(metadata_path, metadata, counts)
        except BaseException as exc:
            if run_error is None:
                raise
            run_error.add_note(f"Finalization also failed: {type(exc).__name__}: {exc}")
            for note in getattr(exc, "__notes__", ()):
                run_error.add_note(note)
    return metadata


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; never overwritten")
    parser.add_argument("--base-seed", type=int, default=20260915)
    args = parser.parse_args(arguments)
    result = run_validation(args.output_dir, base_seed=args.base_seed)
    print(json.dumps({key: result[key] for key in (
        "run_status", "sample_count", "pair_count", "repeat_count", "failed_repeat_count",
    )}, indent=2))
    return 0 if result["run_status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
