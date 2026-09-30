"""Artificial peaks only; these fixtures are not research measurements."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from research_log import analyze_memory_runtime_validation as analysis
from research_log import verify_memory_runtime_validation as audit
import test_verify_memory_runtime_validation as fixtures


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        for run in (1, 2, 3):
            for algorithm in audit.ALGORITHMS:
                for phase in audit.PHASES:
                    # Median paired difference differs from difference of medians.
                    arms = dict(import_only=[10, 20, 30, 40, 50],
                                input_only=[100, 10, 20, 30, 40], codec=[101, 11, 21, 31, 1])
                    if algorithm == 'bz2':
                        arms['codec'] = ([50, 5, 10, 15, 1] if run == 3 else
                                         [v + (run - 1) * 10 for v in [101, 21, 31, 41, 11]])
                    elif algorithm == 'lzma':
                        arms['codec'] = [201, 111, 121, 131, 101]
                    for arm, values in arms.items():
                        for round_id, value in enumerate(values, 1):
                            self.rows.append(dict(run_id=str(run), sample_id='fixture', algorithm=algorithm,
                                                  phase=phase, arm=arm, round_index=str(round_id),
                                                  peak_process_working_set_bytes=str(value)))
        # Schedule order must not accidentally become pairing order.
        self.report = analysis._calculate(list(reversed(self.rows)))

    def test_paired_signed_values_ratios_and_median_of_differences(self):
        records = {r['contrast']: r for r in self.report['paired_by_run']
                   if r['run_id'] == 1 and r['algorithm'] == 'gzip' and r['phase'] == 'compress'}
        self.assertEqual(records['D_input']['values'], [90, -10, -10, -10, -10])
        self.assertEqual(records['D_codec']['values'], [1, 1, 1, 1, -39])
        self.assertEqual(records['D_codec']['median'], 1)
        self.assertEqual(records['R_input']['values'], [100/101, 10/11, 20/21, 30/31, 40])
        pair = next(r for r in self.report['arm_pairs_by_run'] if r['run_id'] == 1
                    and r['algorithm'] == 'gzip' and r['phase'] == 'compress'
                    and r['left'] == 'input_only' and r['right'] == 'codec')
        self.assertEqual(pair['median_difference_bytes'], 9)

    def test_all_pairs_ties_overlap_and_cross_run_rank_reversal(self):
        pairs = [r for r in self.report['algorithm_pairs_by_run'] if r['run_id'] == 1 and r['phase'] == 'compress']
        self.assertEqual(len(pairs), 6)
        tie = next(r for r in pairs if r['left'] == 'gzip' and r['right'] == 'zstd')
        self.assertTrue(tie['tied'])
        self.assertEqual(tie['sign'], 0)
        self.assertTrue(tie['ranges_overlap'])
        # gzip [1,101], lzma [101,201]: touching endpoints count as overlap.
        self.assertTrue(next(r for r in pairs if r['left'] == 'gzip' and r['right'] == 'lzma')['ranges_overlap'])
        self.assertFalse(analysis._comparison([1, 2, 3, 4, 5], [6, 7, 8, 9, 10])['ranges_overlap'])
        cross = next(r for r in self.report['algorithm_pairs_across_runs']
                     if r['left'] == 'gzip' and r['right'] == 'bz2' and r['phase'] == 'compress')
        self.assertEqual(cross['run_values'], [-10, -20, 11])
        self.assertEqual(cross['signs'], [-1, -1, 1])
        self.assertFalse(cross['sign_consistent'])
        self.assertFalse(analysis._across([-1, 0, 1])['sign_consistent'])

    def test_peak_population_statistics_and_separate_runs(self):
        peak = next(r for r in self.report['peak_by_run'] if r['run_id'] == 1 and r['algorithm'] == 'gzip'
                    and r['phase'] == 'compress' and r['arm'] == 'import_only')
        self.assertEqual(peak['values'], [10, 20, 30, 40, 50])
        self.assertEqual(peak['median'], 30)
        self.assertAlmostEqual(peak['population_std'], 200 ** 0.5)
        self.assertAlmostEqual(peak['cv'], (200 ** 0.5) / 30)
        self.assertTrue(all(len(r['values']) == 5 for r in self.report['peak_by_run']))
        self.assertTrue(all(len(r['run_values']) == 3 for r in self.report['paired_across_runs']))
        ratio = next(r for r in self.report['paired_across_runs'] if r['contrast'] == 'R_input')
        self.assertEqual(ratio['sign_reference'], 1)


@unittest.skipUnless(sys.platform == 'win32', 'Fixture uses Windows environment metadata')
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RuntimeAuditTests.setUpClass.__func__(cls)

    def setUp(self):
        self.directory = self.root / self._testMethodName
        shutil.copytree(self.original, self.directory)

    def test_real_audit_full_matrix_no_measurement_and_byte_preservation(self):
        before = {p.relative_to(self.directory): p.read_bytes() for p in self.directory.rglob('*') if p.is_file()}
        with patch.object(fixtures.runner, 'run_worker', side_effect=AssertionError('measurement')), \
             patch.object(fixtures.runner.compressors, 'compress_data', side_effect=AssertionError('compression')), \
             patch.object(fixtures.runner.compressors, 'decompress_data', side_effect=AssertionError('restoration')):
            result = analysis.analyze(self.directory)
        self.assertTrue(result['audit']['audit_passed'])
        self.assertFalse(result['score_inclusion'])
        self.assertEqual(result['measurement_status'], 'validation_only')
        self.assertEqual(len(result['peak_by_run']), 1080)
        self.assertEqual(len(result['paired_by_run']), 1080)
        self.assertEqual(len(result['arm_pairs_by_run']), 1080)
        self.assertEqual(len(result['algorithm_pairs_by_run']), 540)
        self.assertEqual(len(result['algorithm_pairs_across_runs']), 180)
        self.assertTrue(all(r['median'] == 1
                            for r in result['paired_by_run'] if r['contrast'] in ('D_input', 'D_codec')))
        self.assertEqual(before, {p.relative_to(self.directory): p.read_bytes() for p in self.directory.rglob('*') if p.is_file()})

    def test_incomplete_evidence_rejected_before_calculation(self):
        path = self.directory / 'metadata.json'
        meta = fixtures.load(path)
        meta['run_status'] = 'interrupted'
        fixtures.save(path, meta)
        with patch.object(analysis, '_calculate', side_effect=AssertionError('must not calculate')):
            with self.assertRaises(audit.AuditError):
                analysis.analyze(self.directory)

    def test_changed_evidence_after_audit_and_during_calculation_rejected(self):
        original_audit = audit.audit
        target = self.directory / 'run_01/repeats.csv'
        original = target.read_bytes()
        def changed(directory):
            result = original_audit(directory)
            target.write_bytes(original + b'\n')
            return result
        with patch.object(audit, 'audit', side_effect=changed):
            with self.assertRaisesRegex(audit.AuditError, 'changed after audit'):
                analysis.analyze(self.directory)
        target.write_bytes(original)
        calculate = analysis._calculate
        def changed_during(rows):
            result = calculate(rows)
            target.write_bytes(original + b'\n')
            return result
        with patch.object(analysis, '_calculate', side_effect=changed_during):
            with self.assertRaisesRegex(audit.AuditError, 'changed during analysis'):
                analysis.analyze(self.directory)

    def test_cli_success_exclusive_output_and_optimized_failure(self):
        base = [sys.executable, '-B']
        module = ['-m', 'research_log.analyze_memory_runtime_validation', '--experiment-dir', str(self.directory)]
        output = self.directory / 'diagnostic_summary.json'
        command = [*base, *module, '--output', str(output)]
        result = subprocess.run(command, cwd=audit.ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), fixtures.load(output))
        saved = output.read_bytes()
        result = subprocess.run(command, cwd=audit.ROOT, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertEqual(output.read_bytes(), saved)
        (self.directory / 'run_01/repeats.csv').write_text('invalid', encoding='utf-8')
        for optimization in ([], ['-O'], ['-OO']):
            failed = self.directory / ('failed' + ''.join(optimization) + '.json')
            result = subprocess.run([*base, *optimization, *module, '--output', str(failed)],
                                    cwd=audit.ROOT, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertFalse(failed.exists())


if __name__ == '__main__':
    unittest.main()
