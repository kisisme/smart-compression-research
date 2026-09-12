"""Reproducible statistical analysis of completed compression experiments."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import tempfile

import numpy as np
import pandas as pd

from src.experiment_runner import COMPRESSION_RESULT_FIELDS, SAMPLE_FIELDS
from src.feature_extractor import FEATURE_NAMES
from src.scoring import ALGORITHMS, MODE_NAMES
from src.selection_labels import SELECTION_LABEL_FIELDS


METRIC_NAMES = (
    "compression_ratio",
    "compression_time_ms",
    "decompression_time_ms",
)
ANALYSIS_FILENAMES = (
    "feature_summary.csv",
    "algorithm_metric_summary.csv",
    "correlations.csv",
    "win_rates_by_mode.csv",
    "win_rates_by_generator_mode.csv",
    "win_rates_by_size_mode.csv",
    "pareto_frequency.csv",
    "analysis_summary.json",
)


@dataclass(frozen=True, slots=True)
class AnalysisArtifacts:
    """Paths and validated row counts for one analysis run."""

    output_dir: Path
    sample_count: int
    compression_result_count: int
    selection_label_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_exact_csv(path: Path, fields: tuple[str, ...], name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name} file not found: {path}")
    if not path.is_file():
        raise ValueError(f"{name} path is not a file: {path}")
    with path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.reader(input_file)
        header = tuple(next(reader, ()))
    if header != fields:
        raise ValueError(f"{name} CSV header does not match the research schema")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if frame.empty:
        raise ValueError(f"{name} CSV contains no data rows")
    return frame


def _numeric(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    for column in columns:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name}.{column} contains a non-numeric value") from exc
        if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise ValueError(f"{name}.{column} contains a non-finite value")


def _validate_inputs(
    samples: pd.DataFrame,
    results: pd.DataFrame,
    labels: pd.DataFrame,
) -> None:
    if (samples["sample_id"] == "").any() or samples["sample_id"].duplicated().any():
        raise ValueError("samples.csv contains an empty or duplicate sample_id")
    _numeric(samples, ("seed", "size", *FEATURE_NAMES), "samples")
    if (samples["size"] <= 0).any() or (samples["file_size"] != samples["size"]).any():
        raise ValueError("Sample sizes must be positive and equal to file_size")

    if results[["sample_id", "algorithm"]].duplicated().any():
        raise ValueError("compression_results.csv contains duplicate sample-algorithm rows")
    _numeric(
        results,
        (
            "original_size",
            "compressed_size",
            "compression_ratio",
            "compression_time_ms",
            "decompression_time_ms",
        ),
        "compression_results",
    )
    if not results["algorithm"].isin(ALGORITHMS).all():
        raise ValueError("compression_results.csv contains an unsupported algorithm")
    if not results["verified"].eq("True").all():
        raise ValueError("All compression results must have verified=True")
    if (results[list(METRIC_NAMES)] <= 0).any().any():
        raise ValueError("Compression ratios and times must be greater than zero")
    if (results[["original_size", "compressed_size"]] <= 0).any().any():
        raise ValueError("Compression result sizes must be greater than zero")
    expected_ratio = results["compressed_size"] / results["original_size"]
    if not np.isclose(
        results["compression_ratio"], expected_ratio, rtol=1e-12, atol=0.0
    ).all():
        raise ValueError("compression_results.csv contains a compression ratio mismatch")

    sample_ids = set(samples["sample_id"])
    if set(results["sample_id"]) != sample_ids:
        raise ValueError("Compression-result sample IDs do not match samples.csv")
    algorithm_sets = results.groupby("sample_id", sort=False)["algorithm"].agg(set)
    if not algorithm_sets.map(lambda value: value == set(ALGORITHMS)).all():
        raise ValueError("Each sample must have exactly the four configured algorithms")
    original_sizes = results.groupby("sample_id", sort=False)["original_size"].nunique()
    if not original_sizes.eq(1).all():
        raise ValueError("Algorithms for one sample must share original_size")
    expected_sizes = samples.set_index("sample_id")["size"]
    result_sizes = results.groupby("sample_id", sort=False)["original_size"].first()
    if not result_sizes.eq(expected_sizes.reindex(result_sizes.index)).all():
        raise ValueError("Compression original_size does not match samples.csv")

    if labels[["sample_id", "mode"]].duplicated().any():
        raise ValueError("selection_labels.csv contains duplicate sample-mode rows")
    if set(labels["sample_id"]) != sample_ids:
        raise ValueError("Selection-label sample IDs do not match samples.csv")
    if not labels["mode"].isin(MODE_NAMES).all():
        raise ValueError("selection_labels.csv contains an unsupported mode")
    if not labels["best_algorithm"].isin(ALGORITHMS).all():
        raise ValueError("selection_labels.csv contains an unsupported best_algorithm")
    mode_sets = labels.groupby("sample_id", sort=False)["mode"].agg(set)
    if not mode_sets.map(lambda value: value == set(MODE_NAMES)).all():
        raise ValueError("Each sample must have exactly the three configured modes")
    score_columns = ("best_score", *(f"score_{item}" for item in ALGORITHMS))
    _numeric(labels, score_columns, "selection_labels")
    score_frame = labels[[f"score_{item}" for item in ALGORITHMS]].copy()
    score_frame.columns = list(ALGORITHMS)
    expected_best = score_frame.idxmin(axis=1)
    expected_score = score_frame.min(axis=1)
    if not labels["best_algorithm"].eq(expected_best).all():
        raise ValueError("selection_labels.csv contains a best_algorithm mismatch")
    if not np.isclose(labels["best_score"], expected_score, rtol=1e-12, atol=1e-15).all():
        raise ValueError("selection_labels.csv contains a best_score mismatch")


def _summary_rows(
    frame: pd.DataFrame, group_columns: tuple[str, ...], value_columns: tuple[str, ...]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    grouped = [((), frame)] if not group_columns else frame.groupby(
        list(group_columns), sort=False, observed=True
    )
    for keys, group in grouped:
        keys = keys if isinstance(keys, tuple) else (keys,)
        prefix = dict(zip(group_columns, keys, strict=True))
        for column in value_columns:
            values = group[column].to_numpy(dtype=float)
            rows.append(
                {
                    **prefix,
                    "feature" if not group_columns else "metric": column,
                    "count": len(values),
                    "mean": float(np.mean(values)),
                    "population_std": float(np.std(values, ddof=0)),
                    "min": float(np.min(values)),
                    "median": float(np.median(values)),
                    "max": float(np.max(values)),
                }
            )
    return rows


def _correlation_rows(merged: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for algorithm in ALGORITHMS:
        group = merged.loc[merged["algorithm"] == algorithm]
        for feature in FEATURE_NAMES:
            x = group[feature].astype(float)
            for metric in METRIC_NAMES:
                y = group[metric].astype(float)
                pearson = x.corr(y, method="pearson")
                spearman = x.rank(method="average").corr(
                    y.rank(method="average"), method="pearson"
                )
                if not math.isfinite(pearson) or not math.isfinite(spearman):
                    raise ValueError(
                        f"Undefined correlation for {algorithm}, {feature}, {metric}"
                    )
                rows.append(
                    {
                        "algorithm": algorithm,
                        "feature": feature,
                        "metric": metric,
                        "count": len(group),
                        "pearson": pearson,
                        "spearman": spearman,
                    }
                )
    return rows


def _win_rate_rows(
    labels: pd.DataFrame,
    samples: pd.DataFrame,
    dimensions: tuple[str, ...],
) -> list[dict[str, object]]:
    joined = labels.merge(
        samples[["sample_id", "generator", "size"]],
        on="sample_id",
        how="left",
        validate="many_to_one",
    )
    dimension_values = {
        "mode": MODE_NAMES,
        "generator": tuple(sorted(samples["generator"].unique())),
        "size": tuple(sorted(int(value) for value in samples["size"].unique())),
    }
    rows: list[dict[str, object]] = []
    for keys in itertools.product(*(dimension_values[item] for item in dimensions)):
        mask = pd.Series(True, index=joined.index)
        for dimension, value in zip(dimensions, keys, strict=True):
            mask &= joined[dimension].eq(value)
        group = joined.loc[mask]
        total = len(group)
        if total == 0:
            raise ValueError(f"No labels found for analysis group {keys}")
        for algorithm in ALGORITHMS:
            count = int(group["best_algorithm"].eq(algorithm).sum())
            rows.append(
                {
                    **dict(zip(dimensions, keys, strict=True)),
                    "algorithm": algorithm,
                    "win_count": count,
                    "total_count": total,
                    "win_rate": count / total,
                }
            )
    return rows


def _pareto_rows(results: pd.DataFrame, sample_count: int) -> list[dict[str, object]]:
    counts = {algorithm: 0 for algorithm in ALGORITHMS}
    for _, group in results.groupby("sample_id", sort=False):
        values = group.set_index("algorithm")[list(METRIC_NAMES)]
        for algorithm in ALGORITHMS:
            candidate = values.loc[algorithm].to_numpy(dtype=float)
            dominated = False
            for other in ALGORITHMS:
                if other == algorithm:
                    continue
                comparison = values.loc[other].to_numpy(dtype=float)
                if np.less_equal(comparison, candidate).all() and np.less(
                    comparison, candidate
                ).any():
                    dominated = True
                    break
            if not dominated:
                counts[algorithm] += 1
    return [
        {
            "algorithm": algorithm,
            "pareto_count": counts[algorithm],
            "sample_count": sample_count,
            "pareto_rate": counts[algorithm] / sample_count,
        }
        for algorithm in ALGORITHMS
    ]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    frame = pd.DataFrame(rows)
    frame.to_csv(path, index=False, encoding="utf-8", float_format="%.17g")


def analyze_experiment(
    samples_path: str | Path,
    compression_results_path: str | Path,
    selection_labels_path: str | Path,
    output_dir: str | Path,
) -> AnalysisArtifacts:
    """Validate raw artifacts and atomically create protocol-aligned summaries."""
    sources = {
        "samples.csv": Path(samples_path),
        "compression_results.csv": Path(compression_results_path),
        "selection_labels.csv": Path(selection_labels_path),
    }
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"Analysis output directory already exists: {destination}")
    resolved_destination = destination.resolve()
    if any(path.resolve() == resolved_destination for path in sources.values()):
        raise ValueError("Analysis output directory must differ from input files")

    samples = _read_exact_csv(sources["samples.csv"], SAMPLE_FIELDS, "samples")
    results = _read_exact_csv(
        sources["compression_results.csv"],
        COMPRESSION_RESULT_FIELDS,
        "compression_results",
    )
    labels = _read_exact_csv(
        sources["selection_labels.csv"], SELECTION_LABEL_FIELDS, "selection_labels"
    )
    _validate_inputs(samples, results, labels)

    merged = results.merge(
        samples[["sample_id", *FEATURE_NAMES]],
        on="sample_id",
        how="left",
        validate="many_to_one",
    )
    feature_rows = _summary_rows(samples, (), FEATURE_NAMES)
    metric_rows = _summary_rows(results, ("algorithm",), METRIC_NAMES)
    correlation_rows = _correlation_rows(merged)
    win_mode_rows = _win_rate_rows(labels, samples, ("mode",))
    win_generator_rows = _win_rate_rows(
        labels, samples, ("generator", "mode")
    )
    win_size_rows = _win_rate_rows(labels, samples, ("size", "mode"))
    pareto_rows = _pareto_rows(results, len(samples))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".analysis_", dir=destination.parent) as temp:
        temporary = Path(temp) / destination.name
        temporary.mkdir()
        _write_csv(temporary / "feature_summary.csv", feature_rows)
        _write_csv(temporary / "algorithm_metric_summary.csv", metric_rows)
        _write_csv(temporary / "correlations.csv", correlation_rows)
        _write_csv(temporary / "win_rates_by_mode.csv", win_mode_rows)
        _write_csv(
            temporary / "win_rates_by_generator_mode.csv", win_generator_rows
        )
        _write_csv(temporary / "win_rates_by_size_mode.csv", win_size_rows)
        _write_csv(temporary / "pareto_frequency.csv", pareto_rows)
        summary = {
            "analysis_version": 1,
            "standard_deviation": "population (ddof=0)",
            "sample_count": len(samples),
            "compression_result_count": len(results),
            "selection_label_count": len(labels),
            "algorithms": list(ALGORITHMS),
            "modes": list(MODE_NAMES),
            "input_sha256": {
                name: _sha256(path) for name, path in sources.items()
            },
            "generated_files": list(ANALYSIS_FILENAMES[:-1]),
        }
        (temporary / "analysis_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(destination)

    return AnalysisArtifacts(
        output_dir=destination,
        sample_count=len(samples),
        compression_result_count=len(results),
        selection_label_count=len(labels),
    )


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze validated samples, measurements, and selection labels."
    )
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--compression-results", type=Path, required=True)
    parser.add_argument("--selection-labels", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_args(arguments)
    artifacts = analyze_experiment(
        args.samples,
        args.compression_results,
        args.selection_labels,
        args.output_dir,
    )
    print(f"samples analyzed: {artifacts.sample_count}")
    print(f"compression results: {artifacts.compression_result_count}")
    print(f"selection labels: {artifacts.selection_label_count}")
    print(f"analysis output: {artifacts.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
