"""Compression helpers and in-memory benchmarks for the research project."""

from __future__ import annotations

import bz2
import gzip
import json
import lzma
import statistics
import time
from pathlib import Path
from typing import Any

import zstandard


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "experiment_config.json"
_SUPPORTED_ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")


def _load_config() -> dict[str, Any]:
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Experiment configuration file not found: {_CONFIG_PATH}"
        ) from exc

    if not isinstance(config, dict):
        raise TypeError(f"Experiment configuration must be a JSON object: {_CONFIG_PATH}")
    return config


def _required_config_value(config: dict[str, Any], *keys: str) -> Any:
    value: Any = config
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            dotted_key = ".".join(keys)
            raise KeyError(f"Missing required experiment config key: {dotted_key}")
        value = value[key]
    return value


def _required_integer(config: dict[str, Any], *keys: str) -> int:
    value = _required_config_value(config, *keys)
    if isinstance(value, bool) or not isinstance(value, int):
        dotted_key = ".".join(keys)
        raise TypeError(f"Experiment config key {dotted_key} must be an integer")
    return value


_CONFIG = _load_config()
_GZIP_LEVEL = _required_integer(_CONFIG, "compression", "gzip", "level")
_BZ2_LEVEL = _required_integer(_CONFIG, "compression", "bz2", "level")
_LZMA_PRESET = _required_integer(_CONFIG, "compression", "lzma", "preset")
_ZSTD_LEVEL = _required_integer(_CONFIG, "compression", "zstd", "level")
_TIMING_REPEATS = _required_integer(_CONFIG, "timing", "repeats")
_TIMING_TIMER = _required_config_value(_CONFIG, "timing", "timer")
_TIMING_AGGREGATE = _required_config_value(_CONFIG, "timing", "aggregate")

if _TIMING_REPEATS <= 0:
    raise ValueError("Experiment config key timing.repeats must be greater than zero")
if _TIMING_TIMER != "time.perf_counter_ns":
    raise ValueError(
        "Unsupported experiment timer: "
        f"{_TIMING_TIMER!r}; expected 'time.perf_counter_ns'"
    )
if _TIMING_AGGREGATE != "median":
    raise ValueError(
        f"Unsupported timing aggregate: {_TIMING_AGGREGATE!r}; expected 'median'"
    )


def _validate_algorithm(algorithm: str) -> None:
    if algorithm not in _SUPPORTED_ALGORITHMS:
        supported = ", ".join(_SUPPORTED_ALGORITHMS)
        raise ValueError(
            f"Unsupported compression algorithm: {algorithm!r}. Supported: {supported}"
        )


def compress_data(data: bytes, algorithm: str) -> bytes:
    """Compress in-memory bytes with the configured algorithm settings."""
    _validate_algorithm(algorithm)

    if algorithm == "gzip":
        return gzip.compress(data, compresslevel=_GZIP_LEVEL, mtime=0)
    if algorithm == "bz2":
        return bz2.compress(data, compresslevel=_BZ2_LEVEL)
    if algorithm == "lzma":
        return lzma.compress(data, preset=_LZMA_PRESET)
    return zstandard.ZstdCompressor(level=_ZSTD_LEVEL).compress(data)


def decompress_data(compressed_data: bytes, algorithm: str) -> bytes:
    """Decompress in-memory bytes produced by a supported algorithm."""
    _validate_algorithm(algorithm)

    if algorithm == "gzip":
        return gzip.decompress(compressed_data)
    if algorithm == "bz2":
        return bz2.decompress(compressed_data)
    if algorithm == "lzma":
        return lzma.decompress(compressed_data)
    return zstandard.ZstdDecompressor().decompress(compressed_data)


def benchmark_compressor(data: bytes, algorithm: str) -> dict[str, object]:
    """Benchmark compression and decompression of non-empty in-memory bytes."""
    if len(data) == 0:
        raise ValueError("Cannot benchmark empty input data")
    _validate_algorithm(algorithm)

    compression_times_ns: list[int] = []
    compressed_results: list[bytes] = []
    for _ in range(_TIMING_REPEATS):
        start_ns = time.perf_counter_ns()
        compressed_data = compress_data(data, algorithm)
        compression_times_ns.append(time.perf_counter_ns() - start_ns)
        compressed_results.append(compressed_data)

    reference_compressed = compressed_results[0]
    if any(result != reference_compressed for result in compressed_results[1:]):
        raise RuntimeError(
            f"{algorithm} produced inconsistent compressed bytes across repeated runs"
        )

    decompression_times_ns: list[int] = []
    verification_results: list[bool] = []
    for _ in range(_TIMING_REPEATS):
        start_ns = time.perf_counter_ns()
        restored_data = decompress_data(reference_compressed, algorithm)
        decompression_times_ns.append(time.perf_counter_ns() - start_ns)
        verification_results.append(restored_data == data)

    original_size = len(data)
    compressed_size = len(reference_compressed)
    return {
        "algorithm": algorithm,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_ratio": compressed_size / original_size,
        "compression_time_ms": statistics.median(compression_times_ns) / 1_000_000,
        "decompression_time_ms": statistics.median(decompression_times_ns)
        / 1_000_000,
        "verified": all(verification_results),
    }
