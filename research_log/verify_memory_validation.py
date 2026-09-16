"""Audit a completed schema-v1 validation matrix; never remeasure or repair it.

Run from the repository root with:
    python -B -m research_log.verify_memory_validation --experiment-dir PATH

Requires the recorded source/config bytes in this checkout. Only saved evidence
and recalculated aggregates are checked; worker round trips are not rerun.
Incomplete/failed runs are rejected, not converted into successful audit reports.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

from src.data_generator import GENERATOR_NAMES, SAMPLE_SIZES, generate_sample


ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_NAMES = ("samples.csv", "memory_repeats.csv", "memory_summary.csv")
SOURCE_NAMES = (
    "src/memory_validation.py", "src/memory_benchmark.py", "src/compressors.py",
    "src/data_generator.py", "config/experiment_config.json", "requirements.txt",
)


class AuditError(ValueError):
    """Saved evidence does not satisfy the completed validation audit contract."""


def require(condition: bool, message: str) -> None:
    """Unlike assert, these checks remain active under python -O and -OO."""
    if not condition:
        raise AuditError(message)


def audit(directory: Path) -> dict:
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def read_csv(name: str) -> list[dict]:
        with (directory / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    meta = json.loads((directory / "memory_validation_metadata.json").read_text(encoding="utf-8"))
    require(isinstance(meta, dict), "Metadata must be a JSON object")
    require(meta.get("run_status") == "completed",
            f"Requires a successful completed run; found run_status={meta.get('run_status')!r}. "
            "Incomplete/failed evidence is preserved, not repaired by this audit.")
    require(type(meta["schema_version"]) is int and meta["schema_version"] == 1,
            "Only validation schema_version=1 is supported")
    require(meta["measurement_status"] == "validation_only" and meta["score_inclusion"] is False,
            "Expected validation_only with score_inclusion=false")
    require(bool(meta["finished_at_utc"]) and not meta.get("run_error"),
            "Missing successful finalization metadata")
    require(meta["provenance_unchanged"] is True, "Source provenance changed during measurement")
    require(meta["source_sha256"] == meta["source_sha256_at_end"], "Start/end source hashes differ")
    require(isinstance(meta["artifact_sha256"], dict) and set(meta["artifact_sha256"]) == set(ARTIFACT_NAMES),
            "Incomplete artifact hash manifest")
    require(isinstance(meta["source_sha256"], dict) and set(meta["source_sha256"]) == set(SOURCE_NAMES),
            "Incomplete source hash manifest")
    for name, expected in meta["artifact_sha256"].items():
        require(digest(directory / name) == expected, f"Artifact SHA-256 mismatch: {name}")
    for name, expected in meta["source_sha256"].items():
        require(digest(ROOT / name) == expected,
                f"Source SHA-256 mismatch: {name}; use the recorded source/config checkout")
    require(meta["config"] == json.loads((ROOT / "config/experiment_config.json").read_text(encoding="utf-8")),
            "Recorded config differs from the source-hashed config")
    require(meta["algorithm_order"] == ["gzip", "bz2", "lzma", "zstd"], "Invalid algorithm matrix")
    require(meta["phase_order"] == ["compress", "decompress"], "Invalid phase matrix")
    require(type(meta["repeats_per_phase"]) is int and meta["repeats_per_phase"] == 5,
            "Validation requires five repeats per phase")
    require(meta["measurement_method"] == "windows_get_process_memory_info_peak_working_set",
            "Unsupported measurement method")
    require(type(meta["base_seed"]) is int, "base_seed must be an integer")
    expected_plan = [
        {"sample_id": f"memory_{index:06d}", "generator": generator,
         "size": size, "seed": meta["base_seed"] + index}
        for index, (size, generator) in enumerate(
            (size, generator) for size in SAMPLE_SIZES for generator in GENERATOR_NAMES)
    ]
    require(meta["sample_plan"] == expected_plan, "Incomplete or changed schema-v1 sample plan")
    samples, rows, summaries = (read_csv(name) for name in (
        "samples.csv", "memory_repeats.csv", "memory_summary.csv"))
    sample_by_id = {sample["sample_id"]: sample for sample in samples}
    require(len(sample_by_id) == len(samples) == len(meta["sample_plan"]), "Duplicate/missing samples")
    require(len(samples) == meta["sample_count"] == meta["planned_sample_count"], "Sample count mismatch")
    for spec in meta["sample_plan"]:
        sample = sample_by_id[spec["sample_id"]]
        require(all(str(sample[key]) == str(value) for key, value in spec.items()), "Sample plan mismatch")
        require(sample["status"] == "ok" and not sample["error"], "Failed sample generation")
        regenerated = generate_sample(spec["generator"], spec["size"], spec["seed"])
        require(hashlib.sha256(regenerated.data).hexdigest() == sample["input_sha256"], "Input SHA-256 mismatch")
        require(regenerated.parameters == json.loads(sample["generation_parameters"]), "Generation parameters mismatch")
    algorithms = meta["algorithm_order"]
    phases = meta["phase_order"]
    repeats = meta["repeats_per_phase"]
    expected_keys = {(sid, algorithm, phase, repeat)
                     for sid in sample_by_id for algorithm in algorithms
                     for phase in phases for repeat in range(1, repeats + 1)}
    actual_keys = {(row["sample_id"], row["algorithm"], row["phase"], int(row["repeat_index"])) for row in rows}
    require(len(rows) == len(actual_keys) == len(expected_keys) == meta["repeat_count"] == meta["planned_repeat_count"],
            "Duplicate/missing repeats or repeat count mismatch")
    require(actual_keys == expected_keys, "Repeat matrix keys mismatch")
    grouped = defaultdict(list)
    digests = defaultdict(set)
    for row in rows:
        sample = sample_by_id[row["sample_id"]]
        require(all(row[key] == sample[key] for key in ("generator", "size", "seed")), "Repeat sample mismatch")
        require(row["status"] == "ok" and row["verified"] == row["reference_roundtrip_verified"] == "True",
                "Failed or unverified repeat")
        require(row["return_code"] == "0" and not row["error"] and not row["stderr"], "Worker error evidence")
        require(row["measurement_method"] == meta["measurement_method"], "Repeat measurement method mismatch")
        peak = int(row["peak_process_working_set_bytes"])
        require(peak > 0, "Nonpositive peak memory")
        payload = json.loads(row["stdout"])
        require(isinstance(payload, dict) and payload.get("verified") is True
                and type(payload.get("peak_process_working_set_bytes")) is int
                and payload == {"operation": row["phase"], "algorithm": row["algorithm"],
                                "peak_process_working_set_bytes": peak, "verified": True},
                "Worker JSON mismatch")
        key = (row["sample_id"], row["algorithm"], row["phase"])
        grouped[key].append(peak)
        digests[key].add(row["expected_sha256"])
        require(re.fullmatch(r"[0-9a-f]{64}", row["expected_sha256"]) is not None, "Invalid expected SHA-256")
        if row["phase"] == "decompress":
            require(row["expected_sha256"] == sample["input_sha256"], "Decompression digest mismatch")
    require(all(len(values) == 1 for values in digests.values()), "Inconsistent expected repeat digests")
    expected_pairs = {(sid, algorithm) for sid in sample_by_id for algorithm in algorithms}
    require({(row["sample_id"], row["algorithm"]) for row in summaries} == expected_pairs, "Summary matrix mismatch")
    require(len(summaries) == len(expected_pairs) == meta["pair_count"] == meta["planned_pair_count"],
            "Duplicate/missing summaries or pair count mismatch")
    phase_variation = []
    for summary in summaries:
        require(summary["verified"] == "True" and summary["failed_repeat_count"] == "0", "Failed summary pair")
        sample = sample_by_id[summary["sample_id"]]
        require(all(summary[key] == sample[key] for key in ("generator", "size", "seed")), "Summary sample mismatch")
        medians = {}
        for phase, prefix in (("compress", "compression"), ("decompress", "decompression")):
            values = grouped[summary["sample_id"], summary["algorithm"], phase]
            median = statistics.median(values)
            medians[phase] = median
            cv = statistics.pstdev(values) / statistics.mean(values)
            expected = {f"{prefix}_peak_memory_bytes": median,
                        f"{phase}_min_bytes": min(values), f"{phase}_max_bytes": max(values),
                        f"{phase}_population_std_bytes": statistics.pstdev(values), f"{phase}_cv": cv}
            for key, value in expected.items():
                require(math.isclose(float(summary[key]), value, rel_tol=1e-12, abs_tol=1e-12),
                        f"Summary statistic mismatch: {key}")
            phase_variation.append({"sample_id": summary["sample_id"], "generator": sample["generator"],
                                    "size": int(sample["size"]), "algorithm": summary["algorithm"],
                                    "phase": phase, "cv": cv, "median_bytes": median,
                                    "min_bytes": min(values), "max_bytes": max(values)})
        require(float(summary["peak_memory_bytes"]) == max(medians.values()), "Combined peak mismatch")
    require(all(meta[key] == 0 for key in ("failed_sample_count", "failed_pair_count", "failed_repeat_count")),
            "Metadata reports failures")
    require(dict(Counter(row["status"] for row in rows)) == meta["repeat_status_counts"], "Status count mismatch")
    result = {
        "audit_passed": True, "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_scope": "completed_schema_v1_saved_evidence_consistency",
        "measurement_status": "validation_only", "score_inclusion": False,
        "limitations": [
            "No memory measurement or compression/decompression round trip was rerun.",
            "Worker verification is saved evidence, not independently repeated verification.",
            "Compression digests are checked for format and consistency, not recomputed.",
            "Requires matching recorded source/config bytes in the current checkout.",
            "Passing this audit does not complete scientific validation or enable memory scoring.",
        ],
        "audit_script_sha256": digest(Path(__file__)), "measurement_commit": meta["git"]["commit_hash"],
        "input_sha256": {name: digest(directory / name) for name in (
            "samples.csv", "memory_repeats.csv", "memory_summary.csv", "memory_validation_metadata.json")},
        "sample_count": len(samples), "pair_count": len(summaries), "repeat_count": len(rows),
        "phase_group_count": len(grouped), "failed_repeat_count": sum(row["status"] != "ok" for row in rows),
        "checks": ["artifact/source SHA-256", "regenerated input SHA-256 and generation parameters",
                   "complete unique matrix keys", "worker JSON and expected digests",
                   "independently recalculated medians/min/max/population std/CV", "metadata counts"],
        "median_phase_cv": statistics.median(item["cv"] for item in phase_variation),
        "largest_phase_cv": max(phase_variation, key=lambda item: item["cv"]),
        "variation_by_algorithm_size": [
            {"algorithm": algorithm, "size": size,
             "max_compress_cv": max(item["cv"] for item in phase_variation
                                    if item["algorithm"] == algorithm and item["size"] == size and item["phase"] == "compress"),
             "max_decompress_cv": max(item["cv"] for item in phase_variation
                                      if item["algorithm"] == algorithm and item["size"] == size and item["phase"] == "decompress")}
            for size in sorted({int(sample["size"]) for sample in samples}) for algorithm in algorithms
        ],
    }
    return result


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Optional new audit JSON; never overwritten")
    args = parser.parse_args(arguments)
    try:
        result = audit(args.experiment_dir)
        serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        parser.exit(1, f"Audit failed: {exc}\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
