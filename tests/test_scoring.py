"""Tests for multi-objective compression scoring."""

from __future__ import annotations

import copy
import math
import unittest

from src import scoring


def _result(
    algorithm: str,
    compressed_size: int,
    compression_time_ms: float,
    decompression_time_ms: float,
    *,
    sample_id: str = "sample_test",
    original_size: int = 100,
    verified: bool | str = True,
) -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "algorithm": algorithm,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_ratio": compressed_size / original_size,
        "compression_time_ms": compression_time_ms,
        "decompression_time_ms": decompression_time_ms,
        "verified": verified,
    }


def _tradeoff_results() -> list[dict[str, object]]:
    return [
        _result("gzip", 100, 4.0, 8.0),
        _result("bz2", 200, 1.0, 4.0),
        _result("lzma", 400, 2.0, 1.0),
        _result("zstd", 800, 8.0, 2.0),
    ]


class ScoringTests(unittest.TestCase):
    def test_protocol_modes_and_weights_are_loaded(self) -> None:
        self.assertEqual(scoring.ALGORITHMS, ("gzip", "bz2", "lzma", "zstd"))
        self.assertEqual(
            scoring.MODE_NAMES, ("archive", "balanced", "fast_access")
        )
        self.assertEqual(
            scoring.MODE_WEIGHTS,
            {
                "archive": {
                    "compression_ratio": 0.70,
                    "compression_time": 0.15,
                    "decompression_time": 0.15,
                },
                "balanced": {
                    "compression_ratio": 0.50,
                    "compression_time": 0.25,
                    "decompression_time": 0.25,
                },
                "fast_access": {
                    "compression_ratio": 0.30,
                    "compression_time": 0.20,
                    "decompression_time": 0.50,
                },
            },
        )

    def test_relative_losses_use_within_sample_log_ratios(self) -> None:
        losses = scoring.calculate_relative_losses(_tradeoff_results())

        self.assertEqual(tuple(losses), scoring.ALGORITHMS)
        self.assertEqual(losses["gzip"]["relative_size_loss"], 0.0)
        self.assertEqual(losses["bz2"]["relative_compression_loss"], 0.0)
        self.assertEqual(losses["lzma"]["relative_decompression_loss"], 0.0)
        self.assertAlmostEqual(losses["zstd"]["relative_size_loss"], math.log(8))
        self.assertAlmostEqual(
            losses["gzip"]["relative_compression_loss"], math.log(4)
        )
        self.assertAlmostEqual(
            losses["bz2"]["relative_decompression_loss"], math.log(4)
        )

    def test_mode_scores_and_best_algorithms_match_manual_calculation(self) -> None:
        selections = scoring.score_sample(_tradeoff_results())

        self.assertEqual(selections["archive"].best_algorithm, "gzip")
        self.assertEqual(selections["balanced"].best_algorithm, "bz2")
        self.assertEqual(selections["fast_access"].best_algorithm, "lzma")

        expected_archive_gzip = 0.15 * math.log(4) + 0.15 * math.log(8)
        expected_balanced_bz2 = 0.50 * math.log(2) + 0.25 * math.log(4)
        expected_fast_access_lzma = 0.30 * math.log(4) + 0.20 * math.log(2)
        self.assertAlmostEqual(
            selections["archive"].scores["gzip"], expected_archive_gzip
        )
        self.assertAlmostEqual(
            selections["balanced"].scores["bz2"], expected_balanced_bz2
        )
        self.assertAlmostEqual(
            selections["fast_access"].scores["lzma"],
            expected_fast_access_lzma,
        )
        for selection in selections.values():
            self.assertEqual(
                selection.best_score, selection.scores[selection.best_algorithm]
            )

    def test_equal_results_produce_zero_scores_and_deterministic_tie_break(self) -> None:
        results = [
            _result(algorithm, 50, 1.0, 1.0) for algorithm in scoring.ALGORITHMS
        ]

        selections = scoring.score_sample(results)

        for selection in selections.values():
            self.assertEqual(selection.best_algorithm, "gzip")
            self.assertEqual(selection.best_score, 0.0)
            self.assertEqual(set(selection.scores.values()), {0.0})

    def test_scores_are_invariant_to_common_metric_scaling(self) -> None:
        original = _tradeoff_results()
        scaled = copy.deepcopy(original)
        for row in scaled:
            row["compressed_size"] = int(row["compressed_size"]) * 2
            row["compression_ratio"] = float(row["compression_ratio"]) * 2
            row["compression_time_ms"] = float(row["compression_time_ms"]) * 10
            row["decompression_time_ms"] = (
                float(row["decompression_time_ms"]) * 7
            )

        original_selections = scoring.score_sample(original)
        scaled_selections = scoring.score_sample(scaled)

        for mode in scoring.MODE_NAMES:
            self.assertEqual(
                original_selections[mode].best_algorithm,
                scaled_selections[mode].best_algorithm,
            )
            for algorithm in scoring.ALGORITHMS:
                self.assertAlmostEqual(
                    original_selections[mode].scores[algorithm],
                    scaled_selections[mode].scores[algorithm],
                )

    def test_csv_string_values_are_accepted_without_mutating_input(self) -> None:
        rows = _tradeoff_results()
        string_rows = [
            {key: str(value) for key, value in row.items()} for row in rows
        ]
        before = copy.deepcopy(string_rows)

        selections = scoring.score_sample(string_rows)

        self.assertEqual(selections["archive"].best_algorithm, "gzip")
        self.assertEqual(string_rows, before)

    def test_incomplete_duplicate_and_unknown_algorithms_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Exactly 4"):
            scoring.score_sample(_tradeoff_results()[:-1])

        duplicate = _tradeoff_results()
        duplicate[-1]["algorithm"] = "gzip"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            scoring.score_sample(duplicate)

        unknown = _tradeoff_results()
        unknown[-1]["algorithm"] = "brotli"
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            scoring.score_sample(unknown)

    def test_unverified_and_invalid_numeric_results_are_rejected(self) -> None:
        unverified = _tradeoff_results()
        unverified[0]["verified"] = False
        with self.assertRaisesRegex(ValueError, "verified=False"):
            scoring.score_sample(unverified)

        invalid_cases = (
            ("compression_ratio", float("nan")),
            ("compression_time_ms", 0.0),
            ("decompression_time_ms", float("inf")),
            ("compressed_size", 0),
        )
        for field, value in invalid_cases:
            with self.subTest(field=field, value=value):
                invalid = _tradeoff_results()
                invalid[0][field] = value
                with self.assertRaises((TypeError, ValueError)):
                    scoring.score_sample(invalid)

        mismatch = _tradeoff_results()
        mismatch[0]["compression_ratio"] = 0.5
        with self.assertRaisesRegex(ValueError, "ratio mismatch"):
            scoring.score_sample(mismatch)

    def test_mixed_sample_ids_and_original_sizes_are_rejected(self) -> None:
        mixed_ids = _tradeoff_results()
        mixed_ids[-1]["sample_id"] = "another_sample"
        with self.assertRaisesRegex(ValueError, "one sample_id"):
            scoring.score_sample(mixed_ids)

        mixed_sizes = _tradeoff_results()
        mixed_sizes[-1]["original_size"] = 200
        mixed_sizes[-1]["compression_ratio"] = (
            int(mixed_sizes[-1]["compressed_size"]) / 200
        )
        with self.assertRaisesRegex(ValueError, "same original_size"):
            scoring.score_sample(mixed_sizes)


if __name__ == "__main__":
    unittest.main()
