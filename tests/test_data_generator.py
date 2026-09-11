"""Tests for reproducible synthetic data generation."""

from __future__ import annotations

import json
import random
import unittest

from src import data_generator


def _run_lengths(data: bytes) -> list[int]:
    lengths: list[int] = []
    current_length = 1
    for index in range(1, len(data)):
        if data[index] == data[index - 1]:
            current_length += 1
        else:
            lengths.append(current_length)
            current_length = 1
    lengths.append(current_length)
    return lengths


class DataGeneratorTests(unittest.TestCase):
    def test_protocol_generator_names_and_sample_sizes(self) -> None:
        self.assertEqual(
            data_generator.GENERATOR_NAMES,
            (
                "random",
                "small_alphabet",
                "repeated_pattern",
                "long_runs",
                "structured",
                "mixed",
            ),
        )
        self.assertEqual(
            data_generator.SAMPLE_SIZES,
            (16_384, 65_536, 262_144, 1_048_576),
        )

    def test_all_generators_produce_every_configured_size(self) -> None:
        for generator_name in data_generator.GENERATOR_NAMES:
            for size in data_generator.SAMPLE_SIZES:
                with self.subTest(generator=generator_name, size=size):
                    sample = data_generator.generate_sample(
                        generator_name, size, seed=20260911
                    )

                    self.assertIsInstance(sample, data_generator.GeneratedSample)
                    self.assertIsInstance(sample.data, bytes)
                    self.assertEqual(len(sample.data), size)
                    self.assertEqual(sample.size, size)
                    self.assertEqual(sample.generator, generator_name)
                    self.assertEqual(sample.seed, 20260911)
                    json.dumps(sample.parameters, sort_keys=True)

    def test_all_generators_are_reproducible_from_seed(self) -> None:
        for generator_name in data_generator.GENERATOR_NAMES:
            with self.subTest(generator=generator_name):
                first = data_generator.generate_sample(
                    generator_name, 4096, seed=314159
                )
                second = data_generator.generate_sample(
                    generator_name, 4096, seed=314159
                )

                self.assertEqual(first, second)

    def test_different_seeds_change_generated_data(self) -> None:
        for generator_name in data_generator.GENERATOR_NAMES:
            with self.subTest(generator=generator_name):
                first = data_generator.generate_sample(generator_name, 4096, seed=1)
                second = data_generator.generate_sample(generator_name, 4096, seed=2)

                self.assertNotEqual(first.data, second.data)

    def test_generation_does_not_modify_global_random_state(self) -> None:
        original_state = random.getstate()
        try:
            random.seed(12345)
            state_before_generation = random.getstate()
            data_generator.generate_sample("mixed", 4096, seed=99)
            self.assertEqual(random.getstate(), state_before_generation)
        finally:
            random.setstate(original_state)

    def test_small_alphabet_uses_only_recorded_byte_values(self) -> None:
        sample = data_generator.generate_sample(
            "small_alphabet", 16_384, seed=20260911
        )
        alphabet = sample.parameters["alphabet"]
        alphabet_size = sample.parameters["alphabet_size"]

        self.assertIsInstance(alphabet, list)
        self.assertIn(alphabet_size, (2, 4, 8, 16))
        self.assertEqual(len(alphabet), alphabet_size)
        self.assertEqual(len(set(alphabet)), alphabet_size)
        self.assertLessEqual(set(sample.data), set(alphabet))

    def test_repeated_pattern_matches_recorded_pattern(self) -> None:
        sample = data_generator.generate_sample(
            "repeated_pattern", 4097, seed=20260911
        )
        pattern = bytes.fromhex(str(sample.parameters["pattern_hex"]))
        pattern_length = sample.parameters["pattern_length"]
        repetitions = (sample.size + len(pattern) - 1) // len(pattern)

        self.assertEqual(len(pattern), pattern_length)
        self.assertIn(pattern_length, (4, 8, 16, 32, 64, 128))
        self.assertEqual(sample.data, (pattern * repetitions)[: sample.size])

    def test_long_runs_follow_recorded_length_range(self) -> None:
        sample = data_generator.generate_sample("long_runs", 16_384, seed=20260911)
        lengths = _run_lengths(sample.data)
        minimum = sample.parameters["min_run_length"]
        maximum = sample.parameters["max_run_length"]

        self.assertGreater(len(lengths), 1)
        self.assertTrue(all(minimum <= length <= maximum for length in lengths[:-1]))
        self.assertGreater(lengths[-1], 0)
        self.assertLessEqual(lengths[-1], maximum)

    def test_structured_generator_can_produce_all_recorded_formats(self) -> None:
        observed_formats = set()
        for seed in range(100):
            sample = data_generator.generate_sample("structured", 2048, seed=seed)
            format_name = sample.parameters["format"]
            observed_formats.add(format_name)
            sample.data.decode("ascii")

            if format_name == "jsonl":
                self.assertTrue(sample.data.startswith(b'{"id":0,'))
            elif format_name == "csv":
                self.assertTrue(sample.data.startswith(b"id,group,active,value\n"))
            elif format_name == "log":
                self.assertTrue(sample.data.startswith(b"2026-01-01 "))
            else:
                self.fail(f"Unexpected structured format: {format_name!r}")

        self.assertEqual(observed_formats, {"jsonl", "csv", "log"})

    def test_mixed_generator_records_all_segment_components(self) -> None:
        sample = data_generator.generate_sample("mixed", 16_384, seed=20260911)
        segments = sample.parameters["segments"]

        self.assertIsInstance(segments, list)
        self.assertEqual(len(segments), 5)
        self.assertEqual(
            {segment["generator"] for segment in segments},
            set(data_generator.GENERATOR_NAMES) - {"mixed"},
        )
        self.assertEqual(sum(segment["size"] for segment in segments), sample.size)
        for segment in segments:
            self.assertGreater(segment["size"], 0)
            self.assertIsInstance(segment["parameters"], dict)

    def test_small_sizes_and_invalid_inputs_are_handled(self) -> None:
        for generator_name in data_generator.GENERATOR_NAMES:
            for size in (1, 2, 17):
                with self.subTest(generator=generator_name, size=size):
                    sample = data_generator.generate_sample(
                        generator_name, size, seed=0
                    )
                    self.assertEqual(len(sample.data), size)

        with self.assertRaisesRegex(ValueError, "Unsupported generator"):
            data_generator.generate_sample("unknown", 16, seed=0)
        for invalid_size in (0, -1):
            with self.subTest(size=invalid_size), self.assertRaisesRegex(
                ValueError, "greater than zero"
            ):
                data_generator.generate_sample("random", invalid_size, seed=0)
        for invalid_size in (True, 1.5, "16"):
            with self.subTest(size=invalid_size), self.assertRaisesRegex(
                TypeError, "must be an integer"
            ):
                data_generator.generate_sample(  # type: ignore[arg-type]
                    "random", invalid_size, seed=0
                )
        for invalid_seed in (True, 1.5, "seed"):
            with self.subTest(seed=invalid_seed), self.assertRaisesRegex(
                TypeError, "must be an integer"
            ):
                data_generator.generate_sample(  # type: ignore[arg-type]
                    "random", 16, seed=invalid_seed
                )


if __name__ == "__main__":
    unittest.main()
