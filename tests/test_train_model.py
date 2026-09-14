"""Baseline tests. Controlled measurement fixtures are NOT research results."""

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.experiment_runner import COMPRESSION_RESULT_FIELDS, SAMPLE_FIELDS
from src.feature_extractor import extract_features
from src.scoring import ALGORITHMS, MODE_NAMES
from src.selection_labels import generate_selection_labels
from src.train_model import classification_metrics, fit_majority, run_baseline, split_samples


SETTINGS = {"test_size": 0.2, "random_state": 42, "group_column": "seed"}
ROOT = Path(__file__).resolve().parent.parent


def write_rows(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def refresh_hashes(root):
    path = root / "experiment_metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["output_files"] = {
        name: {"sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
        for name in ("samples.csv", "compression_results.csv")
    }
    path.write_text(json.dumps(metadata), encoding="utf-8")


def fixture(root):
    samples = []
    for i in range(16):
        data = bytes(range(100))
        samples.append({"sample_id": f"s{i:02d}", "generator": "random",
                        "seed": i // 2, "size": len(data), "generation_parameters": "{}",
                        **extract_features(data)})
    split = split_samples(pd.DataFrame(samples), SETTINGS).set_index("sample_id")
    results = []
    for sample in samples:
        # Deliberately opposite test majority detects leakage from test labels.
        winner = "gzip" if split.loc[sample["sample_id"], "split"] == "train" else "bz2"
        for algorithm in ALGORITHMS:
            factor = 1 if algorithm == winner else 2
            results.append({"sample_id": sample["sample_id"], "algorithm": algorithm,
                            "original_size": 100, "compressed_size": 20 * factor,
                            "compression_ratio": 0.2 * factor, "compression_time_ms": factor,
                            "decompression_time_ms": factor, "verified": True})
    write_rows(root / "samples.csv", SAMPLE_FIELDS, samples)
    write_rows(root / "compression_results.csv", COMPRESSION_RESULT_FIELDS, results)
    generate_selection_labels(root / "compression_results.csv", root / "selection_labels.csv")
    config = json.loads((ROOT / "config/experiment_config.json").read_text(encoding="utf-8"))
    metadata = {"sample_count": 16, "compression_result_count": 64, "verification_failure_count": 0,
                "compression_settings": config["compression"], "timing": config["timing"],
                "feature_settings": config["features"]}
    (root / "experiment_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    refresh_hashes(root)


class BaselineTests(unittest.TestCase):
    def test_group_split_is_disjoint_reproducible_and_row_order_independent(self):
        samples = pd.DataFrame({"sample_id": [f"s{i}" for i in range(20)],
                                "seed": [str(i // 2) for i in range(20)]})
        first = split_samples(samples, SETTINGS)
        second = split_samples(samples.iloc[::-1], SETTINGS)
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(first.groupby("seed")["split"].nunique().max(), 1)
        self.assertEqual(first["split"].value_counts().to_dict(), {"train": 16, "test": 4})

    def test_invalid_split_settings_and_seeds_fail(self):
        samples = pd.DataFrame({"sample_id": ["a", "b"], "seed": [1, 2]})
        for override in ({"test_size": 0}, {"test_size": float("nan")},
                         {"random_state": True}, {"group_column": "sample_id"}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                split_samples(samples, {**SETTINGS, **override})
        for seeds in ([1, 1], ["1.5", "2"], ["", "2"]):
            with self.subTest(seeds=seeds), self.assertRaises(ValueError):
                split_samples(samples.assign(seed=seeds), SETTINGS)

    def test_majority_ties_and_fixed_four_class_metrics(self):
        self.assertEqual(fit_majority(["zstd", "gzip"])["algorithm"], "gzip")
        self.assertEqual(fit_majority(["bz2", "gzip", "bz2"])["algorithm"], "bz2")
        with self.assertRaises(ValueError):
            fit_majority([])
        metrics = classification_metrics(["gzip", "bz2", "bz2", "zstd"], ["bz2"] * 4)
        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertAlmostEqual(metrics["macro_f1"], 1 / 6)

    def test_complete_evaluation_uses_training_only_and_never_compresses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            output = root / "baseline"
            with patch("src.compressors.compress_data", side_effect=AssertionError("must not compress")):
                summary = run_baseline(root, output)
            for mode in MODE_NAMES:
                self.assertEqual(summary["models"][mode]["algorithm"], "gzip")
                self.assertEqual(summary["test_label_counts"][mode]["bz2"], 4)
            self.assertEqual(summary["train_count"], 12)
            self.assertEqual(summary["test_count"], 4)
            self.assertIsNone(summary["feature_importance"])
            self.assertTrue(all(row["accuracy"] == 0 for row in summary["metrics"]))
            errors = pd.read_csv(output / "misclassified_samples.csv")
            self.assertEqual(len(errors), 12)
            self.assertTrue((errors["regret"] > 0).all())
            matrix = pd.read_csv(output / "confusion_matrix.csv")
            self.assertEqual(len(matrix), 48)
            self.assertTrue(matrix.groupby("mode")["count"].sum().eq(4).all())
            comparisons = pd.read_csv(output / "strategy_comparison.csv")
            self.assertEqual(len(comparisons), 18)
            self.assertTrue(comparisons.loc[comparisons["strategy"] == "oracle", "mean_regret"].eq(0).all())
            again = root / "repeat"
            run_baseline(root, again)
            for name, digest in summary["output_sha256"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
                self.assertEqual((output / name).read_bytes(), (again / name).read_bytes())
            before = (output / "baseline_summary.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_baseline(root, output)
            self.assertEqual((output / "baseline_summary.json").read_bytes(), before)

    def test_invalid_inputs_are_rejected_without_publishing(self):
        for problem in ("hash", "duplicate", "nan", "verified", "zero_time", "header", "scores"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root)
                if problem in ("duplicate", "nan"):
                    path = root / "samples.csv"
                    frame = pd.read_csv(path)
                    if problem == "duplicate":
                        frame.loc[1, "sample_id"] = frame.loc[0, "sample_id"]
                    else:
                        frame.loc[0, "entropy"] = float("inf")
                    frame.to_csv(path, index=False)
                elif problem == "scores":
                    path = root / "selection_labels.csv"
                    frame = pd.read_csv(path)
                    for column in ("best_score", *(f"score_{a}" for a in ALGORITHMS)):
                        frame[column] += 1  # Keeps argmin internally valid; raw recomputation must catch it.
                    frame.to_csv(path, index=False)
                elif problem == "header":
                    (root / "selection_labels.csv").write_text("sample_id\na\n", encoding="utf-8")
                else:
                    path = root / "compression_results.csv"
                    frame = pd.read_csv(path)
                    if problem == "verified":
                        frame.loc[0, "verified"] = False
                    else:
                        frame.loc[0, "compression_time_ms"] = 0
                    frame.to_csv(path, index=False)
                if problem != "hash":
                    refresh_hashes(root)
                with self.assertRaises(ValueError):
                    run_baseline(root, root / "baseline")
                self.assertFalse((root / "baseline").exists())


if __name__ == "__main__":
    unittest.main()
