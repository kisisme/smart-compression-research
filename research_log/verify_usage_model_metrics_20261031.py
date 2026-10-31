"""Independent arithmetic/metric audit of the fixed external-corpus study."""
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from research_log.analyze_pilot_tradeoffs_20261029 import read_csv,write_json

OUT=ROOT/'data/results/usage_candidate_study_20261031_01'
ALGS=('gzip','bz2','lzma','zstd')
def require(ok,message):
    if not ok:raise ValueError(message)
def close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-12)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def manual_metrics(rows):
    matrix=[[0]*4 for _ in ALGS]
    for r in rows:matrix[ALGS.index(r['true_algorithm'])][ALGS.index(r['chosen_algorithm'])]+=1
    f1=[]
    for i in range(4):
        tp=matrix[i][i];fp=sum(matrix[j][i] for j in range(4) if j!=i);fn=sum(matrix[i][j] for j in range(4) if j!=i)
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    return sum(matrix[i][i] for i in range(4))/len(rows),sum(f1)/4,matrix


def main():
    target=OUT/'metrics_verification.json';require(not target.exists(),'Existing verification')
    lock=json.loads((OUT/'study_lock.json').read_bytes());plan=lock['plan']
    frozen=json.loads((ROOT/plan['scenario_freeze']).read_bytes());training=json.loads((OUT/'training.json').read_bytes())
    original=json.loads((OUT/'corpus/manifest.json').read_bytes());entries={r['sample_id']:r for r in original['candidates'] if r['selection_status']=='selected'}
    models={(r['sample_id'],r['scenario_id'],r['model']):r['predicted_algorithm'] for r in read_csv(OUT/'predictions/frozen_predictions.csv')}
    measured=defaultdict(dict)
    for r in read_csv(OUT/'benchmark/compression_results.csv'):measured[r['sample_id']][r['algorithm']]=r
    definitions={s['id']:s['policy'] for s in frozen['expanded_cost_scenarios']};values={}
    for sid,p in definitions.items():
        for sample,data in measured.items():
            costs={}
            for a in ALGS:
                row=data[a];ks,h,kc,kd,n=(float(p[k]) for k in ('storage_cost_per_byte_day','retention_days','compression_cost_per_ms','decompression_cost_per_ms','expected_restorations'))
                score=math.fsum(((ks*h)*int(row['compressed_size']),kc*float(row['compression_time_ms']),(kd*n)*float(row['decompression_time_ms'])))
                f=Fraction
                exact=f(p['storage_cost_per_byte_day'])*f(p['retention_days'])*int(row['compressed_size'])+f(p['compression_cost_per_ms'])*f(row['compression_time_ms'])+f(p['decompression_cost_per_ms'])*f(p['expected_restorations'])*f(row['decompression_time_ms'])
                require(close(score,float(exact)),'Fraction objective mismatch');costs[a]=score
            values[(sid,sample)]=costs
    choices=read_csv(OUT/'evaluation/strategy_choices.csv');buckets=defaultdict(list)
    for r in choices:
        sid,sample,strategy=r['scenario_id'],r['sample_id'],r['strategy'];costs=values[(sid,sample)]
        truth=min(ALGS,key=costs.__getitem__)
        expected=(strategy if strategy in ALGS else training['majorities'][sid]['algorithm'] if strategy=='train_majority'
                  else truth if strategy=='oracle' else models[(sample,sid,strategy)])
        require(r['chosen_algorithm']==expected and r['true_algorithm']==truth,'Strategy target/choice mismatch')
        require(r['origin_group_id']==entries[sample]['origin_group_id'] and r['format']==entries[sample]['format'],'Group metadata mismatch')
        require(close(r['policy_cost'],costs[expected]) and close(r['oracle_cost'],costs[truth]),'Saved cost mismatch')
        require(close(r['difference_vs_majority'],costs[expected]-costs[training['majorities'][sid]['algorithm']]),'Baseline difference mismatch')
        buckets[(sid,strategy)].append(r)
    metrics=json.loads((OUT/'evaluation/codec_metrics.json').read_bytes())
    for (sid,strategy),rows in buckets.items():
        require(len(rows)==len(entries) and {r['sample_id'] for r in rows}==set(entries),'Metric sample coverage mismatch')
        actual=metrics[sid][strategy];accuracy,f1,matrix=manual_metrics(rows)
        require(close(actual['accuracy'],accuracy) and close(actual['macro_f1'],f1) and actual['confusion_matrix']==matrix,'Independent classification metrics mismatch')
        groups=defaultdict(list)
        for r in rows:groups[r['origin_group_id']].append(float(r['difference_vs_majority']))
        primary=statistics.fmean(statistics.fmean(v) for v in groups.values())
        require(close(actual['primary_group_mean_difference_vs_majority'],primary),'Independent primary metric mismatch')
        cost=math.fsum(float(r['policy_cost']) for r in rows);base=math.fsum(float(r['zstd_cost']) for r in rows)
        require(close(actual['cost_saving_pct_vs_zstd'],100*(base-cost)/base),'Aggregate policy saving mismatch')
        require(close(actual['mean_regret'],statistics.fmean(float(r['regret']) for r in rows)),'Mean regret mismatch')
    trials=defaultdict(list)
    for r in read_csv(OUT/'pipeline/raw_trials.csv'):trials[(r['sample_id'],r['strategy'])].append(r)
    aggregate={}
    for key,rows in trials.items():
        require(len(rows)==5,'Pipeline repeat coverage')
        aggregate[key]={'bytes':int(rows[0]['package_bytes']),**{k:statistics.median(int(r[k]) for r in rows)/1e6 for k in ('compression_ns','restoration_ns','feature_ns','prediction_ns')}}
    loads=defaultdict(list)
    for r in read_csv(OUT/'pipeline/model_load_repeats.csv'):loads[(r['scenario_id'],r['model'])].append(int(r['elapsed_ns'])/1e6)
    pipeline_rows=read_csv(OUT/'evaluation/pipeline_metrics.csv')
    for r in pipeline_rows:
        sid,kind=r['scenario_id'],r['model'];p={k:float(v) for k,v in definitions[sid].items()}
        def cost(v):return math.fsum((p['storage_cost_per_byte_day']*p['retention_days']*v['bytes'],p['compression_cost_per_ms']*v['compression_ns'],p['decompression_cost_per_ms']*p['expected_restorations']*v['restoration_ns']))
        baseline=math.fsum(cost(aggregate[(s,'fixed_zstd')]) for s in entries)
        records=[aggregate[(s,sid+'__'+kind)] for s in entries];total=math.fsum(cost(v) for v in records)
        require(close(r['warm_pipeline_cost_saving_pct'],100*(baseline-total)/baseline),'Independent pipeline saving mismatch')
        require(close(r['median_verified_model_load_ms'],statistics.median(loads[(sid,kind)])),'Load median mismatch')
        require(close(r['mean_feature_ms'],statistics.fmean(v['feature_ns'] for v in records)),'Feature overhead mismatch')
        require(close(r['mean_prediction_ms'],statistics.fmean(v['prediction_ns'] for v in records)),'Prediction overhead mismatch')
    for name,value in lock['protected_after_sha256'].items():require(sha(ROOT/name)==value,'Protected input changed')
    value={'status':'independent_metrics_verified','created_at_utc':datetime.now(timezone.utc).isoformat(),
           'source_sha256':sha(Path(__file__)),'sample_count':len(entries),'strategy_choice_count':len(choices),
           'codec_metric_conditions':len(buckets),'pipeline_metric_conditions':len(pipeline_rows),
           'checks':['Exact Fraction costs','Frozen strategy targets/choices','Manual four-class confusion/accuracy/Macro F1',
                     'Independent equal-origin-group primary difference','Pooled cost/regret','Raw pipeline medians and cost/loading/feature/prediction overhead'],
           'verified_artifact_sha256':{name:sha(OUT/name) for name in ('evaluation/codec_metrics.json','evaluation/strategy_choices.csv','evaluation/pipeline_metrics.csv')},
           'summary_all_model_conditions':{sid:{k:{n:metrics[sid][k][n] for n in ('accuracy','macro_f1','cost_saving_pct_vs_zstd','primary_group_mean_difference_vs_majority')} for k in ('decision_tree','random_forest')} for sid in definitions},
           'pipeline_saving_range_pct':[min(float(r['warm_pipeline_cost_saving_pct']) for r in pipeline_rows),max(float(r['warm_pipeline_cost_saving_pct']) for r in pipeline_rows)]}
    write_json(target,value)
    print(json.dumps({'status':value['status'],'codec_metric_conditions':len(buckets),'pipeline_metric_conditions':len(pipeline_rows),
                      'pipeline_saving_range_pct':value['pipeline_saving_range_pct'],'model_metrics':value['summary_all_model_conditions']},ensure_ascii=False))


if __name__=='__main__':main()
