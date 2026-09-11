"""Create mode-specific selection labels from raw compression measurements."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
from pathlib import Path
import sys
import tempfile

from src.experiment_runner import COMPRESSION_RESULT_FIELDS
from src.scoring import ALGORITHMS, MODE_NAMES, score_sample


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_COMPRESSION_RESULTS_PATH = (
    _PROJECT_ROOT / "data" / "results" / "compression_results.csv"
)
_DEFAULT_OUTPUT_PATH = _PROJECT_ROOT / "data" / "results" / "selection_labels.csv"

SELECTION_LABEL_FIELDS = (
    "sample_id",
    "mode",
    "best_algorithm",
    "best_score",
    "score_gzip",
    "score_bz2",
    "score_lzma",
    "score_zstd",
)


@dataclass(frozen=True, slots=True)
class SelectionLabelArtifacts:
    """Location and row counts for a generated selection-label file."""

    output_path: Path
    sample_count: int
    label_count: int


def _read_compression_results(path: Path) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Compression results file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Compression results path is not a file: {path}")

    rows_by_sample: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        actual_fields = tuple(reader.fieldnames or ())
        if actual_fields != COMPRESSION_RESULT_FIELDS:
            raise ValueError(
                "Compression results CSV header does not match the research schema"
            )
        for row in reader:
            rows_by_sample[row["sample_id"]].append(row)

    if not rows_by_sample:
        raise ValueError("Compression results CSV contains no data rows")
    return dict(rows_by_sample)


def generate_selection_labels(
    compression_results_path: str | Path = _DEFAULT_COMPRESSION_RESULTS_PATH,
    output_path: str | Path = _DEFAULT_OUTPUT_PATH,
    *,
    overwrite: bool = False,
) -> SelectionLabelArtifacts:
    """Calculate all sample-mode scores and atomically write selection labels."""
    source = Path(compression_results_path)
    destination = Path(output_path)
    if source.resolve() == destination.resolve():
        raise ValueError("Selection-label output must differ from compression input")
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"Selection-label output already exists: {destination}. "
            "Use overwrite=True only for an intentional replacement."
        )

    rows_by_sample = _read_compression_results(source)
    selections_by_sample = {
        sample_id: score_sample(rows)
        for sample_id, rows in rows_by_sample.items()
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".selection_labels_", dir=destination.parent
    ) as temporary_directory:
        temporary_output = Path(temporary_directory) / destination.name
        with temporary_output.open(
            "w", encoding="utf-8", newline=""
        ) as output_file:
            writer = csv.DictWriter(
                output_file,
                fieldnames=SELECTION_LABEL_FIELDS,
            )
            writer.writeheader()
            for sample_id in sorted(selections_by_sample):
                selections = selections_by_sample[sample_id]
                for mode in MODE_NAMES:
                    selection = selections[mode]
                    writer.writerow(
                        {
                            "sample_id": sample_id,
                            "mode": mode,
                            "best_algorithm": selection.best_algorithm,
                            "best_score": selection.best_score,
                            **{
                                f"score_{algorithm}": selection.scores[algorithm]
                                for algorithm in ALGORITHMS
                            },
                        }
                    )
        temporary_output.replace(destination)

    return SelectionLabelArtifacts(
        output_path=destination,
        sample_count=len(selections_by_sample),
        label_count=len(selections_by_sample) * len(MODE_NAMES),
    )


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create mode-specific labels from compression results."
    )
    parser.add_argument(
        "--compression-results",
        type=Path,
        default=_DEFAULT_COMPRESSION_RESULTS_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT_PATH,
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Intentionally replace an existing selection-label file.",
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_args(arguments)
    artifacts = generate_selection_labels(
        compression_results_path=args.compression_results,
        output_path=args.output,
        overwrite=args.overwrite,
    )
    print(f"samples scored: {artifacts.sample_count}")
    print(f"selection labels: {artifacts.label_count} -> {artifacts.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
