"""Select from pre-compression features, then compress with one saved model's choice.

Only load trusted, locally generated model directories: pickle hashes detect
accidental changes, but do not make an untrusted pickle safe to execute.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import pickle
import platform
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier

from src import compressors, feature_extractor
from src.feature_extractor import FEATURE_NAMES
from src.scoring import ALGORITHMS, MODE_NAMES


_ROOT = Path(__file__).resolve().parent
_CONFIG_PATH = _ROOT / "config/experiment_config.json"
MODEL_TYPES = {"decision_tree": DecisionTreeClassifier, "random_forest": RandomForestClassifier}
_EXTENSIONS = {"gzip": ".gz", "bz2": ".bz2", "lzma": ".xz", "zstd": ".zst"}
_RUNTIME_PACKAGES = ("numpy", "pandas", "scikit-learn", "zstandard")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_information() -> dict:
    command = ["git", "-c", f"safe.directory={_ROOT.as_posix()}", "-C", str(_ROOT)]
    try:
        commit = subprocess.run([*command, "rev-parse", "HEAD"], check=True,
                                capture_output=True, text=True)
        status = subprocess.run([*command, "status", "--porcelain"], check=True,
                                capture_output=True, text=True)
        return {"commit_hash": commit.stdout.strip(), "worktree_dirty": bool(status.stdout.strip())}
    except (OSError, subprocess.CalledProcessError):
        return {"commit_hash": None, "worktree_dirty": None}


def load_selector(model_dir: str | Path, model_kind: str, mode: str) -> tuple[object, dict]:
    """Check saved training metadata before deserializing the requested mode only."""
    if model_kind not in MODEL_TYPES or mode not in MODE_NAMES:
        raise ValueError("Unsupported model or usage mode")
    directory = Path(model_dir).resolve()
    summary_bytes = (directory / f"{model_kind}_summary.json").read_bytes()
    summary = json.loads(summary_bytes)
    config_bytes = _CONFIG_PATH.read_bytes()
    config = json.loads(config_bytes)
    measurement = summary["measurement_metadata"]
    for recorded, current in (("compression_settings", "compression"),
                              ("feature_settings", "features"), ("timing", "timing")):
        if measurement[recorded] != config[current]:
            raise ValueError(f"Model/config mismatch: {current}")
    if summary["selection_modes"] != config["selection_modes"]:
        raise ValueError("Model/config mismatch: selection_modes")
    if summary["model_settings"] != config[model_kind]:
        raise ValueError("Model/config mismatch: model_settings")
    if summary["input_features"] != list(FEATURE_NAMES) or summary["algorithms"] != list(ALGORITHMS):
        raise ValueError("Model feature schema or algorithms differ from protocol")
    if compressors._CONFIG["compression"] != config["compression"] or (
        feature_extractor._CONFIG["features"] != config["features"]
    ):
        raise ValueError("Configuration changed since module import; restart the process")
    source_hashes = {}
    for name in ("src/feature_extractor.py", "src/compressors.py", "src/scoring.py"):
        source_hashes[name] = _digest((_ROOT / name).read_bytes())
        if summary["source_sha256"][name] != source_hashes[name]:
            raise ValueError(f"Model source definition mismatch: {name}")
    packages = {name: version(name) for name in _RUNTIME_PACKAGES}
    if summary["python_version"] != platform.python_version():
        raise ValueError("Saved model Python version differs from runtime")
    for name, installed in packages.items():
        if summary["package_versions"][name] != installed:
            raise ValueError(f"Saved model package version differs: {name}")

    filename = f"{model_kind}_{mode}.pkl"
    model_bytes = (directory / filename).read_bytes()
    if _digest(model_bytes) != summary["output_sha256"][filename]:
        raise ValueError("Saved model SHA-256 mismatch")
    # Read exactly the checked bytes; callers must trust the model and its summary.
    model = pickle.loads(model_bytes)
    if type(model) is not MODEL_TYPES[model_kind]:
        raise ValueError("Saved estimator type differs from requested model")
    if list(model.feature_names_in_) != list(FEATURE_NAMES):
        raise ValueError("Saved estimator feature order differs from protocol")
    classes = list(model.classes_)
    if not classes or len(set(classes)) != len(classes) or not set(classes) <= set(ALGORITHMS):
        raise ValueError("Saved estimator has invalid algorithm classes")
    for name, value in config[model_kind].items():
        if model.get_params()[name] != value:
            raise ValueError(f"Saved estimator parameter mismatch: {name}")
    return model, {
        "model_kind": model_kind, "model_path": str(directory / filename),
        "model_sha256": _digest(model_bytes), "model_summary_sha256": _digest(summary_bytes),
        "training_git": summary["git"], "config_sha256": _digest(config_bytes),
        "compression_settings": config["compression"], "feature_settings": config["features"],
        "selection_weights": config["selection_modes"][mode], "model_settings": config[model_kind],
        "source_sha256": source_hashes, "package_versions": packages,
        "python_version": platform.python_version(), "operating_system": platform.platform(),
        "prediction_confidence_definition": summary["prediction_confidence_definition"],
    }


def smart_compress(input_path: str | Path, output_dir: str | Path, *, mode: str,
                   model_kind: str, model_dir: str | Path | None = None) -> dict:
    """Publish a native compressed payload and manifest in a new output directory.

    One compression and one decompression are performed. This is a file operation,
    not a five-repeat research benchmark or an oracle evaluation.
    """
    source = Path(input_path).resolve()
    destination = Path(output_dir).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Output directory already exists: {destination}")
    original = source.read_bytes()
    if not original:
        raise ValueError("Cannot smart-compress empty input: protocol features require non-empty bytes")
    if model_dir is None:
        model_dir = _ROOT / "data/results/pilot_1008" / model_kind
    model, provenance = load_selector(model_dir, model_kind, mode)
    features = feature_extractor.extract_features(original)
    frame = pd.DataFrame([features], columns=list(FEATURE_NAMES))
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("Extracted features must be finite")
    predicted = str(model.predict(frame)[0])
    probabilities = np.asarray(model.predict_proba(frame), dtype=float)
    if probabilities.shape != (1, len(model.classes_)) or not np.isfinite(probabilities).all():
        raise ValueError("Invalid model probabilities")
    probability = probabilities[0]
    if (probability < 0).any() or (probability > 1).any() or not np.isclose(
        probability.sum(), 1.0, rtol=0, atol=1e-12
    ):
        raise ValueError("Invalid model probability range or sum")
    if predicted not in ALGORITHMS or predicted != str(model.classes_[int(probability.argmax())]):
        raise ValueError("Prediction and model probabilities disagree")

    compressed = compressors.compress_data(original, predicted)
    restored = compressors.decompress_data(compressed, predicted)
    verified = restored == original
    if not verified:
        raise RuntimeError("Lossless verification failed (verified=False); no output published")
    if not compressed:
        raise RuntimeError("Compressor returned empty output")
    if _digest(_CONFIG_PATH.read_bytes()) != provenance["config_sha256"]:
        raise RuntimeError("Configuration changed during Smart Mode")
    payload_name = "payload" + _EXTENSIONS[predicted]
    by_class = {str(name): float(value) for name, value in zip(model.classes_, probability, strict=True)}
    manifest = {
        "smart_mode_version": 1, "mode": mode, "algorithm": predicted,
        "input_path": str(source), "original_filename": source.name,
        "input_sha256": _digest(original), "original_size": len(original),
        "compressed_file": payload_name, "compressed_sha256": _digest(compressed),
        "compressed_size": len(compressed), "compression_ratio": len(compressed) / len(original),
        "verified": verified, "features": features,
        "prediction_confidence": float(probability.max()),
        "algorithm_probabilities": {name: by_class.get(name, 0.0) for name in ALGORITHMS},
        "provenance": provenance, "git": _git_information(),
        "smart_compress_source_sha256": _digest(Path(__file__).read_bytes()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "operation": "One selected compression and one verification decompression; no benchmark or oracle.",
        "limitations": [
            "Pilot models have not demonstrated improvement over the majority baseline.",
            "Confidence is uncalibrated model output, not a validated probability of correctness.",
            "Generalization to unseen real files has not been established.",
        ],
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".smart_", dir=destination.parent) as temporary:
        staged = Path(temporary) / "output"
        staged.mkdir()
        payload = staged / payload_name
        payload.write_bytes(compressed)
        (staged / "manifest.json").write_text(manifest_text, encoding="utf-8")
        if payload.read_bytes() != compressed:
            raise OSError("Saved compressed bytes differ from verified bytes")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Output directory already exists: {destination}")
        staged.rename(destination)
    return manifest


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Non-empty input file")
    parser.add_argument("--mode", choices=MODE_NAMES, required=True)
    parser.add_argument("--model", choices=tuple(MODEL_TYPES), required=True)
    parser.add_argument("--model-dir", type=Path, help="Trusted model directory; defaults to saved Pilot models")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for payload and manifest")
    args = parser.parse_args(arguments)
    try:
        result = smart_compress(args.input, args.output_dir, mode=args.mode,
                                model_kind=args.model, model_dir=args.model_dir)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError,
            pickle.UnpicklingError, EOFError) as exc:
        print(f"Smart Mode failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "mode": result["mode"], "algorithm": result["algorithm"],
        "prediction_confidence": result["prediction_confidence"],
        "confidence_note": "Uncalibrated model output; not a validated correctness probability.",
        "verified": result["verified"], "output_dir": str(args.output_dir.absolute()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
