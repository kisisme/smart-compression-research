"""Artificial saved-evidence fixtures; peaks below are NOT research measurements.

No memory workers, compressor calls, or existing result writes are performed.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_log import verify_memory_validation as verifier
from src.data_generator import GENERATOR_NAMES, SAMPLE_SIZES, generate_sample


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SavedMemoryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = []
        cls.samples = []
        cls.repeats = []
        cls.summaries = []
        cls.generated = {}
        for size in SAMPLE_SIZES:
            for generator in GENERATOR_NAMES:
                index = len(cls.plan)
                spec = dict(sample_id=f"memory_{index:06d}", generator=generator, size=size, seed=100 + index)
                cls.plan.append(spec)
                sample = generate_sample(generator, size, spec["seed"])
                cls.generated[generator, size, spec["seed"]] = sample
                input_hash = digest(sample.data)
                cls.samples.append({**spec, "generation_parameters": json.dumps(sample.parameters),
                                    "input_sha256": input_hash, "status": "ok", "error": ""})
                for algorithm in ("gzip", "bz2", "lzma", "zstd"):
                    summary = {**spec, "algorithm": algorithm, "verified": True, "failed_repeat_count": 0,
                               "compression_peak_memory_bytes": 120, "decompression_peak_memory_bytes": 220,
                               "peak_memory_bytes": 220}
                    for phase, base in (("compress", 100), ("decompress", 200)):
                        summary.update({f"{phase}_min_bytes": base, f"{phase}_max_bytes": base + 40,
                                        f"{phase}_population_std_bytes": math.sqrt(200),
                                        f"{phase}_cv": math.sqrt(200) / (base + 20)})
                        for repeat_index in range(1, 6):
                            peak = base + (repeat_index - 1) * 10
                            payload = dict(operation=phase, algorithm=algorithm,
                                           peak_process_working_set_bytes=peak, verified=True)
                            cls.repeats.append({**spec, "algorithm": algorithm, "phase": phase,
                                                "repeat_index": repeat_index,
                                                "measurement_method": "windows_get_process_memory_info_peak_working_set",
                                                "expected_sha256": input_hash if phase == "decompress" else "a" * 64,
                                                "reference_roundtrip_verified": True,
                                                "peak_process_working_set_bytes": peak,
                                                "verified": True, "status": "ok", "error": "",
                                                "return_code": 0, "stdout": json.dumps(payload), "stderr": ""})
                    cls.summaries.append(summary)

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="audit_artificial_fixture_")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.tables = {"samples.csv": copy.deepcopy(self.samples),
                       "memory_repeats.csv": copy.deepcopy(self.repeats),
                       "memory_summary.csv": copy.deepcopy(self.summaries)}
        sources = {name: digest((verifier.ROOT / name).read_bytes()) for name in verifier.SOURCE_NAMES}
        self.meta = dict(
            schema_version=1, run_status="completed", measurement_status="validation_only", score_inclusion=False,
            finished_at_utc="2026-01-01T00:00:00+00:00", provenance_unchanged=True,
            source_sha256=sources, source_sha256_at_end=dict(sources),
            config=json.loads((verifier.ROOT / "config/experiment_config.json").read_text(encoding="utf-8")),
            base_seed=100, sample_plan=copy.deepcopy(self.plan),
            algorithm_order=["gzip", "bz2", "lzma", "zstd"], phase_order=["compress", "decompress"],
            repeats_per_phase=5, measurement_method="windows_get_process_memory_info_peak_working_set",
            sample_count=len(self.samples), planned_sample_count=len(self.samples),
            pair_count=len(self.summaries), planned_pair_count=len(self.summaries),
            repeat_count=len(self.repeats), planned_repeat_count=len(self.repeats),
            failed_sample_count=0, failed_pair_count=0, failed_repeat_count=0,
            repeat_status_counts={"ok": len(self.repeats)}, git={"commit_hash": "artificial-fixture-not-a-run"},
        )
        self.save_tables()
        cache = patch.object(verifier, "generate_sample", side_effect=lambda *args: self.generated[args])
        cache.start()
        self.addCleanup(cache.stop)

    def save_metadata(self) -> None:
        (self.directory / "memory_validation_metadata.json").write_text(json.dumps(self.meta), encoding="utf-8")

    def save_tables(self) -> None:
        for name, rows in self.tables.items():
            with (self.directory / name).open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        self.meta["artifact_sha256"] = {name: digest((self.directory / name).read_bytes()) for name in self.tables}
        self.save_metadata()

    def snapshot(self) -> dict:
        return {p.name: p.read_bytes() for p in self.directory.iterdir()}

    def cli(self, *arguments: str, optimization: str | None = None) -> subprocess.CompletedProcess:
        options = [optimization] if optimization else []
        return subprocess.run([sys.executable, "-B", *options, "-m", "research_log.verify_memory_validation",
                               "--experiment-dir", str(self.directory), *arguments],
                              cwd=verifier.ROOT, capture_output=True, text=True, timeout=60)

    def test_success_recalculates_statistics_and_preserves_inputs(self) -> None:
        before = self.snapshot()
        result = verifier.audit(self.directory)
        self.assertTrue(result["audit_passed"])
        self.assertEqual(result["sample_count"], len(self.samples))
        self.assertEqual(result["repeat_count"], len(self.repeats))
        self.assertEqual(result["largest_phase_cv"]["median_bytes"], 120)
        self.assertAlmostEqual(result["largest_phase_cv"]["cv"], math.sqrt(200) / 120)
        self.assertFalse(result["score_inclusion"])
        self.assertIn("not independently repeated", result["limitations"][1])
        self.assertEqual(self.snapshot(), before)

    def test_incomplete_and_failed_statuses_are_rejected_without_reading_artifacts(self) -> None:
        for status in ("running", "interrupted", "aborted", "completed_with_failures", "invalid_provenance_changed",
                       "finalizing", "finalization_failed"):
            with self.subTest(status=status):
                self.meta = {"run_status": status}
                self.save_metadata()
                before = self.snapshot()
                with self.assertRaisesRegex(verifier.AuditError, "Requires a successful completed run"):
                    verifier.audit(self.directory)
                self.assertEqual(self.snapshot(), before)
        verifier.generate_sample.assert_not_called()

    def test_missing_manifests_or_changed_source_are_rejected(self) -> None:
        original = copy.deepcopy(self.meta)
        for field in ("artifact_sha256", "source_sha256"):
            with self.subTest(field=field):
                self.meta = copy.deepcopy(original)
                self.meta[field] = {}
                if field == "source_sha256":
                    self.meta["source_sha256_at_end"] = {}
                self.save_metadata()
                with self.assertRaisesRegex(verifier.AuditError, "hash manifest"):
                    verifier.audit(self.directory)
        self.meta = copy.deepcopy(original)
        self.meta["source_sha256"]["requirements.txt"] = "0" * 64
        self.meta["source_sha256_at_end"] = dict(self.meta["source_sha256"])
        self.save_metadata()
        with self.assertRaisesRegex(verifier.AuditError, "Source SHA-256 mismatch"):
            verifier.audit(self.directory)

    def test_artifact_hash_mismatch_is_rejected(self) -> None:
        path = self.directory / "samples.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(verifier.AuditError, "Artifact SHA-256 mismatch"):
            verifier.audit(self.directory)

    def test_reduced_matrix_and_missing_finalization_are_rejected(self) -> None:
        original = copy.deepcopy(self.meta)
        for key, value in (("algorithm_order", ["gzip"]), ("phase_order", ["compress"]),
                           ("repeats_per_phase", 1), ("sample_plan", self.plan[:-1]),
                           ("finished_at_utc", ""), ("score_inclusion", True)):
            with self.subTest(key=key):
                self.meta = copy.deepcopy(original)
                self.meta[key] = value
                self.save_metadata()
                with self.assertRaises(verifier.AuditError):
                    verifier.audit(self.directory)

    def test_duplicate_or_missing_repeat_is_rejected_even_with_updated_hash(self) -> None:
        self.tables["memory_repeats.csv"][-1] = dict(self.tables["memory_repeats.csv"][0])
        self.save_tables()
        with self.assertRaisesRegex(verifier.AuditError, "Duplicate/missing repeats"):
            verifier.audit(self.directory)

    def test_failed_worker_or_numeric_verified_payload_is_rejected(self) -> None:
        row = self.tables["memory_repeats.csv"][0]
        row["status"] = "worker_failed"
        self.save_tables()
        with self.assertRaisesRegex(verifier.AuditError, "Failed or unverified repeat"):
            verifier.audit(self.directory)
        row["status"] = "ok"
        payload = json.loads(row["stdout"])
        payload["verified"] = 1
        row["stdout"] = json.dumps(payload)
        self.save_tables()
        with self.assertRaisesRegex(verifier.AuditError, "Worker JSON mismatch"):
            verifier.audit(self.directory)

    def test_incorrect_or_nonfinite_summary_is_rejected(self) -> None:
        for value in (121, "nan", "inf"):
            with self.subTest(value=value):
                self.tables["memory_summary.csv"][0]["compression_peak_memory_bytes"] = value
                self.save_tables()
                with self.assertRaisesRegex(verifier.AuditError, "Summary statistic mismatch"):
                    verifier.audit(self.directory)

    def test_cli_optional_output_never_overwrites_existing_file(self) -> None:
        before = self.snapshot()
        output = self.directory / "audit.json"
        result = self.cli("--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["audit_passed"])
        self.assertEqual(json.loads(result.stdout), json.loads(output.read_text(encoding="utf-8")))
        after = self.snapshot()
        self.assertEqual({name: after[name] for name in before}, before)
        result = self.cli("--output", str(output))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.snapshot(), after)

    def test_cli_optimization_still_rejects_failed_repeat_and_creates_no_report(self) -> None:
        self.tables["memory_repeats.csv"][0]["verified"] = False
        self.save_tables()
        before = self.snapshot()
        for option in (None, "-O", "-OO"):
            with self.subTest(optimization=option):
                result = self.cli("--output", str(self.directory / "audit.json"), optimization=option)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Failed or unverified repeat", result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(self.snapshot(), before)

    def test_cli_incomplete_and_malformed_input_have_no_success_output(self) -> None:
        for payload, message in (({"run_status": "running"}, "Requires a successful completed run"),
                                 ({"run_status": "completed"}, "schema_version"),
                                 ([], "Metadata must be a JSON object")):
            with self.subTest(payload=payload):
                self.meta = payload
                self.save_metadata()
                before = self.snapshot()
                result = self.cli("--output", str(self.directory / "audit.json"), optimization="-O")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
