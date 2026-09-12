"""Tests for reproducible experiment statistical analysis."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.analysis import ANALYSIS_FILENAMES, analyze_experiment, main
from src.experiment_runner import COMPRESSION_RESULT_FIELDS, SAMPLE_FIELDS
from src.feature_extractor import FEATURE_NAMES
from src.scoring import ALGORITHMS
from src.selection_labels import generate_selection_labels


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fixture(directory: Path) -> tuple[Path, Path, Path]:
    samples_path = directory / "samples.csv"
    results_path = directory / "compression_results.csv"
    labels_path = directory / "selection_labels.csv"
    samples: list[dict[str, object]] = []
    results: list[dict[str, object]] = []
    for index in range(4):
        sample_id = f"sample_{index}"
        size = 100 * (index + 1)
        features = {
            name: float(index + feature_index + 1)
            for feature_index, name in enumerate(FEATURE_NAMES)
        }
        features["file_size"] = size
        samples.append(
            {
                "sample_id": sample_id,
                "generator": "first" if index < 2 else "second",
                "seed": 1000 + index,
                "size": size,
                "generation_parameters": "{}",
                **features,
            }
        )
        for algorithm_index, algorithm in enumerate(ALGORITHMS):
            ratio = 0.2 + index * 0.1 + algorithm_index * 0.05
            compressed_size = round(size * ratio)
            results.append(
                {
                    "sample_id": sample_id,
                    "algorithm": algorithm,
                    "original_size": size,
                    "compressed_size": compressed_size,
                    "compression_ratio": compressed_size / size,
                    "compression_time_ms": 8 - algorithm_index + index,
                    "decompression_time_ms": 2 + algorithm_index + index,
                    "verified": True,
                }
            )
    _write_csv(samples_path, SAMPLE_FIELDS, samples)
    _write_csv(results_path, COMPRESSION_RESULT_FIELDS, results)
    generate_selection_labels(results_path, labels_path)
    return samples_path, results_path, labels_path


class AnalysisTests(unittest.TestCase):
    def test_generates_all_expected_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples, results, labels = _fixture(root)
            output = root / "analysis"

            artifacts = analyze_experiment(samples, results, labels, output)

            self.assertEqual(artifacts.sample_count, 4)
            self.assertEqual(artifacts.compression_result_count, 16)
            self.assertEqual(artifacts.selection_label_count, 12)
            self.assertEqual(
                {path.name for path in output.iterdir()}, set(ANALYSIS_FILENAMES)
            )

            feature_summary = pd.read_csv(output / "feature_summary.csv")
            self.assertEqual(len(feature_summary), len(FEATURE_NAMES))
            entropy = feature_summary.loc[
                feature_summary["feature"] == "entropy"
            ].iloc[0]
            self.assertEqual(entropy["count"], 4)
            self.assertAlmostEqual(entropy["population_std"], math.sqrt(1.25))

            metric_summary = pd.read_csv(output / "algorithm_metric_summary.csv")
            self.assertEqual(len(metric_summary), len(ALGORITHMS) * 3)
            correlations = pd.read_csv(output / "correlations.csv")
            self.assertEqual(len(correlations), len(ALGORITHMS) * len(FEATURE_NAMES) * 3)
            gzip_ratio = correlations.loc[
                (correlations["algorithm"] == "gzip")
                & (correlations["feature"] == "entropy")
                & (correlations["metric"] == "compression_ratio")
            ].iloc[0]
            self.assertAlmostEqual(gzip_ratio["pearson"], 1.0)
            self.assertAlmostEqual(gzip_ratio["spearman"], 1.0)

            mode_rates = pd.read_csv(output / "win_rates_by_mode.csv")
            self.assertEqual(len(mode_rates), 3 * len(ALGORITHMS))
            self.assertTrue(
                mode_rates.groupby("mode")["win_rate"].sum().eq(1.0).all()
            )
            generator_rates = pd.read_csv(output / "win_rates_by_generator_mode.csv")
            self.assertEqual(len(generator_rates), 2 * 3 * len(ALGORITHMS))
            size_rates = pd.read_csv(output / "win_rates_by_size_mode.csv")
            self.assertEqual(len(size_rates), 4 * 3 * len(ALGORITHMS))
            pareto = pd.read_csv(output / "pareto_frequency.csv")
            self.assertEqual(list(pareto["algorithm"]), list(ALGORITHMS))
            self.assertTrue(pareto["pareto_rate"].between(0, 1).all())

            summary = json.loads((output / "analysis_summary.json").read_text())
            self.assertEqual(summary["standard_deviation"], "population (ddof=0)")
            self.assertEqual(summary["sample_count"], 4)
            self.assertEqual(set(summary["input_sha256"]), {
                "samples.csv", "compression_results.csv", "selection_labels.csv"
            })

    def test_existing_output_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples, results, labels = _fixture(root)
            output = root / "analysis"
            analyze_experiment(samples, results, labels, output)
            original = (output / "analysis_summary.json").read_bytes()

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                analyze_experiment(samples, results, labels, output)
            self.assertEqual((output / "analysis_summary.json").read_bytes(), original)

    def test_invalid_header_and_failed_verification_create_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples, results, labels = _fixture(root)
            invalid_samples = root / "invalid_samples.csv"
            invalid_samples.write_text("sample_id,generator\n", encoding="utf-8")
            invalid_output = root / "invalid_analysis"
            with self.assertRaisesRegex(ValueError, "header"):
                analyze_experiment(invalid_samples, results, labels, invalid_output)
            self.assertFalse(invalid_output.exists())

            with results.open(encoding="utf-8", newline="") as input_file:
                rows = list(csv.DictReader(input_file))
            rows[0]["verified"] = "False"
            invalid_results = root / "invalid_results.csv"
            _write_csv(invalid_results, COMPRESSION_RESULT_FIELDS, rows)
            verified_output = root / "verified_analysis"
            with self.assertRaisesRegex(ValueError, "verified=True"):
                analyze_experiment(samples, invalid_results, labels, verified_output)
            self.assertFalse(verified_output.exists())

    def test_cli_main_generates_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples, results, labels = _fixture(root)
            output = root / "analysis"

            exit_code = main(
                [
                    "--samples", str(samples),
                    "--compression-results", str(results),
                    "--selection-labels", str(labels),
                    "--output-dir", str(output),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output / "analysis_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
