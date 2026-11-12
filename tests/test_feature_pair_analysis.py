"""Artificial saved-record fixtures, not research measurements."""
import copy
import unittest
from research_log.analyze_feature_pairs_20261112 import audit_calls, summary


class PairAnalysisTests(unittest.TestCase):
    def fixture(self):
        slot = dict(comparison='both_numpy', mode='extract_and_frame', sample_id='fixture',
                    first='reference', second='both_numpy', is_warmup='False')
        expected = {'fixture': [['n', 'int', '3'], ['f', 'float', (0.5).hex()]]}
        rows = []
        for position, variant, start, end in [('first','reference',10,30),('second','both_numpy',35,40)]:
            rows.append(dict(slot, position=position, variant=variant, status='ok',
                             data_kind='observed_development_corpus', input_sha256='fixture_hash',
                             features=expected['fixture'], frame=[(3.0).hex(),(0.5).hex()],
                             start_ns=start,end_ns=end,elapsed_ns=end-start))
        return [slot],rows,expected,{'fixture':dict(input_sha256='fixture_hash')}

    def test_pair_difference_and_frame(self):
        result = audit_calls(*self.fixture())
        self.assertEqual(result[0]['delta_ns'],-15)
        self.assertEqual(result[0]['reference_ns'],20)

    def test_partial_duplicates_and_corruption_rejected(self):
        slots,rows,expected,inventory = self.fixture()
        bad = [rows[:-1],rows+rows,list(reversed(rows))]
        for key,value in [('elapsed_ns',0),('elapsed_ns',5.0),('start_ns',29),
                          ('status','error'),('input_sha256','bad'),('features',[]),('frame',[]),
                          ('data_kind','test_fixture'),('variant','run_numpy')]:
            changed=copy.deepcopy(rows)
            changed[1][key]=value
            bad.append(changed)
        for changed in bad:
            with self.subTest(rows=changed):
                with self.assertRaises(ValueError): audit_calls(slots,changed,expected,inventory)

    def test_equal_group_weight_is_not_pooled_file_weight(self):
        rows=[dict(origin_group_id='a',paired_median_delta_ns=-10,reference_median_ns=30,candidate_median_ns=20),
              dict(origin_group_id='a',paired_median_delta_ns=-10,reference_median_ns=30,candidate_median_ns=20),
              dict(origin_group_id='b',paired_median_delta_ns=20,reference_median_ns=10,candidate_median_ns=30)]
        value=summary(rows)
        self.assertEqual(value['equal_origin_mean_paired_delta_ns'],5)
        self.assertEqual(value['pooled_median_ratio'],1)
        self.assertEqual((value['improved'],value['regressed'],value['tied']),(2,1,0))


if __name__ == '__main__': unittest.main()
