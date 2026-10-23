"""Compare Mode operation tests; controlled timings are not research data."""
import contextlib
import csv
import io
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import compare_compress as compare
from src import compressors, scoring


def load(path):
    return json.loads(path.read_bytes())


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def clock_values():
    values = []
    for i, duration in enumerate([9, 1, 7, 3, 5, 8, 2, 6, 4, 10]):
        start = 1000 + i * 100
        values.extend([start, start + duration])
    return values


class CompareTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="compare_fixture_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "한글 입력 🧪.bin"
        self.original = b"ABC\x00" * 1024 + bytes(range(256))
        self.source.write_bytes(self.original)
        self.output = self.root / "new_comparison"

    def run_compare(self):
        return compare.compare_file(self.source, self.output)

    def test_complete_actual_comparison_raw_medians_hashes_and_manual_scores(self):
        with patch.object(compressors, "compress_data", wraps=compressors.compress_data) as encode, \
             patch.object(compressors, "decompress_data", wraps=compressors.decompress_data) as decode:
            report = self.run_compare()
        self.assertEqual(encode.call_count, 20)
        self.assertEqual(decode.call_count, 20)
        self.assertEqual([c.args[1] for c in encode.call_args_list], [a for a in scoring.ALGORITHMS for _ in range(5)])
        self.assertEqual(report["status"], "completed")
        self.assertFalse(report["memory_measured"])
        raw = rows(self.output / "timing_repeats.csv")
        measured = rows(self.output / "compression_results.csv")
        labels = rows(self.output / "selection_labels.csv")
        self.assertEqual(len(raw), 40)
        self.assertEqual(len(measured), 4)
        self.assertEqual(len(labels), 3)
        self.assertEqual(len({(r["algorithm"],r["phase"],r["repeat_index"]) for r in raw}), 40)
        self.assertTrue(all(r["status"] == "ok" and int(r["elapsed_ns"]) > 0 for r in raw))
        for row in measured:
            self.assertEqual(row["verified"], "True")
            for phase, field in (("compress","compression_time_ms"),("decompress","decompression_time_ms")):
                values = [int(r["elapsed_ns"]) for r in raw if r["algorithm"] == row["algorithm"] and r["phase"] == phase]
                self.assertEqual(float(row[field]), statistics.median(values) / 1_000_000)
        for label in labels:
            weights = report["selection_modes"][label["mode"]]
            for row in measured:
                expected = sum(weights[w] * math.log(float(row[f]) / min(float(r[f]) for r in measured))
                    for w, f in (("compression_ratio","compression_ratio"),("compression_time","compression_time_ms"),
                                 ("decompression_time","decompression_time_ms")))
                # Independent summation can differ by one floating-point bit.
                # This tolerance is only numeric QA, never selection/tie policy.
                self.assertTrue(math.isclose(float(label["score_" + row["algorithm"]]), expected,
                                             rel_tol=1e-12, abs_tol=1e-15))
        for name, checksum in report["artifact_sha256"].items():
            self.assertEqual(compare._digest((self.output / name).read_bytes()), checksum)
        self.assertEqual(load(self.output / "comparison.json"), report)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_measurement_matches_existing_benchmark_with_controlled_raw_ns(self):
        def controls():
            return (patch.object(compare.time, "perf_counter_ns", side_effect=clock_values()),
                    patch.object(compressors, "compress_data", return_value=b"encoded"),
                    patch.object(compressors, "decompress_data", return_value=b"original"))
        timer, encode, decode = controls()
        with timer, encode, decode:
            actual, raw = compare._measure(b"original", "artificial", "gzip")
        timer, encode, decode = controls()
        with timer, encode, decode:
            existing = compressors.benchmark_compressor(b"original", "gzip")
        self.assertEqual({k:actual[k] for k in existing}, existing)
        self.assertEqual([r["elapsed_ns"] for r in raw], [9,1,7,3,5,8,2,6,4,10])

    def test_exact_tie_uses_existing_algorithm_order_for_all_modes(self):
        with patch.object(compare.time, "perf_counter_ns", side_effect=[x for i in range(40) for x in (i*100, i*100+5)]), \
             patch.object(compressors, "compress_data", return_value=b"encoded"), \
             patch.object(compressors, "decompress_data", return_value=self.original):
            report = self.run_compare()
        self.assertEqual([s["best_algorithm"] for s in report["selections"]], ["gzip"] * 3)
        self.assertTrue(all(s["score_" + a] == 0 for s in report["selections"] for a in scoring.ALGORITHMS))

    def test_compression_failure_kept_with_unexecuted_slots_and_no_partial_scoring(self):
        encode = compressors.compress_data
        def fail(data, algorithm):
            if algorithm == "gzip":
                raise OSError("Artificial codec failure")
            return encode(data, algorithm)
        with patch.object(compressors, "compress_data", side_effect=fail), \
             patch.object(scoring, "score_sample", side_effect=AssertionError("No partial-set score")) as score:
            report = self.run_compare()
        score.assert_not_called()
        self.assertEqual(report["status"], "completed_with_failures")
        self.assertEqual(report["row_counts"]["attempted_repeats"], 31)
        self.assertEqual(report["selections"], [])
        self.assertEqual(rows(self.output / "selection_labels.csv"), [])
        raw = rows(self.output / "timing_repeats.csv")
        self.assertEqual(sum(r["status"] == "error" for r in raw), 1)
        self.assertEqual(sum(r["status"] == "not_run" for r in raw), 9)
        self.assertEqual(sum(r["verified"] for r in report["measurements"]), 3)
        self.assertIsNone(report["measurements"][0]["compression_time_ms"])
        self.assertIn("Artificial codec failure", report["errors"][0])

    def test_inconsistent_compressed_bytes_and_bad_restoration_remain_failures(self):
        encode, decode = compressors.compress_data, compressors.decompress_data
        calls = 0
        def inconsistent(data, algorithm):
            nonlocal calls
            value = encode(data, algorithm)
            if algorithm == "gzip":
                calls += 1
                if calls == 2:
                    return value + b"different"
            return value
        for problem in ("inconsistent", "restoration"):
            output = self.root / problem
            target = (patch.object(compressors, "compress_data", side_effect=inconsistent) if problem == "inconsistent" else
                      patch.object(compressors, "decompress_data", side_effect=lambda b,a: b"wrong" if a == "gzip" else decode(b,a)))
            with target:
                report = compare.compare_file(self.source, output)
            self.assertEqual(report["status"], "completed_with_failures")
            self.assertFalse(report["measurements"][0]["verified"])
            self.assertEqual(report["selections"], [])
            bad = [r for r in rows(output / "timing_repeats.csv") if r["status"] == "error"]
            self.assertEqual(len(bad), 1)
            self.assertEqual(bad[0]["consistent_with_reference"] if problem == "inconsistent" else bad[0]["verified"], "False")

    def test_nonpositive_times_preserved_without_epsilon_or_scoring(self):
        with patch.object(compare.time, "perf_counter_ns", return_value=100), \
             patch.object(scoring, "score_sample", side_effect=AssertionError("No score")) as score:
            report = self.run_compare()
        score.assert_not_called()
        self.assertEqual(report["status"], "completed_with_failures")
        self.assertEqual(report["row_counts"]["attempted_repeats"], 4)
        self.assertTrue(all(r["elapsed_ns"] == "0" for r in rows(self.output / "timing_repeats.csv") if r["status"] == "error"))

    def test_preflight_rejects_existing_output_empty_missing_and_directory_inputs(self):
        existing = self.root / "existing"
        existing.mkdir()
        (existing / "keep").write_bytes(b"keep")
        empty = self.root / "empty"
        empty.write_bytes(b"")
        with patch.object(compare, "_measure", side_effect=AssertionError("Must reject first")) as measure:
            for source, output, error in ((self.source, existing, FileExistsError), (self.source, self.source, FileExistsError),
                    (empty,self.output,ValueError), (self.root / "missing",self.output,ValueError), (self.root,self.output,ValueError)):
                with self.assertRaises(error):
                    compare.compare_file(source, output)
            measure.assert_not_called()
        self.assertEqual((existing / "keep").read_bytes(), b"keep")
        self.assertFalse(self.output.exists())

    def test_changed_runtime_config_rejected_before_measurement(self):
        with patch.object(compressors, "_TIMING_REPEATS", 3), \
             patch.object(compare, "_measure", side_effect=AssertionError("Must reject first")) as measure:
            with self.assertRaisesRegex(ValueError, "restart Compare Mode"):
                self.run_compare()
            measure.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_input_change_saves_invalidated_evidence_without_labels(self):
        measure = compare._measure
        def change(*args):
            result = measure(*args)
            if args[-1] == "zstd":
                self.source.write_bytes(b"changed input")
            return result
        with patch.object(compare, "_measure", side_effect=change), \
             patch.object(scoring, "score_sample", side_effect=AssertionError("Invalidated input")) as score:
            report = self.run_compare()
        score.assert_not_called()
        self.assertEqual(report["status"], "invalidated")
        self.assertEqual(report["selections"], [])
        self.assertEqual(len(rows(self.output / "timing_repeats.csv")), 40)
        self.assertEqual(report["input_sha256"], compare._digest(self.original))
        self.assertIn("Input changed", report["errors"][0])

    def test_source_drift_saved_as_invalidated_not_normal_results(self):
        read = Path.read_bytes
        target = compare.ROOT / "src/scoring.py"
        calls = 0
        def drift(path):
            nonlocal calls
            data = read(path)
            if path == target:
                calls += 1
                if calls > 1:
                    return data + b"\n"
            return data
        with patch.object(Path, "read_bytes", drift):
            report = self.run_compare()
        self.assertEqual(report["status"], "invalidated")
        self.assertEqual(rows(self.output / "selection_labels.csv"), [])
        self.assertIn("Source/config changed", report["errors"][0])

    def test_scoring_error_keeps_measured_results_without_labels(self):
        with patch.object(scoring, "score_sample", side_effect=ValueError("Artificial score failure")):
            report = self.run_compare()
        self.assertEqual(report["status"], "completed_with_failures")
        self.assertTrue(all(r["verified"] for r in report["measurements"]))
        self.assertEqual(report["selections"], [])
        self.assertIn("Scoring failed", report["errors"][0])

    def test_disk_failure_keeps_partial_raw_evidence_and_failure_marker(self):
        with patch.object(compare.os, "fsync", side_effect=OSError("Artificial disk failure")):
            with self.assertRaisesRegex(OSError, "Artificial disk failure"):
                self.run_compare()
        self.assertTrue((self.output / "timing_repeats.csv").exists())
        self.assertFalse((self.output / "comparison.json").exists())
        self.assertEqual(load(self.output / "publication_failed.json")["analysis_status"], "inconclusive")
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_postpublication_drift_marks_saved_outputs_invalid(self):
        check = compare._recheck
        calls = 0
        def drift(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise ValueError("Artificial postpublication drift")
            return check(*args)
        with patch.object(compare, "_recheck", side_effect=drift):
            with self.assertRaisesRegex(ValueError, "postpublication drift"):
                self.run_compare()
        self.assertTrue((self.output / "comparison.json").exists())
        self.assertEqual(load(self.output / "publication_failed.json")["publication_status"], "failed")

    def test_output_claim_race_never_writes_into_existing_directory(self):
        measure = compare._measure
        def claim(*args):
            result = measure(*args)
            if args[-1] == "zstd":
                self.output.mkdir()
                (self.output / "keep").write_bytes(b"keep")
            return result
        with patch.object(compare, "_measure", side_effect=claim):
            with self.assertRaises(FileExistsError):
                self.run_compare()
        self.assertEqual({p.name:p.read_bytes() for p in self.output.iterdir()}, {"keep":b"keep"})

    def test_failed_measurements_cli_return_one_and_preserve_diagnostics(self):
        with patch.object(compressors, "compress_data", side_effect=OSError("Artificial failure")), \
             contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = compare.main([str(self.source), "--output-dir", str(self.output)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "completed_with_failures")
        self.assertIn("incomplete", stderr.getvalue())
        self.assertEqual(rows(self.output / "selection_labels.csv"), [])

    def test_fresh_cli_has_no_models_features_or_memory_dependencies(self):
        guard = """import importlib.abc,sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'numpy','pandas','sklearn'} or fullname in {
            'smart_compress','smart_decompress','src.feature_extractor','src.train_model',
            'src.memory_benchmark','src.memory_validation','src.memory_repeatability_validation'}:
            raise RuntimeError('Prohibited import: '+fullname)
sys.meta_path.insert(0,Guard())
from compare_compress import main
raise SystemExit(main(sys.argv[1:]))
"""
        result = subprocess.run([sys.executable,"-B","-c",guard,str(self.source),"--output-dir",str(self.output)],
                                cwd=compare.ROOT,capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(json.loads(result.stdout)["status"], "completed")
        result = subprocess.run([sys.executable,"-B","compare_compress.py",str(self.source),"--output-dir",str(self.output)],
                                cwd=compare.ROOT,capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"already exists", result.stderr)


if __name__ == "__main__":
    unittest.main()
