"""Raw timing worker for memory_stability_v1 (validation only).

Invoke with python -B -m src.memory_stability_timing_worker. The parent prepares
and verifies reference round trips. This worker does not launch subprocesses,
measure memory, aggregate measurements, or write study results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from src import compressors


DESIGN_ID = "memory_stability_v1"
ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
REPEATS = 5
EXPECTED_COMPRESSION = {
    "gzip": {"level": 9}, "bz2": {"level": 9},
    "lzma": {"preset": 6}, "zstd": {"level": 3},
}
EXPECTED_TIMING = {
    "repeats": REPEATS, "timer": "time.perf_counter_ns", "aggregate": "median",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_configuration() -> None:
    config = compressors._load_config()
    if config != compressors._CONFIG:
        raise ValueError("Configuration differs from the loaded compression module")
    compression, timing = config.get("compression"), config.get("timing")
    if compression != EXPECTED_COMPRESSION or timing != EXPECTED_TIMING:
        raise ValueError("Compression/timing configuration differs from the design")
    for algorithm, settings in EXPECTED_COMPRESSION.items():
        for key in settings:
            if type(compression[algorithm][key]) is not int:
                raise TypeError("Compression settings must be integers, not booleans")
    if type(timing["repeats"]) is not int:
        raise TypeError("Timing repeats must be an integer, not a boolean")
    loaded = (compressors._GZIP_LEVEL, compressors._BZ2_LEVEL,
              compressors._LZMA_PRESET, compressors._ZSTD_LEVEL,
              compressors._TIMING_REPEATS, compressors._TIMING_TIMER,
              compressors._TIMING_AGGREGATE)
    if loaded != (9, 9, 6, 3, REPEATS, "time.perf_counter_ns", "median"):
        raise ValueError("Loaded codec/timing settings differ from the design")


def measure_timing(*, request_id: str, algorithm: str, original: Path,
                   reference_compressed: Path, original_sha256: str,
                   compressed_sha256: str) -> dict:
    """Return raw evidence, including completed/failed attempts on errors.

    Ordinary errors produce worker_failed; interrupts propagate for the parent
    to preserve abnormal stdout/stderr. No unexecuted record is fabricated.
    """
    result = {
        "schema_version": 1, "design_id": DESIGN_ID,
        "measurement_status": "validation_only", "score_inclusion": False,
        "request_id": request_id, "algorithm": algorithm,
        "timer": "time.perf_counter_ns", "original_size": None,
        "compressed_size": None, "original_sha256": None,
        "compressed_sha256": None, "records": [],
        "status": "worker_failed", "error": "",
    }
    try:
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id must be a nonempty string")
        if algorithm not in ALGORITHMS:
            raise ValueError("Unsupported algorithm")
        for name, value in (("original_sha256", original_sha256),
                            ("compressed_sha256", compressed_sha256)):
            if (not isinstance(value, str) or len(value) != 64
                    or any(character not in "0123456789abcdef" for character in value)):
                raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
        if sys.platform != "win32":
            raise RuntimeError("Stability validation requires Windows")
        if not sys.dont_write_bytecode:
            raise RuntimeError("Disable bytecode writes with python -B or PYTHONDONTWRITEBYTECODE=1")
        _check_configuration()

        original_data = original.read_bytes()
        result.update(original_size=len(original_data), original_sha256=_sha256(original_data))
        compressed_data = reference_compressed.read_bytes()
        result.update(compressed_size=len(compressed_data), compressed_sha256=_sha256(compressed_data))
        if not original_data or not compressed_data:
            raise ValueError("Original and reference compressed inputs must not be empty")
        if (result["original_sha256"] != original_sha256
                or result["compressed_sha256"] != compressed_sha256):
            raise ValueError("Input SHA-256 mismatch")

        # Retain all five compressed outputs, as benchmark_compressor does.
        compressed_results: list[bytes] = []
        failed_verification = False
        for phase, codec, input_data, expected in (
                ("compress", compressors.compress_data, original_data, compressed_data),
                ("decompress", compressors.decompress_data, compressed_data, original_data)):
            for repeat_index in range(1, REPEATS + 1):
                record = {
                    "phase": phase, "repeat_index": repeat_index, "elapsed_ns": None,
                    "actual_output_sha256": None, "verified": None,
                    "status": "worker_failed", "error": "",
                }
                result["records"].append(record)
                try:
                    start_ns = time.perf_counter_ns()
                    output = codec(input_data, algorithm)
                    end_ns = time.perf_counter_ns()
                    if type(start_ns) is not int or type(end_ns) is not int:
                        raise TypeError("Timer readings must be integers, not booleans")
                    record["elapsed_ns"] = end_ns - start_ns
                    if not isinstance(output, bytes):
                        raise TypeError("Codec output must be bytes")
                    if phase == "compress":
                        compressed_results.append(output)
                    record["actual_output_sha256"] = _sha256(output)
                    record["verified"] = output == expected
                    if record["elapsed_ns"] <= 0:
                        raise ValueError("Elapsed ns must be a positive integer")
                    record["status"] = "ok" if record["verified"] else "verification_failed"
                    record["error"] = "" if record["verified"] else "Output bytes differ from reference"
                    failed_verification |= not record["verified"]
                except Exception as exc:
                    record["error"] = f"{type(exc).__name__}: {exc}"
                    raise
        result["status"] = "verification_failed" if failed_verification else "ok"
        result["error"] = "Output bytes differ from reference" if failed_verification else ""
    except Exception as exc:
        result["status"] = "worker_failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--algorithm", choices=ALGORITHMS, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--reference-compressed", type=Path, required=True)
    parser.add_argument("--original-sha256", required=True)
    parser.add_argument("--compressed-sha256", required=True)
    result = measure_timing(**vars(parser.parse_args(arguments)))
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return {"ok": 0, "verification_failed": 2}.get(result["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
