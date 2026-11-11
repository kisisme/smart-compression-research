"""Synthetic fixtures only; no real corpus read, stored model load or research run."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r
from research_log import verify_feature_profile_run_20261111 as audit
from research_log import run_feature_profile_20261111 as runner

PLAN = json.loads((r.FREEZE / 'plan.json').read_bytes())
CONTRACT = PLAN['feature_contract']
TARGETS = PLAN['timing']['instrumented_targets']
FIXTURE_EVIDENCE = []


class StepClock:
    def __init__(self): self.value = 0
    def __call__(self):
        self.value += 10
        return self.value


def fixture_setup(mode):
    reference = r.load_reference()
    data = b'AB'*2050+b'Z'
    features = reference.extract_features(data)
    expected = {'fixture': r.canonical_features(features, CONTRACT)}
    slots = [dict(mode=mode, round_index=str(i), is_warmup=str(i == 0), order_in_round='1', sample_id='fixture') for i in range(6)]
    inventory = {'fixture': dict(input_sha256=r.digest(data), original_size=len(data))}
    return reference, data, expected, slots, inventory


def fixture_worker(out, mode):
    reference, data, expected, slots, _ = fixture_setup(mode)
    r.run_mode(mode, slots, {'fixture': data}, expected, reference, r.load_frame_factory(CONTRACT['names_in_order']),
               Path(out), CONTRACT, TARGETS, data_kind='test_fixture')


class FakeModel:
    def __init__(self, classes=('gzip', 'zstd'), probabilities=(.25, .75), chosen='zstd'):
        import numpy as np
        self.classes_ = np.array(classes)
        self.probabilities, self.chosen, self.calls = probabilities, chosen, []
    def predict(self, frame):
        self.calls.append('predict')
        return [self.chosen]
    def predict_proba(self, frame):
        self.calls.append('predict_proba')
        return [self.probabilities]


class FeatureProfileTests(unittest.TestCase):
    def temp(self):
        parent = ROOT / 'data/temp'
        parent.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(prefix='feature_profile_fixture_', dir=parent)
        self.assertTrue(Path(directory.name).resolve().is_relative_to(parent.resolve()))
        return directory

    def test_all_131_planned_valid_fixtures_preserve_exact_values_frame_and_tree(self):
        reference, instrumented = r.load_reference(), r.load_reference()
        frame = r.load_frame_factory(CONTRACT['names_in_order'])
        seen = set()
        with r.CallProfiler(instrumented, TARGETS, StepClock()) as profiler:
            for name, data in r.fixture_inputs(PLAN):
                with self.subTest(fixture=name):
                    self.assertNotIn(name, seen)
                    seen.add(name)
                    expected = r.canonical_features(reference.extract_features(data), CONTRACT)
                    profiler.reset()
                    value = instrumented.extract_features(data)
                    self.assertEqual(r.assert_features(value, expected, CONTRACT), expected)
                    r.frame_values(frame(value), value, CONTRACT)
                    events = profiler.events
                    trial = dict(start_ns=min(e['start_ns'] for e in events)-1, end_ns=max(e['end_ns'] for e in events)+1)
                    audit.call_tree(events, trial, len(data), CONTRACT, TARGETS)
                    FIXTURE_EVIDENCE.append(dict(kind='valid_test_fixture', fixture=name, input_sha256=r.digest(data),
                                                 original_size=len(data), canonical_features=expected, verified=True))
        self.assertEqual(len(seen), 131)

    def test_all_five_invalid_fixtures_preserve_exception_type_and_message(self):
        for name, data in [('empty bytes', b''), ('bytearray', bytearray(b'a')), ('memoryview', memoryview(b'a')), ('str', 'a'), ('None', None)]:
            reference, instrumented = r.load_reference(), r.load_reference()
            try:
                reference.extract_features(data)
                self.fail('Reference unexpectedly accepted invalid input')
            except (ValueError, TypeError) as exc:
                expected_type, expected_message = type(exc), str(exc)
            originals = {k: getattr(instrumented, k) for k in TARGETS}
            with r.CallProfiler(instrumented, TARGETS, StepClock()) as profiler:
                with self.assertRaises(expected_type) as raised:
                    instrumented.extract_features(data)
                self.assertEqual(str(raised.exception), expected_message)
                self.assertTrue(any(e['status'] == 'error' for e in profiler.events))
            self.assertTrue(all(getattr(instrumented, k) is v for k, v in originals.items()))
            FIXTURE_EVIDENCE.append(dict(kind='invalid_test_fixture', fixture=name, exception_type=expected_type.__name__,
                                         exception_message=expected_message, verified=True))

    def test_signed_zero_float_step_types_order_and_nonfinite_are_rejected(self):
        features = r.load_reference().extract_features(b'A'*17)
        expected = r.canonical_features(features, CONTRACT)
        altered = dict(features, entropy=0.0)
        self.assertNotEqual(features['entropy'].hex(), altered['entropy'].hex())
        cases = [altered, dict(features, adjacent_repeat_ratio=math.nextafter(features['adjacent_repeat_ratio'], 0.)),
                 dict(features, file_size=17.), dict(features, max_run_length=True), dict(reversed(list(features.items()))),
                 dict(features, entropy=math.nan), dict(features, score=1)]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                r.assert_features(value, expected, CONTRACT)

    def test_canonical_decode_rejects_duplicate_and_wrong_type_fields(self):
        value = r.canonical_features(r.load_reference().extract_features(b'ABC'), CONTRACT)
        self.assertEqual(r.canonical_features(r.decode_features(value, CONTRACT), CONTRACT), value)
        bad = copy.deepcopy(value)
        bad[1] = bad[0]
        with self.assertRaises(ValueError): r.decode_features(bad, CONTRACT)
        bad = copy.deepcopy(value)
        bad[0] = ['file_size', 'float', float(3).hex()]
        with self.assertRaises(ValueError): r.decode_features(bad, CONTRACT)

    def test_frame_dtype_columns_values_and_index_are_checked(self):
        features = r.load_reference().extract_features(b'ABCABC')
        frame = r.load_frame_factory(CONTRACT['names_in_order'])(features)
        r.frame_values(frame, features, CONTRACT)
        bad_value = frame.copy()
        bad_value.iloc[0, 1] = math.nextafter(float(frame.iloc[0, 1]), math.inf)
        for bad in (frame.astype('float32'), frame.iloc[:, ::-1], bad_value, frame.rename(index={0: 1})):
            with self.assertRaises(ValueError): r.frame_values(bad, features, CONTRACT)
        with self.assertRaises(ValueError): r.load_frame_factory(CONTRACT['names_in_order'])({**features, 'policy_cost': 1})

    def test_fake_prediction_gate_checks_all_probabilities_without_fit(self):
        expected = dict(predicted_algorithm='zstd', uncalibrated_confidence='.75', probability_gzip='.25',
                        probability_bz2='0.0', probability_lzma='0.0', probability_zstd='.75')
        model = FakeModel()
        actual = r.prediction_record(model, None, expected, ['gzip', 'zstd'])
        self.assertEqual(actual['probability_bz2'], (0.).hex())
        self.assertEqual(model.calls, ['predict', 'predict_proba'])
        for bad in (FakeModel(chosen='gzip'), FakeModel(probabilities=(math.nextafter(.25, 0.), .75)),
                    FakeModel(classes=('zstd', 'gzip')), FakeModel(probabilities=(math.nan, .75))):
            with self.assertRaises(ValueError): r.prediction_record(bad, None, expected, ['gzip', 'zstd'])

    def test_profiler_restores_after_partial_install_failure(self):
        module = r.load_reference()
        original = module.extract_features
        with self.assertRaises(AttributeError):
            with r.CallProfiler(module, ['extract_features', 'missing_target']): pass
        self.assertIs(module.extract_features, original)

    def test_all_four_modes_write_complete_fixture_schedule_and_audit(self):
        with self.temp() as parent:
            for mode in r.MODES:
                reference, data, expected, slots, inventory = fixture_setup(mode)
                out = Path(parent) / mode
                r.run_mode(mode, slots, {'fixture': data}, expected, reference, r.load_frame_factory(CONTRACT['names_in_order']),
                           out, CONTRACT, TARGETS, data_kind='test_fixture', clock=StepClock())
                rows = audit.read_jsonl(out / 'trials.jsonl')
                audit.audit_mode(mode, slots, rows, expected, inventory, CONTRACT, TARGETS, 'test_fixture')
                self.assertEqual(len(rows), 6)
                self.assertTrue((out / 'complete.json').exists())
                self.assertFalse((out / 'failure.json').exists())

    def test_independent_auditor_rejects_partial_duplicate_value_kind_hash_and_timer_drift(self):
        with self.temp() as parent:
            reference, data, expected, slots, inventory = fixture_setup('extract_only')
            out = Path(parent) / 'mode'
            r.run_mode('extract_only', slots, {'fixture': data}, expected, reference, None, out, CONTRACT, TARGETS,
                       data_kind='test_fixture', clock=StepClock())
            good = audit.read_jsonl(out / 'trials.jsonl')
            variants = [good[:-1], good+[good[-1]]]
            for field, value in [('elapsed_ns', 0), ('input_sha256', 'wrong'), ('data_kind', 'research'), ('round_index', '4')]:
                bad = copy.deepcopy(good)
                bad[0][field] = value
                variants.append(bad)
            bad = copy.deepcopy(good)
            bad[0]['features'][1][2] = '0x0.0p+0'
            variants.append(bad)
            for rows in variants:
                with self.assertRaises(ValueError):
                    audit.audit_mode('extract_only', slots, rows, expected, inventory, CONTRACT, TARGETS, 'test_fixture')

    def test_tree_audit_rejects_self_double_count_missing_calls_and_wrong_parent(self):
        reference = r.load_reference()
        with r.CallProfiler(reference, TARGETS, StepClock()) as profiler:
            reference.extract_features(b'AB'*2100)
            events = copy.deepcopy(profiler.events)
        trial = dict(start_ns=0, end_ns=max(e['end_ns'] for e in events)+1)
        variants = [events[:-1]]
        for field, value in [('self_ns', -1), ('parent_id', 999), ('depth', 99), ('elapsed_ns', 0)]:
            bad = copy.deepcopy(events)
            bad[0][field] = value
            variants.append(bad)
        for calls in variants:
            with self.assertRaises(ValueError): audit.call_tree(calls, trial, 4200, CONTRACT, TARGETS)

    def test_failure_preserves_partial_trial_and_restores_wrappers_without_retry(self):
        with self.temp() as parent:
            reference, data, expected, slots, _ = fixture_setup('instrumented_extract')
            original_extract = reference.extract_features
            def broken(data): raise RuntimeError('synthetic injected failure')
            reference._bigram_diversity = broken
            out = Path(parent) / 'failed'
            with self.assertRaisesRegex(RuntimeError, 'synthetic injected failure'):
                r.run_mode('instrumented_extract', slots, {'fixture': data}, expected, reference, None, out,
                           CONTRACT, TARGETS, data_kind='test_fixture', clock=StepClock())
            self.assertIs(reference.extract_features, original_extract)
            self.assertIs(reference._bigram_diversity, broken)
            self.assertFalse((out / 'complete.json').exists())
            self.assertTrue((out / 'failure.json').exists())
            rows = audit.read_jsonl(out / 'trials.jsonl')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'error')
            before = (out / 'trials.jsonl').read_bytes()
            with self.assertRaises(FileExistsError):
                r.run_mode('instrumented_extract', slots, {'fixture': data}, expected, reference, None, out,
                           CONTRACT, TARGETS, data_kind='test_fixture')
            self.assertEqual((out / 'trials.jsonl').read_bytes(), before)

    def test_exact_output_failure_and_nonpositive_duration_cannot_complete(self):
        with self.temp() as parent:
            for i, clock in enumerate((lambda: 10, StepClock())):
                reference, data, expected, slots, _ = fixture_setup('extract_only')
                if i: expected['fixture'][1][2] = '0x0.0p+0'
                out = Path(parent) / str(i)
                with self.assertRaises(ValueError):
                    r.run_mode('extract_only', slots, {'fixture': data}, expected, reference, None, out, CONTRACT,
                               TARGETS, data_kind='test_fixture', clock=clock)
                self.assertTrue((out / 'failure.json').exists())
                self.assertFalse((out / 'complete.json').exists())

    def test_frozen_schedule_mutations_reject_and_paths_stay_in_root(self):
        rows = r.read_csv(r.FREEZE / 'schedule.csv')
        inventory = r.read_csv(r.FREEZE / 'input_inventory.csv')
        r.validate_schedule(rows, inventory, PLAN)
        for bad in (rows[:-1], rows+[rows[-1]], list(reversed(rows))):
            with self.assertRaises(ValueError): r.validate_schedule(bad, inventory, PLAN)
        with self.assertRaises(ValueError): r.under(ROOT, '../outside')
        with self.assertRaises(ValueError): runner.profile_output(ROOT / 'data/temp/wrong')

    def test_missing_implementation_lock_stops_before_real_input_read(self):
        with self.temp() as parent:
            with patch.object(r, 'IMPLEMENTATION', Path(parent) / 'absent.json'), patch.object(r, 'read_corpus') as reader:
                with self.assertRaises(FileNotFoundError): runner.run(ROOT / 'data/results/feature_profile_baseline_fixture_guard', 'fixture')
                reader.assert_not_called()
        self.assertFalse((ROOT / 'data/results/feature_profile_baseline_fixture_guard').exists())

    def test_fresh_subprocess_smoke_uses_synthetic_input_only(self):
        with self.temp() as parent:
            out = Path(parent) / 'child'
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--fixture-worker', str(out), 'instrumented_extract'],
                                    cwd=ROOT, capture_output=True, text=True, timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.assertEqual(result.returncode, 0, result.stderr)
            started = json.loads((out / 'started.json').read_bytes())
            self.assertNotEqual(started['pid'], os.getpid())
            self.assertEqual(started['data_kind'], 'test_fixture')
            _, _, expected, slots, inventory = fixture_setup('instrumented_extract')
            audit.audit_mode('instrumented_extract', slots, audit.read_jsonl(out / 'trials.jsonl'), expected, inventory, CONTRACT, TARGETS, 'test_fixture')

    def test_worker_interrupt_terminates_only_owned_child_and_preserves_process_record(self):
        from unittest.mock import MagicMock
        with self.temp() as parent:
            child = MagicMock(pid=12345, returncode=-1)
            child.wait.side_effect = [KeyboardInterrupt(), 0]
            with patch.object(runner.subprocess, 'Popen', return_value=child):
                with self.assertRaises(KeyboardInterrupt): runner.execute_worker('extract_only', Path(parent))
            child.terminate.assert_called_once()
            child.kill.assert_not_called()
            record = json.loads((Path(parent) / 'extract_only_process.json').read_bytes())
            self.assertEqual(record['status'], 'interrupted')
            self.assertEqual(record['pid'], 12345)
            self.assertTrue((Path(parent) / 'extract_only.log').exists())

    def test_worker_nonzero_exit_is_failure_and_never_retried(self):
        from unittest.mock import MagicMock
        with self.temp() as parent:
            child = MagicMock(pid=12345)
            child.wait.return_value = 7
            with patch.object(runner.subprocess, 'Popen', return_value=child) as spawn:
                with self.assertRaisesRegex(ValueError, 'Worker failed'): runner.execute_worker('frame_only', Path(parent))
            spawn.assert_called_once()
            self.assertEqual(json.loads((Path(parent) / 'frame_only_process.json').read_bytes())['returncode'], 7)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--fixture-worker':
        fixture_worker(sys.argv[2], sys.argv[3])
    else:
        unittest.main()
