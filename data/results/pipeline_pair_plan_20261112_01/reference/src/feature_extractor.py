"""Statistical feature extraction for in-memory byte data."""

from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import statistics
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "experiment_config.json"

FEATURE_NAMES = (
    "file_size",
    "entropy",
    "unique_byte_count",
    "most_common_byte_ratio",
    "zero_byte_ratio",
    "adjacent_repeat_ratio",
    "average_run_length",
    "max_run_length",
    "duplicate_block_ratio",
    "bigram_diversity",
    "segment_entropy_mean",
    "segment_entropy_std",
)


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


def _required_positive_integer(config: dict[str, Any], *keys: str) -> int:
    value: Any = config
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            dotted_key = ".".join(keys)
            raise KeyError(f"Missing required experiment config key: {dotted_key}")
        value = value[key]

    dotted_key = ".".join(keys)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Experiment config key {dotted_key} must be an integer")
    if value <= 0:
        raise ValueError(
            f"Experiment config key {dotted_key} must be greater than zero"
        )
    return value


_CONFIG = _load_config()
_DUPLICATE_BLOCK_SIZE = _required_positive_integer(
    _CONFIG, "features", "duplicate_block_size"
)
_SEGMENT_SIZE = _required_positive_integer(_CONFIG, "features", "segment_size")


def _entropy_from_counts(counts: Counter[int], size: int) -> float:
    return -math.fsum(
        (count / size) * math.log2(count / size) for count in counts.values()
    )


def _run_statistics(data: bytes) -> tuple[float, float, int]:
    run_count = 1
    current_run_length = 1
    max_run_length = 1
    adjacent_repeat_count = 0

    for index in range(1, len(data)):
        if data[index] == data[index - 1]:
            adjacent_repeat_count += 1
            current_run_length += 1
            max_run_length = max(max_run_length, current_run_length)
        else:
            run_count += 1
            current_run_length = 1

    adjacent_repeat_ratio = (
        adjacent_repeat_count / (len(data) - 1) if len(data) > 1 else 0.0
    )
    average_run_length = len(data) / run_count
    return adjacent_repeat_ratio, average_run_length, max_run_length


def _duplicate_block_ratio(data: bytes) -> float:
    seen_blocks: set[bytes] = set()
    duplicate_count = 0
    block_count = 0

    for offset in range(0, len(data), _DUPLICATE_BLOCK_SIZE):
        block = data[offset : offset + _DUPLICATE_BLOCK_SIZE]
        block_count += 1
        if block in seen_blocks:
            duplicate_count += 1
        else:
            seen_blocks.add(block)

    return duplicate_count / block_count


def _bigram_diversity(data: bytes) -> float:
    if len(data) < 2:
        return 0.0

    denominator = min(len(data) - 1, 65_536)
    seen_bigrams = bytearray(65_536)
    unique_bigram_count = 0

    for index in range(1, len(data)):
        bigram = (data[index - 1] << 8) | data[index]
        if not seen_bigrams[bigram]:
            seen_bigrams[bigram] = 1
            unique_bigram_count += 1
            if unique_bigram_count == denominator:
                break

    return unique_bigram_count / denominator


def _segment_entropy_statistics(data: bytes) -> tuple[float, float]:
    entropies = []
    for offset in range(0, len(data), _SEGMENT_SIZE):
        segment = data[offset : offset + _SEGMENT_SIZE]
        entropies.append(_entropy_from_counts(Counter(segment), len(segment)))

    return statistics.fmean(entropies), statistics.pstdev(entropies)


def extract_features(data: bytes) -> dict[str, int | float]:
    """Return the protocol-defined statistical features for non-empty bytes."""
    if not isinstance(data, bytes):
        raise TypeError("Feature extraction input must be bytes")
    if not data:
        raise ValueError("Cannot extract features from empty input data")

    size = len(data)
    byte_counts = Counter(data)
    adjacent_repeat_ratio, average_run_length, max_run_length = _run_statistics(
        data
    )
    segment_entropy_mean, segment_entropy_std = _segment_entropy_statistics(data)

    features: dict[str, int | float] = {
        "file_size": size,
        "entropy": _entropy_from_counts(byte_counts, size),
        "unique_byte_count": len(byte_counts),
        "most_common_byte_ratio": max(byte_counts.values()) / size,
        "zero_byte_ratio": byte_counts.get(0, 0) / size,
        "adjacent_repeat_ratio": adjacent_repeat_ratio,
        "average_run_length": average_run_length,
        "max_run_length": max_run_length,
        "duplicate_block_ratio": _duplicate_block_ratio(data),
        "bigram_diversity": _bigram_diversity(data),
        "segment_entropy_mean": segment_entropy_mean,
        "segment_entropy_std": segment_entropy_std,
    }
    return features
