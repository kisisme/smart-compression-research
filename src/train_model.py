"""Train and evaluate protocol-v2 majority, Decision Tree, and Random Forest models."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import pickle
import re
import tempfile

import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.ensemble import RandomForestClassifier

from src.analysis import METRIC_NAMES, _read_exact_csv, _sha256, _validate_inputs
from src.data_generator import GENERATOR_NAMES
from src.experiment_runner import (
    COMPRESSION_RESULT_FIELDS, SAMPLE_FIELDS,
    _direct_dependency_versions, _git_information,
)
from src.feature_extractor import FEATURE_NAMES
from src.scoring import ALGORITHMS, MODE_NAMES, MODE_WEIGHTS, score_sample
from src.selection_labels import SELECTION_LABEL_FIELDS


_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "experiment_config.json"


def split_samples(samples: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """Split once without using labels; identical seeds stay on the same side."""
    if settings.get("group_column") != "seed":
        raise ValueError("Baseline group_column must be seed for synthetic data")
    fraction = settings.get("test_size")
    state = settings.get("random_state")
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
        raise ValueError("Baseline test_size must be numeric")
    if not 0 < fraction < 1:
        raise ValueError("Baseline test_size must be between zero and one")
    if isinstance(state, bool) or not isinstance(state, int) or not 0 <= state < 2**32:
        raise ValueError("Baseline random_state must be an integer in [0, 2**32)")
    split = samples[["sample_id", "seed"]].sort_values("sample_id").reset_index(drop=True)
    if split["sample_id"].eq("").any() or split["sample_id"].duplicated().any():
        raise ValueError("Empty or duplicate sample_id in split input")
    # Parse integer text exactly: do not merge distinct seeds through float rounding.
    if not split["seed"].map(lambda v: bool(re.fullmatch(r"[+-]?\d+", str(v)))).all():
        raise ValueError("Every seed must be an integer")
    split["seed"] = split["seed"].map(int)
    if split["seed"].nunique() < 2:
        raise ValueError("At least two seed groups are required")
    splitter = GroupShuffleSplit(n_splits=1, test_size=float(fraction), random_state=state)
    train, test = next(splitter.split(split, groups=split["seed"]))
    split["split"] = "train"
    split.loc[test, "split"] = "test"
    if set(split.loc[train, "seed"]) & set(split.loc[test, "seed"]):
        raise RuntimeError("Train/test seed groups overlap")
    return split


def fit_majority(training_labels: list[str]) -> dict[str, object]:
    """Fit a constant predictor using only training labels; ties use ALGORITHMS order."""
    if not training_labels or not set(training_labels) <= set(ALGORITHMS):
        raise ValueError("Training labels must be non-empty supported algorithms")
    counts = Counter(training_labels)
    return {
        "algorithm": max(ALGORITHMS, key=lambda a: counts[a]),
        "training_label_counts": {a: counts[a] for a in ALGORITHMS},
    }


def classification_metrics(truth: list[str], prediction: list[str]) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(truth, prediction)),
        "macro_f1": float(f1_score(
            truth, prediction, labels=list(ALGORITHMS), average="macro", zero_division=0,
        )),
    }


def _validate_scores(results: pd.DataFrame, labels: pd.DataFrame) -> None:
    indexed = labels.set_index(["sample_id", "mode"])
    for sample_id, rows in results.groupby("sample_id", sort=False):
        selections = score_sample(rows.to_dict("records"))
        for mode, selection in selections.items():
            label = indexed.loc[(sample_id, mode)]
            if label["best_algorithm"] != selection.best_algorithm:
                raise ValueError(f"Recomputed best_algorithm mismatch: {sample_id}/{mode}")
            for algorithm, score in selection.scores.items():
                if not math.isclose(label[f"score_{algorithm}"], score, rel_tol=1e-12, abs_tol=1e-15):
                    raise ValueError(f"Recomputed score mismatch: {sample_id}/{mode}/{algorithm}")


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, encoding="utf-8", float_format="%.17g")


def _validate_training_inputs(features: pd.DataFrame, labels: list[str], settings: dict) -> None:
    """Require pre-compression features and a recorded deterministic seed."""
    if list(features.columns) != list(FEATURE_NAMES):
        raise ValueError("Model requires exactly the ordered protocol features")
    if not np.isfinite(features.to_numpy(dtype=float)).all():
        raise ValueError("Model features must be finite")
    if not labels or not set(labels) <= set(ALGORITHMS):
        raise ValueError("Model labels must be supported algorithms")
    if len(features) != len(labels):
        raise ValueError("Training feature and label counts differ")
    state = settings.get("random_state")
    if isinstance(state, bool) or not isinstance(state, int) or not 0 <= state < 2**32:
        raise ValueError("Model random_state must be a fixed integer")


def fit_decision_tree(features: pd.DataFrame, labels: list[str], settings: dict) -> DecisionTreeClassifier:
    """Fit on explicitly selected training features only, without evaluation data."""
    _validate_training_inputs(features, labels, settings)
    return DecisionTreeClassifier(**settings).fit(features, labels)


def fit_random_forest(features: pd.DataFrame, labels: list[str], settings: dict) -> RandomForestClassifier:
    """Fit a fresh forest on training features and labels only."""
    _validate_training_inputs(features, labels, settings)
    return RandomForestClassifier(**settings).fit(features, labels)


def _baseline_reference(directory: Path, input_hashes: dict, config: dict,
                        expected_splits: pd.DataFrame) -> tuple[dict, pd.DataFrame, dict]:
    """Require the original baseline data, scoring definition, and split assignments."""
    summary_path = directory / "baseline_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["input_sha256"] != input_hashes:
        raise ValueError("Baseline input hashes differ from current experiment")
    if summary["split_settings"] != config["baseline"] or summary["selection_modes"] != config["selection_modes"]:
        raise ValueError("Baseline split/scoring settings differ from current config")
    if summary["macro_f1_labels"] != list(ALGORITHMS) or summary["zero_division"] != 0:
        raise ValueError("Baseline metric definition differs")
    hashes = {"baseline_summary.json": _sha256(summary_path)}
    for name, digest in summary["output_sha256"].items():
        if Path(name).name != name or _sha256(directory / name) != digest:
            raise ValueError(f"Baseline artifact hash mismatch: {name}")
        hashes[name] = digest
    if "split_assignments.csv" not in hashes:
        raise ValueError("Baseline split hash is missing")
    splits = _read_exact_csv(directory / "split_assignments.csv",
                             ("sample_id", "seed", "split"), "baseline split")
    splits["seed"] = splits["seed"].map(int)
    if not splits.equals(expected_splits):
        raise ValueError("Baseline split assignments differ from configured group split")
    return summary, splits, hashes


def _run_model(experiment_dir: str | Path, output_dir: str | Path, *,
               model_kind: str = "baseline", baseline_dir: str | Path | None = None) -> dict:
    """Share validation and evaluation so all models use the same definitions."""
    source = Path(experiment_dir)
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"Evaluation output already exists: {destination}")
    if model_kind not in ("baseline", "decision_tree", "random_forest"):
        raise ValueError("Unsupported model kind")
    uses_features = model_kind != "baseline"
    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    if config["selection_modes"] != MODE_WEIGHTS:
        raise ValueError("Loaded scoring weights differ from the current config")
    paths = {name: source / name for name in (
        "samples.csv", "compression_results.csv", "selection_labels.csv", "experiment_metadata.json",
    )}
    input_hashes = {name: _sha256(path) for name, path in paths.items()}
    metadata = json.loads(paths["experiment_metadata.json"].read_text(encoding="utf-8"))
    for name in ("samples.csv", "compression_results.csv"):
        if metadata["output_files"][name]["sha256"] != input_hashes[name]:
            raise ValueError(f"Experiment metadata hash mismatch: {name}")
    for recorded, current in (
        ("compression_settings", "compression"), ("timing", "timing"), ("feature_settings", "features"),
    ):
        if metadata[recorded] != config[current]:
            raise ValueError(f"Experiment/config mismatch: {recorded}")
    samples = _read_exact_csv(paths["samples.csv"], SAMPLE_FIELDS, "samples")
    results = _read_exact_csv(paths["compression_results.csv"], COMPRESSION_RESULT_FIELDS, "results")
    labels = _read_exact_csv(paths["selection_labels.csv"], SELECTION_LABEL_FIELDS, "labels")
    if not samples["generator"].isin(GENERATOR_NAMES).all():
        raise ValueError("Seed grouping currently supports only the synthetic generators")
    splits = split_samples(samples, config["baseline"])
    # Match scoring.py's Python float parser. pandas.to_numeric can truncate
    # small decimal ratios, changing their logarithmic relative losses.
    for frame, columns in (
        (samples, tuple(n for n in FEATURE_NAMES if n not in
                        ("file_size", "unique_byte_count", "max_run_length"))),
        (results, METRIC_NAMES),
        (labels, ("best_score", *(f"score_{a}" for a in ALGORITHMS))),
    ):
        for column in columns:
            frame[column] = frame[column].map(float)
    _validate_inputs(samples, results, labels)
    _validate_scores(results, labels)
    if len(samples) != metadata["sample_count"] or len(results) != metadata["compression_result_count"]:
        raise ValueError("Experiment metadata row counts do not match CSVs")
    if metadata["verification_failure_count"] != 0:
        raise ValueError("Experiment metadata reports verification failures")

    reference, reference_hashes = None, {}
    if uses_features:
        if baseline_dir is None:
            raise ValueError("Feature model evaluation requires a saved baseline directory")
        reference, splits, reference_hashes = _baseline_reference(
            Path(baseline_dir), input_hashes, config, splits,
        )

    train_ids = splits.loc[splits["split"].eq("train"), "sample_id"].tolist()
    test_ids = splits.loc[splits["split"].eq("test"), "sample_id"].tolist()
    measurements = results.set_index(["sample_id", "algorithm"])
    models, metrics, confusion, predictions, comparisons = {}, [], [], [], []
    majority_models, trees, importance_rows = {}, {}, []
    features = samples.set_index("sample_id").loc[:, list(FEATURE_NAMES)]
    for mode in MODE_NAMES:
        mode_labels = labels.loc[labels["mode"].eq(mode)].set_index("sample_id")
        model = fit_majority(mode_labels.loc[train_ids, "best_algorithm"].tolist())
        majority_models[mode] = model
        if reference is not None and model != reference["models"][mode]:
            raise ValueError(f"Recomputed training baseline differs: {mode}")
        models[mode] = model
        test_labels = mode_labels.loc[test_ids]
        truth = test_labels["best_algorithm"].tolist()
        prediction = [model["algorithm"]] * len(test_ids)
        probability_rows = [{} for _ in test_ids]
        if uses_features:
            fit_model = fit_decision_tree if model_kind == "decision_tree" else fit_random_forest
            tree = fit_model(
                features.loc[train_ids], mode_labels.loc[train_ids, "best_algorithm"].tolist(),
                config[model_kind],
            )
            trees[mode] = tree
            prediction = tree.predict(features.loc[test_ids]).tolist()
            probabilities = tree.predict_proba(features.loc[test_ids])
            class_indices = {str(a): i for i, a in enumerate(tree.classes_)}
            probability_rows = [
                {"prediction_confidence": float(row.max()),
                 **{f"probability_{a}": float(row[class_indices[a]]) if a in class_indices else 0.0
                    for a in ALGORITHMS}}
                for row in probabilities
            ]
            models[mode] = {
                "model_file": f"{model_kind}_{mode}.pkl", "classes": tree.classes_.tolist(),
                "parameters": tree.get_params(),
                "training_label_counts": model["training_label_counts"],
                "training_metrics": classification_metrics(
                    mode_labels.loc[train_ids, "best_algorithm"].tolist(),
                    tree.predict(features.loc[train_ids]).tolist(),
                ),
            }
            if model_kind == "decision_tree":
                models[mode].update(depth=int(tree.get_depth()), leaf_count=int(tree.get_n_leaves()))
            else:
                models[mode].update(
                    estimator_count=len(tree.estimators_),
                    tree_depths=[int(t.get_depth()) for t in tree.estimators_],
                    tree_leaf_counts=[int(t.get_n_leaves()) for t in tree.estimators_],
                )
            importance_rows.extend(
                {"mode": mode, "feature": name, "importance": float(value)}
                for name, value in zip(FEATURE_NAMES, tree.feature_importances_, strict=True)
            )
        metrics.append({
            "mode": mode, "algorithm": model["algorithm"] if model_kind == "baseline" else model_kind,
            "train_count": len(train_ids), "test_count": len(test_ids),
            **classification_metrics(truth, prediction),
        })
        matrix = confusion_matrix(truth, prediction, labels=list(ALGORITHMS))
        for i, actual in enumerate(ALGORITHMS):
            for j, predicted in enumerate(ALGORITHMS):
                confusion.append({"mode": mode, "true_algorithm": actual,
                                  "predicted_algorithm": predicted, "count": int(matrix[i, j])})
        for sample_id, actual, predicted, probability in zip(test_ids, truth, prediction, probability_rows, strict=True):
            row = test_labels.loc[sample_id]
            predictions.append({
                "sample_id": sample_id, "mode": mode, "true_algorithm": actual,
                "predicted_algorithm": predicted, "correct": actual == predicted,
                "predicted_score": row[f"score_{predicted}"], "oracle_score": row["best_score"],
                "regret": row[f"score_{predicted}"] - row["best_score"],
                **probability,
            })
        strategies = (*ALGORITHMS, "baseline", "oracle")
        if uses_features:
            strategies = (*strategies, model_kind)
        for strategy in strategies:
            if strategy == "oracle":
                chosen = truth
            elif uses_features and strategy == model_kind:
                chosen = prediction
            else:
                chosen = [model["algorithm"] if strategy == "baseline" else strategy] * len(test_ids)
            measured = [measurements.loc[(sid, a)] for sid, a in zip(test_ids, chosen, strict=True)]
            scores = [test_labels.loc[sid, f"score_{a}"] for sid, a in zip(test_ids, chosen, strict=True)]
            comparisons.append({
                "mode": mode, "strategy": strategy, "test_count": len(test_ids),
                **classification_metrics(truth, chosen),
                **{f"mean_{metric}": math.fsum(float(row[metric]) for row in measured) / len(measured)
                   for metric in METRIC_NAMES},
                "mean_score": math.fsum(scores) / len(scores),
                "mean_regret": math.fsum(s - b for s, b in zip(scores, test_labels["best_score"], strict=True)) / len(scores),
            })

    prediction_frame = pd.DataFrame(predictions).merge(
        samples[["sample_id", "generator", "seed", "size", *FEATURE_NAMES]],
        on="sample_id", validate="many_to_one",
    )
    summary = {
        f"{model_kind}_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_settings": config["baseline"], "split_method": "GroupShuffleSplit",
        "test_size_unit": "unique seed groups, rounded up", "sample_order": "sample_id ascending",
        "sample_count": len(samples), "train_count": len(train_ids), "test_count": len(test_ids),
        "train_group_count": int(splits.loc[splits["split"].eq("train"), "seed"].nunique()),
        "test_group_count": int(splits.loc[splits["split"].eq("test"), "seed"].nunique()),
        "algorithms": list(ALGORITHMS), "selection_modes": config["selection_modes"],
        "majority_tie_break": list(ALGORITHMS), "macro_f1_labels": list(ALGORITHMS), "zero_division": 0,
        "feature_importance": None,
        "feature_importance_reason": "Constant majority baseline does not use input features.",
        "metrics": metrics, "models": models,
        "test_label_counts": {m: {a: int(((labels["mode"] == m) & labels["sample_id"].isin(test_ids)
                                        & (labels["best_algorithm"] == a)).sum()) for a in ALGORITHMS} for m in MODE_NAMES},
        "input_sha256": input_hashes, "config_sha256": _sha256(_CONFIG_PATH),
        "source_sha256": {str(p.relative_to(_ROOT)).replace("\\", "/"): _sha256(p)
                          for p in sorted((_ROOT / "src").glob("*.py"))},
        "git": _git_information(), "python_version": platform.python_version(),
        "package_versions": _direct_dependency_versions(), "operating_system": platform.platform(),
        "measurement_metadata": metadata,
        "limitations": ["Synthetic Pilot evaluation; not a final unseen-file evaluation.",
                        "Seed grouping does not detect similarity across different seeds.",
                        "Stored algorithm times exclude feature extraction and prediction overhead."],
    }
    if uses_features:
        summary.update({
            "feature_importance": "feature_importance.csv",
            "feature_importance_reason": "Normalized training impurity reduction (MDI), not a causal explanation.",
            "input_features": list(FEATURE_NAMES), "model_settings": config[model_kind],
            "baseline_reference_sha256": reference_hashes,
            "prediction_confidence_definition": (
                "Maximum uncalibrated leaf class proportion from predict_proba."
                if model_kind == "decision_tree" else
                "Maximum of mean per-tree leaf class probabilities; uncalibrated predict_proba."
            ),
            "hyperparameter_selection": (
                "Fixed configuration; no test-based tuning, reweighting, or resampling."
                if model_kind == "decision_tree" else
                "Fixed configuration; standard training bootstrap only; no test-based tuning or class balancing."
            ),
            "prediction_tie_break": "First maximum in fitted sklearn classes_ order.",
        })
    # Detect changed inputs before publishing; never overwrite existing results.
    if any(_sha256(path) != input_hashes[name] for name, path in paths.items()):
        raise RuntimeError("Experiment input changed during evaluation")
    if any(_sha256(Path(baseline_dir) / name) != digest for name, digest in reference_hashes.items()):
        raise RuntimeError("Baseline reference changed during evaluation")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{model_kind}_", dir=destination.parent) as temporary:
        output = Path(temporary) / "artifacts"
        output.mkdir()
        _write_frame(output / "split_assignments.csv", splits)
        _write_frame(output / "metrics.csv", pd.DataFrame(metrics))
        _write_frame(output / "confusion_matrix.csv", pd.DataFrame(confusion))
        _write_frame(output / "test_predictions.csv", prediction_frame)
        _write_frame(output / "misclassified_samples.csv", prediction_frame.loc[~prediction_frame["correct"]])
        _write_frame(output / "strategy_comparison.csv", pd.DataFrame(comparisons))
        (output / "baseline_models.json").write_text(json.dumps(majority_models, indent=2) + "\n", encoding="utf-8")
        if uses_features:
            _write_frame(output / "feature_importance.csv", pd.DataFrame(importance_rows))
            for mode, tree in trees.items():
                model_path = output / f"{model_kind}_{mode}.pkl"
                model_path.write_bytes(pickle.dumps(tree, protocol=pickle.HIGHEST_PROTOCOL))
                # Load only the model just written by this process and check round-trip predictions.
                restored = pickle.loads(model_path.read_bytes())
                test_features = features.loc[test_ids]
                if not np.array_equal(restored.predict(test_features), tree.predict(test_features)) or not np.array_equal(
                    restored.predict_proba(test_features), tree.predict_proba(test_features)
                ):
                    raise RuntimeError(f"Serialized model prediction mismatch: {mode}")
                if model_kind == "decision_tree":
                    (output / f"decision_tree_{mode}_rules.txt").write_text(
                        export_text(tree, feature_names=list(FEATURE_NAMES),
                                    max_depth=max(1, tree.get_depth()), decimals=10, show_weights=True),
                        encoding="utf-8",
                    )
        summary["output_sha256"] = {p.name: _sha256(p) for p in sorted(output.iterdir())}
        (output / f"{model_kind}_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8",
        )
        output.rename(destination)
    return summary


def run_baseline(experiment_dir: str | Path, output_dir: str | Path) -> dict:
    return _run_model(experiment_dir, output_dir)


def run_decision_tree(experiment_dir: str | Path, baseline_dir: str | Path,
                      output_dir: str | Path) -> dict:
    return _run_model(experiment_dir, output_dir, model_kind="decision_tree", baseline_dir=baseline_dir)


def run_random_forest(experiment_dir: str | Path, baseline_dir: str | Path,
                      output_dir: str | Path) -> dict:
    return _run_model(experiment_dir, output_dir, model_kind="random_forest", baseline_dir=baseline_dir)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", choices=("baseline", "decision_tree", "random_forest"), default="baseline")
    parser.add_argument("--baseline-dir", type=Path)
    args = parser.parse_args(arguments)
    if args.model != "baseline" and args.baseline_dir is None:
        parser.error(f"--model {args.model} requires --baseline-dir")
    summary = _run_model(args.experiment_dir, args.output_dir,
                         model_kind=args.model, baseline_dir=args.baseline_dir)
    print(json.dumps({"output_dir": str(args.output_dir), "metrics": summary["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
