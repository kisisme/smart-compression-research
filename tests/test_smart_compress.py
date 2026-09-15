"""Smart Mode integration tests. Controlled model fixtures are not research results."""

import contextlib
import hashlib
from importlib.metadata import version
import io
import json
from pathlib import Path
import pickle
import platform
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import smart_compress as smart
from src import compressors
from src.feature_extractor import FEATURE_NAMES, extract_features
from src.scoring import ALGORITHMS, MODE_NAMES


def fixture(directory, kind="decision_tree", algorithm="gzip"):
    """Fit a constant, controlled estimator to exercise each compression branch."""
    directory.mkdir()
    config = json.loads(smart._CONFIG_PATH.read_bytes())
    data = [b"A" * 128, bytes(range(256))]
    frame = pd.DataFrame([extract_features(item) for item in data], columns=list(FEATURE_NAMES))
    model = smart.MODEL_TYPES[kind](**config[kind]).fit(frame, [algorithm] * len(data))
    summary = {
        "measurement_metadata": {"compression_settings": config["compression"],
                                 "feature_settings": config["features"], "timing": config["timing"]},
        "selection_modes": config["selection_modes"], "model_settings": config[kind],
        "input_features": list(FEATURE_NAMES), "algorithms": list(ALGORITHMS),
        "source_sha256": {name: hashlib.sha256((smart._ROOT / name).read_bytes()).hexdigest()
                          for name in ("src/feature_extractor.py", "src/compressors.py", "src/scoring.py")},
        "python_version": platform.python_version(),
        "package_versions": {name: version(name) for name in smart._RUNTIME_PACKAGES},
        "git": {"commit_hash": None, "worktree_dirty": None},
        "prediction_confidence_definition": "Uncalibrated test model class probability.",
        "output_sha256": {},
    }
    for mode in MODE_NAMES:
        name = f"{kind}_{mode}.pkl"
        blob = pickle.dumps(model)
        (directory / name).write_bytes(blob)
        summary["output_sha256"][name] = hashlib.sha256(blob).hexdigest()
    summary_path = directory / f"{kind}_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    return summary_path


class SmartCompressTests(unittest.TestCase):
    def test_both_models_all_modes_and_compressors_select_before_single_compression(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "한글 입력.bin"
            original = b"ABC\x00" * 4096 + bytes(range(256))
            source.write_bytes(original)
            for kind in smart.MODEL_TYPES:
                for algorithm in ALGORITHMS:
                    models = root / f"{kind}_{algorithm}"
                    fixture(models, kind, algorithm)
                    before = {p.name: p.read_bytes() for p in models.iterdir()}
                    for mode in MODE_NAMES:
                        with self.subTest(model=kind, algorithm=algorithm, mode=mode):
                            output = root / f"out_{kind}_{algorithm}_{mode}"
                            estimator = smart.MODEL_TYPES[kind]
                            original_predict = estimator.predict
                            predict_inputs = []

                            def predict(model, features):
                                predict_inputs.append(features.copy())
                                self.assertEqual(compress.call_count, 0)
                                return original_predict(model, features)

                            with patch.object(estimator, "predict", predict), patch.object(
                                compressors, "compress_data", wraps=compressors.compress_data
                            ) as compress, patch.object(
                                compressors, "decompress_data", wraps=compressors.decompress_data
                            ) as decompress, patch.object(
                                compressors, "benchmark_compressor", side_effect=AssertionError("No benchmark")
                            ), patch.object(estimator, "fit", side_effect=AssertionError("No refitting")):
                                result = smart.smart_compress(source, output, mode=mode,
                                                             model_kind=kind, model_dir=models)
                            compress.assert_called_once_with(original, algorithm)
                            self.assertEqual(decompress.call_count, 1)
                            self.assertEqual(decompress.call_args.args[1], algorithm)
                            self.assertEqual(predict_inputs[0].columns.tolist(), list(FEATURE_NAMES))
                            self.assertEqual(predict_inputs[0].iloc[0].to_dict(), extract_features(original))
                            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                            self.assertEqual(manifest, result)
                            self.assertEqual(result["algorithm"], algorithm)
                            self.assertTrue(result["verified"])
                            payload = (output / result["compressed_file"]).read_bytes()
                            self.assertEqual(compressors.decompress_data(payload, algorithm), original)
                            self.assertEqual(result["compression_ratio"], len(payload) / len(original))
                            self.assertEqual(result["compressed_sha256"], hashlib.sha256(payload).hexdigest())
                            self.assertEqual(result["prediction_confidence"], 1)
                            self.assertEqual(result["algorithm_probabilities"],
                                             {a: float(a == algorithm) for a in ALGORITHMS})
                    self.assertEqual(before, {p.name: p.read_bytes() for p in models.iterdir()})
            self.assertEqual(source.read_bytes(), original)

    def test_incompatible_metadata_or_damaged_model_rejected_before_unpickling(self):
        for problem in ("hash", "weights", "feature_order", "feature_source", "settings", "package", "python"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = fixture(root / "models")
                summary = json.loads(path.read_bytes())
                if problem == "hash":
                    (root / "models/decision_tree_archive.pkl").write_bytes(b"damaged")
                elif problem == "weights":
                    summary["selection_modes"]["archive"]["compression_ratio"] = 1
                elif problem == "feature_order":
                    summary["input_features"].reverse()
                elif problem == "feature_source":
                    summary["source_sha256"]["src/feature_extractor.py"] = "invalid"
                elif problem == "settings":
                    summary["measurement_metadata"]["compression_settings"]["gzip"]["level"] = 1
                elif problem == "package":
                    summary["package_versions"]["scikit-learn"] = "different"
                else:
                    summary["python_version"] = "different"
                path.write_text(json.dumps(summary), encoding="utf-8")
                with patch.object(smart.pickle, "loads", side_effect=AssertionError("Must reject first")):
                    with self.assertRaises(ValueError):
                        smart.load_selector(root / "models", "decision_tree", "archive")

    def test_failed_restoration_or_invalid_probabilities_publish_nothing(self):
        for problem in ("restoration", "nan", "sum", "negative"):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "input"
                source.write_bytes(b"ABC" * 100)
                fixture(root / "models")
                target = (patch.object(compressors, "decompress_data", return_value=b"wrong")
                          if problem == "restoration" else patch.object(
                              smart.MODEL_TYPES["decision_tree"], "predict_proba",
                              return_value=[[{"nan": float("nan"), "sum": 0.5, "negative": -1}[problem]]]))
                with target, patch.object(compressors, "compress_data", wraps=compressors.compress_data) as compress:
                    with self.assertRaises((ValueError, RuntimeError)):
                        smart.smart_compress(source, root / "output", mode="archive",
                                             model_kind="decision_tree", model_dir=root / "models")
                    self.assertEqual(compress.call_count, 1 if problem == "restoration" else 0)
                self.assertFalse((root / "output").exists())
                self.assertFalse(list(root.glob(".smart_*")))

    def test_existing_output_and_empty_input_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            source.write_bytes(b"")
            output = root / "output"
            output.mkdir()
            (output / "keep").write_bytes(b"keep")
            with patch.object(smart, "load_selector", side_effect=AssertionError("No model load")):
                for destination, error in ((output, FileExistsError), (source, FileExistsError),
                                           (root / "new", ValueError)):
                    with self.assertRaises(error):
                        smart.smart_compress(source, destination, mode="archive", model_kind="random_forest")
            self.assertEqual((output / "keep").read_bytes(), b"keep")
            self.assertEqual(source.read_bytes(), b"")

    def test_cli_success_and_missing_input_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root / "models")
            source = root / "input"
            source.write_bytes(b"ABC" * 100)
            args = [str(source), "--mode", "balanced", "--model", "decision_tree",
                    "--model-dir", str(root / "models"), "--output-dir", str(root / "output")]
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(smart.main(args), 0)
            self.assertTrue(json.loads(stdout.getvalue())["verified"])
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(smart.main([str(root / "missing"), *args[1:-1], str(root / "new")]), 1)
            self.assertIn("Smart Mode failed", stderr.getvalue())
            self.assertFalse((root / "new").exists())


if __name__ == "__main__":
    unittest.main()
