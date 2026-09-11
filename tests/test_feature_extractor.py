"""Tests for protocol-defined statistical feature extraction."""

from __future__ import annotations

import math
import random
import unittest

from src import feature_extractor


class FeatureExtractorTests(unittest.TestCase):
    def test_protocol_configuration_and_output_order(self) -> None:
        expected_names = (
            "file_size",
            "entropy",
            "unique_byte_count",
            "most_common_byte_ratio",
            "zero_byte_ratio",
            "adjacent_repeat_ratio",
            "average_run_length",
            "max_run_length",
            "duplicate_block_ratio",
            "bigram_diversity",
            "segment_entropy_mean",
            "segment_entropy_std",
        )

        self.assertEqual(feature_extractor.FEATURE_NAMES, expected_names)
        self.assertEqual(feature_extractor._DUPLICATE_BLOCK_SIZE, 16)
        self.assertEqual(feature_extractor._SEGMENT_SIZE, 4096)
        self.assertEqual(
            tuple(feature_extractor.extract_features(b"data")), expected_names
        )

    def test_repeated_single_byte_has_expected_features(self) -> None:
        features = feature_extractor.extract_features(b"A" * 32)

        self.assertEqual(features["file_size"], 32)
        self.assertEqual(features["entropy"], 0.0)
        self.assertEqual(features["unique_byte_count"], 1)
        self.assertEqual(features["most_common_byte_ratio"], 1.0)
        self.assertEqual(features["zero_byte_ratio"], 0.0)
        self.assertEqual(features["adjacent_repeat_ratio"], 1.0)
        self.assertEqual(features["average_run_length"], 32.0)
        self.assertEqual(features["max_run_length"], 32)
        self.assertEqual(features["duplicate_block_ratio"], 0.5)
        self.assertAlmostEqual(features["bigram_diversity"], 1 / 31)
        self.assertEqual(features["segment_entropy_mean"], 0.0)
        self.assertEqual(features["segment_entropy_std"], 0.0)

    def test_all_zero_data_has_full_zero_byte_ratio(self) -> None:
        features = feature_extractor.extract_features(bytes(32))

        self.assertEqual(features["entropy"], 0.0)
        self.assertEqual(features["unique_byte_count"], 1)
        self.assertEqual(features["most_common_byte_ratio"], 1.0)
        self.assertEqual(features["zero_byte_ratio"], 1.0)
        self.assertEqual(features["adjacent_repeat_ratio"], 1.0)
        self.assertEqual(features["average_run_length"], 32.0)
        self.assertEqual(features["max_run_length"], 32)

    def test_repeated_abc_pattern_has_expected_entropy_and_bigrams(self) -> None:
        features = feature_extractor.extract_features(b"ABCABC")

        self.assertAlmostEqual(features["entropy"], math.log2(3))
        self.assertEqual(features["unique_byte_count"], 3)
        self.assertAlmostEqual(features["most_common_byte_ratio"], 1 / 3)
        self.assertEqual(features["adjacent_repeat_ratio"], 0.0)
        self.assertEqual(features["average_run_length"], 1.0)
        self.assertEqual(features["max_run_length"], 1)
        self.assertAlmostEqual(features["bigram_diversity"], 3 / 5)

    def test_sequential_bytes_have_maximum_byte_entropy(self) -> None:
        features = feature_extractor.extract_features(bytes(range(256)))

        self.assertEqual(features["file_size"], 256)
        self.assertEqual(features["entropy"], 8.0)
        self.assertEqual(features["unique_byte_count"], 256)
        self.assertEqual(features["most_common_byte_ratio"], 1 / 256)
        self.assertEqual(features["zero_byte_ratio"], 1 / 256)
        self.assertEqual(features["adjacent_repeat_ratio"], 0.0)
        self.assertEqual(features["average_run_length"], 1.0)
        self.assertEqual(features["max_run_length"], 1)
        self.assertEqual(features["duplicate_block_ratio"], 0.0)
        self.assertEqual(features["bigram_diversity"], 1.0)

    def test_run_statistics_follow_protocol_definitions(self) -> None:
        features = feature_extractor.extract_features(b"AAABBCCCC")

        self.assertEqual(features["adjacent_repeat_ratio"], 6 / 8)
        self.assertEqual(features["average_run_length"], 3.0)
        self.assertEqual(features["max_run_length"], 4)

    def test_duplicate_block_ratio_counts_previously_seen_blocks(self) -> None:
        data = b"A" * 16 + b"A" * 16 + b"B" * 16 + b"A" * 16
        features = feature_extractor.extract_features(data)

        self.assertEqual(features["duplicate_block_ratio"], 2 / 4)

    def test_segment_entropy_uses_mean_and_population_standard_deviation(self) -> None:
        constant_segment = bytes(4096)
        binary_segment = bytes((0, 1)) * 2048
        features = feature_extractor.extract_features(
            constant_segment + binary_segment
        )

        self.assertAlmostEqual(features["segment_entropy_mean"], 0.5)
        self.assertAlmostEqual(features["segment_entropy_std"], 0.5)

    def test_seeded_random_and_small_alphabet_data_are_distinguishable(self) -> None:
        random_data = random.Random(20260911).randbytes(16_384)
        alphabet_rng = random.Random(20260911)
        small_alphabet_data = bytes(
            alphabet_rng.randrange(4) for _ in range(16_384)
        )

        random_features = feature_extractor.extract_features(random_data)
        alphabet_features = feature_extractor.extract_features(small_alphabet_data)

        self.assertEqual(random_features["unique_byte_count"], 256)
        self.assertEqual(alphabet_features["unique_byte_count"], 4)
        self.assertGreater(random_features["entropy"], alphabet_features["entropy"])
        self.assertGreater(
            random_features["bigram_diversity"],
            alphabet_features["bigram_diversity"],
        )
        for features in (random_features, alphabet_features):
            for value in features.values():
                self.assertTrue(math.isfinite(value))

    def test_single_byte_and_invalid_inputs_are_handled(self) -> None:
        features = feature_extractor.extract_features(b"X")

        self.assertEqual(features["adjacent_repeat_ratio"], 0.0)
        self.assertEqual(features["average_run_length"], 1.0)
        self.assertEqual(features["max_run_length"], 1)
        self.assertEqual(features["duplicate_block_ratio"], 0.0)
        self.assertEqual(features["bigram_diversity"], 0.0)
        self.assertEqual(features["segment_entropy_mean"], 0.0)
        self.assertEqual(features["segment_entropy_std"], 0.0)

        with self.assertRaisesRegex(ValueError, "empty input"):
            feature_extractor.extract_features(b"")
        for invalid_data in (bytearray(b"data"), memoryview(b"data"), "data"):
            with self.subTest(invalid_type=type(invalid_data)), self.assertRaisesRegex(
                TypeError, "must be bytes"
            ):
                feature_extractor.extract_features(invalid_data)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
