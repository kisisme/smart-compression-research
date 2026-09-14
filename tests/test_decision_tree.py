"""Decision Tree tests; controlled fixtures are not research measurements."""

import hashlib
import json
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.feature_extractor import FEATURE_NAMES
from src.scoring import ALGORITHMS, MODE_NAMES
from src.train_model import fit_decision_tree, run_baseline, run_decision_tree, main
from test_train_model import ROOT, fixture


def settings():
    return json.loads((ROOT / "config/experiment_config.json").read_text(encoding="utf-8"))["decision_tree"]


class DecisionTreeTests(unittest.TestCase):
    def test_learns_feature_threshold_and_rejects_leakage_columns(self):
        features = pd.DataFrame(0.0, index=range(8), columns=FEATURE_NAMES)
        features["entropy"] = [0, 0.1, 0.2, 0.3, 7.7, 7.8, 7.9, 8]
        labels = ["gzip"] * 4 + ["zstd"] * 4
        tree = fit_decision_tree(features, labels, settings())
        self.assertEqual(tree.predict(features).tolist(), labels)
        self.assertEqual(tree.feature_names_in_.tolist(), list(FEATURE_NAMES))
        self.assertEqual(tree.feature_importances_[FEATURE_NAMES.index("entropy")], 1)
        self.assertEqual(tree.get_params()["random_state"], 42)
        self.assertIsNone(tree.get_params()["class_weight"])
        for column in ("sample_id", "generator", "compression_ratio", "score_zstd"):
            with self.subTest(column=column), self.assertRaises(ValueError):
                fit_decision_tree(features.assign(**{column: 1}), labels, settings())
        with self.assertRaises(ValueError):
            fit_decision_tree(features.assign(entropy=float("nan")), labels, settings())
        with self.assertRaises(ValueError):
            fit_decision_tree(features, labels, {**settings(), "random_state": None})

    def test_saved_split_training_only_missing_classes_and_model_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            baseline = root / "baseline"
            baseline_summary = run_baseline(root, baseline)
            split = pd.read_csv(baseline / "split_assignments.csv")
            train_ids = split.loc[split["split"] == "train", "sample_id"].tolist()
            output = root / "tree"
            with patch("src.train_model.fit_decision_tree", wraps=fit_decision_tree) as fit, patch(
                "src.compressors.compress_data", side_effect=AssertionError("must not compress")
            ):
                summary = run_decision_tree(root, baseline, output)
            self.assertEqual(fit.call_count, len(MODE_NAMES))
            for call in fit.call_args_list:
                self.assertEqual(call.args[0].index.tolist(), train_ids)
                self.assertEqual(call.args[0].columns.tolist(), list(FEATURE_NAMES))
                self.assertEqual(call.args[1], ["gzip"] * len(train_ids))
            self.assertEqual((baseline / "split_assignments.csv").read_bytes(),
                             (output / "split_assignments.csv").read_bytes())
            self.assertEqual(summary["input_features"], list(FEATURE_NAMES))
            predictions = pd.read_csv(output / "test_predictions.csv")
            importance = pd.read_csv(output / "feature_importance.csv")
            self.assertEqual(len(importance), 3 * len(FEATURE_NAMES))
            self.assertTrue(importance["importance"].eq(0).all())  # Single training class.
            for mode in MODE_NAMES:
                with (output / f"decision_tree_{mode}.pkl").open("rb") as stream:
                    tree = pickle.load(stream)
                rows = predictions.loc[predictions["mode"] == mode]
                self.assertEqual(tree.classes_.tolist(), ["gzip"])
                self.assertEqual(tree.predict(rows[list(FEATURE_NAMES)]).tolist(), rows["predicted_algorithm"].tolist())
                self.assertTrue(rows["prediction_confidence"].eq(1).all())
                self.assertTrue(rows["probability_bz2"].eq(0).all())
                self.assertTrue(rows["correct"].eq(False).all())  # Test-only bz2 must remain unseen.
            comparison = pd.read_csv(output / "strategy_comparison.csv")
            self.assertEqual(len(comparison), 3 * 7)
            self.assertTrue(comparison.loc[comparison["strategy"] == "oracle", "mean_regret"].eq(0).all())
            repeated = root / "tree_repeat"
            run_decision_tree(root, baseline, repeated)
            for name in summary["output_sha256"]:
                self.assertEqual((output / name).read_bytes(), (repeated / name).read_bytes())
            for name, digest in baseline_summary["output_sha256"].items():
                self.assertEqual(hashlib.sha256((baseline / name).read_bytes()).hexdigest(), digest)
            with self.assertRaises(FileExistsError):
                run_decision_tree(root, baseline, output)

    def test_changed_baseline_split_is_rejected_before_training(self):
        for update_hash in (False, True):
            with self.subTest(update_hash=update_hash), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root)
                baseline = root / "baseline"
                run_baseline(root, baseline)
                path = baseline / "split_assignments.csv"
                splits = pd.read_csv(path)
                splits.loc[0, "split"] = "test" if splits.loc[0, "split"] == "train" else "train"
                splits.to_csv(path, index=False)
                if update_hash:
                    summary_path = baseline / "baseline_summary.json"
                    summary = json.loads(summary_path.read_text())
                    summary["output_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                    summary_path.write_text(json.dumps(summary), encoding="utf-8")
                with patch("src.train_model.fit_decision_tree", side_effect=AssertionError("must not fit")):
                    with self.assertRaisesRegex(ValueError, "Baseline (artifact hash|split assignments)"):
                        run_decision_tree(root, baseline, root / "tree")
                self.assertFalse((root / "tree").exists())

    def test_cli_requires_baseline_and_runs_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            baseline = root / "baseline"
            run_baseline(root, baseline)
            args = ["--model", "decision_tree", "--experiment-dir", str(root),
                    "--output-dir", str(root / "tree")]
            with self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(main([*args, "--baseline-dir", str(baseline)]), 0)
            summary = json.loads((root / "tree/decision_tree_summary.json").read_text())
            self.assertEqual(summary["model_settings"], settings())


if __name__ == "__main__":
    unittest.main()
