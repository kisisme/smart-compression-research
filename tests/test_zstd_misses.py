"""Artificial diagnostics only: strict comparisons, failed joins and saved choices."""
import importlib.util
import math
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'research_log/analyze_zstd_misses_20261031.py'
SPEC = importlib.util.spec_from_file_location('zstd_misses', PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class ZstdMissTests(unittest.TestCase):
    def test_include_better_non_oracle_alternatives(self):
        best, better, equal = m.classify(dict(gzip=3., bz2=2., lzma=5., zstd=4.))
        self.assertEqual((best, better, equal), ('bz2', ['gzip', 'bz2'], []))

    def test_strict_gain_survives_one_float_step_and_ties_are_separate(self):
        costs = dict(gzip=math.nextafter(1., 0.), bz2=1., lzma=2., zstd=1.)
        self.assertEqual(m.classify(costs), ('gzip', ['gzip'], ['bz2']))
        costs['gzip'] = 1.
        self.assertEqual(m.classify(costs), ('gzip', [], ['gzip', 'bz2']))

    def test_bad_or_incomplete_costs_reject(self):
        for bad in (0., -1., math.inf, math.nan):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                m.classify(dict(gzip=bad, bz2=1., lzma=2., zstd=3.))
        with self.assertRaises(ValueError):
            m.classify(dict(gzip=1., zstd=2.))

    def test_identity_keeps_same_name_distinct_but_duplicate_keys_reject(self):
        rows = [dict(sample_id='a', filename='package.json', scenario='x', model='dt'),
                dict(sample_id='b', filename='package.json', scenario='x', model='dt')]
        self.assertEqual(len(m.index_unique(rows, ('sample_id', 'scenario', 'model'))), 2)
        with self.assertRaises(ValueError):
            m.index_unique(rows + [rows[0]], ('sample_id', 'scenario', 'model'))

    def test_cost_decomposition_accounts_for_storage_and_multiple_restorations(self):
        row = dict(compressed_size='10', compression_time_ms='2', decompression_time_ms='3')
        policy = dict(storage_cost_per_byte_day='0.5', retention_days='4', compression_cost_per_ms='2',
                      decompression_cost_per_ms='0.1', expected_restorations='10')
        self.assertEqual(m.independent_components(row, policy), dict(storage=20., compression=4., restoration=3.))

    def test_saved_choice_mismatch_rejects_instead_of_changing_truth(self):
        costs = dict(gzip=1., bz2=3., lzma=4., zstd=2.)
        metadata = dict(format='text', origin_group_id='fixture')
        prediction = dict(predicted_algorithm='zstd')
        row = dict(true_algorithm='gzip', chosen_algorithm='zstd', policy_cost='2', oracle_cost='1',
                   zstd_cost='2', regret='1', **metadata)
        m.validate_choice(row, costs, prediction, metadata)
        for field, wrong in (('oracle_cost', '2'), ('chosen_algorithm', 'gzip'),
                             ('origin_group_id', 'wrong'), ('true_algorithm', 'bz2')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                m.validate_choice({**row, field: wrong}, costs, prediction, metadata)

    def test_raw_status_uses_phase_specific_fields_and_checks_restored_hash(self):
        row = dict(status='ok', error='', consistent_with_reference='True', verified='', output_sha256='compressed')
        m.validate_repeat_status(row, 'compress', 'original')
        restored = dict(row, consistent_with_reference='', verified='True', output_sha256='original')
        m.validate_repeat_status(restored, 'decompress', 'original')
        with self.assertRaises(ValueError):
            m.validate_repeat_status(restored, 'decompress', 'different')
        with self.assertRaises(ValueError):
            m.validate_repeat_status(dict(row, consistent_with_reference='False'), 'compress', 'original')
        with self.assertRaises(ValueError):
            m.validate_repeat_status(dict(restored, verified='False'), 'decompress', 'original')


if __name__ == '__main__':
    unittest.main()
