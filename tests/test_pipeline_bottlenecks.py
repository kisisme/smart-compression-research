"""Artificial timer fixtures, not empirical compression measurements."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'research_log/analyze_pipeline_bottlenecks_20261109.py'
SPEC = importlib.util.spec_from_file_location('pipeline_bottlenecks', PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def trials():
    return [dict(repeat_index=i, verified=True, compression_ns=100_000_000, restoration_ns=10_000_000,
                 feature_ns=f*1_000_000, prediction_ns=p*1_000_000, package_bytes=20,
                 algorithm='zstd', payload_sha256='fixture_payload', restored_sha256='fixture_source')
            for i, (f, p) in enumerate(((10, 10), (40, 10), (40, 40), (10, 40), (10, 10)), 1)]


class BottleneckTests(unittest.TestCase):
    def test_nonadditive_medians_get_explicit_alignment(self):
        result = m.aggregate(trials())
        self.assertEqual(result['feature_ms'], 10)
        self.assertEqual(result['prediction_ms'], 10)
        self.assertEqual(result['compression_remainder_ms'], 50)
        self.assertEqual(result['median_alignment_ms'], 30)
        self.assertEqual(result['without_both_ms'], 50)
        self.assertNotEqual(result['without_both_ms'], result['compression_ms']-result['feature_ms']-result['prediction_ms'])

    def test_incomplete_duplicate_or_invalid_nested_timers_reject(self):
        for kind in ('incomplete', 'duplicate', 'nested', 'unverified', 'negative', 'inconsistent'):
            rows = trials()
            if kind == 'incomplete': rows.pop()
            elif kind == 'duplicate': rows[0]['repeat_index'] = 2
            elif kind == 'nested': rows[0]['feature_ns'] = 200_000_000
            elif kind == 'unverified': rows[0]['verified'] = False
            elif kind == 'negative': rows[0]['prediction_ns'] = -1
            else: rows[0]['payload_sha256'] = 'different'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                m.aggregate(rows)

    def test_decomposition_closes_with_nonadditive_medians_and_signed_remainder(self):
        observed = m.aggregate(trials())
        baseline = dict(observed, compression_ms=110, restoration_ms=15, package_bytes=22)
        selected = dict(compressed_size=10, compression_time_ms=60, decompression_time_ms=2)
        zstd = dict(compressed_size=12, compression_time_ms=20, decompression_time_ms=3)
        p = dict(storage_cost_per_byte_day=.5, retention_days=2, compression_cost_per_ms=2,
                 decompression_cost_per_ms=.1, expected_restorations=10)
        delta, terms = m.decompose(p, observed, baseline, selected, zstd)
        self.assertEqual(delta, -27)
        self.assertAlmostEqual(sum(terms.values()), delta)
        self.assertLess(terms['compression_remainder_delta'], 0)
        self.assertEqual(terms['median_alignment_delta'], 60)

    def test_zero_overhead_baseline_has_no_alignment(self):
        rows = trials()
        for r in rows:
            r['feature_ns'] = r['prediction_ns'] = 0
        value = m.aggregate(rows)
        self.assertEqual(value['median_alignment_ms'], 0)
        self.assertEqual(value['without_both_ms'], value['compression_ms'])

    def test_same_names_keep_distinct_samples_but_duplicate_key_rejects(self):
        rows = [dict(sample_id=s, filename='package.json') for s in ('a', 'b')]
        self.assertEqual(len(m.index(rows, ('sample_id',))), 2)
        with self.assertRaises(ValueError):
            m.index(rows + [copy.copy(rows[0])], ('sample_id',))

    def test_multiple_restorations_are_charged_and_package_bytes_used(self):
        p = dict(storage_cost_per_byte_day=.5, retention_days=2, compression_cost_per_ms=2,
                 decompression_cost_per_ms=.1, expected_restorations=10)
        self.assertEqual(m.cost(p, 20, 3, 4), 30)


if __name__ == '__main__':
    unittest.main()
