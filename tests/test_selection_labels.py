"""Tests for selection-label CSV generation."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
import unittest

from src.experiment_runner import COMPRESSION_RESULT_FIELDS
from src.scoring import ALGORITHMS, MODE_NAMES, score_sample
from src.selection_labels import (
    SELECTION_LABEL_FIELDS,
    generate_selection_labels,
    main,
)


def _sample_rows(sample_id: str) -> list[dict[str, object]]:
    measurements = (
        ("gzip", 50, 4.0, 8.0),
        ("bz2", 60, 1.0, 4.0),
        ("lzma", 70, 2.0, 1.0),
        ("zstd", 80, 8.0, 2.0),
    )
    return [
        {
            "sample_id": sample_id,
            "algorithm": algorithm,
            "original_size": 100,
            "compressed_size": compressed_size,
            "compression_ratio": compressed_size / 100,
            "compression_time_ms": compression_time,
            "decompression_time_ms": decompression_time,
            "verified": True,
        }
        for algorithm, compressed_size, compression_time, decompression_time in measurements
    ]


def _write_compression_results(
    path: Path, rows: list[dict[str, object]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=COMPRESSION_RESULT_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)


class SelectionLabelTests(unittest.TestCase):
    def test_generates_protocol_rows_and_scores_for_each_sample_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            source = directory_path / "compression_results.csv"
            destination = directory_path / "selection_labels.csv"
            input_rows = _sample_rows("sample_b") + _sample_rows("sample_a")
            _write_compression_results(source, input_rows)

            artifacts = generate_selection_labels(source, destination)

            self.assertEqual(artifacts.sample_count, 2)
            self.assertEqual(artifacts.label_count, 6)
            with destination.open(encoding="utf-8", newline="") as input_file:
                reader = csv.DictReader(input_file)
                self.assertEqual(tuple(reader.fieldnames or ()), SELECTION_LABEL_FIELDS)
                label_rows = list(reader)

            self.assertEqual(len(label_rows), 6)
            self.assertEqual(
                [(row["sample_id"], row["mode"]) for row in label_rows],
                [
                    (sample_id, mode)
                    for sample_id in ("sample_a", "sample_b")
                    for mode in MODE_NAMES
                ],
            )

            source_by_sample = {
                sample_id: _sample_rows(sample_id)
                for sample_id in ("sample_a", "sample_b")
            }
            for row in label_rows:
                expected = score_sample(source_by_sample[row["sample_id"]])[
                    row["mode"]
                ]
                self.assertEqual(row["best_algorithm"], expected.best_algorithm)
                self.assertAlmostEqual(float(row["best_score"]), expected.best_score)
                for algorithm in ALGORITHMS:
                    self.assertAlmostEqual(
                        float(row[f"score_{algorithm}"]),
                        expected.scores[algorithm],
                    )

    def test_output_is_deterministic_for_identical_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            source = directory_path / "compression_results.csv"
            first_output = directory_path / "first.csv"
            second_output = directory_path / "second.csv"
            _write_compression_results(
                source, _sample_rows("sample_b") + _sample_rows("sample_a")
            )

            generate_selection_labels(source, first_output)
            generate_selection_labels(source, second_output)

            self.assertEqual(first_output.read_bytes(), second_output.read_bytes())

    def test_existing_output_is_not_replaced_without_explicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            source = directory_path / "compression_results.csv"
            destination = directory_path / "selection_labels.csv"
            _write_compression_results(source, _sample_rows("sample_test"))
            generate_selection_labels(source, destination)
            original_output = destination.read_bytes()

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                generate_selection_labels(source, destination)
            self.assertEqual(destination.read_bytes(), original_output)

            artifacts = generate_selection_labels(
                source, destination, overwrite=True
            )
            self.assertEqual(artifacts.label_count, 3)
            self.assertEqual(destination.read_bytes(), original_output)

    def test_invalid_header_and_incomplete_sample_do_not_create_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            invalid_source = directory_path / "invalid.csv"
            invalid_output = directory_path / "invalid_labels.csv"
            invalid_source.write_text("sample_id,algorithm\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "header"):
                generate_selection_labels(invalid_source, invalid_output)
            self.assertFalse(invalid_output.exists())

            incomplete_source = directory_path / "incomplete.csv"
            incomplete_output = directory_path / "incomplete_labels.csv"
            _write_compression_results(
                incomplete_source, _sample_rows("sample_test")[:-1]
            )
            with self.assertRaisesRegex(ValueError, "Exactly 4"):
                generate_selection_labels(incomplete_source, incomplete_output)
            self.assertFalse(incomplete_output.exists())

    def test_missing_source_and_same_input_output_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            missing = directory_path / "missing.csv"
            output = directory_path / "labels.csv"
            with self.assertRaises(FileNotFoundError):
                generate_selection_labels(missing, output)

            source = directory_path / "compression_results.csv"
            _write_compression_results(source, _sample_rows("sample_test"))
            with self.assertRaisesRegex(ValueError, "must differ"):
                generate_selection_labels(source, source)

    def test_cli_main_generates_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            source = directory_path / "compression_results.csv"
            destination = directory_path / "selection_labels.csv"
            _write_compression_results(source, _sample_rows("sample_test"))

            exit_code = main(
                [
                    "--compression-results",
                    str(source),
                    "--output",
                    str(destination),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(destination.exists())


if __name__ == "__main__":
    unittest.main()
