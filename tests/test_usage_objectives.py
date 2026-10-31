"""Artificial fixtures for candidate objectives; no research measurements."""
from __future__ import annotations

import copy
from dataclasses import replace
from fractions import Fraction
import itertools
import math
from pathlib import Path
import subprocess
import sys
import unittest

from src.usage_objectives import (
    ALGORITHMS, LifetimePolicy, evaluate_lifetime_cost, select_under_deadlines,
)


def fixture():
    values = ((100,20,8),(140,5,2),(500,100,100),(800,200,200))
    return [dict(sample_id="synthetic_fixture",algorithm=a,original_size=1000,
                 compressed_size=b,compression_time_ms=c,decompression_time_ms=d,
                 verified=True,status="ok")
            for a,(b,c,d) in zip(ALGORITHMS,values,strict=True)]


def policy(**overrides):
    return LifetimePolicy(**{
        "retention_days":1,"expected_restorations":10,
        "storage_cost_per_byte_day":1,"compression_cost_per_ms":1,
        "decompression_cost_per_ms":1,**overrides,
    })


class UsageObjectiveTests(unittest.TestCase):
    def test_lifetime_formula_and_components(self):
        result = evaluate_lifetime_cost(fixture(),policy=policy())
        self.assertEqual(result["selected_algorithm"],"bz2")
        self.assertEqual(result["values"]["gzip"],200)
        self.assertEqual(result["values"]["bz2"],165)
        self.assertEqual(result["components"]["gzip"],{"storage":100,"compression":20,"restoration":80})
        self.assertFalse(result["official_score"])
        self.assertEqual(result["value_unit"],"policy_cost_points")

    def test_storage_and_restoration_crossover(self):
        cases = ((1,0,"gzip"),(1,10,"bz2"),(5,10,"gzip"),(.975,3,"gzip"),(.975,5,"bz2"))
        for h,n,winner in cases:
            with self.subTest(h=h,n=n):
                result = evaluate_lifetime_cost(fixture(),policy=policy(retention_days=h,expected_restorations=n))
                self.assertEqual(result["selected_algorithm"],winner)

    def test_retention_boundary_tie_has_fixed_order(self):
        rows = fixture()
        for h,n in ((.375,0),(.975,4)):
            for permuted in (rows,list(reversed(rows))):
                result = evaluate_lifetime_cost(permuted,policy=policy(retention_days=h,expected_restorations=n))
                self.assertEqual(result["selected_algorithm"],"gzip")
                self.assertEqual(result["tied_algorithms"],["gzip","bz2"])

    def test_independent_fraction_oracle(self):
        rows = fixture()
        rows[0]["compression_time_ms"] = "1.2345"
        rows[1]["decompression_time_ms"] = "2.3456"
        p = policy(retention_days="1.25",expected_restorations="0.125",
                   storage_cost_per_byte_day="0.0007",compression_cost_per_ms="0.035",
                   decompression_cost_per_ms="0.08")
        result = evaluate_lifetime_cost(rows,policy=p)
        exact = {}
        f = lambda x:Fraction(str(x))
        for row in rows:
            exact[row["algorithm"]] = (f(p.storage_cost_per_byte_day)*f(p.retention_days)*row["compressed_size"]
                +f(p.compression_cost_per_ms)*f(row["compression_time_ms"])
                +f(p.decompression_cost_per_ms)*f(p.expected_restorations)*f(row["decompression_time_ms"]))
        self.assertEqual(result["selected_algorithm"],min(ALGORITHMS,key=exact.__getitem__))
        for a,value in exact.items():
            self.assertTrue(math.isclose(result["values"][a],float(value),rel_tol=1e-14))

    def test_coefficient_scale_invariance(self):
        p = policy()
        before = evaluate_lifetime_cost(fixture(),policy=p)
        after = evaluate_lifetime_cost(fixture(),policy=replace(p,storage_cost_per_byte_day=3.5,
                    compression_cost_per_ms=3.5,decompression_cost_per_ms=3.5))
        self.assertEqual(before["selected_algorithm"],after["selected_algorithm"])
        for a in ALGORITHMS:
            self.assertEqual(after["values"][a],3.5*before["values"][a])

    def test_ms_seconds_conversion_preserves_cost(self):
        rows = fixture()
        before = evaluate_lifetime_cost(rows,policy=policy())
        for row in rows:
            row["compression_time_ms"] /= 1000
            row["decompression_time_ms"] /= 1000
        after = evaluate_lifetime_cost(rows,policy=policy(compression_cost_per_ms=1000,decompression_cost_per_ms=1000))
        self.assertEqual(before["values"],after["values"])

    def test_time_only_requires_explicit_profile_kind(self):
        with self.assertRaises(ValueError):
            policy(retention_days=0)
        p = policy(retention_days=0,expected_restorations=0,profile_kind="time_only")
        self.assertEqual(evaluate_lifetime_cost(fixture(),policy=p)["selected_algorithm"],"bz2")
        with self.assertRaises(ValueError):
            policy(profile_kind="time_only")

    def test_all_effective_coefficients_zero_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"effective coefficient"):
            policy(retention_days=0,expected_restorations=0,compression_cost_per_ms=0,profile_kind="time_only")

    def test_policy_values_are_explicit_finite_and_non_negative(self):
        for name in ("retention_days","expected_restorations","storage_cost_per_byte_day",
                     "compression_cost_per_ms","decompression_cost_per_ms"):
            for value in (None,True,False,-1,float("nan"),float("inf"),"",{},"unknown",10**400):
                with self.subTest(name=name,value=str(value)):
                    with self.assertRaises(ValueError):
                        policy(**{name:value})
        with self.assertRaises(ValueError):
            policy(profile_kind="archive")
        with self.assertRaises(TypeError):
            evaluate_lifetime_cost(fixture(),policy=None)

    def test_decimal_csv_strings_and_fractional_count(self):
        rows = fixture()
        for row in rows:
            for name in ("original_size","compressed_size","compression_time_ms","decompression_time_ms","verified"):
                row[name] = str(row[name])
        result = evaluate_lifetime_cost(rows,policy=policy(expected_restorations="0.5"))
        self.assertEqual(result["values"]["gzip"],124)
        self.assertEqual(result["values"]["bz2"],146)

    def test_deadline_size_selection_and_inclusive_boundary(self):
        for tc,td,winner in ((25,10,"gzip"),(25,3,"bz2"),(20,8,"gzip")):
            with self.subTest(tc=tc,td=td):
                result = select_under_deadlines(fixture(),compression_limit_ms=tc,decompression_limit_ms=td)
                self.assertEqual(result["selected_algorithm"],winner)
                self.assertEqual(result["status"],"selected")
                self.assertIn("lzma",result["violations"])

    def test_empty_feasible_set_has_no_fallback(self):
        rows = fixture()
        result = select_under_deadlines(rows,compression_limit_ms=1,decompression_limit_ms=1)
        self.assertEqual(result["status"],"constraint_unsatisfied")
        self.assertIsNone(result["selected_algorithm"])
        self.assertIsNone(result["selection_value"])
        self.assertEqual(result["feasible_algorithms"],[])
        self.assertEqual(len(result["violations"]),len(ALGORITHMS))
        self.assertEqual(result["measurements"],rows)

    def test_deadline_bytes_remain_integers_beyond_float_precision(self):
        rows = fixture()
        for i,row in enumerate(rows):
            row["compressed_size"] = 2**53+4-i
            row["compression_time_ms"] = 1
            row["decompression_time_ms"] = 1
        result = select_under_deadlines(rows,compression_limit_ms=2,decompression_limit_ms=2)
        self.assertEqual(result["selected_algorithm"],"zstd")
        self.assertEqual(result["selection_value"],2**53+1)

    def test_deadline_tie_uses_codec_order_not_speed_or_input_order(self):
        rows = fixture()
        rows[1]["compressed_size"] = rows[0]["compressed_size"]
        result = select_under_deadlines(reversed(rows),compression_limit_ms=25,decompression_limit_ms=10)
        self.assertEqual(result["selected_algorithm"],"gzip")
        self.assertEqual(result["tied_algorithms"],["gzip","bz2"])

    def test_deadline_limits_must_be_positive_finite_values(self):
        for key in ("compression_limit_ms","decompression_limit_ms"):
            for value in (None,True,0,-1,"NaN",float("inf"),"",[]):
                with self.subTest(key=key,value=value):
                    args = dict(compression_limit_ms=25,decompression_limit_ms=10)
                    args[key] = value
                    with self.assertRaises(ValueError):
                        select_under_deadlines(fixture(),**args)

    def test_missing_row_never_selects_from_remaining_algorithms(self):
        for rows in (fixture()[:3],[]):
            for result in (evaluate_lifetime_cost(rows,policy=policy()),
                           select_under_deadlines(rows,compression_limit_ms=25,decompression_limit_ms=10)):
                self.assertEqual(result["status"],"measurement_required")
                self.assertIsNone(result["selected_algorithm"])
                self.assertEqual(result["values"],{})
                self.assertIn("zstd",result["missing_measurements"])

    def test_each_missing_field_is_reported_without_imputation(self):
        for field in ("sample_id","original_size","compressed_size","compression_time_ms","decompression_time_ms","verified"):
            for value in (None,""):
                rows = fixture()
                rows[0][field] = value
                result = evaluate_lifetime_cost(rows,policy=policy())
                self.assertEqual(result["status"],"measurement_required")
                self.assertIn(field,result["missing_measurements"]["gzip"])
        rows = fixture()
        del rows[0]["decompression_time_ms"]
        self.assertEqual(select_under_deadlines(rows,compression_limit_ms=25,decompression_limit_ms=10)["status"],"measurement_required")

    def test_failed_measurements_reject_even_when_another_row_is_missing(self):
        for field,value in (("verified",False),("verified","False"),("verified",1),("status","error"),("status",None)):
            rows = fixture()[:3]
            rows[0][field] = value
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError):
                    evaluate_lifetime_cost(rows,policy=policy())
                with self.assertRaises(ValueError):
                    select_under_deadlines(rows,compression_limit_ms=25,decompression_limit_ms=10)

    def test_invalid_time_and_integer_byte_measurements_reject(self):
        for field,values in (("compression_time_ms",(True,0,-1,"NaN","inf",{})),
                             ("decompression_time_ms",(False,0,-1,"NaN","inf",[])),
                             ("compressed_size",(True,0,-1,"1.5",1.0,"NaN")),
                             ("original_size",(False,0,-1,"1e3",1000.0))):
            for value in values:
                rows = fixture()
                rows[0][field] = value
                with self.subTest(field=field,value=value):
                    with self.assertRaises(ValueError):
                        evaluate_lifetime_cost(rows,policy=policy())

    def test_duplicate_unknown_mixed_sample_and_original_size_reject(self):
        invalid = []
        rows = fixture(); rows.append(dict(rows[0])); invalid.append(rows)
        for field,value in (("algorithm","brotli"),("algorithm",["gzip"]),("sample_id","other"),
                            ("sample_id",123),("original_size",2000)):
            rows = fixture(); rows[0][field] = value; invalid.append(rows)
        invalid.append([None])
        for rows in invalid:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    evaluate_lifetime_cost(rows,policy=policy())

    def test_all_input_permutations_are_equivalent_and_inputs_are_not_mutated(self):
        rows = fixture()
        rows[0]["source_note"] = "synthetic metadata retained"
        before = copy.deepcopy(rows)
        expected = evaluate_lifetime_cost(rows,policy=policy())
        deadline = select_under_deadlines(rows,compression_limit_ms=25,decompression_limit_ms=10)
        for order in itertools.permutations(rows):
            self.assertEqual(evaluate_lifetime_cost(order,policy=policy()),expected)
            self.assertEqual(select_under_deadlines(iter(order),compression_limit_ms=25,decompression_limit_ms=10),deadline)
        self.assertEqual(rows,before)

    def test_no_epsilon_merges_nearby_costs(self):
        rows = fixture()
        rows[0]["compression_time_ms"] = 1.0000000000001
        rows[1]["compression_time_ms"] = 1.0
        p = policy(retention_days=0,expected_restorations=0,profile_kind="time_only")
        result = evaluate_lifetime_cost(rows,policy=p)
        self.assertEqual(result["selected_algorithm"],"bz2")
        self.assertEqual(result["tied_algorithms"],["bz2"])

    def test_overflow_and_underflow_are_not_silently_clipped(self):
        with self.assertRaisesRegex(ValueError,"underflows"):
            policy(compression_cost_per_ms="1e-1000")
        for kwargs in (dict(storage_cost_per_byte_day=1e308,retention_days=10),
                       dict(storage_cost_per_byte_day=1e-308,retention_days=1e-308)):
            with self.assertRaises(ValueError):
                policy(**kwargs)
        with self.assertRaises(ValueError):
            evaluate_lifetime_cost(fixture(),policy=policy(storage_cost_per_byte_day=1e308))
        rows = fixture()
        for row in rows:
            row["compression_time_ms"] = 1e308
            row["decompression_time_ms"] = 1e308
        p = policy(retention_days=0,expected_restorations=1,profile_kind="time_only")
        with self.assertRaisesRegex(ValueError,"Total cost"):
            evaluate_lifetime_cost(rows,policy=p)
        rows = fixture(); rows[0]["compression_time_ms"] = 1e-100
        with self.assertRaisesRegex(ValueError,"underflows"):
            evaluate_lifetime_cost(rows,policy=policy(compression_cost_per_ms=1e-300))

    def test_zero_coefficient_does_not_overflow_unused_huge_integer_size(self):
        rows = fixture()
        for row in rows:
            row["compressed_size"] = 10**400
        p = policy(retention_days=0,expected_restorations=0,profile_kind="time_only")
        result = evaluate_lifetime_cost(rows,policy=p)
        self.assertEqual(result["selected_algorithm"],"bz2")
        self.assertTrue(all(v["storage"]==0 for v in result["components"].values()))

    def test_fresh_import_has_no_codec_model_or_config_dependency(self):
        script = '''
import builtins, sys
original = builtins.__import__
blocked = {'gzip','bz2','lzma','zstandard','sklearn','pandas','numpy','src.scoring',
           'src.compressors','src.feature_extractor','smart_compress','smart_decompress'}
def guarded(name,*args,**kwargs):
    if name in blocked or any(name.startswith(x+'.') for x in blocked):
        raise RuntimeError('Forbidden import: '+name)
    return original(name,*args,**kwargs)
builtins.__import__ = guarded
def audit(event,args):
    if event=='open':
        path=str(args[0]).replace(chr(92),'/')
        if '/data/' in path or '/models/' in path or path.endswith('experiment_config.json'):
            raise RuntimeError('Forbidden file access: '+path)
sys.addaudithook(audit)
from src.usage_objectives import LifetimePolicy, evaluate_lifetime_cost, select_under_deadlines
print('isolated-import-ok')
'''
        result = subprocess.run([sys.executable,"-B","-c",script],cwd=Path(__file__).resolve().parents[1],
                                capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),"isolated-import-ok")


if __name__ == "__main__":
    unittest.main()
