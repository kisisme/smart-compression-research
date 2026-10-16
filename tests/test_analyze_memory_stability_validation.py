"""Artificial numeric fixtures; no values here are research measurements."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_log import analyze_memory_stability_validation as analysis
from research_log import verify_memory_stability_validation as audit
import test_verify_memory_stability_validation as fixtures


def numeric_fixture(edit=None):
    samples = [dict(sample_id="core_fixture", stratum="core"), dict(sample_id="tiny_fixture", stratum="tiny")]
    measurements, raw = {}, {}
    for run in range(1, 7):
        measurements[run], raw[run] = [], dict(memory=[], timing=[])
        for sample in samples:
            for algorithm in audit.ALGORITHMS:
                values = dict(size=1., compress=1000000, decompress=1000000, mc=10000, md=10000)
                if edit:
                    edit(run, sample["sample_id"], algorithm, values)
                identity = dict(sample_id=sample["sample_id"], algorithm=algorithm)
                measurements[run].append(dict(**identity, verified="True", failed_repeat_count="0",
                    compression_ratio=str(values["size"]), compression_time_ms=str(values["compress"] / 1000000),
                    decompression_time_ms=str(values["decompress"] / 1000000), compression_peak_memory_bytes=str(values["mc"]),
                    decompression_peak_memory_bytes=str(values["md"]), peak_memory_bytes=str(max(values["mc"], values["md"]))))
                for phase in audit.PHASES:
                    for index in range(1, 6):
                        common = dict(**identity, phase=phase, repeat_index=str(index))
                        # Raw distributions need not pair memory/timing or phases.
                        raw[run]["memory"].append(dict(**common, peak_process_working_set_bytes=str(values["mc" if phase == "compress" else "md"])))
                        raw[run]["timing"].append(dict(**common, elapsed_ns=str(values[phase])))
    return samples, measurements, raw


class CalculationTests(unittest.TestCase):
    def test_exact_ties_zero_gap_full_directed_matrix_and_stability_without_benefit(self):
        report = analysis._calculate(*numeric_fixture())
        self.assertEqual(report["counts"], dict(samples=2, representatives=48, phase_groups=192,
                                             candidate_labels=114, transfer_regrets=648, anchor_regrets=108, comparisons=36))
        self.assertTrue(all(r["tied_algorithms"] == list(audit.ALGORITHMS) and r["best_algorithm"] == "gzip"
                            and r["best_score"] == r["second_best_gap"] == 0 for r in report["candidate_labels"]))
        self.assertTrue(all(r["regret"] == 0 for r in report["transfer_regrets"]))
        self.assertTrue(all(r["maximum_phases"] == ["compress", "decompress"] for r in report["representatives"]))
        self.assertEqual(report["decision"]["status"], "observed_conditions_satisfied")
        self.assertEqual(report["observed_memory_benefit_condition_count"], 0)
        self.assertTrue(all(r["tied_by_run"] == [True] * 6 for r in report["memory_algorithm_pairs"]))

    def test_unrounded_near_tie_is_not_forced_to_a_tie(self):
        metrics = {a: dict(size=1., compress=1., decompress=1., memory=1.) for a in audit.ALGORITHMS}
        metrics["gzip"]["size"] = math.nextafter(1., math.inf)
        selected = analysis.select(metrics, audit.WEIGHTS["archive"])
        self.assertEqual(selected["best_algorithm"], "bz2")
        self.assertGreater(selected["score_gzip"], 0)
        self.assertNotIn("gzip", selected["tied_algorithms"])

    def test_directional_regret_asymmetry_memory_only_and_phase_switch(self):
        def edit(run, sid, algorithm, v):
            if algorithm == "gzip":
                v.update(mc=100 if run == 1 else 390, md=90 if run == 1 else 400)
            elif algorithm == "zstd":
                v.update(mc=200 if run == 1 else 100, md=180 if run == 1 else 90)
        report = analysis._calculate(*numeric_fixture(edit))
        rows = {(r["source_run_id"], r["target_run_id"]): r for r in report["transfer_regrets"]
                if r["sample_id"] == "core_fixture" and r["mode"] == "archive" and r["scenario"] == "memory_only"}
        self.assertAlmostEqual(rows[1, 2]["regret"], .15 * math.log(4))
        self.assertAlmostEqual(rows[2, 1]["regret"], .15 * math.log(2))
        self.assertGreater(rows[1, 2]["regret"], rows[2, 1]["regret"])
        self.assertTrue(all(rows[r, r]["regret"] == 0 for r in range(1, 7)))
        self.assertEqual(report["decision"]["status"], "memory_stability_not_satisfied")
        representatives = [r for r in report["representatives"] if r["sample_id"] == "core_fixture" and r["algorithm"] == "gzip"]
        self.assertEqual([r["maximum_phases"] for r in representatives[:2]], [["compress"], ["decompress"]])
        pair = next(r for r in report["memory_algorithm_pairs"] if r["sample_id"] == "core_fixture" and r["left"] == "gzip" and r["right"] == "zstd")
        self.assertEqual(pair["signs"], [-1, 1, 1, 1, 1, 1])
        self.assertFalse(pair["sign_consistent"])

    def test_timing_influence_separated_and_memory_satisfaction_does_not_hide_joint_failure(self):
        def edit(run, sid, algorithm, v):
            factor = (1 if run == 1 else 4) if algorithm == "gzip" else (2 if run == 1 else 1) if algorithm == "zstd" else 100
            v.update(compress=factor * 1000000, decompress=factor * 1000000)
        report = analysis._calculate(*numeric_fixture(edit))
        self.assertEqual(report["decision"]["status"], "joint_stability_not_satisfied")
        self.assertIs(report["decision"]["memory_stability_satisfied"], True)
        self.assertIs(report["decision"]["joint_stability_satisfied"], False)
        self.assertTrue(all(r["regret"] == 0 for r in report["transfer_regrets"] if r["scenario"] == "memory_only"))
        self.assertTrue(any(r["regret"] > .01 for r in report["transfer_regrets"] if r["scenario"] == "timing_only"))

    def test_small_gap_label_changes_are_allowed_by_regret(self):
        def edit(run, sid, algorithm, v):
            if algorithm in ("gzip", "zstd"):
                small = (algorithm == "gzip") == (run % 2 == 1)
                v.update(mc=10000 if small else 10050, md=10000 if small else 10050)
            else:
                v.update(mc=20000, md=20000)
        report = analysis._calculate(*numeric_fixture(edit))
        self.assertEqual(report["decision"]["status"], "observed_conditions_satisfied")
        self.assertTrue(any(r["selected_algorithm"] != r["target_best_algorithm"] for r in report["transfer_regrets"]))
        self.assertTrue(all(r["regret"] <= .01 for r in report["transfer_regrets"]))

    def test_dominant_labels_do_not_exempt_memory_span_or_tiny_stratum(self):
        def edit(run, sid, algorithm, v):
            v["size"] = 1. if algorithm == "gzip" else 100.
            if sid == "tiny_fixture":
                v.update(mc=10000 * run, md=10000 * run)
        report = analysis._calculate(*numeric_fixture(edit))
        self.assertTrue(all(r["regret"] == 0 for r in report["transfer_regrets"]))
        self.assertEqual(report["decision"]["status"], "memory_stability_not_satisfied")
        self.assertEqual(report["decision"]["by_stratum"]["core"]["status"], "observed_conditions_satisfied")
        self.assertEqual(report["decision"]["by_stratum"]["tiny"]["status"], "memory_stability_not_satisfied")

    def test_policy_exact_boundaries_no_rounding_and_inconclusive_precedence(self):
        limit = audit.CRITERIA["epsilon"] / (2 * audit.CRITERIA["w_memory_max"])
        self.assertEqual(analysis.judgment(True, [limit], [.01], [.01])["status"], "observed_conditions_satisfied")
        self.assertEqual(analysis.judgment(True, [math.nextafter(limit, math.inf)], [.01], [.01])["status"], "memory_stability_not_satisfied")
        self.assertEqual(analysis.judgment(True, [limit], [math.nextafter(.01, math.inf)], [0])["status"], "memory_stability_not_satisfied")
        self.assertEqual(analysis.judgment(True, [limit], [0], [math.nextafter(.01, math.inf)])["status"], "joint_stability_not_satisfied")
        self.assertEqual(analysis.judgment(False, [], [], [])["status"], "inconclusive")
        for bad in (True, float("nan"), float("inf"), -1):
            with self.assertRaises(audit.AuditError):
                analysis.judgment(True, [bad], [0], [0])

    def test_anchor_is_median_of_run_representatives_and_combined_not_max_of_phase_anchors(self):
        def edit(run, sid, algorithm, v):
            v.update(mc=9000 if run <= 3 else 1000, md=1000 if run <= 3 else 9000,
                     compress=(run * 2 + 1) * 1000000)
        report = analysis._calculate(*numeric_fixture(edit))
        anchor = report["reference_anchors"][0]
        self.assertEqual(anchor["compress"], 8.)  # median(3,5,7,9,11,13)
        self.assertEqual(anchor["memory"], 9000)  # not max(median(Mc),median(Md)) == 5000
        across = next(r for r in report["representative_across_runs"] if r["metric"] == "memory")
        self.assertEqual(across["values"], [9000] * 6)
        self.assertTrue(all(len(r["values"]) == 5 for r in report["phase_diagnostics"]))
        self.assertTrue(all(len(r["values"]) == 6 for r in report["representative_across_runs"]))

    def test_population_CV_order_invariance_and_memory_arithmetic_check(self):
        data = numeric_fixture()
        samples, measurements, raw = data
        for run in range(1, 7):
            for row in raw[run]["memory"]:
                row["peak_process_working_set_bytes"] = str(10000 + int(row["repeat_index"]) * 10)
            for row in measurements[run]:
                row.update(compression_peak_memory_bytes="10030", decompression_peak_memory_bytes="10030", peak_memory_bytes="10030")
        result = analysis._calculate(*data)
        for run in raw:
            measurements[run].reverse()
            for kind in raw[run]:
                raw[run][kind].reverse()
        reordered = analysis._calculate(*data)
        self.assertEqual(result["candidate_labels"], reordered["candidate_labels"])
        self.assertEqual(result["transfer_regrets"], reordered["transfer_regrets"])
        phase = next(r for r in result["phase_diagnostics"] if r["kind"] == "memory")
        self.assertAlmostEqual(phase["population_std"], math.sqrt(200))
        self.assertAlmostEqual(phase["cv"], math.sqrt(200) / 10030)
        self.assertTrue(all(r["consistency_check_passed"] and r["floating_QA_tolerance"]["used_for_policy"] is False for r in result["arithmetic_checks"]))

    def test_official_v2_and_nonmemory_weights_are_distinct_and_signed_benefit_preserved(self):
        def edit(run, sid, algorithm, v):
            if algorithm == "gzip":
                v.update(size=1., mc=10000, md=10000)
            elif algorithm == "zstd":
                v.update(size=1.02, mc=1000, md=1000)
            else:
                v.update(size=2., mc=20000, md=20000)
        result = analysis._calculate(*numeric_fixture(edit))
        comparisons = result["official_and_nonmemory_comparisons"]
        self.assertTrue(all(r["official_v2"]["best_algorithm"] == r["candidate_without_memory"]["best_algorithm"] == "gzip" for r in comparisons))
        self.assertTrue(all(r["candidate_joint_algorithm"] == "zstd" and r["benefit_exceeds_delta"] for r in comparisons))
        archive = next(r for r in comparisons if r["mode"] == "archive")
        self.assertAlmostEqual(archive["official_v2"]["score_zstd"], .70 * math.log(1.02))
        self.assertAlmostEqual(archive["candidate_without_memory"]["score_zstd"], .65 * math.log(1.02))
        self.assertAlmostEqual(archive["weighted_memory_benefit"], .15 * math.log(10))
        self.assertEqual(result["observed_memory_benefit_condition_count"], 6)
        self.assertLess(analysis.log_ratio(100, 200), 0)

    def test_invalid_partial_duplicate_and_nonfinite_inputs_fail_explicitly(self):
        for mutation in (lambda d: d[0].pop(), lambda d: d[1][1].pop(),
                         lambda d: d[2][1]["memory"].append(dict(d[2][1]["memory"][0])),
                         lambda d: d[2][1]["timing"].pop(), lambda d: d[1][1][0].update(verified="False"),
                         lambda d: d[1][1][0].update(compression_ratio="NaN"),
                         lambda d: d[2][1]["memory"][0].update(peak_process_working_set_bytes="0")):
            data = numeric_fixture()
            mutation(data)
            with self.assertRaises((audit.AuditError, KeyError)):
                analysis._calculate(*data)
        for value in (True, float("nan"), 0, -1):
            with self.assertRaises(audit.AuditError):
                analysis.number(value, "fixture")

    def test_finite_extreme_metrics_do_not_overflow_intermediate_ratios(self):
        metrics = {a: dict(size=1., compress=1., decompress=1., memory=1.) for a in audit.ALGORITHMS}
        metrics["gzip"].update(size=1e-300)
        metrics["zstd"].update(size=1e300)
        selected = analysis.select(metrics, audit.WEIGHTS["archive"])
        self.assertTrue(math.isfinite(selected["score_zstd"]))
        self.assertEqual(selected["best_algorithm"], "gzip")

    def test_evidence_recheck_rejects_added_runs_and_claims(self):
        with tempfile.TemporaryDirectory(prefix="analysis_recheck_fixture_") as temporary:
            directory = Path(temporary)
            for run in range(1, 7):
                (directory / f"run_{run:02d}").mkdir()
            (directory / "fixture.csv").write_bytes(b"artificial fixture\n")
            evidence = {"fixture.csv": audit.digest((directory / "fixture.csv").read_bytes())}
            script = Path(analysis.__file__).resolve()
            sources = {str(script): audit.digest(script.read_bytes())}
            analysis._recheck(directory, evidence, sources)
            extra = directory / "run_07"
            extra.mkdir()
            with self.assertRaisesRegex(audit.AuditError, "Run inventory changed"):
                analysis._recheck(directory, evidence, sources)
            extra.rmdir()
            (directory / ".active_run.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(audit.AuditError, "Active claim appeared"):
                analysis._recheck(directory, evidence, sources)


@unittest.skipUnless(sys.platform == "win32", "Integration fixture records Windows environment")
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the producer-based full fixture without executing its test class.
        fixtures.StabilityAuditTests.setUpClass.__func__(cls)

    def setUp(self):
        self.directory = self.root / self._testMethodName
        shutil.copytree(self.original, self.directory)
        self.addCleanup(shutil.rmtree, self.directory)
        if self._testMethodName != "test_real_audit_full_matrix_binding_no_codec_and_byte_preservation":
            replacement = patch.object(audit, "generated_samples", return_value=self.canonical_samples)
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_real_audit_full_matrix_binding_no_codec_and_byte_preservation(self):
        before = {p: audit.digest(p.read_bytes()) for p in self.directory.rglob("*") if p.is_file()}
        forbidden = AssertionError("No measurement/codec execution during analysis")
        with patch.object(fixtures.runner, "run_worker", side_effect=forbidden), \
             patch.object(fixtures.runner.compressors, "compress_data", side_effect=forbidden), \
             patch.object(fixtures.runner.compressors, "decompress_data", side_effect=forbidden):
            report = analysis.analyze(self.directory)
        self.assertTrue(report["audit"]["audit_passed"])
        self.assertFalse(report["score_inclusion"])
        self.assertEqual(report["counts"], dict(samples=84, representatives=2016, phase_groups=8064,
                                             candidate_labels=4788, transfer_regrets=27216, anchor_regrets=4536, comparisons=1512))
        self.assertEqual(report["decision"]["status"], "observed_conditions_satisfied")
        self.assertEqual(before, {p: audit.digest(p.read_bytes()) for p in before})
        for name, checksum in report["audit"]["input_sha256"].items():
            self.assertEqual(audit.digest((self.directory / name).read_bytes()), checksum)

    def test_bad_audit_incomplete_evidence_rejected_before_calculation_or_output(self):
        path = self.directory / "metadata.json"
        value = fixtures.load(path)
        value["run_status"] = "interrupted"
        fixtures.save(path, value)
        with patch.object(analysis, "_calculate", side_effect=AssertionError("must not calculate")):
            with self.assertRaises(audit.AuditError):
                analysis.analyze(self.directory)

    def test_evidence_drift_after_audit_and_during_analysis(self):
        target = self.directory / "run_01/measurements.csv"
        original = target.read_bytes()
        perform_audit = audit.audit
        def changed(directory):
            result = perform_audit(directory)
            target.write_bytes(original + b"\n")
            return result
        with patch.object(audit, "audit", side_effect=changed):
            with self.assertRaisesRegex(audit.AuditError, "changed after audit"):
                analysis.analyze(self.directory)
        target.write_bytes(original)
        calculate = analysis._calculate
        def changed_during(*args):
            result = calculate(*args)
            target.write_bytes(original + b"\n")
            return result
        with patch.object(analysis, "_calculate", side_effect=changed_during):
            with self.assertRaisesRegex(audit.AuditError, "changed during analysis"):
                analysis.analyze(self.directory)

    def test_analysis_source_drift_and_active_claim_rejected(self):
        original_read = Path.read_bytes
        target = Path(analysis.__file__).resolve()
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
            with self.assertRaisesRegex(audit.AuditError, "Source changed"):
                analysis.analyze(self.directory)
        claim = self.directory / ".active_run.json"
        claim.write_text("{}", encoding="utf-8")
        with self.assertRaises(audit.AuditError):
            analysis.analyze(self.directory)

    def test_export_tables_hashes_exclusive_directory_and_original_preservation(self):
        report = analysis.analyze(self.directory)
        before = {p: audit.digest(p.read_bytes()) for p in self.directory.rglob("*") if p.is_file()}
        destination = self.root / "publication_fixture"
        analysis.publish(report, self.directory, destination)
        self.assertEqual({p.name for p in destination.iterdir()}, {"audit.json", "candidate_labels.csv", "transfer_regrets.csv", "stability_summary.json"})
        summary = fixtures.load(destination / "stability_summary.json")
        self.assertEqual(summary["decision"], report["decision"])
        for name, checksum in summary["output_artifact_sha256"].items():
            self.assertEqual(audit.digest((destination / name).read_bytes()), checksum)
        labels = fixtures.rows(destination / "candidate_labels.csv")
        regrets = fixtures.rows(destination / "transfer_regrets.csv")
        self.assertEqual(len(labels), 4788)
        self.assertEqual(len(regrets), 27216)
        self.assertEqual(json.loads(labels[0]["tied_algorithms"]), report["candidate_labels"][0]["tied_algorithms"])
        self.assertEqual([float(r["regret"]) for r in regrets], [r["regret"] for r in report["transfer_regrets"]])
        output_before = {p: p.read_bytes() for p in destination.iterdir()}
        with self.assertRaises(FileExistsError):
            analysis.publish(report, self.directory, destination)
        self.assertEqual(output_before, {p: p.read_bytes() for p in destination.iterdir()})
        self.assertEqual(before, {p: audit.digest(p.read_bytes()) for p in before})

    def test_publication_disk_failure_preserves_partial_evidence_and_original_exception(self):
        report = analysis.analyze(self.directory)
        destination = self.root / "failed_publication_fixture"
        with patch.object(analysis.os, "fsync", side_effect=OSError("fixture disk error")):
            with self.assertRaisesRegex(OSError, "fixture disk error"):
                analysis.publish(report, self.directory, destination)
        self.assertTrue((destination / "audit.json").exists())
        self.assertFalse((destination / "stability_summary.json").exists())
        self.assertEqual(fixtures.load(destination / "publication_failed.json")["validity_status"], "inconclusive")

    def test_postpublication_drift_marks_export_failed_and_preserves_files(self):
        report = analysis.analyze(self.directory)
        destination = self.root / "drift_publication_fixture"
        original = analysis._recheck
        calls = 0
        def fail_last(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise audit.AuditError("fixture postpublication drift")
            return original(*args)
        with patch.object(analysis, "_recheck", side_effect=fail_last):
            with self.assertRaisesRegex(audit.AuditError, "postpublication drift"):
                analysis.publish(report, self.directory, destination)
        self.assertTrue((destination / "stability_summary.json").exists())
        self.assertEqual(fixtures.load(destination / "publication_failed.json")["publication_status"], "failed")

    def test_cli_guard_optimized_failure_and_bytecode_requirement(self):
        guard = """import importlib.abc, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'src.memory_stability_validation','src.memory_stability_timing_worker','src.memory_validation','src.memory_benchmark','src.compressors','src.scoring'}:
            raise RuntimeError('Prohibited import: ' + fullname)
sys.meta_path.insert(0, Guard())
from research_log.analyze_memory_stability_validation import main
raise SystemExit(main(sys.argv[1:]))
"""
        destination = self.root / "cli_publication_fixture"
        command = [sys.executable, "-B", "-c", guard, "--experiment-dir", str(self.directory), "--output-dir", str(destination)]
        result = subprocess.run(command, cwd=audit.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["transfer_regrets"], 27216)
        (self.directory / "run_01/measurements.csv").write_text("invalid", encoding="utf-8")
        for flag in (None, "-O", "-OO"):
            output = self.root / f"invalid_analysis_{flag}"
            result = subprocess.run([sys.executable, "-B", *([flag] if flag else []), "-m", "research_log.analyze_memory_stability_validation",
                                     "--experiment-dir", str(self.directory), "--output-dir", str(output)],
                                    cwd=audit.ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("inconclusive", result.stderr)
            self.assertFalse(output.exists())
        with patch.object(sys, "dont_write_bytecode", False):
            with self.assertRaisesRegex(audit.AuditError, "python -B"):
                analysis.analyze(self.directory)


if __name__ == "__main__":
    unittest.main()
