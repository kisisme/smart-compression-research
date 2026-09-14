"""Random Forest tests; controlled fixtures are not research measurements."""

import hashlib
import json
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.feature_extractor import FEATURE_NAMES
from src.scoring import ALGORITHMS, MODE_NAMES
from src.train_model import fit_random_forest, run_baseline, run_random_forest, main
from test_train_model import ROOT, fixture


def settings():
    return json.loads((ROOT / "config/experiment_config.json").read_text(encoding="utf-8"))["random_forest"]


class RandomForestTests(unittest.TestCase):
    def test_learns_features_reproducibly_and_probabilities_are_tree_means(self):
        features = pd.DataFrame(0.0, index=range(40), columns=FEATURE_NAMES)
        features["entropy"] = [0.1] * 20 + [7.9] * 20
        labels = ["gzip"] * 20 + ["zstd"] * 20
        forest = fit_random_forest(features, labels, settings())
        repeated = fit_random_forest(features, labels, settings())
        self.assertEqual(forest.predict(features).tolist(), labels)
        np.testing.assert_array_equal(forest.predict_proba(features), repeated.predict_proba(features))
        mean_probability = np.mean([t.predict_proba(features.to_numpy()) for t in forest.estimators_], axis=0)
        np.testing.assert_allclose(forest.predict_proba(features), mean_probability)
        self.assertEqual(forest.feature_names_in_.tolist(), list(FEATURE_NAMES))
        self.assertEqual(forest.feature_importances_[FEATURE_NAMES.index("entropy")], 1)
        self.assertEqual(len(forest.estimators_), settings()["n_estimators"])
        for key, value in settings().items():
            self.assertEqual(forest.get_params()[key], value)
        for column in ("sample_id", "seed", "generator", "compression_ratio", "score_zstd"):
            with self.subTest(column=column), self.assertRaises(ValueError):
                fit_random_forest(features.assign(**{column: 1}), labels, settings())
        for invalid in (features.assign(entropy=float("nan")), features.assign(entropy=float("inf")),
                        features[list(reversed(FEATURE_NAMES))]):
            with self.assertRaises(ValueError):
                fit_random_forest(invalid, labels, settings())
        for state in (None, True, -1):
            with self.assertRaises(ValueError):
                fit_random_forest(features, labels, {**settings(), "random_state": state})
        with self.assertRaises(ValueError):
            fit_random_forest(features, labels[:-1], settings())

    def test_saved_split_training_only_missing_classes_roundtrip_and_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            baseline = root / "baseline"
            run_baseline(root, baseline)
            preserved = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
            split = pd.read_csv(baseline / "split_assignments.csv")
            train_ids = split.loc[split["split"] == "train", "sample_id"].tolist()
            output = root / "forest"
            with patch("src.train_model.fit_random_forest", wraps=fit_random_forest) as fit, patch(
                "src.compressors.compress_data", side_effect=AssertionError("must not compress")
            ):
                summary = run_random_forest(root, baseline, output)
            self.assertEqual(fit.call_count, len(MODE_NAMES))
            for call in fit.call_args_list:
                self.assertEqual(call.args[0].index.tolist(), train_ids)
                self.assertEqual(call.args[0].columns.tolist(), list(FEATURE_NAMES))
                self.assertEqual(call.args[1], ["gzip"] * len(train_ids))
            self.assertEqual((baseline / "split_assignments.csv").read_bytes(),
                             (output / "split_assignments.csv").read_bytes())
            predictions = pd.read_csv(output / "test_predictions.csv")
            importance = pd.read_csv(output / "feature_importance.csv")
            self.assertEqual(len(importance), len(MODE_NAMES) * len(FEATURE_NAMES))
            self.assertTrue(importance["importance"].eq(0).all())
            for mode in MODE_NAMES:
                forest = pickle.loads((output / f"random_forest_{mode}.pkl").read_bytes())
                rows = predictions.loc[predictions["mode"] == mode]
                self.assertEqual(forest.classes_.tolist(), ["gzip"])
                self.assertEqual(forest.predict(rows[list(FEATURE_NAMES)]).tolist(), rows["predicted_algorithm"].tolist())
                self.assertTrue(rows["prediction_confidence"].eq(1).all())
                self.assertTrue(rows["correct"].eq(False).all())  # Test-only bz2 must remain unseen.
                self.assertEqual(summary["models"][mode]["estimator_count"], settings()["n_estimators"])
                for algorithm in ALGORITHMS:
                    self.assertTrue(rows[f"probability_{algorithm}"].eq(1 if algorithm == "gzip" else 0).all())
            comparisons = pd.read_csv(output / "strategy_comparison.csv")
            self.assertEqual(set(comparisons["strategy"]), {*ALGORITHMS, "baseline", "oracle", "random_forest"})
            self.assertTrue(comparisons.loc[comparisons["strategy"] == "oracle", "mean_regret"].eq(0).all())
            self.assertEqual(len(pd.read_csv(output / "confusion_matrix.csv")), len(MODE_NAMES) * len(ALGORITHMS)**2)
            self.assertEqual(len(pd.read_csv(output / "misclassified_samples.csv")), len(predictions))
            self.assertTrue(all(m["accuracy"] == 0 and m["macro_f1"] == 0 for m in summary["metrics"]))
            run_random_forest(root, baseline, root / "repeat")
            for name, digest in summary["output_sha256"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
                self.assertEqual((output / name).read_bytes(), (root / "repeat" / name).read_bytes())
            for path, digest in preserved.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            with self.assertRaises(FileExistsError):
                run_random_forest(root, baseline, output)

    def test_changed_split_or_scores_rejected_before_training(self):
        for problem in ("split_hash", "split_assignment", "scores"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root)
                baseline = root / "baseline"
                run_baseline(root, baseline)
                if problem == "scores":
                    path = root / "selection_labels.csv"
                    rows = pd.read_csv(path)
                    for column in ("best_score", *(f"score_{a}" for a in ALGORITHMS)):
                        rows[column] += 1
                    rows.to_csv(path, index=False)
                else:
                    path = baseline / "split_assignments.csv"
                    rows = pd.read_csv(path)
                    rows.loc[0, "split"] = "test" if rows.loc[0, "split"] == "train" else "train"
                    rows.to_csv(path, index=False)
                    if problem == "split_assignment":
                        summary_path = baseline / "baseline_summary.json"
                        summary = json.loads(summary_path.read_text())
                        summary["output_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                        summary_path.write_text(json.dumps(summary), encoding="utf-8")
                with patch("src.train_model.fit_random_forest", side_effect=AssertionError("must not fit")):
                    with self.assertRaises(ValueError):
                        run_random_forest(root, baseline, root / "forest")
                self.assertFalse((root / "forest").exists())

    def test_cli_requires_baseline_and_runs_forest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            baseline = root / "baseline"
            run_baseline(root, baseline)
            args = ["--model", "random_forest", "--experiment-dir", str(root),
                    "--output-dir", str(root / "forest")]
            with self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(main([*args, "--baseline-dir", str(baseline)]), 0)
            summary = json.loads((root / "forest/random_forest_summary.json").read_text())
            self.assertEqual(summary["model_settings"], settings())


if __name__ == "__main__":
    unittest.main()
