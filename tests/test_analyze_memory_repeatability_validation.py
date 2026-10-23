"""Artificial full replacement evidence; fixture values are not research data."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from research_log import analyze_memory_repeatability_validation as analysis
from research_log import verify_memory_repeatability_validation as audit
import test_analyze_memory_stability_validation as numeric_tests
import test_verify_memory_repeatability_validation as fixtures


class PolicyTests(unittest.TestCase):
    def test_numeric_kernel_is_unchanged_and_all_frozen_rules_match(self):
        self.assertIs(analysis._calculate, analysis.numeric._calculate)
        plan = audit.fixed_plan("artificial", "Artificial test only")
        config = audit.parse_json((audit.ROOT / "config/experiment_config.json").read_bytes())
        analysis._check_policy(plan, config)
        for section, key, value in (("candidate_weights", "balanced", dict(size=.4, compress=.2, decompress=.1, memory=.3)),
                                    ("criteria", "delta", .02), ("criteria", "tie_order", list(reversed(audit.ALGORITHMS)))):
            altered = copy.deepcopy(plan)
            altered[section][key] = value
            with self.assertRaises(audit.AuditError):
                analysis._check_policy(altered, config)
        config["selection_modes"]["balanced"]["compression_ratio"] = .4
        with self.assertRaisesRegex(audit.AuditError, "Official comparison weights"):
            analysis._check_policy(plan, config)

    def test_adapter_uses_same_kernel_for_unfavorable_memory_and_joint_results(self):
        def edit(run, sid, algorithm, values):
            if algorithm == "gzip" and run == 2:
                values.update(mc=100000, compress=100000000)
        result = analysis._calculate(*numeric_tests.numeric_fixture(edit))
        self.assertEqual(result["decision"]["status"], "memory_stability_not_satisfied")
        self.assertFalse(result["decision"]["joint_stability_satisfied"])
        self.assertFalse(result["decision"]["by_stratum"]["tiny"]["memory_stability_satisfied"])


@unittest.skipUnless(sys.platform == "win32", "Full fixture records Windows paths")
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only fixture construction uses producers/codecs, never the analysis.
        fixtures.RepeatabilityAuditTests.setUpClass.__func__(cls)

    def setUp(self):
        self.case = self.root / self._testMethodName
        shutil.copytree(self.template, self.case)
        self.addCleanup(shutil.rmtree, self.case)
        self.directory, self.session = self.case / "active", self.case / "replacement"
        self.output = self.root / (self._testMethodName + "_output")
        if self._testMethodName != "test_full_audit_binding_no_producers_and_complete_tables":
            patched = patch.object(audit, "generated_samples", return_value=self.canonical_samples)
            patched.start()
            self.addCleanup(patched.stop)

    def analyze(self):
        return analysis.analyze(self.directory, self.session)

    def test_full_audit_binding_no_producers_and_complete_tables(self):
        before = fixtures.publisher.tree_hashes(self.case)
        forbidden = AssertionError("Analysis invoked producer, codec or old auditor/analyzer")
        with patch.object(fixtures.runner, "run_worker", side_effect=forbidden), \
             patch.object(fixtures.runner.compressors, "compress_data", side_effect=forbidden), \
             patch.object(fixtures.runner.compressors, "decompress_data", side_effect=forbidden), \
             patch.object(fixtures.publisher, "validate_saved", side_effect=forbidden), \
             patch.object(audit.base, "audit", side_effect=forbidden), \
             patch.object(analysis.numeric, "analyze", side_effect=forbidden):
            report = self.analyze()
        self.assertEqual(report["counts"], dict(samples=84, representatives=2016, phase_groups=8064,
                        candidate_labels=4788, transfer_regrets=27216, anchor_regrets=4536, comparisons=1512))
        self.assertEqual(report["decision"]["status"], "observed_conditions_satisfied")
        self.assertEqual(report["active_execution_order"], [1, 3, 4, 5, 6, 2])
        self.assertFalse(report["original_schedule_order_preserved"])
        self.assertEqual(report["audit"]["original_counts"]["failed_repeats"], 3)
        self.assertEqual(report["audit"]["active_counts"]["failed_repeats"], 0)
        self.assertFalse(report["score_inclusion"])
        self.assertNotIn("day_offsets_hours", report["criteria"])
        self.assertIn("analyze_memory_stability_validation.py", " ".join(report["source_sha256"]))
        self.assertEqual(before, fixtures.publisher.tree_hashes(self.case))

    def test_invalid_audit_never_calculates(self):
        (self.session / "original_snapshot/run_02/memory_repeats.csv").write_bytes(b"invalid")
        with patch.object(analysis, "_calculate", side_effect=AssertionError("Must not calculate")):
            with self.assertRaises(audit.AuditError):
                self.analyze()
        self.assertFalse(self.output.exists())

    def test_drift_after_audit_in_either_root_is_rejected(self):
        perform = audit.audit
        for target in (self.directory / "run_01/measurements.csv", self.session / "original_snapshot/run_02/memory_repeats.csv"):
            original = target.read_bytes()
            def changed(*args):
                result = perform(*args)
                target.write_bytes(original + b"\n")
                return result
            with patch.object(audit, "audit", side_effect=changed):
                with self.assertRaisesRegex(audit.AuditError, "Evidence changed"):
                    self.analyze()
            target.write_bytes(original)

    def test_drift_during_calculation_and_inventory_changes_are_rejected(self):
        calculate = analysis._calculate
        for target in (self.session / "archive_extra.txt", self.directory / ".active_run.json"):
            def changed(*args):
                result = calculate(*args)
                target.write_bytes(b"{}")
                return result
            with patch.object(analysis, "_calculate", side_effect=changed):
                with self.assertRaises(audit.AuditError):
                    self.analyze()
            target.unlink()

    def test_analysis_and_numeric_source_drift_rejected(self):
        original_read = Path.read_bytes
        for module in (analysis, analysis.numeric):
            target = Path(module.__file__).resolve()
            calls = 0
            def changed(path):
                nonlocal calls
                data = original_read(path)
                if path.resolve() == target:
                    calls += 1
                    if calls > 1:
                        return data + b"\n"
                return data
            with patch.object(Path, "read_bytes", changed):
                with self.assertRaisesRegex(audit.AuditError, "source changed"):
                    self.analyze()

    def test_export_csv_roundtrip_hashes_and_no_overwrite_or_input_writes(self):
        report = self.analyze()
        before = fixtures.publisher.tree_hashes(self.case)
        analysis.publish(report, self.output)
        self.assertEqual({p.name for p in self.output.iterdir()},
                         {".gitattributes", "audit.json", "candidate_labels.csv", "transfer_regrets.csv", "stability_summary.json"})
        summary = fixtures.load(self.output / "stability_summary.json")
        self.assertEqual(summary["decision"], report["decision"])
        for name, checksum in summary["output_artifact_sha256"].items():
            self.assertEqual(audit.digest((self.output / name).read_bytes()), checksum)
        self.assertEqual(len(fixtures.rows(self.output / "candidate_labels.csv")), 4788)
        regrets = fixtures.rows(self.output / "transfer_regrets.csv")
        self.assertEqual([float(r["regret"]) for r in regrets], [r["regret"] for r in report["transfer_regrets"]])
        saved = fixtures.publisher.tree_hashes(self.output)
        with self.assertRaisesRegex(audit.AuditError, "already exists"):
            analysis.publish(report, self.output)
        self.assertEqual(saved, fixtures.publisher.tree_hashes(self.output))
        for root in (self.directory, self.session):
            with self.assertRaisesRegex(audit.AuditError, "outside input evidence"):
                analysis.publish(report, root / "new_analysis")
        self.assertEqual(before, fixtures.publisher.tree_hashes(self.case))

    def test_disk_failure_preserves_partial_output_and_marks_inconclusive(self):
        report = self.analyze()
        with patch.object(analysis.os, "fsync", side_effect=OSError("Artificial disk failure")):
            with self.assertRaisesRegex(OSError, "Artificial disk failure"):
                analysis.publish(report, self.output)
        self.assertTrue((self.output / "audit.json").exists())
        self.assertFalse((self.output / "stability_summary.json").exists())
        self.assertEqual(fixtures.load(self.output / "publication_failed.json")["validity_status"], "inconclusive")

    def test_postwrite_drift_keeps_files_and_failure_marker(self):
        report = self.analyze()
        original = analysis._recheck
        calls = 0
        def drift(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                (self.session / "late_file.txt").write_bytes(b"artificial")
            return original(*args)
        with patch.object(analysis, "_recheck", side_effect=drift):
            with self.assertRaises(audit.AuditError):
                analysis.publish(report, self.output)
        self.assertTrue((self.output / "stability_summary.json").exists())
        self.assertEqual(fixtures.load(self.output / "publication_failed.json")["publication_status"], "failed")

    def test_cli_guard_optimized_rejection_and_bytecode_requirement(self):
        guard = """import importlib.abc, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'src.memory_repeatability_validation','research_log.replace_memory_repeatability_run02',
                        'src.memory_stability_validation','src.memory_stability_timing_worker','src.memory_validation',
                        'src.memory_benchmark','src.compressors','src.scoring'}:
            raise RuntimeError('Prohibited import: ' + fullname)
sys.meta_path.insert(0, Guard())
from research_log.analyze_memory_repeatability_validation import main
raise SystemExit(main(sys.argv[1:]))
"""
        args = ["--experiment-dir", str(self.directory), "--replacement-dir", str(self.session), "--output-dir", str(self.output)]
        result = subprocess.run([sys.executable, "-B", "-c", guard, *args], cwd=audit.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["transfer_regrets"], 27216)
        (self.directory / "run_01/measurements.csv").write_bytes(b"invalid")
        for flag in (None, "-O", "-OO"):
            output = self.root / (self._testMethodName + str(flag))
            invalid_args = args[:-1] + [str(output)]
            result = subprocess.run([sys.executable, "-B", *([flag] if flag else []), "-m",
                                     "research_log.analyze_memory_repeatability_validation", *invalid_args],
                                    cwd=audit.ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("inconclusive", result.stderr)
            self.assertFalse(output.exists())
        with patch.object(sys, "dont_write_bytecode", False):
            with self.assertRaisesRegex(audit.AuditError, "python -B"):
                self.analyze()


if __name__ == "__main__":
    unittest.main()
