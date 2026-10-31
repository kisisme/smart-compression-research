"""Scenario aggregation fixtures, never real research results."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/'research_log/analyze_usage_scenarios_20261031.py'
SPEC=importlib.util.spec_from_file_location('usage_scenarios',PATH)
m=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)


def fixture():
    values=((100,20,8),(140,5,2),(500,100,100),(800,200,200))
    grouped={'fixture':{a:dict(sample_id='fixture',algorithm=a,original_size=1000,
                             compressed_size=b,compression_time_ms=c,decompression_time_ms=d,verified=True)
                        for a,(b,c,d) in zip(m.ALGORITHMS,values)}}
    samples={'fixture':{'generator':'artificial','size':'1000'}}
    plan={'profiles':[{'id':'fixture','retention_days':'1','expected_restorations':'10'}],
          'base_costs':{'storage_cost_per_byte_day':'1','compression_cost_per_ms':'1','decompression_cost_per_ms':'1'},
          'time_cost_multipliers':['0.1','1','10'],'deadline_compression_ms':['1','25'],
          'deadline_decompression_ms':['1','10']}
    return samples,grouped,plan


class ScenarioTests(unittest.TestCase):
    def test_full_cartesian_scenarios_and_duplicate_ids(self):
        _,_,plan=fixture(); costs,deadlines=m.scenarios(plan)
        self.assertEqual((len(costs),len(deadlines)),(3,4))
        self.assertEqual(costs[0]['policy']['compression_cost_per_ms'],'0.1')
        plan['profiles'].append(dict(plan['profiles'][0]))
        with self.assertRaises(ValueError): m.scenarios(plan)

    def test_cost_summary_uses_total_cost_not_mean_of_percentages(self):
        rows=[dict(selected_algorithm='gzip',cost_zstd=100,selected_cost=50,relative_cost_saving_pct=50,
                   size_saved_bytes=5,compression_delta_ms=1,decompression_delta_ms=-1),
              dict(selected_algorithm='zstd',cost_zstd=900,selected_cost=900,relative_cost_saving_pct=0,
                   size_saved_bytes=0,compression_delta_ms=0,decompression_delta_ms=0)]
        result=m.cost_summary(rows)
        self.assertEqual(result['total_cost_saving_pct'],5)
        self.assertEqual(result['mean_per_file_cost_saving_pct'],25)

    def test_deadline_infeasibility_stays_in_all_sample_denominator(self):
        rows=[dict(selected_algorithm='gzip',zstd_feasible=False),
              dict(selected_algorithm=None,zstd_feasible=False)]
        result=m.deadline_summary(rows)
        self.assertEqual(result['non_zstd_selected_pct_all'],50)
        self.assertEqual(result['non_zstd_selected_pct_feasible'],100)
        self.assertEqual(result['constraint_unsatisfied_count'],1)
        self.assertEqual(result['feasibility_recovery_count'],1)

    def test_zero_feasible_subset_is_null_not_zero_performance(self):
        result=m.deadline_summary([dict(selected_algorithm=None,zstd_feasible=False)])
        self.assertIsNone(result['non_zstd_selected_pct_feasible'])
        self.assertEqual(result['selected_count'],0)

    def test_all_combinations_and_group_counts_preserve_inputs(self):
        samples,grouped,plan=fixture(); before=copy.deepcopy(grouped)
        summary,tables=m.calculate(samples,grouped,m.scenarios(plan))
        self.assertEqual(len(tables['lifetime_results.csv']),3)
        self.assertEqual(len(tables['deadline_results.csv']),4)
        self.assertEqual(summary['cost']['fixture_t1']['selected_counts']['bz2'],1)
        self.assertEqual(summary['deadline']['deadline_c1_d1']['constraint_unsatisfied_count'],1)
        self.assertEqual(grouped,before)

    def test_unknown_measurement_aborts_instead_of_dropping_sample(self):
        samples,grouped,plan=fixture(); del grouped['fixture']['zstd']
        with self.assertRaises(ValueError): m.calculate(samples,grouped,m.scenarios(plan))

    def test_mismatched_sample_coverage_is_rejected(self):
        samples,grouped,plan=fixture(); samples['other']=dict(samples['fixture'])
        with self.assertRaises(ValueError): m.calculate(samples,grouped,m.scenarios(plan))


if __name__=='__main__': unittest.main()
