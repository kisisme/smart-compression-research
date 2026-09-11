"""Tests for the compression and in-memory benchmark engine."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src import compressors


class CompressorTests(unittest.TestCase):
    ALGORITHMS = ("gzip", "bz2", "lzma", "zstd")
    SAMPLE_DATA = bytes(range(256)) * 8 + b"A" * 4096 + b"ABC123" * 512

    def test_protocol_configuration_is_loaded(self) -> None:
        self.assertEqual(compressors._SUPPORTED_ALGORITHMS, self.ALGORITHMS)
        self.assertEqual(compressors._GZIP_LEVEL, 9)
        self.assertEqual(compressors._BZ2_LEVEL, 9)
        self.assertEqual(compressors._LZMA_PRESET, 6)
        self.assertEqual(compressors._ZSTD_LEVEL, 3)
        self.assertEqual(compressors._TIMING_REPEATS, 5)
        self.assertEqual(compressors._TIMING_TIMER, "time.perf_counter_ns")
        self.assertEqual(compressors._TIMING_AGGREGATE, "median")

    def test_all_algorithms_restore_original_data(self) -> None:
        for algorithm in self.ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                compressed = compressors.compress_data(self.SAMPLE_DATA, algorithm)
                restored = compressors.decompress_data(compressed, algorithm)

                self.assertIsInstance(compressed, bytes)
                self.assertEqual(restored, self.SAMPLE_DATA)

    def test_benchmark_returns_required_measurements(self) -> None:
        expected_fields = {
            "algorithm",
            "original_size",
            "compressed_size",
            "compression_ratio",
            "compression_time_ms",
            "decompression_time_ms",
            "verified",
        }

        for algorithm in self.ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                result = compressors.benchmark_compressor(
                    self.SAMPLE_DATA, algorithm
                )

                self.assertEqual(set(result), expected_fields)
                self.assertEqual(result["algorithm"], algorithm)
                self.assertEqual(result["original_size"], len(self.SAMPLE_DATA))
                self.assertGreater(result["compressed_size"], 0)
                self.assertEqual(
                    result["compression_ratio"],
                    result["compressed_size"] / result["original_size"],
                )
                self.assertGreater(result["compression_time_ms"], 0)
                self.assertGreater(result["decompression_time_ms"], 0)
                self.assertIs(result["verified"], True)

    def test_benchmark_uses_five_repeats_and_median_times(self) -> None:
        compression_durations_ns = [9, 1, 7, 3, 5]
        decompression_durations_ns = [8, 2, 6, 4, 10]
        clock_values: list[int] = []
        cursor = 1_000
        for duration in compression_durations_ns + decompression_durations_ns:
            clock_values.extend((cursor, cursor + duration))
            cursor += 100

        with (
            patch.object(
                compressors.time,
                "perf_counter_ns",
                side_effect=clock_values,
            ),
            patch.object(
                compressors,
                "compress_data",
                return_value=b"encoded",
            ) as compress_mock,
            patch.object(
                compressors,
                "decompress_data",
                return_value=b"original",
            ) as decompress_mock,
        ):
            result = compressors.benchmark_compressor(b"original", "gzip")

        self.assertEqual(compress_mock.call_count, 5)
        self.assertEqual(decompress_mock.call_count, 5)
        self.assertEqual(result["compression_time_ms"], 5 / 1_000_000)
        self.assertEqual(result["decompression_time_ms"], 6 / 1_000_000)
        self.assertIs(result["verified"], True)

    def test_benchmark_reports_failed_restoration(self) -> None:
        restored_results = [b"original"] * 4 + [b"corrupted"]

        with (
            patch.object(compressors, "compress_data", return_value=b"encoded"),
            patch.object(
                compressors,
                "decompress_data",
                side_effect=restored_results,
            ),
        ):
            result = compressors.benchmark_compressor(b"original", "gzip")

        self.assertIs(result["verified"], False)

    def test_benchmark_rejects_empty_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty input"):
            compressors.benchmark_compressor(b"", "gzip")

    def test_public_functions_reject_unknown_algorithm(self) -> None:
        calls = (
            lambda: compressors.compress_data(b"data", "unknown"),
            lambda: compressors.decompress_data(b"data", "unknown"),
            lambda: compressors.benchmark_compressor(b"data", "unknown"),
        )

        for call in calls:
            with self.subTest(call=call), self.assertRaisesRegex(
                ValueError, "Unsupported compression algorithm"
            ):
                call()


if __name__ == "__main__":
    unittest.main()
