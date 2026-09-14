"""Controlled failure analysis fixtures are not research measurements."""

import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.failure_analysis import run_failure_analysis
from src.scoring import MODE_WEIGHTS
from src.train_model import run_baseline, run_decision_tree, run_random_forest
from src.selection_labels import generate_selection_labels
from test_train_model import fixture, refresh_hashes


def prepare(root, perfect=False):
    fixture(root)
    if perfect:
        path = root / "compression_results.csv"
        rows = pd.read_csv(path)
        for index, row in rows.iterrows():
            factor = 1 if row["algorithm"] == "gzip" else 2
            rows.loc[index, ["compressed_size", "compression_ratio", "compression_time_ms", "decompression_time_ms"]] = [20 * factor, .2 * factor, factor, factor]
        rows.to_csv(path, index=False)
        generate_selection_labels(path, root / "selection_labels.csv", overwrite=True)
        refresh_hashes(root)
    run_baseline(root, root / "baseline")
    run_decision_tree(root, root / "baseline", root / "decision_tree")
    run_random_forest(root, root / "baseline", root / "random_forest")


class FailureAnalysisTests(unittest.TestCase):
    def test_decomposition_denominators_confidence_and_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root)
            preserved = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
            with patch("src.compressors.compress_data", side_effect=AssertionError("must not compress")), patch(
                "src.train_model.fit_decision_tree", side_effect=AssertionError("must not fit")
            ), patch("src.train_model.fit_random_forest", side_effect=AssertionError("must not fit")):
                summary = run_failure_analysis(root, root / "analysis")
            self.assertEqual(summary["error_row_count"], 36)
            self.assertEqual(summary["unique_error_samples"], 4)
            errors = pd.read_csv(root / "analysis/error_details.csv")
            for row in errors.to_dict("records"):
                self.assertAlmostEqual(row["regret"], math.log(2))
                for component, weight in zip(("size", "compression", "decompression"), ("compression_ratio", "compression_time", "decompression_time")):
                    self.assertAlmostEqual(row[f"{component}_regret"], MODE_WEIGHTS[row["mode"]][weight] * math.log(2))
                self.assertAlmostEqual(sum(row[f"{n}_regret"] for n in ("size", "compression", "decompression")), row["regret"])
            groups = pd.read_csv(root / "analysis/grouped_error_rates.csv")
            self.assertTrue(groups["test_count"].eq(4).all())
            self.assertTrue(groups["error_rate"].eq(1).all())
            confidence = pd.read_csv(root / "analysis/confidence_summary.csv")
            self.assertTrue(confidence["confidence_equal_one_count"].eq(4).all())
            self.assertTrue(confidence["correct"].eq(False).all())
            for path, digest in preserved.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            run_failure_analysis(root, root / "repeat")
            for name, digest in summary["output_sha256"].items():
                self.assertEqual(hashlib.sha256((root / "analysis" / name).read_bytes()).hexdigest(), digest)
                self.assertEqual((root / "analysis" / name).read_bytes(), (root / "repeat" / name).read_bytes())
            with self.assertRaises(FileExistsError):
                run_failure_analysis(root, root / "analysis")

    def test_no_errors_keeps_empty_csv_headers_and_all_group_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root, perfect=True)
            summary = run_failure_analysis(root, root / "analysis")
            self.assertEqual(summary["error_row_count"], 0)
            for name in ("error_details.csv", "error_algorithm_metrics.csv", "error_feature_context.csv"):
                self.assertTrue(pd.read_csv(root / "analysis" / name).empty)
            groups = pd.read_csv(root / "analysis/grouped_error_rates.csv")
            self.assertTrue(groups["test_count"].eq(4).all())
            self.assertTrue(groups["error_count"].eq(0).all())

    def test_changed_prediction_rejected_even_when_output_hash_updated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare(root)
            path = root / "random_forest/test_predictions.csv"
            summary_path = root / "random_forest/random_forest_summary.json"
            original, original_summary = path.read_bytes(), summary_path.read_bytes()
            for problem in ("hash", "score", "feature", "probability", "duplicate"):
                with self.subTest(problem=problem):
                    path.write_bytes(original)
                    summary_path.write_bytes(original_summary)
                    rows = pd.read_csv(path)
                    if problem == "duplicate":
                        rows.loc[1] = rows.loc[0]
                    else:
                        column = {"hash": "regret", "score": "regret", "feature": "entropy", "probability": "probability_gzip"}[problem]
                        rows.loc[0, column] = -1
                    rows.to_csv(path, index=False)
                    if problem != "hash":
                        saved = json.loads(original_summary)
                        saved["output_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                        summary_path.write_text(json.dumps(saved), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        run_failure_analysis(root, root / "analysis")
                    self.assertFalse((root / "analysis").exists())


if __name__ == "__main__":
    unittest.main()
