"""Compare four codecs on one non-empty file using protocol-v2 timing and scores.

Reports only: no compressed package, model prediction, training, or memory
measurement. Raw repeat ns and measured medians are separate from mode labels.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from src import compressors, scoring

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config/experiment_config.json"
SOURCES = ("compare_compress.py", "src/compressors.py", "src/scoring.py", "config/experiment_config.json",
           "research_protocol_v2.md", "requirements.txt")
REPEAT_FIELDS = ("sample_id", "algorithm", "phase", "repeat_index", "elapsed_ns", "status",
                 "consistent_with_reference", "verified", "output_size", "output_sha256", "error")
MEASUREMENT_FIELDS = ("sample_id", "algorithm", "original_size", "compressed_size", "compression_ratio",
                      "compression_time_ms", "decompression_time_ms", "verified", "status", "error")
LABEL_FIELDS = ("sample_id", "mode", "best_algorithm", "best_score", *("score_" + a for a in scoring.ALGORITHMS))


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _configuration(data):
    config = json.loads(data)
    expected_timing = dict(repeats=5, timer="time.perf_counter_ns", aggregate="median")
    if config["timing"] != expected_timing:
        raise ValueError("Compare Mode requires protocol-v2 timing: five repeats, perf_counter_ns, median")
    loaded_timing = dict(repeats=compressors._TIMING_REPEATS, timer=compressors._TIMING_TIMER,
                         aggregate=compressors._TIMING_AGGREGATE)
    if (config["compression"] != compressors._CONFIG["compression"] or config["timing"] != loaded_timing
            or config["selection_modes"] != scoring.MODE_WEIGHTS):
        raise ValueError("Runtime config changed since import; restart Compare Mode")
    if tuple(compressors._SUPPORTED_ALGORITHMS) != scoring.ALGORITHMS:
        raise ValueError("Compression/scoring algorithm order differs")
    return config


def _measure(data, sample_id, algorithm):
    """Same five-compress/five-reference-decompress contract as the benchmark.

    Keep each attempted duration, failed verification, and unexecuted slot.
    A failed repeat stops that algorithm; other algorithms are still compared.
    """
    rows, reference, blocked = [], None, False
    for phase in ("compress", "decompress"):
        for index in range(1, 6):
            row = dict.fromkeys(REPEAT_FIELDS)
            row.update(sample_id=sample_id, algorithm=algorithm, phase=phase, repeat_index=index,
                       status="not_run", error="Previous repeat failed; no measurement retry" if blocked else "")
            if not blocked:
                try:
                    started = time.perf_counter_ns()
                    try:
                        value = (compressors.compress_data(data, algorithm) if phase == "compress"
                                 else compressors.decompress_data(reference, algorithm))
                    finally:
                        row["elapsed_ns"] = time.perf_counter_ns() - started
                    if type(row["elapsed_ns"]) is not int or row["elapsed_ns"] <= 0:
                        raise ValueError("Measured elapsed_ns must be positive; no epsilon substitution")
                    if not isinstance(value, bytes) or not value:
                        raise ValueError("Codec returned empty or non-bytes output")
                    row.update(output_size=len(value), output_sha256=_digest(value))
                    if phase == "compress":
                        if reference is None:
                            reference = value
                        row["consistent_with_reference"] = value == reference
                        if value != reference:
                            raise ValueError("Compressed bytes differ across repeats")
                    else:
                        row["verified"] = value == data
                        if value != data:
                            raise ValueError("Lossless restoration failed (verified=False)")
                    row["status"] = "ok"
                except Exception as exc:
                    row.update(status="error", error=f"{type(exc).__name__}: {exc}")
                    blocked = True
            rows.append(row)
    good = all(row["status"] == "ok" for row in rows)
    measurement = dict.fromkeys(MEASUREMENT_FIELDS)
    measurement.update(sample_id=sample_id, algorithm=algorithm, original_size=len(data), verified=good,
                       status="ok" if good else "failed", error=next((r["error"] for r in rows if r["status"] == "error"), ""))
    if good:
        measurement.update(compressed_size=len(reference), compression_ratio=len(reference) / len(data),
            compression_time_ms=statistics.median(r["elapsed_ns"] for r in rows if r["phase"] == "compress") / 1_000_000,
            decompression_time_ms=statistics.median(r["elapsed_ns"] for r in rows if r["phase"] == "decompress") / 1_000_000)
    return measurement, rows


def _recheck(source, original, snapshots):
    if source.read_bytes() != original:
        raise ValueError("Input changed during comparison")
    for name, data in snapshots.items():
        if (ROOT / name).read_bytes() != data:
            raise ValueError(f"Source/config changed during comparison: {name}")


def _csv_bytes(fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != data:
        raise OSError(f"Saved report bytes mismatch: {path.name}")


def _publish(destination, report, measurements, repeats, labels, config_bytes, fence):
    # Claim a new directory exclusively; preserve partial evidence if saving fails.
    destination.mkdir(exist_ok=False)
    try:
        payloads = {"timing_repeats.csv": _csv_bytes(REPEAT_FIELDS, repeats),
                    "compression_results.csv": _csv_bytes(MEASUREMENT_FIELDS, measurements),
                    "selection_labels.csv": _csv_bytes(LABEL_FIELDS, labels),
                    "config_snapshot.json": config_bytes, ".gitattributes": b"* -text\n"}
        for name, data in payloads.items():
            _write(destination / name, data)
        if fence:
            fence()
        report["artifact_sha256"] = {name: _digest(data) for name, data in payloads.items()}
        _write(destination / "comparison.json", (json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"))
        if fence:
            fence()
    except BaseException as exc:
        try:
            _write(destination / "publication_failed.json", (json.dumps(dict(publication_status="failed",
                analysis_status="inconclusive", error=f"{type(exc).__name__}: {exc}"), allow_nan=False) + "\n").encode("utf-8"))
        except BaseException as marker_error:
            exc.add_note(f"Recording publication failure also failed: {marker_error}")
        raise


def compare_file(input_path: str | Path, output_dir: str | Path) -> dict:
    """Save complete or explicitly failed single-file comparison evidence."""
    source, destination = Path(input_path).resolve(), Path(output_dir).absolute()
    if destination.exists() or destination.is_symlink() or destination.is_junction():
        raise FileExistsError(f"Output directory already exists: {destination}")
    if not source.is_file():
        raise ValueError(f"Expected an input file: {source}")
    original = source.read_bytes()
    if not original:
        raise ValueError("Cannot compare empty input")
    snapshots = {name: (ROOT / name).read_bytes() for name in SOURCES}
    config = _configuration(snapshots["config/experiment_config.json"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    sample_id = "file_" + _digest(original)[:16]
    measurements, repeats, labels, errors = [], [], [], []
    for algorithm in scoring.ALGORITHMS:
        measurement, raw = _measure(original, sample_id, algorithm)
        measurements.append(measurement)
        repeats.extend(raw)
        if not measurement["verified"]:
            errors.append(f"{algorithm}: {measurement['error']}")
    invalidated = False
    try:
        _recheck(source, original, snapshots)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        invalidated = True
    if not errors:
        try:
            selections = scoring.score_sample(measurements)
            labels = [dict(sample_id=sample_id, mode=mode, best_algorithm=s.best_algorithm, best_score=s.best_score,
                           **{"score_" + a: s.scores[a] for a in scoring.ALGORITHMS}) for mode, s in selections.items()]
            # Require finite serialized scores before publishing any normal label.
            json.dumps(labels, allow_nan=False)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            labels = []
            errors.append(f"Scoring failed: {exc}")
    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    report = dict(compare_mode_version=1, status="invalidated" if invalidated else "completed_with_failures" if errors else "completed",
        scope="Single-file measured comparison; not Smart prediction, model evaluation, or a new Pilot",
        input_path=str(source), original_filename=source.name, input_sha256=_digest(original), original_size=len(original),
        sample_id=sample_id, seed=None, output_dir=str(destination), started_at_utc=started,
        finished_measurement_at_utc=datetime.now(timezone.utc).isoformat(),
        algorithm_order=list(scoring.ALGORITHMS), phase_order=["compress", "decompress"],
        compression_settings=config["compression"], timing=config["timing"], selection_modes=config["selection_modes"],
        tie_order=list(scoring.ALGORITHMS), score_epsilon=None, memory_measured=False, memory_score_inclusion=False,
        git_commit=commit, source_sha256={name: _digest(data) for name, data in snapshots.items()},
        environment=dict(python_version=platform.python_version(), python_executable=sys.executable,
                         operating_system=platform.platform(), zstandard_version=version("zstandard")),
        row_counts=dict(algorithms=len(measurements), planned_repeats=len(repeats),
                        attempted_repeats=sum(r["status"] != "not_run" for r in repeats), labels=len(labels)),
        measurements=measurements, selections=labels, errors=errors,
        publication_contract="Use scores only for status=completed, successful return, and no publication_failed.json.",
        limitations=["Fixed algorithm order and one execution environment; no generalization or model accuracy claim.",
            "All data are in memory; file I/O and verification/hash work are outside timed codec calls.",
            "Five repeats per phase; medians in ms are derived from raw ns; no warmup, epsilon or measurement retries.",
            "Failed repeats stop that algorithm and retain unexecuted slots; other algorithms continue; no partial-set scoring.",
            "No model or features are loaded; no memory measurement, training or compressed packages are produced.",
            "Source byte hashes describe this execution; Git HEAD may predate working-tree implementation."])
    fence = None if invalidated else lambda: _recheck(source, original, snapshots)
    _publish(destination, report, measurements, repeats, labels, snapshots["config/experiment_config.json"], fence)
    return report


def main(arguments: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, prog=prog)
    parser.add_argument("input", type=Path, help="Non-empty input file to benchmark with all four codecs")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for comparison reports")
    args = parser.parse_args(arguments)
    try:
        report = compare_file(args.input, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, OverflowError) as exc:
        print(f"Compare Mode failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: report[key] for key in ("status", "output_dir", "measurements", "selections", "errors")},
                     indent=2, allow_nan=False))
    if report["status"] != "completed":
        print("Compare Mode incomplete; failed measurements were saved without normal selection labels.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
