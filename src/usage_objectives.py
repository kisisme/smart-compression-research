"""Experimental, codec-only objectives. No config reads, codecs, models or I/O.

These functions are offline selectors over supplied measurements, not Smart Mode.
They do not replace protocol-v2 scoring or provide operational profile defaults.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal
import math
import re
from typing import Any


ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
LIFETIME_OBJECTIVE = "lifetime_policy_cost_v1"
DEADLINE_OBJECTIVE = "deadline_constrained_size_v1"
IMPLEMENTATION_VERSION = 1
MEASUREMENT_FIELDS = (
    "sample_id", "original_size", "compressed_size", "compression_time_ms",
    "decompression_time_ms", "verified",
)


def _number(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be an explicit numeric value")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite and numeric") from exc
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'non-negative'}")
    if isinstance(value, str) and result == 0 and Decimal(value) != 0:
        raise ValueError(f"{name} underflows to zero in binary64")
    return result


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not (
        isinstance(value, int)
        or isinstance(value, str) and re.fullmatch(r"[+]?[0-9]+", value.strip())
    ):
        raise ValueError(f"{name} must be a positive integer byte count")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _product(a: float, b: float | int, name: str) -> float:
    if a == 0 or b == 0:
        return 0.0
    try:
        result = a * b
    except OverflowError as exc:
        raise ValueError(f"{name} overflows binary64") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} overflows binary64")
    if result == 0 and a != 0 and b != 0:
        raise ValueError(f"{name} underflows to zero")
    return result


@dataclass(frozen=True, kw_only=True)
class LifetimePolicy:
    """Explicit policy points/(byte day), points/ms, days and expected count.

    profile_kind='time_only' must be requested explicitly to disable storage cost.
    Float-compatible decimal strings, ints and floats are accepted; bool is not.
    """

    retention_days: float
    expected_restorations: float
    storage_cost_per_byte_day: float
    compression_cost_per_ms: float
    decompression_cost_per_ms: float
    profile_kind: str = "storage"

    def __post_init__(self) -> None:
        for name in (
            "retention_days", "expected_restorations", "storage_cost_per_byte_day",
            "compression_cost_per_ms", "decompression_cost_per_ms",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if self.profile_kind not in ("storage", "time_only"):
            raise ValueError("profile_kind must be storage or time_only")
        storage = _product(self.storage_cost_per_byte_day, self.retention_days, "storage coefficient")
        restore = _product(self.decompression_cost_per_ms, self.expected_restorations, "restoration coefficient")
        if not any(v > 0 for v in (storage, self.compression_cost_per_ms, restore)):
            raise ValueError("At least one effective coefficient must be positive")
        if self.profile_kind == "storage" and storage == 0:
            raise ValueError("Storage profiles require positive storage cost and retention")
        if self.profile_kind == "time_only" and storage != 0:
            raise ValueError("A time_only profile must have zero effective storage cost")


def _missing(row: Mapping[str, object], field: str) -> bool:
    return field not in row or row[field] is None or (
        isinstance(row[field], str) and not row[field].strip()
    )


def _measurements(results: Iterable[Mapping[str, object]]) -> tuple[dict, dict, dict]:
    """Validate every supplied value before reporting missing measurements.

    Missing rows/fields never make a smaller implicit candidate set. A supplied
    failed/invalid value always raises, even when another measurement is absent.
    Original row fields are copied and retained; inputs are never modified.
    """
    raw, normal, missing = {}, {}, {}
    sample_ids, sizes = set(), set()
    for row in results:
        if not isinstance(row, Mapping):
            raise ValueError("Each measurement must be a mapping")
        algorithm = row.get("algorithm")
        if not isinstance(algorithm, str) or algorithm not in ALGORITHMS:
            raise ValueError("Unknown or missing algorithm")
        if algorithm in raw:
            raise ValueError(f"Duplicate algorithm: {algorithm}")
        raw[algorithm] = dict(row)
        absent = [f for f in MEASUREMENT_FIELDS if _missing(row, f)]
        if absent:
            missing[algorithm] = absent
        if "status" in row and row["status"] != "ok":
            raise ValueError(f"Failed or unknown measurement status: {algorithm}")
        parsed = {}
        for field in MEASUREMENT_FIELDS:
            if field in absent:
                continue
            value = row[field]
            if field == "sample_id":
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("sample_id must be a non-empty string")
                sample_ids.add(value)
                parsed[field] = value
            elif field == "verified":
                if value is not True and not (isinstance(value, str) and value == "True"):
                    raise ValueError(f"Cannot select an unverified result: {algorithm}")
                parsed[field] = True
            elif field in ("original_size", "compressed_size"):
                parsed[field] = _integer(value, f"{algorithm}.{field}")
                if field == "original_size":
                    sizes.add(parsed[field])
            else:
                parsed[field] = _number(value, f"{algorithm}.{field}", positive=True)
        if not absent:
            normal[algorithm] = parsed
    if len(sample_ids) > 1 or len(sizes) > 1:
        raise ValueError("Measurements must describe one sample and one original size")
    for algorithm in ALGORITHMS:
        if algorithm not in raw:
            missing[algorithm] = list(MEASUREMENT_FIELDS)
    return (
        {a: raw[a] for a in ALGORITHMS if a in raw},
        {a: normal[a] for a in ALGORITHMS if a in normal},
        {a: missing[a] for a in ALGORITHMS if a in missing},
    )


def _response(objective: str, raw: dict, missing: dict, parameters: dict) -> dict[str, Any]:
    return {
        "objective_id": objective, "implementation_version": IMPLEMENTATION_VERSION,
        "official_score": False, "measurement_scope": "codec_only_offline_oracle",
        "status": "measurement_required" if missing else "selected",
        "selected_algorithm": None, "selection_value": None,
        "value_unit": "policy_cost_points" if objective == LIFETIME_OBJECTIVE else "bytes",
        "values": {}, "components": {}, "feasible_algorithms": [],
        "tied_algorithms": [], "violations": {}, "missing_measurements": missing,
        "measurements": list(raw.values()), "parameters": parameters,
        "numerics": "binary64 parameters/times/products; math.fsum costs; integer bytes; exact ties; no epsilon",
    }


def evaluate_lifetime_cost(
    results: Iterable[Mapping[str, object]], *, policy: LifetimePolicy,
) -> dict[str, Any]:
    """Minimize k_s*H*B + k_c*T_c + k_d*N*T_d over four verified codecs.

    Missing measurement -> structured status; failed/malformed input -> ValueError.
    All parameters must be explicitly supplied. No filesystem/config/model access.
    """
    if not isinstance(policy, LifetimePolicy):
        raise TypeError("policy must be an explicit LifetimePolicy")
    raw, rows, missing = _measurements(results)
    response = _response(LIFETIME_OBJECTIVE, raw, missing, asdict(policy))
    if missing:
        return response
    storage = _product(policy.storage_cost_per_byte_day, policy.retention_days, "storage coefficient")
    restore = _product(policy.decompression_cost_per_ms, policy.expected_restorations, "restoration coefficient")
    for algorithm, row in rows.items():
        components = {
            "storage": _product(storage, row["compressed_size"], "storage cost"),
            "compression": _product(policy.compression_cost_per_ms, row["compression_time_ms"], "compression cost"),
            "restoration": _product(restore, row["decompression_time_ms"], "restoration cost"),
        }
        try:
            value = math.fsum(components.values())
        except OverflowError as exc:
            raise ValueError("Total cost overflows binary64") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Total cost must be finite and positive")
        response["components"][algorithm] = components
        response["values"][algorithm] = value
    winner = min(ALGORITHMS, key=response["values"].__getitem__)
    best = response["values"][winner]
    response.update(selected_algorithm=winner, selection_value=best,
                    feasible_algorithms=list(ALGORITHMS),
                    tied_algorithms=[a for a in ALGORITHMS if response["values"][a] == best])
    return response


def select_under_deadlines(
    results: Iterable[Mapping[str, object]], *, compression_limit_ms: float,
    decompression_limit_ms: float,
) -> dict[str, Any]:
    """Minimize integer compressed bytes subject to inclusive codec time limits.

    This is an offline measured oracle, not a prediction-time deadline guarantee.
    An empty feasible set returns constraint_unsatisfied without a fallback codec.
    """
    limit_c = _number(compression_limit_ms, "compression_limit_ms", positive=True)
    limit_d = _number(decompression_limit_ms, "decompression_limit_ms", positive=True)
    raw, rows, missing = _measurements(results)
    response = _response(DEADLINE_OBJECTIVE, raw, missing, {
        "compression_limit_ms": limit_c, "decompression_limit_ms": limit_d,
    })
    if missing:
        return response
    for algorithm, row in rows.items():
        reasons = []
        if row["compression_time_ms"] > limit_c:
            reasons.append("compression_time_ms_exceeds_limit")
        if row["decompression_time_ms"] > limit_d:
            reasons.append("decompression_time_ms_exceeds_limit")
        response["values"][algorithm] = row["compressed_size"]
        if reasons:
            response["violations"][algorithm] = reasons
        else:
            response["feasible_algorithms"].append(algorithm)
    feasible = response["feasible_algorithms"]
    if not feasible:
        response["status"] = "constraint_unsatisfied"
        return response
    winner = min(feasible, key=response["values"].__getitem__)
    best = response["values"][winner]
    response.update(selected_algorithm=winner, selection_value=best,
                    tied_algorithms=[a for a in feasible if response["values"][a] == best])
    return response
