"""Artificial exactness checks; no stored model or real corpus execution."""
import copy
import io
import json
from pathlib import Path
import unittest
from research_log import feature_pair_candidates_20261111 as c
from research_log import feature_profile_runtime_20261111 as r

PLAN = json.loads((r.FREEZE / 'plan.json').read_bytes())
CONTRACT = PLAN['feature_contract']
EVIDENCE = []


class IndexedBytes(bytes):
    def __getitem__(self, key): return 0 if isinstance(key, int) else super().__getitem__(key)


class ShortLengthBytes(bytes):
    def __len__(self): return super().__len__()-1


class PairCandidatesTests(unittest.TestCase):
    def test_133_public_inputs_all_variants_exact(self):
        reference = c.build('reference')
        modules = {v: c.build(v) for v in c.VARIANTS[1:]}
        frame = r.load_frame_factory(CONTRACT['names_in_order'])
        inputs = list(r.fixture_inputs(PLAN))+[('indexed_subclass', IndexedBytes(b'ABCDEF')),
                                              ('length_subclass', ShortLengthBytes(b'ABCDEF'))]
        self.assertEqual(len(inputs), 133)
        for name, data in inputs:
            expected = r.canonical_features(reference.extract_features(data), CONTRACT)
            original = bytes(data)
            for variant, module in modules.items():
                with self.subTest(name=name, variant=variant):
                    value = module.extract_features(data)
                    r.assert_features(value, expected, CONTRACT)
                    r.frame_values(frame(value), value, CONTRACT)
                    self.assertEqual(bytes(data), original)
            EVIDENCE.append(dict(fixture=name, input_sha256=r.digest(data), variants=list(modules), exact=True))

    def test_invalid_inputs_and_private_short_helpers(self):
        ref = c.build('reference')
        for variant in c.VARIANTS[1:]:
            module = c.build(variant)
            for data in (b'', bytearray(b'a'), memoryview(b'a'), 'a', None):
                try: ref.extract_features(data)
                except (ValueError, TypeError) as exc: kind, message = type(exc), str(exc)
                with self.assertRaises(kind) as actual: module.extract_features(data)
                self.assertEqual(str(actual.exception), message)
            for name in ('_run_statistics', '_bigram_diversity'):
                for data in (b'', b'X'):
                    self.assertEqual(getattr(module, name)(data), getattr(ref, name)(data))

    def records(self):
        data = b'ABC'*20
        expected = {'fixture': r.canonical_features(c.build('reference').extract_features(data), CONTRACT)}
        schedule = [dict(comparison=v, mode=m, sample_id='fixture', first=first,
                         second=v if first == 'reference' else 'reference', round_index='1', is_warmup='False')
                    for v in c.VARIANTS[1:] for m in ('extract_only', 'extract_and_frame') for first in ('reference', v)]
        stream = io.StringIO()
        c.execute_pairs(schedule, {'fixture': data}, expected, CONTRACT, r.load_frame_factory(CONTRACT['names_in_order']), stream, data_kind='test_fixture')
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        return schedule, rows, expected, {'fixture': dict(input_sha256=r.digest(data))}

    def test_both_orders_all_candidates_and_modes(self):
        schedule, rows, expected, inventory = self.records()
        result = c.verify_pairs(schedule, rows, expected, inventory, data_kind='test_fixture')
        self.assertEqual(len(result), 12)
        for pair, delta in zip(schedule, result): self.assertEqual(delta['comparison'], pair['comparison'])

    def test_partial_duplicate_timing_output_and_order_tampering_reject(self):
        schedule, rows, expected, inventory = self.records()
        bad_sets = [rows[:-1], rows+[rows[-1]], list(reversed(rows))]
        for field, value in [('elapsed_ns', 0), ('input_sha256', 'wrong'), ('data_kind', 'research'), ('variant', 'wrong')]:
            bad = copy.deepcopy(rows); bad[0][field] = value; bad_sets.append(bad)
        for bad in bad_sets:
            with self.assertRaises(ValueError): c.verify_pairs(schedule, bad, expected, inventory, data_kind='test_fixture')

    def test_failure_is_flushed_and_not_retried(self):
        data = b'ABC'
        expected = {'fixture': r.canonical_features(c.build('reference').extract_features(data), CONTRACT)}
        expected['fixture'][1][2] = '0x0.0p+0'
        stream = io.StringIO()
        schedule = [dict(comparison='both_numpy', mode='extract_only', sample_id='fixture', first='reference', second='both_numpy')]
        with self.assertRaises(ValueError): c.execute_pairs(schedule, {'fixture': data}, expected, CONTRACT, None, stream, data_kind='test_fixture')
        rows = stream.getvalue().splitlines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0])['status'], 'error')

    def test_namespaces_and_unmodified_helpers_are_isolated(self):
        modules = [c.build(v) for v in c.VARIANTS]
        self.assertEqual(len({id(m) for m in modules}), 4)
        self.assertEqual(len({m._entropy_from_counts.__code__.co_code for m in modules}), 1)
        with self.assertRaises(ValueError): c.build('unknown')

    def test_controller_requires_lock_before_corpus_reads(self):
        from unittest.mock import patch
        from research_log import run_feature_pairs_20261111 as runner
        with patch.object(runner, 'LOCK', Path(__file__).parent / 'absent_pair_lock.json'), patch.object(r, 'read_corpus') as reader:
            with self.assertRaises(FileNotFoundError): runner.context()
            reader.assert_not_called()
