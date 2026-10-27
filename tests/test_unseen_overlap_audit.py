"""Artificial fixtures only; verify audit rejection and exact-match behavior."""
import copy
import hashlib
import json
from pathlib import Path
import platform
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from research_log import audit_unseen_overlap_20261027 as audit


class OverlapAuditTests(unittest.TestCase):
    def setUp(self):
        self.generator = SimpleNamespace(GENERATOR_NAMES=("fixture",), SAMPLE_SIZES=(3,),
            generate_sample=lambda name, size, seed: SimpleNamespace(
                generator=name, size=size, seed=seed, data=b"abc", parameters={"fixture": True}))
        self.config = {"sample_sizes": [3], "compression": {}, "timing": {}, "features": {}}
        self.meta = dict(git=dict(commit_hash="trusted_fixture", worktree_dirty=False),
            python_version=platform.python_version(), python_implementation=platform.python_implementation(),
            schema_version=1, sample_count=1, seed_strategy="base_seed + zero_based_sample_index",
            sample_id_strategy="sample_{zero_based_sample_index:06d}", generators=["fixture"], sample_sizes=[3],
            compression_settings={}, timing={}, feature_settings={}, base_seed=41,
            generator_counts={"fixture": 1}, size_counts={"3": 1})
        self.rows = [dict(sample_id="sample_000000", generator="fixture", seed="41", size="3", file_size="3",
                          generation_parameters=json.dumps({"fixture": True}))]

    def reconstruct(self):
        return list(audit.reconstruct(self.meta, self.rows, self.generator, self.config, 1, "trusted_fixture"))

    def test_fixture_digest_and_exact_overlap(self):
        synthetic = self.reconstruct()
        self.assertEqual(synthetic[0]["input_sha256"], hashlib.sha256(b"abc").hexdigest())
        synthetic[0]["dataset"] = "artificial_fixture"
        candidates = [dict(candidate_id="match", input_sha256=synthetic[0]["input_sha256"]),
                      dict(candidate_id="different", input_sha256=hashlib.sha256(b"abd").hexdigest())]
        result = audit.compare(candidates, synthetic)
        self.assertEqual(len(result[0]["reconstructed_matches"]), 1)
        self.assertIsNotNone(result[0]["exclusion_reason"])
        self.assertEqual(result[1]["reconstructed_matches"], [])
        self.assertIsNone(result[1]["exclusion_reason"])

    def test_multiple_synthetic_matches_are_all_preserved(self):
        first = dict(self.reconstruct()[0], dataset="fixture1")
        second = dict(first, dataset="fixture2")
        result = audit.compare([dict(candidate_id="c", input_sha256=first["input_sha256"])], [first, second])
        self.assertEqual([r["dataset"] for r in result[0]["reconstructed_matches"]], ["fixture1", "fixture2"])

    def test_dirty_execution_and_wrong_commit_rejected(self):
        for git in (dict(commit_hash="trusted_fixture", worktree_dirty=True),
                    dict(commit_hash="different", worktree_dirty=False)):
            with self.subTest(git=git):
                self.meta["git"] = git
                with self.assertRaisesRegex(ValueError, "execution commit"):
                    self.reconstruct()

    def test_python_version_mismatch_rejected(self):
        self.meta["python_version"] = "0.0.0"
        with self.assertRaisesRegex(ValueError, "runtime mismatch"):
            self.reconstruct()

    def test_missing_sample_and_changed_seed_rejected(self):
        original = copy.deepcopy(self.rows)
        for rows in ([], [dict(original[0], seed="42")], original * 2):
            with self.subTest(rows=rows):
                self.rows = rows
                with self.assertRaises(ValueError):
                    self.reconstruct()

    def test_changed_parameters_rejected(self):
        self.rows[0]["generation_parameters"] = '{"fixture": false}'
        with self.assertRaisesRegex(ValueError, "parameters mismatch"):
            self.reconstruct()

    def test_changed_generated_size_rejected(self):
        self.generator.generate_sample = lambda *args: SimpleNamespace(
            generator="fixture", size=3, seed=41, data=b"ab", parameters={"fixture": True})
        with self.assertRaisesRegex(ValueError, "size/identity mismatch"):
            self.reconstruct()

    def test_historical_config_mismatch_rejected(self):
        self.config["features"] = {"changed": True}
        with self.assertRaisesRegex(ValueError, "Historical config mismatch"):
            self.reconstruct()

    def test_historical_plan_function_is_used(self):
        source = '''def build_experiment_plan(sample_count: int, base_seed: int) -> list[SampleSpec]:
    return [SampleSpec(sample_id="original", generator=GENERATOR_NAMES[0], size=SAMPLE_SIZES[0], seed=base_seed)]
'''
        plan = audit.historical_plan(source, self.generator, 1, 41)
        self.assertEqual((plan[0].sample_id, plan[0].size, plan[0].seed), ("original", 3, 41))

    def test_partial_failure_is_preserved_and_output_reuse_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parent = root / "data/results/real_unseen"
            parent.mkdir(parents=True)
            output = parent / "artificial_fixture"
            with patch.object(audit, "ROOT", root), patch.object(audit, "read", side_effect=ValueError("fixture failure")):
                with self.assertRaisesRegex(ValueError, "fixture failure"):
                    audit.run(output)
                failure = json.loads((output / "failure.json").read_bytes())
                self.assertEqual(failure["status"], "failed_incomplete")
                self.assertFalse(failure["evaluation_ready"])
                before = (output / "failure.json").read_bytes()
                with self.assertRaises(FileExistsError):
                    audit.run(output)
                self.assertEqual((output / "failure.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
