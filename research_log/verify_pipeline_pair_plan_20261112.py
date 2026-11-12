"""Independent hash, full-grid, six-order and resource-formula plan verification."""
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
from pathlib import Path
import random
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT/'research_log/pipeline_pair_plan_20261112.json'


def require(value, message):
    if not value: raise ValueError(message)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding='utf-8',newline='') as stream: return list(csv.DictReader(stream))


def main():
    plan = json.loads(PLAN.read_bytes())
    out = ROOT/plan['freeze_root']
    target = out/'verification.json'
    require(not target.exists(),'Refuse overwrite')
    freeze = json.loads((out/'freeze.json').read_bytes())
    require(freeze['status']=='pipeline_plan_frozen_before_engine_implementation','Wrong freeze state')
    require(freeze['plan_sha256']==sha(PLAN) and json.loads((out/'plan.json').read_bytes())==plan,'Plan differs')
    design = ROOT/'research_log/pipeline_pair_design_20261112.md'
    require(sha(design)==freeze['design_sha256'],'Design differs')
    require(sha(ROOT/'research_log/prepare_pipeline_pair_plan_20261112.py')==freeze['preparer_sha256'],'Preparer differs')
    for name,digest in freeze['protected_input_sha256'].items(): require(sha(ROOT/name)==digest,'Protected input differs: '+name)
    for name,digest in freeze['artifact_sha256'].items(): require(sha(out/name)==digest,'Frozen artifact differs')
    require({p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}==set(freeze['artifact_sha256'])|{'freeze.json'},'Artifact set differs')
    entries = read(out/'input_inventory.csv')
    original = read(ROOT/'data/results/feature_profile_plan_20261109_01/input_inventory.csv')
    require(entries==sorted(original,key=lambda v:(v['origin_group_id'],v['sample_id'])),'Corpus changed')
    models = json.loads((out/'models.json').read_bytes())
    training = json.loads((ROOT/plan['reference_study']/'training.json').read_bytes())
    require(models==training['models'],'Models/order changed')
    policies = json.loads((out/'policies.json').read_bytes())
    require(policies==json.loads((ROOT/plan['scenario_freeze']).read_bytes())['expanded_cost_scenarios'],'Policy changed')
    require({(v['scenario_id'],v['kind']) for v in models}=={(v['id'],k) for v in policies for k in ('decision_tree','random_forest')},'Incomplete model grid')
    arms = plan['arms_in_order']
    require(arms==['reference','both_numpy','fixed_zstd'],'Arm scope changed')
    permutations = list(itertools.permutations(arms))
    rows = read(out/'triplet_schedule.csv')
    keys = [(v['worker_index'],v['round_index'],v['sample_id']) for v in rows]
    require(len(keys)==len(set(keys))==len(models)*7*len(entries),'Duplicate/missing triplets')
    reconstructed = []
    positions = defaultdict(Counter)
    precedences = defaultdict(Counter)
    per_file_orders = defaultdict(Counter)
    for worker,model in enumerate(models):
        for round_index in range(7):
            block = [v for v in rows if v['worker_index']==str(worker) and v['round_index']==str(round_index)]
            shuffled = list(entries)
            random.Random(plan['schedule']['seed']+1000*worker+round_index).shuffle(shuffled)
            require([v['sample_id'] for v in block]==[e['sample_id'] for e in shuffled],'Shuffle differs')
            require([int(v['order_in_round']) for v in block]==list(range(1,len(entries)+1)),'Position differs')
            require(Counter(v['permutation_index'] for v in block)==Counter({str(i):len(entries)//6 for i in range(6)}),'Round not balanced')
            for row in block:
                require(row['scenario_id']==model['scenario_id'] and row['model']==model['kind'],'Worker/model mismatch')
                require(row['is_warmup']==str(round_index==0),'Warmup mismatch')
                base = next(i for i,e in enumerate(entries) if e['sample_id']==row['sample_id'])
                wanted = (base+worker+(round_index-1 if round_index else 0))%6
                require(int(row['permutation_index'])==wanted,'Permutation index mismatch')
                order = tuple(row[k] for k in ('first','second','third'))
                require(order==permutations[wanted],'Arm order mismatch')
                if round_index:
                    key = (worker,row['sample_id'])
                    per_file_orders[key][order]+=1
                    for p,arm in enumerate(order): positions[(key,arm)][p]+=1
                    for first,second in itertools.combinations(order,2): precedences[key][(first,second)]+=1
            reconstructed.extend(block)
    require(rows==reconstructed,'Global schedule differs')
    require(len(per_file_orders)==len(models)*len(entries),'File/worker coverage')
    require(all(v==Counter({p:1 for p in permutations}) for v in per_file_orders.values()),'Not all six orders per file')
    require(all(v==Counter({0:2,1:2,2:2}) for v in positions.values()),'Position imbalance')
    require(all(v==Counter({(a,b):3 for a in arms for b in arms if a!=b}) for v in precedences.values()),'Precedence imbalance')
    history = read(ROOT/plan['reference_study']/'pipeline/raw_trials.csv')
    package_sizes = defaultdict(set)
    for row in history:
        require(row['verified']=='True','Invalid historical fixture for resource estimate')
        package_sizes[(row['sample_id'],row['strategy'])].add(int(row['package_bytes']))
    require(all(len(v)==1 for v in package_sizes.values()),'Historical size instability')
    lengths = {e['sample_id']:int(e['original_size']) for e in entries}
    estimate = 0
    for row in rows:
        for arm in arms:
            key=(row['sample_id'],'fixed_zstd' if arm=='fixed_zstd' else row['scenario_id']+'__'+row['model'])
            estimate+=lengths[row['sample_id']]+next(iter(package_sizes[key]))
    resource = json.loads((out/'resource_estimate.json').read_bytes())
    require(resource['estimated_payload_manifest_restored_bytes']==estimate and resource['minimum_free_disk_bytes']==2*estimate+1024**3,'Resource arithmetic mismatch')
    require(resource['source_raw_sha256']==sha(ROOT/plan['reference_study']/'pipeline/raw_trials.csv'),'Resource source changed')
    measured = sum(v['is_warmup']=='False' for v in rows)
    coverage = dict(files=len(entries),origins=len({e['origin_group_id'] for e in entries}),conditions=len(models),policies=len(policies),
                    permutations=len(permutations),planned_measured_triplets=measured,planned_measured_trials=measured*3,
                    planned_warmup_triplets=len(rows)-measured,planned_warmup_trials=(len(rows)-measured)*3,
                    planned_prediction_checks_per_model_arm=len(entries)*len(models))
    require(coverage==freeze['coverage']==json.loads((out/'coverage.json').read_bytes()),'Coverage arithmetic')
    require(plan['schedule']['warmup_triplets_per_file']==1 and plan['schedule']['measured_triplets_per_file']==6,'Repeat contract changed')
    for name in ('corpus_bytes_read','model_execution','engine_implemented','measurement_executed'): require(freeze[name] is False,'Unexpected execution claim')
    require(not any((ROOT/plan[k]).exists() for k in ('future_result_root','future_artifact_root')),'Future output already exists')
    links = [(design.parent/v).resolve() for v in re.findall(r'\]\(([^)]+)\)',design.read_text(encoding='utf-8'))]
    require(all(p==target.resolve() or p.is_file() for p in links),'Design link missing')
    value=dict(status='pipeline_plan_grid_schedule_and_preservation_verified',at_utc=datetime.now(timezone.utc).isoformat(),
               verifier_sha256=sha(Path(__file__)),freeze_sha256=sha(out/'freeze.json'),coverage=coverage,
               protected_files=len(freeze['protected_input_sha256']),resource_estimate_verified=True,
               corpus_bytes_read=False,model_execution=False,measurement_executed=False,
               checks=['Full original corpus and model/policy grid','All old/frozen artifact hashes',
                       'Exact seeded round/file/permutation order','Six orders per file','Two slots per position',
                       'Three precedences in each direction','Historical-only resource formula','No execution claims','Document links'])
    with target.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    require(all(p.is_file() for p in links),'Link missing after verification publication')
    print(json.dumps(value,ensure_ascii=False))


if __name__ == '__main__': main()
