"""Validate frozen planning artifacts only; never run features, models or timings."""
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'research_log/feature_profile_plan_20261109.json'


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
    out, study = ROOT / plan['freeze_root'], ROOT / plan['source_study']
    target = out / 'verification.json'
    require(not target.exists(), 'Refuse to overwrite plan verification')
    freeze = json.loads((out / 'freeze.json').read_bytes())
    require(sha(PLAN) == freeze['plan_sha256'] and json.loads((out / 'plan.json').read_bytes()) == plan, 'Plan mismatch')
    require(sha(ROOT / 'research_log/feature_profile_design_20261109.md') == freeze['design_sha256'], 'Design changed')
    require(sha(ROOT / 'research_log/prepare_feature_profile_20261109.py') == freeze['preparation_source_sha256'], 'Preparation source changed')
    for name, digest in freeze['protected_input_sha256'].items():
        require(sha(ROOT / name) == digest, f'Protected input changed: {name}')
    for name, digest in freeze['artifact_sha256'].items():
        require(sha(out / name) == digest, f'Artifact changed: {name}')
    require({p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()} == set(freeze['artifact_sha256']) | {'freeze.json'}, 'Unexpected artifact set')
    for name in plan['reference_sources']:
        require((ROOT / name).read_bytes() == (out / 'reference' / name).read_bytes(), 'Reference bytes differ')
    reference_runner = ast.parse((out / 'reference/research_log/run_usage_model_study_20261031.py').read_text(encoding='utf-8'))
    frame = next(n for n in reference_runner.body if isinstance(n, ast.FunctionDef) and n.name == 'feature_frame')
    copied_frame = ast.parse((out / 'reference/feature_frame.py').read_text(encoding='utf-8')).body
    require(len(copied_frame) == 1 and ast.dump(frame) == ast.dump(copied_frame[0]), 'Frame definition changed')
    manifest = json.loads((study / 'corpus/manifest.json').read_bytes())
    original = {r['sample_id']: r for r in manifest['candidates'] if r['selection_status'] == 'selected'}
    inventory = read(out / 'input_inventory.csv')
    require(len(inventory) == len(original) == 60 and {r['sample_id'] for r in inventory} == set(original), 'Input inventory coverage')
    for r in inventory:
        require(all(r[k] == str(original[r['sample_id']][k]) for k in r), 'Inventory metadata mismatch')
    require(json.loads((out / 'input_root.json').read_bytes()) == dict(original_input_root=manifest['input_root'], original_bytes_verified=False), 'Input-root scope mismatch')
    saved = {r['sample_id']: r for r in read(study / 'predictions/samples.csv')}
    canonical = read(out / 'expected_features.csv')
    names = plan['feature_contract']['names_in_order']
    require(len(canonical) == 720 and {(r['sample_id'], r['feature']) for r in canonical} == {(s, n) for s in original for n in names}, 'Expected feature coverage')
    for r in canonical:
        value = saved[r['sample_id']][r['feature']]
        integer = r['feature'] in plan['feature_contract']['integer_features']
        require(r['builtin_type'] == ('int' if integer else 'float'), 'Canonical type')
        require(r['stored_decimal'] == value and r['canonical_value'] == (str(int(value)) if integer else float(value).hex()), 'Canonical expected value')
    require((out / 'expected_predictions.csv').read_bytes() == (study / 'predictions/frozen_predictions.csv').read_bytes(), 'Prediction bytes changed')
    require(len(read(out / 'expected_predictions.csv')) == 1080, 'Prediction coverage')
    models = read(out / 'model_inventory.csv')
    require(len(models) == len({(r['scenario_id'], r['model']) for r in models}) == 18, 'Model inventory')
    for r in models:
        require(sha(study / r['relative_path']) == r['sha256'], 'Model hash')
    schedule = read(out / 'schedule.csv')
    require(len(schedule) == 1440, 'Schedule size')
    source_order = sorted(original.values(), key=lambda r: (r['origin_group_id'], r['sample_id']))
    for i, mode in enumerate(plan['timing']['modes_in_order']):
        for round_index in range(6):
            rows = [r for r in schedule if r['mode'] == mode and int(r['round_index']) == round_index]
            require(len(rows) == 60 and {r['sample_id'] for r in rows} == set(original), 'Incomplete schedule round')
            require([int(r['order_in_round']) for r in rows] == list(range(1, 61)), 'Schedule positions')
            expected = list(source_order)
            random.Random(plan['timing']['schedule_seed'] + 1000*i + round_index).shuffle(expected)
            require([r['sample_id'] for r in rows] == [r['sample_id'] for r in expected], 'Schedule seed/order')
            require(all(r['is_warmup'] == str(round_index == 0) for r in rows), 'Warmup labeling')
    for key in ('original_bytes_verified', 'feature_execution', 'model_deserialization', 'prediction_execution', 'profile_measurement', 'optimization_implemented'):
        require(freeze[key] is False, f'Unexpected execution claim: {key}')
    require(not (ROOT / plan['future_profile_root']).exists(), 'Real profile output already exists')
    design = ROOT / 'research_log/feature_profile_design_20261109.md'
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', design.read_text(encoding='utf-8'))
    require(all((design.parent / link).resolve().is_file() for link in links), 'Broken design link')
    value = dict(status='plan_references_and_schedule_verified', created_at_utc=datetime.now(timezone.utc).isoformat(),
                 verifier_sha256=sha(Path(__file__)), freeze_sha256=sha(out / 'freeze.json'), coverage=freeze['coverage'],
                 protected_file_count=len(freeze['protected_input_sha256']), design_link_count=len(links),
                 checks=['Plan/source/snapshot hashes', 'Frame AST identity', 'Complete inventory and stored canonical features',
                         'Byte-exact frozen prediction file', 'Unchanged model hashes without deserialization',
                         'Every deterministic schedule round', 'Explicit no-execution scope', 'Design links'])
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=value['status'], coverage=value['coverage'], protected_files=value['protected_file_count'])))


if __name__ == '__main__':
    main()
