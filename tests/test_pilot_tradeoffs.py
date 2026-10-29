"""Synthetic numerical fixtures only; no research compression or model runs."""
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1]/'research_log/analyze_pilot_tradeoffs_20261029.py'
SPEC = importlib.util.spec_from_file_location('pilot_tradeoff_analysis', PATH)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def measurements():
    values = {'gzip':(.4,4,2),'bz2':(.2,8,8),'lzma':(.5,10,10),'zstd':(.4,1,1)}
    return {a:dict(zip(analysis.METRICS,v)) for a,v in values.items()}


class TradeoffTests(unittest.TestCase):
    def test_tradeoff_changes_winner_and_dominated_codec_never_wins(self):
        loss = analysis.losses(measurements())
        self.assertEqual(analysis.select(loss,(1,0,0))[0],'bz2')
        self.assertEqual(analysis.select(loss,(0,.5,.5))[0],'zstd')
        self.assertEqual(analysis.select(loss,(.7,.15,.15))[0],'zstd')

    def test_exact_tie_selection_is_distinct_from_strict_gain(self):
        rows = measurements()
        rows['bz2']['compression_ratio'] = .6
        result = analysis.sensitivity_row({'fixture':analysis.losses(rows)},(1,0,0),'fixture')
        self.assertEqual(result['gzip_selected'],1)
        self.assertEqual(result['non_zstd_selected_pct'],100)
        self.assertEqual(result['strict_non_zstd_gain_count'],0)
        self.assertEqual(result['non_zstd_tie_only_count'],1)

    def test_pareto_handles_tradeoff_and_equal_values(self):
        rows = measurements()
        rows['gzip'] = dict(rows['zstd'])
        front, dominators = analysis.pareto(rows)
        self.assertEqual(front,['gzip','bz2','zstd'])
        self.assertIn('zstd',dominators['lzma'])
        self.assertEqual(dominators['gzip'],[])

    def test_unit_scaling_does_not_change_score(self):
        rows = measurements()
        original = analysis.select(analysis.losses(rows),(.5,.25,.25))
        for row in rows.values():
            row['compression_time_ms'] *= 1000000
            row['decompression_time_ms'] *= 1000
        converted = analysis.select(analysis.losses(rows),(.5,.25,.25))
        self.assertEqual(original[0],converted[0])
        for a in original[1]:
            self.assertAlmostEqual(original[1][a],converted[1][a],places=14)

    def test_tiny_strict_gain_is_not_reported_as_robust_gain(self):
        loss = {a:(0,1,1) for a in analysis.ALGORITHMS}
        loss['zstd'] = (1e-14,1,1)
        result = analysis.sensitivity_row({'fixture':loss},(1,0,0),'fixture')
        self.assertEqual(result['strict_non_zstd_gain_count'],1)
        self.assertEqual(result['gain_over_1e_12_count'],0)

    def test_empty_singleton_and_interpolated_distributions(self):
        self.assertIsNone(analysis.distribution([])['mean'])
        self.assertEqual(analysis.distribution([3])['p90'],3)
        self.assertAlmostEqual(analysis.distribution([0,10])['p90'],9)

    def test_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'evidence.json'
            analysis.write_json(path,{'fixture':True})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                analysis.write_json(path,{'fixture':False})
            self.assertEqual(path.read_bytes(),before)

    def test_duplicate_csv_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'fixture.csv'
            path.write_text('sample_id,sample_id\na,b\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate CSV columns'):
                analysis.read_csv(path)


if __name__ == '__main__':
    unittest.main()
