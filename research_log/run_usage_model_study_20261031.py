"""Candidate-only train -> frozen predictions -> benchmarks -> measured engine -> audit."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import pickle
import platform
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from src.feature_extractor import FEATURE_NAMES, extract_features
from src.compressors import compress_data, decompress_data
from src.usage_objectives import ALGORITHMS, LifetimePolicy, evaluate_lifetime_cost, select_under_deadlines
from src.train_model import split_samples, fit_majority, fit_decision_tree, fit_random_forest
from src.unseen_manifest import audit_manifest
from compare_compress import compare_file
from research_log.analyze_pilot_tradeoffs_20261029 import load_inputs, read_csv, write_csv, write_json

OUT=ROOT/'data/results/usage_candidate_study_20261031_01'
LOCK_SHA='4c6a67792e9475cee3ea329b93ed6d10b8d2d8034f345478196fb48f78835586'
KINDS=('decision_tree','random_forest')


def require(ok,message):
    if not ok: raise ValueError(message)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(data): return hashlib.sha256(data).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def runtime_sources():
    paths=[*sorted((ROOT/'src').glob('*.py')),ROOT/'compare_compress.py',Path(__file__),ROOT/'tests/test_usage_model_study.py']
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}
def check_hashes(hashes):
    for relative,value in hashes.items(): require(sha(ROOT/relative)==value,'Hash changed: '+relative)
def context():
    require(sha(OUT/'study_lock.json')==LOCK_SHA,'Study criteria lock changed')
    lock=json.loads((OUT/'study_lock.json').read_bytes());check_hashes(lock['source_sha256']);check_hashes(lock['protected_after_sha256'])
    for relative,value in lock['corpus_artifact_sha256'].items(): require(sha(OUT/relative)==value,'Corpus artifact changed')
    plan=lock['plan']; frozen=json.loads((ROOT/plan['scenario_freeze']).read_bytes())
    require(sha(ROOT/plan['scenario_freeze'])==plan['scenario_freeze_sha256'],'Scenario changed')
    config=json.loads((ROOT/'config/experiment_config.json').read_bytes())
    return lock,plan,frozen,config
def phase(name):
    meta=json.loads((OUT/(name+'.json')).read_bytes())
    require(meta['status']=='completed' and not (OUT/(name+'_failed.json')).exists(),'Incomplete '+name)
    check_hashes(meta['runtime_source_sha256'])
    for relative,value in meta['artifact_sha256'].items(): require(sha(OUT/relative)==value,'Phase artifact changed: '+relative)
    return meta
def finish(name,directory,metadata):
    lock,_,_,_=context()
    check_hashes(lock['protected_after_sha256'])
    metadata.update(status='completed',completed_at_utc=now(),git_head=git('rev-parse','HEAD'),
                    runtime_source_sha256=runtime_sources(),
                    artifact_sha256={p.relative_to(OUT).as_posix():sha(p) for p in sorted(directory.rglob('*')) if p.is_file()})
    write_json(OUT/(name+'.json'),metadata)
    print(json.dumps({'phase':name,'status':'completed',**{k:v for k,v in metadata.items() if k.endswith('_count')}},ensure_ascii=False),flush=True)
def new_directory(name):
    p=OUT/name;require(not p.exists() and not (OUT/(name+'.json')).exists(),'Existing phase output: '+name);p.mkdir();return p
def corpus():
    lock,_,_,_=context(); audit_manifest(OUT/'corpus',lock['corpus_manifest_sha256'])
    manifest=json.loads((OUT/'corpus/manifest.json').read_bytes())
    entries=sorted((r for r in manifest['candidates'] if r['selection_status']=='selected'),key=lambda r:(r['origin_group_id'],r['sample_id']))
    require(len(entries)==lock['corpus_sample_count'],'Corpus selection coverage changed')
    return Path(manifest['input_root']),entries
def source_bytes(root,entry):
    path=root/entry['relative_path']; data=path.read_bytes()
    require(len(data)==entry['original_size'] and digest(data)==entry['input_sha256'],'Input bytes changed')
    return path,data
def feature_frame(features):
    require(set(features)==set(FEATURE_NAMES),'Feature schema differs')
    frame=pd.DataFrame([[float(features[n]) for n in FEATURE_NAMES]],columns=list(FEATURE_NAMES))
    require(np.isfinite(frame.to_numpy()).all(),'Non-finite features');return frame
def classification(truth,predicted):
    require(len(truth)==len(predicted)>0,'Prediction coverage mismatch')
    return {'accuracy':float(accuracy_score(truth,predicted)),
            'macro_f1':float(f1_score(truth,predicted,labels=list(ALGORITHMS),average='macro',zero_division=0)),
            'confusion_matrix':confusion_matrix(truth,predicted,labels=list(ALGORITHMS)).tolist()}


def train():
    lock,plan,frozen,config=context()
    implementation=json.loads((OUT/'implementation_lock.json').read_bytes())
    require(implementation['status']=='fixture_tests_passed_before_training','Implementation not validated')
    require(implementation['runtime_source_sha256']==runtime_sources(),'Implementation lock differs')
    directory=new_directory('training'); started=now(); initial_sources=runtime_sources()
    samples,grouped,_,_=load_inputs(ROOT/plan['training']['source'],config)
    sample_ids=sorted(samples)
    split=split_samples(pd.DataFrame([samples[s] for s in sample_ids]),config['baseline'])
    reference=read_csv(ROOT/plan['training']['split_reference'])
    require([(r.sample_id,int(r.seed),r.split) for r in split.itertuples()]==[(r['sample_id'],int(r['seed']),r['split']) for r in reference],'Original split mismatch')
    train_ids=split.loc[split['split']=='train','sample_id'].tolist(); test_ids=split.loc[split['split']=='test','sample_id'].tolist()
    require(not set(train_ids)&set(test_ids),'Train/test overlap')
    X=pd.DataFrame([[float(samples[s][f]) for f in FEATURE_NAMES] for s in sample_ids],index=sample_ids,columns=list(FEATURE_NAMES))
    require(np.isfinite(X.to_numpy()).all(),'Invalid training features')
    labels,development,models,majorities=[],[],[],{}
    for scenario in frozen['expanded_cost_scenarios']:
        sid=scenario['id']; target={}; cost_values={}
        for sample_id in sample_ids:
            result=evaluate_lifetime_cost(grouped[sample_id].values(),policy=LifetimePolicy(**scenario['policy']))
            require(result['status']=='selected','Incomplete Pilot target')
            target[sample_id]=result['selected_algorithm'];cost_values[sample_id]=result['values']
            labels.append({'scenario_id':sid,'sample_id':sample_id,'best_algorithm':target[sample_id],
                           **{'cost_'+a:result['values'][a] for a in ALGORITHMS}})
        majority=fit_majority([target[s] for s in train_ids]);majorities[sid]=majority
        for kind,fit in (('decision_tree',fit_decision_tree),('random_forest',fit_random_forest)):
            model=fit(X.loc[train_ids],[target[s] for s in train_ids],config[kind])
            filename=sid+'__'+kind+'.pkl'; path=directory/filename
            with path.open('xb') as stream: pickle.dump(model,stream,protocol=pickle.HIGHEST_PROTOCOL)
            predicted=model.predict(X.loc[test_ids]).tolist()
            for sample_id,choice in zip(test_ids,predicted,strict=True):
                development.append({'scenario_id':sid,'model':kind,'sample_id':sample_id,'true_algorithm':target[sample_id],
                                    'predicted_algorithm':choice,'policy_cost':cost_values[sample_id][choice],
                                    'oracle_cost':min(cost_values[sample_id].values()),'development_only':True})
            models.append({'scenario_id':sid,'kind':kind,'file':path.relative_to(OUT).as_posix(),'sha256':sha(path),
                           'classes':model.classes_.tolist(),'parameters':model.get_params(),
                           'development_metrics':classification([target[s] for s in test_ids],predicted)})
        print(json.dumps({'trained_scenario':sid}),flush=True)
    write_csv(directory/'candidate_labels.csv',labels);write_csv(directory/'development_predictions.csv',development)
    write_csv(directory/'split_assignments.csv',split.to_dict('records'))
    require(initial_sources==runtime_sources(),'Training source changed')
    finish('training',directory,{'started_at_utc':started,'models':models,'majorities':majorities,
        'feature_names':list(FEATURE_NAMES),'train_ids':train_ids,'development_ids':test_ids,
        'train_count':len(train_ids),'development_count':len(test_ids),'model_count':len(models),
        'packages':{p:version(p) for p in ('numpy','pandas','scikit-learn','zstandard')},
        'python':platform.python_version(),'platform':platform.platform(),'criteria_lock_sha256':LOCK_SHA,
        'implementation_lock_sha256':sha(OUT/'implementation_lock.json')})


def load_model(item,training,config):
    path=OUT/item['file'];require(sha(path)==item['sha256'],'Model hash mismatch')
    require(training['python']==platform.python_version() and all(version(p)==v for p,v in training['packages'].items()),'Model runtime/package versions differ')
    with path.open('rb') as stream: model=pickle.load(stream)
    expected=DecisionTreeClassifier if item['kind']=='decision_tree' else RandomForestClassifier
    require(type(model) is expected and model.get_params()==item['parameters'],'Model type/recorded settings mismatch')
    require(all(model.get_params().get(k)==v for k,v in config[item['kind']].items()),'Model explicit config mismatch')
    require(model.feature_names_in_.tolist()==training['feature_names']==list(FEATURE_NAMES),'Model input names mismatch')
    require(model.classes_.tolist()==item['classes'] and set(item['classes'])<=set(ALGORITHMS),'Model classes mismatch')
    return model


def predict():
    _,_,_,config=context(); training=phase('training');directory=new_directory('predictions'); started=now()
    root,entries=corpus(); models={(i['scenario_id'],i['kind']):load_model(i,training,config) for i in training['models']}
    samples,predictions=[],[]
    for entry in entries:
        _,data=source_bytes(root,entry);t=time.perf_counter_ns();features=extract_features(data);frame=feature_frame(features);elapsed=time.perf_counter_ns()-t
        samples.append({**{k:entry[k] for k in ('sample_id','candidate_id','format','origin_group_id','input_sha256','original_size')},
                        'feature_elapsed_ns':elapsed,**features})
        for item in training['models']:
            model=models[(item['scenario_id'],item['kind'])]; t=time.perf_counter_ns();choice=str(model.predict(frame)[0]);prediction_ns=time.perf_counter_ns()-t
            values=model.predict_proba(frame)[0];probs={str(a):float(v) for a,v in zip(model.classes_,values,strict=True)}
            predictions.append({'sample_id':entry['sample_id'],'scenario_id':item['scenario_id'],'model':item['kind'],
                                'predicted_algorithm':choice,'uncalibrated_confidence':max(probs.values()),
                                'prediction_elapsed_ns':prediction_ns,'model_sha256':item['sha256'],
                                **{'probability_'+a:probs.get(a,0.) for a in ALGORITHMS}})
    write_csv(directory/'samples.csv',samples);write_csv(directory/'frozen_predictions.csv',predictions)
    finish('predictions',directory,{'started_at_utc':started,'sample_count':len(samples),'prediction_count':len(predictions),
                                  'training_sha256':sha(OUT/'training.json'),'before_benchmark':True})


def benchmark():
    context(); phase('predictions'); directory=new_directory('benchmark');started=now();root,entries=corpus()
    index,measurements,repeats=[] ,[],[]
    for number,entry in enumerate(entries):
        path,_=source_bytes(root,entry);folder=directory/f'{number:02d}'
        report=compare_file(path,folder)
        require(report['input_sha256']==entry['input_sha256'],'Compare input mismatch')
        index.append({'sample_id':entry['sample_id'],'candidate_id':entry['candidate_id'],'directory':folder.relative_to(OUT).as_posix(),
                      'status':report['status'],'comparison_sha256':sha(folder/'comparison.json')})
        for r in report['measurements']: measurements.append({**r,'sample_id':entry['sample_id']})
        for r in read_csv(folder/'timing_repeats.csv'): repeats.append({**r,'sample_id':entry['sample_id']})
        if number%5==0: print(json.dumps({'benchmarked_files':number+1,'total':len(entries)}),flush=True)
    write_csv(directory/'index.csv',index);write_csv(directory/'compression_results.csv',measurements);write_csv(directory/'timing_repeats.csv',repeats)
    require(all(r['status']=='completed' for r in index),'One or more Compare jobs failed; retained partial results')
    finish('benchmark',directory,{'started_at_utc':started,'sample_count':len(entries),'measurement_count':len(measurements),'raw_repeat_count':len(repeats),
                                'predictions_sha256':sha(OUT/'predictions.json')})


def execute_pipeline(source,directory,expected_hash,*,model=None,expected_algorithm=None):
    """Research package engine: predict before one compression; exact restoration."""
    directory.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter_ns();data=source.read_bytes();original_hash=digest(data)
    require(original_hash==expected_hash and bool(data),'Pipeline input hash mismatch/empty')
    feature_ns=prediction_ns=0
    if model is None: algorithm='zstd'
    else:
        t=time.perf_counter_ns();frame=feature_frame(extract_features(data));feature_ns=time.perf_counter_ns()-t
        t=time.perf_counter_ns();algorithm=str(model.predict(frame)[0]);prediction_ns=time.perf_counter_ns()-t
    require(algorithm in ALGORITHMS,'Unsupported model output')
    require(expected_algorithm is None or algorithm==expected_algorithm,'Prediction drift from frozen phase')
    payload=compress_data(data,algorithm)
    require(decompress_data(payload,algorithm)==data,'Compression-side restoration failed')
    manifest={'research_package_version':1,'algorithm':algorithm,'original_name':source.name,'original_size':len(data),
              'input_sha256':original_hash,'payload_sha256':digest(payload)}
    with (directory/'payload.bin').open('xb') as stream:stream.write(payload)
    encoded=json.dumps(manifest,ensure_ascii=False,sort_keys=True).encode('utf-8')
    with (directory/'manifest.json').open('xb') as stream:stream.write(encoded)
    compression_ns=time.perf_counter_ns()-started
    started=time.perf_counter_ns();saved=json.loads((directory/'manifest.json').read_bytes());compressed=(directory/'payload.bin').read_bytes()
    require(digest(compressed)==saved['payload_sha256'],'Payload verification failed')
    restored=decompress_data(compressed,saved['algorithm'])
    require(len(restored)==saved['original_size'] and digest(restored)==saved['input_sha256'],'Restoration verification failed')
    require(Path(saved['original_name']).name==saved['original_name'],'Unsafe restoration name')
    restored_dir=directory/'restored';restored_dir.mkdir()
    restored_path=restored_dir/saved['original_name']
    with restored_path.open('xb') as stream:stream.write(restored)
    restoration_ns=time.perf_counter_ns()-started
    require(restored==data and restored_path.read_bytes()==data,'Saved restoration differs from source')
    require(compression_ns>0 and restoration_ns>0,'Nonpositive pipeline time')
    return {'algorithm':algorithm,'compression_ns':compression_ns,'restoration_ns':restoration_ns,
            'feature_ns':feature_ns,'prediction_ns':prediction_ns,'package_bytes':len(payload)+len(encoded),
            'directory':directory.relative_to(ROOT).as_posix(),'payload_sha256':digest(payload),'manifest_sha256':digest(encoded),
            'restored_relative_path':restored_path.relative_to(ROOT).as_posix(),'restored_sha256':digest(restored),'verified':True}


def pipeline():
    _,plan,_,config=context();training=phase('training');phase('predictions');phase('benchmark')
    directory=new_directory('pipeline');trial_root=ROOT/plan['e2e_artifact_root'];require(not trial_root.exists(),'Existing pipeline artifact root')
    trial_root.mkdir(parents=True);started=now();root,entries=corpus();loads=[];models={}
    for item in training['models']:
        for repeat in range(5):
            t=time.perf_counter_ns();model=load_model(item,training,config);elapsed=time.perf_counter_ns()-t
            loads.append({'scenario_id':item['scenario_id'],'model':item['kind'],'repeat_index':repeat+1,'elapsed_ns':elapsed})
        models[(item['scenario_id'],item['kind'])]=model
    frozen={(r['sample_id'],r['scenario_id'],r['model']):r['predicted_algorithm'] for r in read_csv(OUT/'predictions/frozen_predictions.csv')}
    strategies=[('fixed_zstd',None,None)]+[(i['scenario_id']+'__'+i['kind'],i['scenario_id'],i['kind']) for i in training['models']]
    raw=[]
    for index,entry in enumerate(entries):
        path,_=source_bytes(root,entry)
        for model_index,(name,sid,kind) in enumerate(strategies):
            for repeat in range(5):
                result=execute_pipeline(path,trial_root/f'{index:02d}'/f'{model_index:02d}'/str(repeat+1),entry['input_sha256'],
                        model=models[(sid,kind)] if sid else None,expected_algorithm=frozen[(entry['sample_id'],sid,kind)] if sid else 'zstd')
                raw.append({'sample_id':entry['sample_id'],'strategy':name,'repeat_index':repeat+1,**result})
        if index%5==0: print(json.dumps({'pipeline_files':index+1,'total':len(entries),'trials':len(raw)}),flush=True)
    write_csv(directory/'raw_trials.csv',raw);write_csv(directory/'model_load_repeats.csv',loads)
    finish('pipeline',directory,{'started_at_utc':started,'sample_count':len(entries),'trial_count':len(raw),'strategy_count':len(strategies),
                                'model_load_repeat_count':len(loads),'artifact_root':plan['e2e_artifact_root']})


def summarize_choices(rows):
    groups=defaultdict(list)
    for r in rows:groups[r['origin_group_id']].append(r)
    count=len(rows); require(count>0,'Empty comparison')
    base=math.fsum(r['zstd_cost'] for r in rows); total=math.fsum(r['policy_cost'] for r in rows)
    return {'sample_count':count,**classification([r['true_algorithm'] for r in rows],[r['chosen_algorithm'] for r in rows]),
            'selected_counts':dict(Counter(r['chosen_algorithm'] for r in rows)),
            'policy_cost_sum':total,'fixed_zstd_cost_sum':base,'cost_saving_pct_vs_zstd':100*(base-total)/base,
            'mean_regret':statistics.fmean(r['regret'] for r in rows),'max_regret':max(r['regret'] for r in rows),
            'primary_group_mean_difference_vs_majority':statistics.fmean(statistics.fmean(r['difference_vs_majority'] for r in g) for g in groups.values()),
            'mean_compressed_size':statistics.fmean(r['compressed_size'] for r in rows),
            'mean_compression_time_ms':statistics.fmean(r['compression_time_ms'] for r in rows),
            'mean_decompression_time_ms':statistics.fmean(r['decompression_time_ms'] for r in rows)}


def aggregate_trials(raw):
    groups=defaultdict(list)
    for r in raw:groups[(r['sample_id'],r['strategy'])].append(r)
    result={}
    for key,rows in groups.items():
        require(len(rows)==5 and sorted(int(r['repeat_index']) for r in rows)==list(range(1,6)),'Incomplete pipeline repeats')
        require(all(int(r[k])>0 for r in rows for k in ('compression_ns','restoration_ns')),'Nonpositive pipeline duration')
        require(all(int(r[k])>=0 for r in rows for k in ('feature_ns','prediction_ns')),'Negative overhead duration')
        require(len({r['algorithm'] for r in rows})==len({int(r['package_bytes']) for r in rows})==len({r['payload_sha256'] for r in rows})==1,'Pipeline output inconsistent')
        require(all(r['verified'] is True or r['verified']=='True' for r in rows),'Unverified pipeline trial')
        result[key]={'algorithm':rows[0]['algorithm'],'package_bytes':int(rows[0]['package_bytes']),
                     **{k:statistics.median(int(r[k]) for r in rows)/1e6 for k in ('compression_ns','restoration_ns','feature_ns','prediction_ns')}}
    return result


def evaluate():
    _,_,frozen,_=context();training=phase('training');phase('predictions');phase('benchmark');phase('pipeline')
    directory=new_directory('evaluation');started=now();_,entries=corpus();entry_map={r['sample_id']:r for r in entries}
    grouped=defaultdict(dict)
    for r in read_csv(OUT/'benchmark/compression_results.csv'):grouped[r['sample_id']][r['algorithm']]=r
    predicted={(r['sample_id'],r['scenario_id'],r['model']):r['predicted_algorithm'] for r in read_csv(OUT/'predictions/frozen_predictions.csv')}
    choices=[];metrics={};deadline_rows=[]
    for scenario in frozen['expanded_cost_scenarios']:
        sid=scenario['id'];by_strategy=defaultdict(list)
        for sample_id,entry in entry_map.items():
            result=evaluate_lifetime_cost(grouped[sample_id].values(),policy=LifetimePolicy(**scenario['policy']));require(result['status']=='selected','Incomplete objective')
            majority=training['majorities'][sid]['algorithm'];values=result['values'];truth=result['selected_algorithm']
            strategies={a:a for a in ALGORITHMS};strategies.update(train_majority=majority,oracle=truth,
                **{kind:predicted[(sample_id,sid,kind)] for kind in KINDS})
            for strategy,chosen in strategies.items():
                r=grouped[sample_id][chosen]
                row={'sample_id':sample_id,'scenario_id':sid,'strategy':strategy,'format':entry['format'],'origin_group_id':entry['origin_group_id'],
                     'true_algorithm':truth,'chosen_algorithm':chosen,'policy_cost':values[chosen],'oracle_cost':result['selection_value'],
                     'zstd_cost':values['zstd'],'majority_cost':values[majority],'regret':values[chosen]-result['selection_value'],
                     'difference_vs_majority':values[chosen]-values[majority],'compressed_size':int(r['compressed_size']),
                     'compression_time_ms':float(r['compression_time_ms']),'decompression_time_ms':float(r['decompression_time_ms'])}
                choices.append(row);by_strategy[strategy].append(row)
        metrics[sid]={name:summarize_choices(rows) for name,rows in by_strategy.items()}
    for scenario in frozen['expanded_deadline_scenarios']:
        for sample_id in entry_map:
            result=select_under_deadlines(grouped[sample_id].values(),compression_limit_ms=scenario['compression_limit_ms'],decompression_limit_ms=scenario['decompression_limit_ms'])
            deadline_rows.append({'sample_id':sample_id,'scenario_id':scenario['id'],'status':result['status'],'selected_algorithm':result['selected_algorithm'],
                                  'feasible_algorithms':'|'.join(result['feasible_algorithms']),'violations_json':json.dumps(result['violations'],sort_keys=True)})
    trials=aggregate_trials(read_csv(OUT/'pipeline/raw_trials.csv'));load_groups=defaultdict(list)
    for r in read_csv(OUT/'pipeline/model_load_repeats.csv'):load_groups[(r['scenario_id'],r['model'])].append(int(r['elapsed_ns'])/1e6)
    e2e=[]
    for scenario in frozen['expanded_cost_scenarios']:
        sid=scenario['id'];p={k:float(v) for k,v in scenario['policy'].items()}
        def cost(v):return math.fsum((p['storage_cost_per_byte_day']*p['retention_days']*v['package_bytes'],p['compression_cost_per_ms']*v['compression_ns'],p['decompression_cost_per_ms']*p['expected_restorations']*v['restoration_ns']))
        base=math.fsum(cost(trials[(sample_id,'fixed_zstd')]) for sample_id in entry_map)
        for kind in KINDS:
            records=[trials[(sample_id,sid+'__'+kind)] for sample_id in entry_map]
            total=math.fsum(cost(r) for r in records);load=statistics.median(load_groups[(sid,kind)])
            e2e.append({'scenario_id':sid,'model':kind,'sample_count':len(records),'fixed_zstd_pipeline_cost_sum':base,
                        'model_pipeline_cost_sum':total,'warm_pipeline_cost_saving_pct':100*(base-total)/base,
                        'mean_feature_ms':statistics.fmean(r['feature_ns'] for r in records),
                        'mean_prediction_ms':statistics.fmean(r['prediction_ns'] for r in records),
                        'median_verified_model_load_ms':load,
                        'load_inclusive_cost_proxy_sum':total+p['compression_cost_per_ms']*load*len(records)})
    write_csv(directory/'strategy_choices.csv',choices);write_json(directory/'codec_metrics.json',metrics)
    write_csv(directory/'pipeline_metrics.csv',e2e);write_csv(directory/'deadline_diagnostics.csv',deadline_rows)
    # Preserve subgroup coverage and all per-file differences, rather than a favorable subset.
    coverage={'formats':dict(Counter(r['format'] for r in entries)),'origin_groups':dict(Counter(r['origin_group_id'] for r in entries))}
    write_json(directory/'coverage.json',coverage)
    finish('evaluation',directory,{'started_at_utc':started,'sample_count':len(entries),'choice_count':len(choices),'scenario_count':len(metrics),
                                  'pipeline_comparison_count':len(e2e),'primary_definition':'equal-origin-group mean model-minus-training-majority policy cost difference'})


def audit():
    lock,_,frozen,config=context();training=phase('training');predmeta=phase('predictions');benchmeta=phase('benchmark');phase('pipeline');phase('evaluation')
    require(predmeta['completed_at_utc']<benchmeta['started_at_utc'],'Predictions not frozen before benchmark')
    root,entries=corpus();index=read_csv(OUT/'benchmark/index.csv');require(len(index)==len(entries),'Compare coverage mismatch')
    entry_map={r['sample_id']:r for r in entries};raw_repeats=0
    for r in index:
        directory=OUT/r['directory'];report=json.loads((directory/'comparison.json').read_bytes());entry=entry_map[r['sample_id']]
        require(report['status']=='completed' and report['input_sha256']==entry['input_sha256'],'Invalid Compare report')
        repeats=read_csv(directory/'timing_repeats.csv');require(len(repeats)==40,'Raw codec slots missing')
        for measurement in report['measurements']:
            a=measurement['algorithm']
            for phase_name,metric in (('compress','compression_time_ms'),('decompress','decompression_time_ms')):
                rows=[v for v in repeats if v['algorithm']==a and v['phase']==phase_name]
                require(len(rows)==5 and all(v['status']=='ok' and int(v['elapsed_ns'])>0 for v in rows),'Codec phase failed')
                require(statistics.median(int(v['elapsed_ns']) for v in rows)/1e6==measurement[metric],'Codec median mismatch')
                if phase_name=='decompress':require(all(v['verified']=='True' and v['output_sha256']==entry['input_sha256'] for v in rows),'Raw restoration mismatch')
        raw_repeats+=len(repeats)
    features={r['sample_id']:r for r in read_csv(OUT/'predictions/samples.csv')}
    predictions=read_csv(OUT/'predictions/frozen_predictions.csv');require(len(predictions)==len(entries)*len(training['models']),'Prediction slots missing')
    models={(i['scenario_id'],i['kind']):load_model(i,training,config) for i in training['models']}
    for r in predictions:
        frame=feature_frame({n:features[r['sample_id']][n] for n in FEATURE_NAMES})
        require(str(models[(r['scenario_id'],r['model'])].predict(frame)[0])==r['predicted_algorithm'],'Frozen prediction differs')
    trials=read_csv(OUT/'pipeline/raw_trials.csv');require(len(trials)==len(entries)*(len(training['models'])+1)*5,'Pipeline slots missing')
    aggregate_trials(trials)
    for number,r in enumerate(trials):
        path=ROOT/r['directory'];manifest=json.loads((path/'manifest.json').read_bytes());entry=entry_map[r['sample_id']]
        require(sha(path/'payload.bin')==r['payload_sha256']==manifest['payload_sha256'],'Stored trial payload changed')
        require(sha(path/'manifest.json')==r['manifest_sha256'] and manifest['algorithm']==r['algorithm'],'Stored trial manifest changed')
        restored=(ROOT/r['restored_relative_path']).read_bytes()
        require(digest(restored)==r['restored_sha256']==entry['input_sha256'] and len(restored)==entry['original_size'],'Stored trial restoration mismatch')
        require((path/'payload.bin').stat().st_size+(path/'manifest.json').stat().st_size==int(r['package_bytes']),'Pipeline byte count mismatch')
        if number%1000==0:print(json.dumps({'audited_pipeline_trials':number}),flush=True)
    choices=read_csv(OUT/'evaluation/strategy_choices.csv');require(len(choices)==len(entries)*len(frozen['expanded_cost_scenarios'])*8,'Strategy coverage mismatch')
    require(len({(r['sample_id'],r['scenario_id'],r['strategy']) for r in choices})==len(choices),'Duplicate strategy slot')
    grouped=defaultdict(dict)
    for r in read_csv(OUT/'benchmark/compression_results.csv'):grouped[r['sample_id']][r['algorithm']]=r
    definitions={s['id']:s for s in frozen['expanded_cost_scenarios']}
    for r in choices:
        values=evaluate_lifetime_cost(grouped[r['sample_id']].values(),policy=LifetimePolicy(**definitions[r['scenario_id']]['policy']))
        require(values['selected_algorithm']==r['true_algorithm'] and values['values'][r['chosen_algorithm']]==float(r['policy_cost']),'Candidate cost/target mismatch')
        require(float(r['oracle_cost'])==values['selection_value'] and float(r['regret'])==float(r['policy_cost'])-float(r['oracle_cost']),'Regret mismatch')
    check_hashes(lock['protected_after_sha256'])
    write_json(OUT/'audit.json',{'status':'study_artifacts_and_raw_measurements_verified','created_at_utc':now(),
        'criteria_lock_sha256':LOCK_SHA,'source_sha256':runtime_sources(),'protected_file_count':len(lock['protected_after_sha256']),
        'phase_sha256':{n:sha(OUT/(n+'.json')) for n in ('training','predictions','benchmark','pipeline','evaluation')},
        'model_count':len(training['models']),'sample_count':len(entries),'prediction_count':len(predictions),
        'codec_repeat_count':raw_repeats,'pipeline_trial_count':len(trials),'strategy_choice_count':len(choices),
        'scope':'Saved source/model/prediction/raw-median/artifact verification; not a causal or population-performance certification.'})
    print((OUT/'audit.json').read_text(encoding='utf-8'))


def report():
    context();audit_data=json.loads((OUT/'audit.json').read_bytes())
    for name,value in audit_data['phase_sha256'].items():require(sha(OUT/(name+'.json'))==value,'Audited phase changed')
    metrics=json.loads((OUT/'evaluation/codec_metrics.json').read_bytes());pipelines=read_csv(OUT/'evaluation/pipeline_metrics.csv')
    doc=ROOT/'research_log/usage_model_study_results_20261031.md';require(not doc.exists(),'Existing report')
    lines=['# 후보 모델 학습·실제 파일 검증 결과 — 2026-10-31','',
           '**범위: 고정된 가상 총비용 정책의 후보 실험. 공식 점수·모델 전환이 아니다. 모든 결과를 보존한다.**','',
           '[실행 전 기준](usage_model_study_design_20261031.md) · [계획](usage_model_study_plan_20261031.json) · '
           '[코드](run_usage_model_study_20261031.py) · [원시/저장 검증](../data/results/usage_candidate_study_20261031_01/audit.json)','',
           '## 완료 범위','',
           f'후보 모델 {audit_data["model_count"]}개, 실제 파일 {audit_data["sample_count"]}개, 사전 예측 {audit_data["prediction_count"]}개를 보존했다. '
           '기존 train 부분만 학습하고 원래 test는 개발 진단으로 구분했다. 원본/권리·notice·기존 재생성 hash 겹침 근거를 동결한 자료 전체를 사용했다. '
           'Generic manifest의 evaluation_ready=false와 독립성/익명성 미인증·과거 합성 원본 hash 미저장 한계를 유지한다.','',
           f'실제 파일의 특징/모델 예측을 네 압축기 benchmark 전에 동결했다. Codec 반복 {audit_data["codec_repeat_count"]:,}개와 '
           f'검증용 package 엔진 trial {audit_data["pipeline_trial_count"]:,}개 모두 원시 기록/저장 복원 검증을 확인했다. '
           f'기존 보호 파일 {audit_data["protected_file_count"]}개는 그대로다. Memory는 측정/점수 편입하지 않았다.','',
           '## 순수 codec 측정값에서 후보 모델 비교','',
           '| 가상 시나리오 | 모델 | Accuracy | Macro F1 | zstd 대비 총비용 절감 | 그룹 평균 차이 vs train-majority ↓ |',
           '|---|---|---:|---:|---:|---:|']
    for scenario,items in metrics.items():
        for kind in KINDS:
            r=items[kind];lines.append(f'| {scenario} | {kind} | {r["accuracy"]:.4f} | {r["macro_f1"]:.4f} | {r["cost_saving_pct_vs_zstd"]:.4f}% | {r["primary_group_mean_difference_vs_majority"]:.8f} |')
    lines += ['', '양의 그룹 평균 차이는 train-majority보다 손실이 큼을 뜻한다. 음수 절감률은 zstd보다 정책 비용이 증가한 것이다. '
              '모든 고정 압축기·train-majority·모델·oracle의 혼동행렬/선택 수·크기·시간·비용/평균·최대 regret는 '
              '[전체 지표](../data/results/usage_candidate_study_20261031_01/evaluation/codec_metrics.json)와 '
              '[파일별 선택](../data/results/usage_candidate_study_20261031_01/evaluation/strategy_choices.csv)에 있다. '
              '네 클래스 고정 Macro F1이며 미등장 클래스도 제외하지 않는다. 확률 출력은 보정된 정답 확률이 아니다.','',
              '## 특징·예측·검증·저장을 포함한 검증용 엔진','',
              '| 가상 시나리오 | 모델 | 상주 모델 총비용 절감 vs 고정 zstd | 평균 특징 ms | 평균 예측 ms | 모델 load 중앙값 ms |',
              '|---|---|---:|---:|---:|---:|']
    for r in pipelines:
        lines.append(f'| {r["scenario_id"]} | {r["model"]} | {float(r["warm_pipeline_cost_saving_pct"]):.4f}% | {float(r["mean_feature_ms"]):.4f} | '
                     f'{float(r["mean_prediction_ms"]):.4f} | {float(r["median_verified_model_load_ms"]):.4f} |')
    lines += ['', '파일 읽기→hash→특징→예측→선택한 압축기 하나→복원/byte 검증→research payload/manifest 저장과, '
              '다시 읽기→해제→크기/hash 검증→원래 이름으로 복원 저장을 각각 실측했다. Package bytes와 각 phase 중앙값을 정책 비용에 넣었다. '
              '음수 절감은 이 범위에서 전체 경로가 고정 zstd보다 불리하다는 결과다. '
              '모델 로딩은 별도 실측이며 상주 모델 경로 밖이다. 로딩을 추가한 비용 proxy도 '
              '[전체 경로 지표](../data/results/usage_candidate_study_20261031_01/evaluation/pipeline_metrics.csv)에 구분했다. '
              'Python 시작/cold cache·fsync·실제 GUI/CLI 배포·모델 배포 공간·네트워크·CPU/전력/메모리 비용은 검증하지 않았다.','',
              '## 해석 한계와 보존','',
              '시나리오의 보관 기간·복원 횟수·정책점수 교환비는 사전 선언한 가정이며 실제 사용량/요금이 아니다. '
              '고정 알고리즘/phase 순서와 OS cache가 있으며, 저장 중앙값을 꼬리/실시간 지연 보장으로 해석하지 않는다. '
              '비확률 형식 quota·알려진 원본 관계가 있는 단일 외부 corpus의 기술적 비교로 제한한다. '
              '통계적 유의성이나 전체 실제 파일 모집단의 개선을 주장하지 않고, 유리한 시나리오/모델만 선택하지 않는다.','',
              '기존 공식 score·라벨·모델/config와 memory 참고 방침을 유지했다. 새 자료를 학습/튜닝·class balancing·calibration에 쓰지 않았다. '
              'GUI 수동 Compare 저장 검증/전체 시각 QA는 이 연구용 엔진 검증과 별개의 미완료 항목이다.','']
    with doc.open('x',encoding='utf-8',newline='\n') as stream:stream.write('\n'.join(lines))
    write_json(OUT/'report_manifest.json',{'report_sha256':sha(doc),'audit_sha256':sha(OUT/'audit.json'),'runtime_source_sha256':runtime_sources()})
    print(str(doc))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('train','predict','benchmark','pipeline','evaluate','audit','report'))
    args=parser.parse_args()
    try:globals()[args.action]()
    except Exception as exc:
        marker=OUT/(args.action+'_failed.json')
        if not marker.exists():write_json(marker,{'status':'failed','created_at_utc':now(),'error':repr(exc),'source_sha256':runtime_sources()})
        raise
