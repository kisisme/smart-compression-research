"""Run reproducible synthetic compression experiments and write raw results."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata as importlib_metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any

from src.compressors import benchmark_compressor
from src.data_generator import GENERATOR_NAMES, SAMPLE_SIZES, generate_sample
from src.feature_extractor import FEATURE_NAMES, extract_features


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "experiment_config.json"
_REQUIREMENTS_PATH = _PROJECT_ROOT / "requirements.txt"
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "results"

ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
SAMPLES_FILENAME = "samples.csv"
COMPRESSION_RESULTS_FILENAME = "compression_results.csv"
METADATA_FILENAME = "experiment_metadata.json"

SAMPLE_FIELDS = (
    "sample_id",
    "generator",
    "seed",
    "size",
    "generation_parameters",
    *FEATURE_NAMES,
)

COMPRESSION_RESULT_FIELDS = (
    "sample_id",
    "algorithm",
    "original_size",
    "compressed_size",
    "compression_ratio",
    "compression_time_ms",
    "decompression_time_ms",
    "verified",
)


@dataclass(frozen=True, slots=True)
class SampleSpec:
    """One deterministic sample generation request."""

    sample_id: str
    generator: str
    size: int
    seed: int


@dataclass(frozen=True, slots=True)
class ExperimentArtifacts:
    """Paths and row counts produced by a completed experiment."""

    samples_path: Path
    compression_results_path: Path
    metadata_path: Path
    sample_count: int
    compression_result_count: int
    verification_failure_count: int


def _load_config() -> dict[str, Any]:
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Experiment configuration file not found: {_CONFIG_PATH}"
        ) from exc

    if not isinstance(config, dict):
        raise TypeError(f"Experiment configuration must be a JSON object: {_CONFIG_PATH}")
    return config


def _validate_config(config: dict[str, Any]) -> None:
    if tuple(config.get("sample_sizes", ())) != SAMPLE_SIZES:
        raise ValueError("Configured sample sizes do not match the data generator")

    compression_config = config.get("compression")
    if not isinstance(compression_config, dict):
        raise TypeError("Experiment config key compression must be an object")
    if set(compression_config) != set(ALGORITHMS):
        raise ValueError(
            "Configured compression algorithms must be gzip, bz2, lzma, and zstd"
        )

    timing_config = config.get("timing")
    if not isinstance(timing_config, dict):
        raise TypeError("Experiment config key timing must be an object")
    expected_timing = {
        "repeats": 5,
        "timer": "time.perf_counter_ns",
        "aggregate": "median",
    }
    if timing_config != expected_timing:
        raise ValueError("Timing configuration does not match research protocol v2")


def build_experiment_plan(sample_count: int, base_seed: int) -> list[SampleSpec]:
    """Build a balanced, deterministic sequence of generator/size conditions."""
    if isinstance(sample_count, bool) or not isinstance(sample_count, int):
        raise TypeError("Sample count must be an integer")
    if sample_count <= 0:
        raise ValueError("Sample count must be greater than zero")
    if isinstance(base_seed, bool) or not isinstance(base_seed, int):
        raise TypeError("Base seed must be an integer")

    conditions = [
        (generator_name, size)
        for size in SAMPLE_SIZES
        for generator_name in GENERATOR_NAMES
    ]
    return [
        SampleSpec(
            sample_id=f"sample_{index:06d}",
            generator=conditions[index % len(conditions)][0],
            size=conditions[index % len(conditions)][1],
            seed=base_seed + index,
        )
        for index in range(sample_count)
    ]


def _git_information() -> dict[str, object]:
    command_prefix = [
        "git",
        "-c",
        f"safe.directory={_PROJECT_ROOT.as_posix()}",
        "-C",
        str(_PROJECT_ROOT),
    ]
    try:
        commit_process = subprocess.run(
            [*command_prefix, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        status_process = subprocess.run(
            [*command_prefix, "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {"commit_hash": None, "worktree_dirty": None}

    return {
        "commit_hash": commit_process.stdout.strip(),
        "worktree_dirty": bool(status_process.stdout.strip()),
    }


def _direct_dependency_versions() -> dict[str, str | None]:
    if not _REQUIREMENTS_PATH.exists():
        return {}

    versions: dict[str, str | None] = {}
    for raw_line in _REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        requirement = raw_line.strip()
        if not requirement or requirement.startswith("#"):
            continue
        package_name = requirement.split("==", maxsplit=1)[0].strip()
        try:
            versions[package_name] = importlib_metadata.version(package_name)
        except importlib_metadata.PackageNotFoundError:
            versions[package_name] = None
    return versions


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target_paths(output_dir: Path) -> tuple[Path, Path, Path]:
    return (
        output_dir / SAMPLES_FILENAME,
        output_dir / COMPRESSION_RESULTS_FILENAME,
        output_dir / METADATA_FILENAME,
    )


def _ensure_targets_available(output_dir: Path, overwrite: bool) -> None:
    existing_targets = [path for path in _target_paths(output_dir) if path.exists()]
    if existing_targets and not overwrite:
        existing_text = ", ".join(str(path) for path in existing_targets)
        raise FileExistsError(
            f"Experiment output already exists: {existing_text}. "
            "Use overwrite=True only for an intentional replacement."
        )


def _write_metadata(
    path: Path,
    *,
    config: dict[str, Any],
    git_information: dict[str, object],
    plan: list[SampleSpec],
    base_seed: int,
    started_at: datetime,
    completed_at: datetime,
    duration_seconds: float,
    verification_failures: list[dict[str, str]],
    samples_path: Path,
    compression_results_path: Path,
) -> None:
    generator_counts = Counter(spec.generator for spec in plan)
    size_counts = Counter(spec.size for spec in plan)
    metadata = {
        "schema_version": 1,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": completed_at.isoformat(),
        "duration_seconds": duration_seconds,
        "sample_count": len(plan),
        "compression_result_count": len(plan) * len(ALGORITHMS),
        "base_seed": base_seed,
        "seed_strategy": "base_seed + zero_based_sample_index",
        "sample_id_strategy": "sample_{zero_based_sample_index:06d}",
        "generators": list(GENERATOR_NAMES),
        "generator_counts": dict(generator_counts),
        "sample_sizes": list(SAMPLE_SIZES),
        "size_counts": {str(size): count for size, count in size_counts.items()},
        "compression_settings": config["compression"],
        "timing": config["timing"],
        "feature_settings": config["features"],
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "package_versions": _direct_dependency_versions(),
        "operating_system": platform.platform(),
        "git": git_information,
        "verification_failure_count": len(verification_failures),
        "verification_failures": verification_failures,
        "output_files": {
            SAMPLES_FILENAME: {"sha256": _sha256(samples_path)},
            COMPRESSION_RESULTS_FILENAME: {
                "sha256": _sha256(compression_results_path)
            },
        },
    }
    with path.open("w", encoding="utf-8", newline="") as metadata_file:
        json.dump(metadata, metadata_file, indent=2, sort_keys=True)
        metadata_file.write("\n")


def run_experiment(
    sample_count: int,
    base_seed: int,
    output_dir: str | Path = _DEFAULT_OUTPUT_DIR,
    *,
    overwrite: bool = False,
) -> ExperimentArtifacts:
    """Generate samples, benchmark all compressors, and atomically publish CSVs."""
    config = _load_config()
    _validate_config(config)
    plan = build_experiment_plan(sample_count, base_seed)
    git_information = _git_information()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _ensure_targets_available(output_path, overwrite)

    target_samples, target_compression_results, target_metadata = _target_paths(
        output_path
    )
    started_at = datetime.now(timezone.utc)
    start_counter = time.perf_counter()
    verification_failures: list[dict[str, str]] = []

    with tempfile.TemporaryDirectory(
        prefix=".experiment_", dir=output_path
    ) as temporary_directory:
        temporary_path = Path(temporary_directory)
        temporary_samples = temporary_path / SAMPLES_FILENAME
        temporary_compression_results = (
            temporary_path / COMPRESSION_RESULTS_FILENAME
        )
        temporary_metadata = temporary_path / METADATA_FILENAME

        with (
            temporary_samples.open(
                "w", encoding="utf-8", newline=""
            ) as samples_file,
            temporary_compression_results.open(
                "w", encoding="utf-8", newline=""
            ) as compression_results_file,
        ):
            samples_writer = csv.DictWriter(samples_file, fieldnames=SAMPLE_FIELDS)
            compression_writer = csv.DictWriter(
                compression_results_file,
                fieldnames=COMPRESSION_RESULT_FIELDS,
            )
            samples_writer.writeheader()
            compression_writer.writeheader()

            for spec in plan:
                generated = generate_sample(spec.generator, spec.size, spec.seed)
                features = extract_features(generated.data)
                if features["file_size"] != spec.size:
                    raise RuntimeError(
                        f"Feature size mismatch for {spec.sample_id}: "
                        f"{features['file_size']} != {spec.size}"
                    )

                samples_writer.writerow(
                    {
                        "sample_id": spec.sample_id,
                        "generator": generated.generator,
                        "seed": generated.seed,
                        "size": generated.size,
                        "generation_parameters": json.dumps(
                            generated.parameters,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        **features,
                    }
                )

                for algorithm in ALGORITHMS:
                    result = benchmark_compressor(generated.data, algorithm)
                    compression_writer.writerow(
                        {"sample_id": spec.sample_id, **result}
                    )
                    if result["verified"] is not True:
                        verification_failures.append(
                            {
                                "sample_id": spec.sample_id,
                                "algorithm": algorithm,
                            }
                        )

        completed_at = datetime.now(timezone.utc)
        duration_seconds = time.perf_counter() - start_counter
        _write_metadata(
            temporary_metadata,
            config=config,
            git_information=git_information,
            plan=plan,
            base_seed=base_seed,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            verification_failures=verification_failures,
            samples_path=temporary_samples,
            compression_results_path=temporary_compression_results,
        )

        temporary_samples.replace(target_samples)
        temporary_compression_results.replace(target_compression_results)
        temporary_metadata.replace(target_metadata)

    return ExperimentArtifacts(
        samples_path=target_samples,
        compression_results_path=target_compression_results,
        metadata_path=target_metadata,
        sample_count=len(plan),
        compression_result_count=len(plan) * len(ALGORITHMS),
        verification_failure_count=len(verification_failures),
    )


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the smart compression synthetic-data experiment."
    )
    parser.add_argument("--sample-count", type=int, required=True)
    parser.add_argument("--base-seed", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Intentionally replace existing experiment result files.",
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_args(arguments)
    artifacts = run_experiment(
        sample_count=args.sample_count,
        base_seed=args.base_seed,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
    )
    print(f"samples: {artifacts.sample_count} -> {artifacts.samples_path}")
    print(
        "compression results: "
        f"{artifacts.compression_result_count} -> "
        f"{artifacts.compression_results_path}"
    )
    print(f"metadata: {artifacts.metadata_path}")
    print(f"verification failures: {artifacts.verification_failure_count}")
    return 2 if artifacts.verification_failure_count else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
