"""Audit and explain saved Pilot prediction errors without fitting or compressing."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import tempfile

import numpy as np
import pandas as pd

from src.analysis import METRIC_NAMES, _read_exact_csv, _sha256, _validate_inputs
from src.experiment_runner import COMPRESSION_RESULT_FIELDS, SAMPLE_FIELDS, _direct_dependency_versions, _git_information
from src.feature_extractor import FEATURE_NAMES
from src.scoring import ALGORITHMS, MODE_NAMES, MODE_WEIGHTS, calculate_relative_losses
from src.selection_labels import SELECTION_LABEL_FIELDS
from src.train_model import _baseline_reference, _validate_scores, _write_frame, classification_metrics, fit_majority, split_samples


ROOT = Path(__file__).resolve().parent.parent
MODEL_NAMES = ("baseline", "decision_tree", "random_forest")
PREDICTION_FIELDS = ("sample_id", "mode", "true_algorithm", "predicted_algorithm", "correct",
                     "predicted_score", "oracle_score", "regret")
PROBABILITY_FIELDS = ("prediction_confidence", *(f"probability_{a}" for a in ALGORITHMS))
SAMPLE_CONTEXT = ("generator", "seed", "size", *FEATURE_NAMES)
COMPONENTS = ("size", "compression", "decompression")
WEIGHTS = ("compression_ratio", "compression_time", "decompression_time")
LOSSES = ("relative_size_loss", "relative_compression_loss", "relative_decompression_loss")


def _close(actual, expected, name):
    if not math.isfinite(float(actual)) or not math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-15):
        raise ValueError(f"Saved {name} mismatch")


def _evaluation(source, kind, raw_hashes, config, splits, tracked):
    directory = source / kind
    path = directory / f"{kind}_summary.json"
    tracked[path] = _sha256(path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    if summary["input_sha256"] != raw_hashes:
        raise ValueError(f"{kind} input hashes differ")
    if summary["selection_modes"] != config["selection_modes"] or summary["split_settings"] != config["baseline"]:
        raise ValueError(f"{kind} scoring/split settings differ")
    if summary["macro_f1_labels"] != list(ALGORITHMS) or summary["zero_division"] != 0:
        raise ValueError(f"{kind} metric definition differs")
    if kind != "baseline" and (summary["model_settings"] != config[kind] or summary["input_features"] != list(FEATURE_NAMES)):
        raise ValueError(f"{kind} model definition differs")
    required = {"test_predictions.csv", "split_assignments.csv", "misclassified_samples.csv"}
    if not required <= set(summary["output_sha256"]):
        raise ValueError(f"{kind} missing required output hashes")
    for name, digest in summary["output_sha256"].items():
        if Path(name).name != name or _sha256(directory / name) != digest:
            raise ValueError(f"{kind} output hash mismatch: {name}")
        tracked[directory / name] = digest
    actual = _read_exact_csv(directory / "split_assignments.csv", ("sample_id", "seed", "split"), "split")
    actual["seed"] = actual["seed"].map(int)
    if not actual.equals(splits):
        raise ValueError(f"{kind} split differs")
    fields = (*PREDICTION_FIELDS, *(PROBABILITY_FIELDS if kind != "baseline" else ()), *SAMPLE_CONTEXT)
    predictions = _read_exact_csv(directory / "test_predictions.csv", fields, "predictions")
    return summary, predictions


def build_tables(samples, results, labels, splits, evaluations):
    """Recompute correctness, regret and signed contributions from audited sources."""
    sample_index = samples.set_index("sample_id")
    label_index = labels.set_index(["sample_id", "mode"])
    measurements = results.set_index(["sample_id", "algorithm"])
    train_ids = splits.loc[splits["split"].eq("train"), "sample_id"].tolist()
    test_ids = splits.loc[splits["split"].eq("test"), "sample_id"].tolist()
    expected_keys = {(sid, mode) for sid in test_ids for mode in MODE_NAMES}
    training = sample_index.loc[train_ids]
    losses = {sid: calculate_relative_losses(rows.to_dict("records")) for sid, rows in results.groupby("sample_id")}
    label_counts, majority = [], {}
    for mode in MODE_NAMES:
        train_labels = label_index.loc[[(sid, mode) for sid in train_ids], "best_algorithm"].tolist()
        majority[mode] = fit_majority(train_labels)["algorithm"]
        for split_name, ids in (("train", train_ids), ("test", test_ids)):
            counts = label_index.loc[[(sid, mode) for sid in ids], "best_algorithm"].value_counts()
            for algorithm in ALGORITHMS:
                count = int(counts.get(algorithm, 0))
                label_counts.append(dict(mode=mode, split=split_name, algorithm=algorithm, count=count,
                                         sample_count=len(ids), fraction=count / len(ids)))
    records = []
    for kind, (summary, predictions) in evaluations.items():
        if predictions[["sample_id", "mode"]].duplicated().any() or set(zip(predictions["sample_id"], predictions["mode"])) != expected_keys:
            raise ValueError(f"{kind} prediction keys differ from test split")
        for row in predictions.to_dict("records"):
            sid, mode, predicted = row["sample_id"], row["mode"], row["predicted_algorithm"]
            if predicted not in ALGORITHMS:
                raise ValueError("Unsupported predicted algorithm")
            sample, label = sample_index.loc[sid], label_index.loc[(sid, mode)]
            truth = label["best_algorithm"]
            correct = predicted == truth
            regret = label[f"score_{predicted}"] - label["best_score"]
            if row["true_algorithm"] != truth or row["correct"] != str(correct):
                raise ValueError("Saved truth/correctness mismatch")
            for column, expected in (("predicted_score", label[f"score_{predicted}"]), ("oracle_score", label["best_score"]), ("regret", regret)):
                _close(row[column], expected, column)
            if row["generator"] != sample["generator"] or int(row["seed"]) != int(sample["seed"]):
                raise ValueError("Saved generator/seed mismatch")
            for column in ("size", *FEATURE_NAMES):
                _close(row[column], sample[column], column)
            confidence = ""  # Not applicable for the majority baseline, not a measured zero.
            if kind == "baseline":
                if predicted != majority[mode]:
                    raise ValueError("Baseline prediction differs from training majority")
            else:
                probabilities = [float(row[f"probability_{a}"]) for a in ALGORITHMS]
                if not all(math.isfinite(p) and 0 <= p <= 1 for p in probabilities):
                    raise ValueError("Invalid prediction probability")
                _close(sum(probabilities), 1, "probability sum")
                _close(row[f"probability_{predicted}"], max(probabilities), "predicted probability")
                _close(row["prediction_confidence"], max(probabilities), "confidence")
                confidence = float(row["prediction_confidence"])
            component = {f"{name}_regret": MODE_WEIGHTS[mode][weight] *
                         (losses[sid][predicted][loss] - losses[sid][truth][loss])
                         for name, weight, loss in zip(COMPONENTS, WEIGHTS, LOSSES)}
            _close(math.fsum(component.values()), regret, "regret decomposition")
            ordered_scores = sorted(float(label[f"score_{a}"]) for a in ALGORITHMS)
            baseline_correct = majority[mode] == truth
            records.append(dict(model=kind, sample_id=sid, mode=mode, true_algorithm=truth,
                                predicted_algorithm=predicted, correct=correct, regret=regret,
                                oracle_score=float(label["best_score"]), predicted_score=float(label[f"score_{predicted}"]),
                                oracle_margin=ordered_scores[1] - ordered_scores[0],
                                prediction_confidence=confidence, baseline_algorithm=majority[mode],
                                baseline_correct=baseline_correct, recovered_from_baseline=correct and not baseline_correct,
                                harmed_vs_baseline=not correct and baseline_correct,
                                **component, **{n: sample[n] for n in SAMPLE_CONTEXT},
                                generation_parameters=sample["generation_parameters"]))
        own = [r for r in records if r["model"] == kind]
        for metric in summary["metrics"]:
            subset = [r for r in own if r["mode"] == metric["mode"]]
            measured = classification_metrics([r["true_algorithm"] for r in subset], [r["predicted_algorithm"] for r in subset])
            for name, value in measured.items():
                _close(metric[name], value, f"{kind}/{name}")
    all_rows = pd.DataFrame(records)
    errors = all_rows.loc[~all_rows["correct"]].sort_values(["model", "mode", "regret", "sample_id"], ascending=[True, True, False, True])
    summaries, grouped, confidence_rows = [], [], []
    for (kind, mode), group in all_rows.groupby(["model", "mode"], sort=True):
        wrong = group.loc[~group["correct"]]
        summaries.append(dict(model=kind, mode=mode, test_count=len(group), error_count=len(wrong),
                              **classification_metrics(group["true_algorithm"].tolist(), group["predicted_algorithm"].tolist()),
                              mean_regret=float(group["regret"].mean()), max_regret=float(group["regret"].max()),
                              recovered_from_baseline=int(group["recovered_from_baseline"].sum()),
                              harmed_vs_baseline=int(group["harmed_vs_baseline"].sum())))
        for dimension in ("generator", "size"):
            for value, subgroup in group.groupby(dimension, sort=True):
                grouped.append(dict(model=kind, mode=mode, dimension=dimension, value=value,
                                    test_count=len(subgroup), error_count=int((~subgroup["correct"]).sum()),
                                    error_rate=float((~subgroup["correct"]).mean()), mean_regret=float(subgroup["regret"].mean())))
        if kind != "baseline":
            for status, subgroup in group.groupby("correct", sort=True):
                values = subgroup["prediction_confidence"].astype(float)
                confidence_rows.append(dict(model=kind, mode=mode, correct=bool(status), count=len(values),
                                            confidence_min=float(values.min()), confidence_mean=float(values.mean()),
                                            confidence_max=float(values.max()), confidence_equal_one_count=int(values.eq(1).sum())))
    context, algorithm_rows = [], []
    for sid, mode in sorted(set(zip(errors["sample_id"], errors["mode"]))):
        label = label_index.loc[(sid, mode)]
        for algorithm in ALGORITHMS:
            measured = measurements.loc[(sid, algorithm)]
            algorithm_rows.append(dict(sample_id=sid, mode=mode, algorithm=algorithm,
                                       original_size=int(measured["original_size"]), compressed_size=int(measured["compressed_size"]),
                                       **{n: float(measured[n]) for n in METRIC_NAMES},
                                       verified=measured["verified"], score=float(label[f"score_{algorithm}"]),
                                       **{f"{n}_score": MODE_WEIGHTS[mode][w] * losses[sid][algorithm][l]
                                          for n, w, l in zip(COMPONENTS, WEIGHTS, LOSSES)}))
    for sid in sorted(set(errors["sample_id"])):
        for feature in FEATURE_NAMES:
            value = float(sample_index.loc[sid, feature])
            values = training[feature].astype(float)
            context.append(dict(sample_id=sid, feature=feature, value=value, train_count=len(values),
                                train_min=float(values.min()), train_max=float(values.max()),
                                train_fraction_le_value=float(values.le(value).mean()),
                                outside_train_range=bool(value < values.min() or value > values.max())))
    return {
        "model_summary.csv": pd.DataFrame(summaries), "error_details.csv": errors,
        "grouped_error_rates.csv": pd.DataFrame(grouped), "label_distribution.csv": pd.DataFrame(label_counts),
        "confidence_summary.csv": pd.DataFrame(confidence_rows),
        "error_algorithm_metrics.csv": pd.DataFrame(algorithm_rows, columns=("sample_id", "mode", "algorithm", "original_size", "compressed_size", *METRIC_NAMES, "verified", "score", *(f"{n}_score" for n in COMPONENTS))),
        "error_feature_context.csv": pd.DataFrame(context, columns=("sample_id", "feature", "value", "train_count", "train_min", "train_max", "train_fraction_le_value", "outside_train_range")),
    }


def _table(frame, columns):
    def cell(value):
        return f"{value:.6f}" if isinstance(value, (float, np.floating)) else str(value)
    return "\n".join(["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |",
                      *("| " + " | ".join(cell(v) for v in row) + " |" for row in frame[columns].itertuples(index=False, name=None))])


def render_report(tables):
    errors = tables["error_details.csv"]
    sections = ["# Pilot 실패 사례 분석", "이 문서의 모든 표와 개수는 Python이 저장된 측정·예측 CSV에서 계산했다.",
                f"오분류는 model × sample × mode 기준 {len(errors)}행, 고유 sample은 {errors['sample_id'].nunique()}개이다.",
                "## 모델별 시험 결과", _table(tables["model_summary.csv"], ["model", "mode", "test_count", "error_count", "accuracy", "macro_f1", "mean_regret", "recovered_from_baseline", "harmed_vs_baseline"]),
                "## 학습·시험 정답 분포", _table(tables["label_distribution.csv"], ["mode", "split", "algorithm", "count", "sample_count"]),
                "## 모든 오분류", _table(errors, ["model", "sample_id", "mode", "generator", "size", "true_algorithm", "predicted_algorithm", "prediction_confidence", "regret", "oracle_margin"]),
                "## 오류가 발생한 generator·크기 그룹", "오류율의 분모는 해당 그룹의 전체 test sample 수이다. 오류가 없는 그룹도 CSV에는 보존한다.",
                _table(tables["grouped_error_rates.csv"].query("error_count > 0"), ["model", "mode", "dimension", "value", "test_count", "error_count", "error_rate"]),
                "## Confidence와 정오답", _table(tables["confidence_summary.csv"], ["model", "mode", "correct", "count", "confidence_min", "confidence_mean", "confidence_max", "confidence_equal_one_count"]),
                "## 오분류 손실의 지표별 기여", "각 항은 w × (예측 알고리즘의 로그 상대 손실 − oracle의 로그 상대 손실)이다. 음수는 그 지표에서 예측 알고리즘이 더 좋았다는 뜻이며, 세 항의 합은 regret이다.",
                _table(errors, ["model", "sample_id", "mode", "size_regret", "compression_regret", "decompression_regret", "regret"]),
                "## 특징과 해석 범위", "error_details.csv에는 실제 특징과 생성 매개변수를, error_feature_context.csv에는 오류 sample의 특징별 training 범위와 누적 비율을 기록했다. train_fraction_le_value는 training 값이 해당 값 이하인 비율이다. 범위 밖 여부나 누적 비율은 관찰이며 모델 판단의 인과적 설명이 아니다.",
                "oracle_margin은 실제 최저 점수와 두 번째 점수의 차이다. 현재 저장된 중앙값만으로 측정 변동, 통계적 유의성 또는 라벨 안정성을 판정할 수 없다. 낮은 margin을 이유로 sample을 제거하거나 정답을 바꾸지 않는다.",
                "Confidence는 보정되지 않은 모델 출력이다. baseline의 빈칸은 해당 없음이다. confidence=1인 오분류도 그대로 보존한다. Macro F1은 네 클래스를 고정하고 없는 클래스의 F1을 0으로 포함한다.",
                "이는 이미 사용한 합성 Pilot test의 사후 진단이다. 재학습·튜닝·압축 재측정을 수행하지 않았으며, 이 분석을 바탕으로 변경한 모델의 최종 성능은 별도 unseen 데이터에서 평가해야 한다. 기존 알고리즘 시간에는 특징 추출·예측 비용이 포함되지 않는다."]
    return "\n\n".join(sections) + "\n"


def run_failure_analysis(experiment_dir, output_dir):
    source, destination = Path(experiment_dir), Path(output_dir)
    if destination.exists():
        raise FileExistsError(f"Analysis output already exists: {destination}")
    config_path = ROOT / "config/experiment_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["selection_modes"] != MODE_WEIGHTS:
        raise ValueError("Loaded scoring settings differ")
    names = ("samples.csv", "compression_results.csv", "selection_labels.csv", "experiment_metadata.json")
    tracked = {source / n: _sha256(source / n) for n in names}
    raw_hashes = {n: tracked[source / n] for n in names}
    tracked[config_path] = _sha256(config_path)
    metadata = json.loads((source / "experiment_metadata.json").read_text(encoding="utf-8"))
    for n in names[:2]:
        if metadata["output_files"][n]["sha256"] != raw_hashes[n]:
            raise ValueError("Raw experiment hash mismatch")
    for old, new in (("compression_settings", "compression"), ("timing", "timing"), ("feature_settings", "features")):
        if metadata[old] != config[new]:
            raise ValueError("Experiment/config mismatch")
    samples = _read_exact_csv(source / names[0], SAMPLE_FIELDS, "samples")
    results = _read_exact_csv(source / names[1], COMPRESSION_RESULT_FIELDS, "results")
    labels = _read_exact_csv(source / names[2], SELECTION_LABEL_FIELDS, "labels")
    splits = split_samples(samples, config["baseline"])
    for frame, columns in ((samples, FEATURE_NAMES), (results, METRIC_NAMES), (labels, ("best_score", *(f"score_{a}" for a in ALGORITHMS)))):
        for column in columns:
            frame[column] = frame[column].map(float)
    _validate_inputs(samples, results, labels)
    _validate_scores(results, labels)
    if metadata["sample_count"] != len(samples) or metadata["compression_result_count"] != len(results) or metadata["verification_failure_count"] != 0:
        raise ValueError("Experiment metadata counts/failures differ")
    _baseline_reference(source / "baseline", raw_hashes, config, splits)
    evaluations = {kind: _evaluation(source, kind, raw_hashes, config, splits, tracked) for kind in MODEL_NAMES}
    tables = build_tables(samples, results, labels, splits, evaluations)
    summary = dict(analysis_version=1, created_at_utc=datetime.now(timezone.utc).isoformat(), git=_git_information(),
                   python_version=platform.python_version(), package_versions=_direct_dependency_versions(), operating_system=platform.platform(),
                   sample_count=len(samples), test_count=int(splits["split"].eq("test").sum()),
                   error_row_count=len(tables["error_details.csv"]), unique_error_samples=int(tables["error_details.csv"]["sample_id"].nunique()),
                   source_sha256={str(p.relative_to(ROOT)).replace("\\", "/"): _sha256(p) for p in sorted((ROOT / "src").glob("*.py"))},
                   input_sha256={str(p.resolve()): digest for p, digest in tracked.items()}, selection_modes=config["selection_modes"],
                   analysis_scope="Saved test predictions; no refitting, compression, label changes or tuning.")
    if any(_sha256(p) != digest for p, digest in tracked.items()):
        raise RuntimeError("Analysis input changed during execution")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".failure_analysis_", dir=destination.parent) as temporary:
        output = Path(temporary) / "artifacts"
        output.mkdir()
        for name, frame in tables.items():
            _write_frame(output / name, frame)
        (output / "report.md").write_text(render_report(tables), encoding="utf-8")
        summary["output_sha256"] = {p.name: _sha256(p) for p in sorted(output.iterdir())}
        (output / "failure_analysis_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        output.rename(destination)
    return summary


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(arguments)
    summary = run_failure_analysis(args.experiment_dir, args.output_dir)
    print(json.dumps({n: summary[n] for n in ("sample_count", "test_count", "error_row_count", "unique_error_samples")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
