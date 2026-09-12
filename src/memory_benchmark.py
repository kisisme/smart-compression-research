"""Isolated Windows peak-working-set benchmarks for compression operations."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from typing import Any

from src.compressors import compress_data, decompress_data


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "experiment_config.json"
_SUPPORTED_ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
_SUPPORTED_OPERATIONS = ("compress", "decompress")
_METHOD = "windows_get_process_memory_info_peak_working_set"


@dataclass(frozen=True, slots=True)
class PeakMemoryBenchmark:
    """Raw repeats and protocol aggregates for one sample-algorithm pair."""

    algorithm: str
    measurement_method: str
    compression_peak_memory_repeats_bytes: tuple[int, ...]
    decompression_peak_memory_repeats_bytes: tuple[int, ...]
    compression_peak_memory_bytes: int
    decompression_peak_memory_bytes: int
    peak_memory_bytes: int
    verified: bool


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD),
        ("page_fault_count", wintypes.DWORD),
        ("peak_working_set_size", ctypes.c_size_t),
        ("working_set_size", ctypes.c_size_t),
        ("quota_peak_paged_pool_usage", ctypes.c_size_t),
        ("quota_paged_pool_usage", ctypes.c_size_t),
        ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
        ("quota_non_paged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t),
        ("peak_pagefile_usage", ctypes.c_size_t),
    )


def _load_config() -> dict[str, Any]:
    with _CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict):
        raise TypeError("Experiment configuration must be a JSON object")
    return config


def _memory_config(config: dict[str, Any]) -> tuple[int, str]:
    memory = config.get("memory")
    if not isinstance(memory, dict):
        raise TypeError("Experiment config key memory must be an object")
    required = {
        "status": "validation_only",
        "platform": "win32",
        "metric": "peak_process_working_set_bytes",
        "backend": "GetProcessMemoryInfo.PeakWorkingSetSize",
        "unit": "bytes",
        "isolation": "fresh_subprocess_per_phase_repeat",
        "aggregate": "median",
        "combined": "max_of_phase_medians",
    }
    for key, expected in required.items():
        if memory.get(key) != expected:
            raise ValueError(f"Experiment config memory.{key} must be {expected!r}")
    repeats = memory.get("repeats")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats <= 0:
        raise ValueError("Experiment config memory.repeats must be a positive integer")
    return repeats, str(memory["status"])


_MEMORY_REPEATS, MEMORY_STATUS = _memory_config(_load_config())


def _validate_algorithm(algorithm: str) -> None:
    if algorithm not in _SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unsupported compression algorithm: {algorithm!r}")


def current_process_peak_working_set_bytes() -> int:
    """Return the Windows process-lifetime PeakWorkingSetSize in bytes."""
    if sys.platform != "win32":
        raise RuntimeError("The configured peak-memory backend requires Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = ()
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCounters),
        wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    process = kernel32.GetCurrentProcess()
    succeeded = psapi.GetProcessMemoryInfo(
        process, ctypes.byref(counters), counters.cb
    )
    if not succeeded:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, "GetProcessMemoryInfo failed")
    peak = int(counters.peak_working_set_size)
    if peak <= 0:
        raise RuntimeError("PeakWorkingSetSize must be greater than zero")
    return peak


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _worker(operation: str, algorithm: str, input_path: Path, expected: str) -> int:
    if operation not in _SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported memory benchmark operation: {operation!r}")
    _validate_algorithm(algorithm)
    input_data = input_path.read_bytes()
    if not input_data:
        raise ValueError("Memory benchmark input must not be empty")

    if operation == "compress":
        output_data = compress_data(input_data, algorithm)
    else:
        output_data = decompress_data(input_data, algorithm)
    verified = _sha256(output_data) == expected
    peak = current_process_peak_working_set_bytes()
    print(
        json.dumps(
            {
                "operation": operation,
                "algorithm": algorithm,
                "peak_process_working_set_bytes": peak,
                "verified": verified,
            },
            sort_keys=True,
        )
    )
    return 0 if verified else 2


def _run_worker(
    operation: str,
    algorithm: str,
    input_path: Path,
    expected_sha256: str,
) -> tuple[int, bool]:
    command = (
        sys.executable,
        "-m",
        "src.memory_benchmark",
        "worker",
        "--operation",
        operation,
        "--algorithm",
        algorithm,
        "--input",
        str(input_path),
        "--expected-sha256",
        expected_sha256,
    )
    completed = subprocess.run(
        command,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode not in (0, 2):
        details = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"Memory benchmark worker failed with code {completed.returncode}: {details}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Memory benchmark worker returned invalid JSON") from exc
    peak = payload.get("peak_process_working_set_bytes")
    verified = payload.get("verified")
    if isinstance(peak, bool) or not isinstance(peak, int) or peak <= 0:
        raise RuntimeError("Memory benchmark worker returned an invalid peak value")
    if not isinstance(verified, bool):
        raise RuntimeError("Memory benchmark worker returned invalid verification")
    return peak, verified


def benchmark_peak_memory(data: bytes, algorithm: str) -> PeakMemoryBenchmark:
    """Measure compression and decompression peaks in fresh worker processes."""
    if not isinstance(data, bytes):
        raise TypeError("Memory benchmark input must be bytes")
    if not data:
        raise ValueError("Memory benchmark input must not be empty")
    _validate_algorithm(algorithm)
    if sys.platform != "win32":
        raise RuntimeError("The configured peak-memory benchmark requires Windows")

    reference_compressed = compress_data(data, algorithm)
    original_digest = _sha256(data)
    compressed_digest = _sha256(reference_compressed)
    compression_peaks: list[int] = []
    decompression_peaks: list[int] = []
    verifications: list[bool] = []

    with tempfile.TemporaryDirectory(prefix="smart_compression_memory_") as directory:
        temporary = Path(directory)
        original_path = temporary / "original.bin"
        compressed_path = temporary / "compressed.bin"
        original_path.write_bytes(data)
        compressed_path.write_bytes(reference_compressed)

        for _ in range(_MEMORY_REPEATS):
            peak, verified = _run_worker(
                "compress", algorithm, original_path, compressed_digest
            )
            compression_peaks.append(peak)
            verifications.append(verified)
        for _ in range(_MEMORY_REPEATS):
            peak, verified = _run_worker(
                "decompress", algorithm, compressed_path, original_digest
            )
            decompression_peaks.append(peak)
            verifications.append(verified)

    compression_median = int(statistics.median(compression_peaks))
    decompression_median = int(statistics.median(decompression_peaks))
    return PeakMemoryBenchmark(
        algorithm=algorithm,
        measurement_method=_METHOD,
        compression_peak_memory_repeats_bytes=tuple(compression_peaks),
        decompression_peak_memory_repeats_bytes=tuple(decompression_peaks),
        compression_peak_memory_bytes=compression_median,
        decompression_peak_memory_bytes=decompression_median,
        peak_memory_bytes=max(compression_median, decompression_median),
        verified=all(verifications),
    )


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure isolated peak working set.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    worker = subparsers.add_parser("worker")
    worker.add_argument("--operation", choices=_SUPPORTED_OPERATIONS, required=True)
    worker.add_argument("--algorithm", choices=_SUPPORTED_ALGORITHMS, required=True)
    worker.add_argument("--input", type=Path, required=True)
    worker.add_argument("--expected-sha256", required=True)
    benchmark = subparsers.add_parser("benchmark")
    benchmark.add_argument("--algorithm", choices=_SUPPORTED_ALGORITHMS, required=True)
    benchmark.add_argument("--input", type=Path, required=True)
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_args(arguments)
    if args.command == "worker":
        return _worker(
            args.operation, args.algorithm, args.input, args.expected_sha256
        )
    data = args.input.read_bytes()
    result = benchmark_peak_memory(data, args.algorithm)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
