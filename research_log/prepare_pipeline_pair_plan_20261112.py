"""Freeze a future research-engine triplet schedule; never read corpus bytes/load models."""
import csv
import itertools
import json
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r
from research_log import run_feature_pairs_20261111 as previous

PLAN = ROOT/'research_log/pipeline_pair_plan_20261112.json'
DESIGN = ROOT/'research_log/pipeline_pair_design_20261112.md'


def table(path, rows):
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    plan = json.loads(PLAN.read_bytes())
    out = ROOT/plan['freeze_root']
    r.require(not any((ROOT/plan[k]).exists() for k in ('freeze_root','future_result_root','future_artifact_root')), 'Existing output')
    ctx, _, _ = previous.context()  # hashes and runtime only; no corpus/model execution
    lock = json.loads(previous.LOCK.read_bytes())
    protected = {**lock['protected_input_sha256'], **lock['source_sha256']}
    for path in [previous.LOCK, *sorted((ROOT/plan['prior_run']).iterdir()),
                 *sorted((ROOT/plan['prior_analysis']).parent.iterdir())]:
        if path.is_file(): protected[path.relative_to(ROOT).as_posix()] = r.sha(path)
    analysis = json.loads((ROOT/plan['prior_analysis']).read_bytes())
    r.require(analysis['status'] == 'independently_verified', 'Prior analysis incomplete')
    r.require(analysis['source_sha256'] == r.sha(ROOT/'research_log/analyze_feature_pairs_20261112.py'), 'Prior analyzer changed')
    for name, digest in analysis['input_sha256'].items():
        r.require(r.sha(ROOT/plan['prior_run']/name) == digest, 'Prior raw evidence differs')
    for name, digest in analysis['artifact_sha256'].items():
        r.require(r.sha((ROOT/plan['prior_analysis']).parent/name) == digest, 'Prior derived evidence differs')
    primary = [v for v in analysis['summaries'] if v['candidate'] == 'both_numpy' and v['mode'] == 'extract_and_frame']
    r.require(len(primary) == 1 and primary[0]['advance_to_pipeline'] is True, 'Primary advance gate failed')
    r.require(primary[0]['equal_origin_mean_paired_delta_ns'] < 0 and primary[0]['pooled_median_ratio'] > 1, 'Advance arithmetic')
    entries = sorted(ctx['inventory'], key=lambda v:(v['origin_group_id'],v['sample_id']))
    models = ctx['training']['models']
    scenarios = json.loads((ROOT/plan['scenario_freeze']).read_bytes())['expanded_cost_scenarios']
    r.require(len(scenarios) == 9 and len(models) == 18, 'Entire existing model/policy grid required')
    r.require({(v['scenario_id'],v['kind']) for v in models} == {(v['id'],k) for v in scenarios for k in ('decision_tree','random_forest')}, 'Model scenario coverage')
    permutations = list(itertools.permutations(plan['arms_in_order']))
    schedule = []
    base_index = {v['sample_id']:i for i,v in enumerate(entries)}
    for w, model in enumerate(models):
        for round_index in range(7):
            shuffled = list(entries)
            random.Random(plan['schedule']['seed']+1000*w+round_index).shuffle(shuffled)
            for position, entry in enumerate(shuffled,1):
                permutation = (base_index[entry['sample_id']]+w+max(0,round_index-1))%len(permutations)
                schedule.append(dict(worker_index=w,scenario_id=model['scenario_id'],model=model['kind'],
                                     round_index=round_index,is_warmup=round_index==0,order_in_round=position,
                                     sample_id=entry['sample_id'],permutation_index=permutation,
                                     **dict(zip(('first','second','third'),permutations[permutation],strict=True))))
    history = r.read_csv(ROOT/plan['reference_study']/'pipeline/raw_trials.csv')
    sizes = {}
    for row in history:
        key = (row['sample_id'],row['strategy'])
        r.require(row['verified'] == 'True', 'Invalid historical resource input')
        size = int(row['package_bytes'])
        r.require(size > 0 and (key not in sizes or sizes[key] == size), 'Historical package size varies')
        sizes[key] = size
    originals = {v['sample_id']:int(v['original_size']) for v in entries}
    estimated_bytes = sum(originals[v['sample_id']]+sizes[(v['sample_id'],
                          'fixed_zstd' if arm == 'fixed_zstd' else v['scenario_id']+'__'+v['model'])]
                          for v in schedule for arm in plan['arms_in_order'])
    copies = ['research_log/run_usage_model_study_20261031.py','src/compressors.py','src/feature_extractor.py',
              'src/usage_objectives.py','config/experiment_config.json','research_log/feature_pair_candidates_20261111.py',
              'research_log/feature_profile_runtime_20261111.py']
    for name in copies+['research_log/analyze_feature_pairs_20261112.py','research_log/feature_pair_analysis_validation_20261112.json']:
        protected[name] = r.sha(ROOT/name)
    for name, digest in protected.items(): r.require(r.sha(ROOT/name)==digest, 'Changed protected input: '+name)
    out.mkdir(parents=True,exist_ok=False)
    for name in copies:
        destination = out/'reference'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes((ROOT/name).read_bytes())
    (out/'reference/feature_frame.py').write_bytes((r.FREEZE/'reference/feature_frame.py').read_bytes())
    for name in ('expected_features.csv','expected_predictions.csv','model_inventory.csv','input_root.json'):
        (out/name).write_bytes((r.FREEZE/name).read_bytes())
    r.write_json(out/'plan.json',plan)
    r.write_json(out/'policies.json',scenarios)
    r.write_json(out/'models.json',models)
    table(out/'input_inventory.csv',entries)
    table(out/'triplet_schedule.csv',schedule)
    measured = sum(not v['is_warmup'] for v in schedule)
    coverage = dict(files=len(entries),origins=len({v['origin_group_id'] for v in entries}),conditions=len(models),
                    policies=len(scenarios),permutations=len(permutations),planned_measured_triplets=measured,
                    planned_measured_trials=measured*len(plan['arms_in_order']),planned_warmup_triplets=len(schedule)-measured,
                    planned_warmup_trials=(len(schedule)-measured)*len(plan['arms_in_order']),
                    planned_prediction_checks_per_model_arm=len(ctx['expected'])*len(models))
    r.write_json(out/'coverage.json',coverage)
    r.write_json(out/'resource_estimate.json',dict(estimated_payload_manifest_restored_bytes=estimated_bytes,
                 minimum_free_disk_bytes=2*estimated_bytes+1024**3,free_disk_bytes_at_plan=shutil.disk_usage(ROOT).free,
                 source_raw_sha256=r.sha(ROOT/plan['reference_study']/'pipeline/raw_trials.csv'),
                 scope='Computed from existing file lengths and package sizes, not new output measurements; excludes filesystem/record overhead. Recheck actual free space before execution.'))
    for name, digest in protected.items(): r.require(r.sha(ROOT/name)==digest, 'Changed input during preparation')
    r.write_json(out/'freeze.json',dict(status='pipeline_plan_frozen_before_engine_implementation',at_utc=r.now(),
                 git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 plan_sha256=r.sha(PLAN),design_sha256=r.sha(DESIGN),preparer_sha256=r.sha(Path(__file__)),
                 python=sys.version,platform=platform.platform(),packages=ctx['frozen']['packages'],
                 corpus_bytes_read=False,model_execution=False,engine_implemented=False,measurement_executed=False,
                 protected_input_sha256=protected,coverage=coverage,
                 artifact_sha256={p.relative_to(out).as_posix():r.sha(p) for p in out.rglob('*') if p.is_file()}))
    print(json.dumps(dict(status='pipeline_plan_frozen',coverage=coverage,estimated_bytes=estimated_bytes,protected_files=len(protected))))


if __name__ == '__main__': main()
