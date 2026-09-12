"""Tests for isolated Windows peak-memory measurement."""

from __future__ import annotations

import sys
import unittest

from src.memory_benchmark import (
    MEMORY_STATUS,
    benchmark_peak_memory,
    current_process_peak_working_set_bytes,
)


@unittest.skipUnless(sys.platform == "win32", "Windows measurement backend")
class MemoryBenchmarkTests(unittest.TestCase):
    def test_configured_backend_returns_positive_process_peak(self) -> None:
        self.assertEqual(MEMORY_STATUS, "validation_only")
        self.assertGreater(current_process_peak_working_set_bytes(), 0)

    def test_isolated_gzip_benchmark_returns_five_verified_repeats(self) -> None:
        result = benchmark_peak_memory(b"ABCD" * 16_384, "gzip")

        self.assertEqual(result.algorithm, "gzip")
        self.assertEqual(
            result.measurement_method,
            "windows_get_process_memory_info_peak_working_set",
        )
        self.assertEqual(len(result.compression_peak_memory_repeats_bytes), 5)
        self.assertEqual(len(result.decompression_peak_memory_repeats_bytes), 5)
        self.assertTrue(all(value > 0 for value in result.compression_peak_memory_repeats_bytes))
        self.assertTrue(all(value > 0 for value in result.decompression_peak_memory_repeats_bytes))
        self.assertEqual(
            result.peak_memory_bytes,
            max(
                result.compression_peak_memory_bytes,
                result.decompression_peak_memory_bytes,
            ),
        )
        self.assertTrue(result.verified)

    def test_invalid_inputs_are_rejected_before_workers_start(self) -> None:
        with self.assertRaises(TypeError):
            benchmark_peak_memory(bytearray(b"data"), "gzip")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            benchmark_peak_memory(b"", "gzip")
        with self.assertRaises(ValueError):
            benchmark_peak_memory(b"data", "unknown")


if __name__ == "__main__":
    unittest.main()
