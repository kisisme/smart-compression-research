"""Protocol-defined multi-objective scoring for compression results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "experiment_config.json"

ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
MODE_NAMES = ("archive", "balanced", "fast_access")
WEIGHT_NAMES = (
    "compression_ratio",
    "compression_time",
    "decompression_time",
)
RELATIVE_LOSS_NAMES = (
    "relative_size_loss",
    "relative_compression_loss",
    "relative_decompression_loss",
)


@dataclass(frozen=True, slots=True)
class ModeSelection:
    """Scores and deterministic best-algorithm selection for one mode."""

    mode: str
    best_algorithm: str
    best_score: float
    scores: dict[str, float]


@dataclass(frozen=True, slots=True)
class _Measurements:
    compression_ratio: float
    compression_time_ms: float
    decompression_time_ms: float


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


def _load_mode_weights(config: dict[str, Any]) -> dict[str, dict[str, float]]:
    modes = config.get("selection_modes")
    if not isinstance(modes, dict):
        raise TypeError("Experiment config key selection_modes must be an object")
    if set(modes) != set(MODE_NAMES):
        raise ValueError(
            "Selection modes must be archive, balanced, and fast_access"
        )

    validated: dict[str, dict[str, float]] = {}
    for mode in MODE_NAMES:
        weights = modes[mode]
        if not isinstance(weights, dict):
            raise TypeError(f"Selection mode {mode!r} must be an object")
        if set(weights) != set(WEIGHT_NAMES):
            raise ValueError(
                f"Selection mode {mode!r} must define exactly: "
                f"{', '.join(WEIGHT_NAMES)}"
            )

        validated_weights: dict[str, float] = {}
        for name in WEIGHT_NAMES:
            value = weights[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"Weight {mode}.{name} must be numeric")
            numeric_value = float(value)
            if not math.isfinite(numeric_value) or numeric_value < 0:
                raise ValueError(
                    f"Weight {mode}.{name} must be finite and non-negative"
                )
            validated_weights[name] = numeric_value

        if not math.isclose(
            math.fsum(validated_weights.values()),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"Selection mode {mode!r} weights must sum to 1")
        validated[mode] = validated_weights
    return validated


_CONFIG = _load_config()
MODE_WEIGHTS = _load_mode_weights(_CONFIG)


def _required_integer(row: Mapping[str, object], field: str) -> int:
    if field not in row:
        raise KeyError(f"Missing required compression result field: {field}")
    value = row[field]
    if isinstance(value, bool):
        raise TypeError(f"Compression result field {field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise TypeError(
                f"Compression result field {field} must be an integer"
            ) from exc
    raise TypeError(f"Compression result field {field} must be an integer")


def _required_positive_number(row: Mapping[str, object], field: str) -> float:
    if field not in row:
        raise KeyError(f"Missing required compression result field: {field}")
    value = row[field]
    if isinstance(value, bool):
        raise TypeError(f"Compression result field {field} must be numeric")
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"Compression result field {field} must be numeric"
        ) from exc
    if not math.isfinite(numeric_value) or numeric_value <= 0:
        raise ValueError(
            f"Compression result field {field} must be finite and greater than zero"
        )
    return numeric_value


def _require_verified(row: Mapping[str, object]) -> None:
    if "verified" not in row:
        raise KeyError("Missing required compression result field: verified")
    if row["verified"] is not True and row["verified"] != "True":
        raise ValueError("Cannot score a compression result with verified=False")


def _normalise_results(
    results: Iterable[Mapping[str, object]],
) -> dict[str, _Measurements]:
    rows = list(results)
    if len(rows) != len(ALGORITHMS):
        raise ValueError(
            f"Exactly {len(ALGORITHMS)} compression results are required; "
            f"received {len(rows)}"
        )

    normalised: dict[str, _Measurements] = {}
    sample_ids: set[str] = set()
    original_sizes: set[int] = set()

    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("Each compression result must be a mapping")
        if "sample_id" not in row or not isinstance(row["sample_id"], str):
            raise TypeError("Compression result field sample_id must be a string")
        if not row["sample_id"]:
            raise ValueError("Compression result field sample_id must not be empty")
        sample_ids.add(row["sample_id"])

        if "algorithm" not in row or not isinstance(row["algorithm"], str):
            raise TypeError("Compression result field algorithm must be a string")
        algorithm = row["algorithm"]
        if algorithm not in ALGORITHMS:
            raise ValueError(f"Unsupported compression algorithm: {algorithm!r}")
        if algorithm in normalised:
            raise ValueError(f"Duplicate compression result for algorithm: {algorithm}")

        original_size = _required_integer(row, "original_size")
        compressed_size = _required_integer(row, "compressed_size")
        if original_size <= 0 or compressed_size <= 0:
            raise ValueError("Compression result sizes must be greater than zero")
        original_sizes.add(original_size)

        compression_ratio = _required_positive_number(row, "compression_ratio")
        expected_ratio = compressed_size / original_size
        if not math.isclose(
            compression_ratio,
            expected_ratio,
            rel_tol=1e-12,
            abs_tol=0.0,
        ):
            raise ValueError(
                f"Compression ratio mismatch for {algorithm}: "
                f"{compression_ratio} != {compressed_size}/{original_size}"
            )

        _require_verified(row)
        normalised[algorithm] = _Measurements(
            compression_ratio=compression_ratio,
            compression_time_ms=_required_positive_number(
                row, "compression_time_ms"
            ),
            decompression_time_ms=_required_positive_number(
                row, "decompression_time_ms"
            ),
        )

    if len(sample_ids) != 1:
        raise ValueError("All compression results must belong to one sample_id")
    if len(original_sizes) != 1:
        raise ValueError("All compression results must have the same original_size")
    if set(normalised) != set(ALGORITHMS):
        missing = set(ALGORITHMS) - set(normalised)
        raise ValueError(f"Missing compression algorithms: {', '.join(sorted(missing))}")
    return normalised


def _relative_losses(
    measurements: dict[str, _Measurements],
) -> dict[str, dict[str, float]]:
    best_ratio = min(
        measurement.compression_ratio for measurement in measurements.values()
    )
    best_compression_time = min(
        measurement.compression_time_ms for measurement in measurements.values()
    )
    best_decompression_time = min(
        measurement.decompression_time_ms for measurement in measurements.values()
    )

    return {
        algorithm: {
            "relative_size_loss": math.log(
                measurements[algorithm].compression_ratio / best_ratio
            ),
            "relative_compression_loss": math.log(
                measurements[algorithm].compression_time_ms
                / best_compression_time
            ),
            "relative_decompression_loss": math.log(
                measurements[algorithm].decompression_time_ms
                / best_decompression_time
            ),
        }
        for algorithm in ALGORITHMS
    }


def calculate_relative_losses(
    results: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, float]]:
    """Calculate the three within-sample logarithmic relative losses."""
    return _relative_losses(_normalise_results(results))


def score_sample(
    results: Iterable[Mapping[str, object]],
) -> dict[str, ModeSelection]:
    """Calculate all mode scores and select the minimum-score algorithm."""
    losses = _relative_losses(_normalise_results(results))
    selections: dict[str, ModeSelection] = {}

    for mode in MODE_NAMES:
        weights = MODE_WEIGHTS[mode]
        scores = {
            algorithm: (
                weights["compression_ratio"]
                * losses[algorithm]["relative_size_loss"]
                + weights["compression_time"]
                * losses[algorithm]["relative_compression_loss"]
                + weights["decompression_time"]
                * losses[algorithm]["relative_decompression_loss"]
            )
            for algorithm in ALGORITHMS
        }
        best_algorithm = min(ALGORITHMS, key=scores.__getitem__)
        selections[mode] = ModeSelection(
            mode=mode,
            best_algorithm=best_algorithm,
            best_score=scores[best_algorithm],
            scores=scores,
        )
    return selections
