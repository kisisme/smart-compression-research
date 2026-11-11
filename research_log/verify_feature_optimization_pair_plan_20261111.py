"""Independent plan/schedule balance audit; no candidate or model execution."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'research_log/feature_optimization_pair_plan_20261111.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    plan = json.loads(PLAN.read_bytes())
    out = ROOT / plan['freeze_root']
    target = out / 'verification.json'
    require(not target.exists(), 'Refuse to overwrite verification')
    frozen = json.loads((out / 'freeze.json').read_bytes())
    require(sha(PLAN) == frozen['plan_sha256'] and json.loads((out / 'plan.json').read_bytes()) == plan, 'Plan mismatch')
    design = ROOT / 'research_log/feature_optimization_pair_design_20261111.md'
    require(sha(design) == frozen['design_sha256'], 'Design changed')
    require(sha(ROOT / 'research_log/prepare_feature_optimization_pair_20261111.py') == frozen['preparation_source_sha256'], 'Preparation source changed')
    for name, digest in frozen['protected_input_sha256'].items():
        require(sha(ROOT / name) == digest, f'Protected input changed: {name}')
    for name, digest in frozen['artifact_sha256'].items():
        require(sha(out / name) == digest, f'Artifact changed: {name}')
    for value in frozen['reference_artifacts'].values():
        require(sha(ROOT / value['path']) == value['sha256'], 'Reference changed')
    require({p.name for p in out.iterdir() if p.is_file()} == set(frozen['artifact_sha256']) | {'freeze.json'}, 'Unexpected artifact set')
    original = read(ROOT / plan['reference_freeze'] / 'input_inventory.csv')
    inventory = read(out / 'input_inventory.csv')
    require(inventory == sorted(original, key=lambda e: (e['origin_group_id'], e['sample_id'])), 'Input list changed')
    rows = read(out / 'pair_schedule.csv')
    keys = [(r['comparison'], r['mode'], r['round_index'], r['sample_id']) for r in rows]
    comp = plan['comparison']
    candidates, modes = comp['comparisons_in_order'], comp['modes_in_order']
    require(len(rows) == len(set(keys)) == 2520, 'Pair coverage/duplicate')
    expected_keys = {(c, m, str(i), e['sample_id']) for c in candidates for m in modes for i in range(7) for e in inventory}
    require(set(keys) == expected_keys, 'Missing/extra pair')
    expected_global_order = []
    balanced = defaultdict(Counter)
    base_index = {e['sample_id']: i for i, e in enumerate(inventory)}
    for c, candidate in enumerate(candidates):
        for m, mode in enumerate(modes):
            for i in range(7):
                block = [r for r in rows if (r['comparison'], r['mode'], r['round_index']) == (candidate, mode, str(i))]
                ordered = list(inventory)
                random.Random(comp['schedule_seed']+10000*c+1000*m+i).shuffle(ordered)
                require([r['sample_id'] for r in block] == [e['sample_id'] for e in ordered], 'File shuffle differs')
                require([int(r['order_in_round']) for r in block] == list(range(1, 61)), 'Pair positions differ')
                require(Counter(r['first'] == 'reference' for r in block) == Counter({True: 30, False: 30}), 'Round first-position imbalance')
                for row in block:
                    require(row['is_warmup'] == str(i == 0), 'Warmup label differs')
                    require({row['first'], row['second']} == {'reference', candidate}, 'Pair variants differ')
                    want_ref_first = (base_index[row['sample_id']]+i+c+m) % 2 == 0
                    require((row['first'] == 'reference') == want_ref_first, 'Pair-order formula differs')
                    if i:
                        balanced[(candidate, mode, row['sample_id'])][row['first'] == 'reference'] += 1
                expected_global_order.extend(block)
    require(rows == expected_global_order, 'Worker/round order changed')
    require(all(v == Counter({True: 3, False: 3}) for v in balanced.values()) and len(balanced) == 360, 'File first-position imbalance')
    for key in ('candidate_implemented', 'candidate_feature_execution', 'model_prediction_execution', 'paired_measurement', 'fixture_tests_executed'):
        require(frozen[key] is False, f'Unexpected execution claim: {key}')
    require(not (ROOT / plan['future_result_root']).exists(), 'Paired experiment output already exists')
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', design.read_text(encoding='utf-8'))
    destinations = [(design.parent / link).resolve() for link in links]
    require(all(path == target.resolve() or path.is_file() for path in destinations), 'Broken design link')
    value = dict(status='paired_plan_and_balance_verified', created_at_utc=datetime.now(timezone.utc).isoformat(),
                 verifier_sha256=sha(Path(__file__)), freeze_sha256=sha(out / 'freeze.json'), coverage=frozen['coverage'],
                 protected_file_count=len(frozen['protected_input_sha256']), balanced_file_mode_comparisons=len(balanced),
                 development_note='Initial verification stopped before output because its own not-yet-created verification.json link was required to exist. Other links are checked first and the self link is checked after publication. Plan and schedule were unchanged.',
                 checks=['Source/reference/old-evidence hashes', 'Exact original input list', 'Complete pair key set',
                         'All seeded file orders', 'Every round 30/30 first position', 'Every file 3/3 measured first position',
                         'Explicit no-implementation/no-execution flags', 'Design links'])
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    require(all(path.is_file() for path in destinations), 'Broken link after verification publication')
    print(json.dumps(dict(status=value['status'], coverage=value['coverage'], protected_files=value['protected_file_count'])))


if __name__ == '__main__':
    main()
