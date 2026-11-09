"""Freeze a profiling plan and stored references; never execute feature/model code."""
import ast
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import random
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'research_log/feature_profile_plan_20261109.json'
DESIGN = ROOT / 'research_log/feature_profile_design_20261109.md'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames), 'CSV columns')
        rows = list(reader)
        require(all(None not in row and None not in row.values() for row in rows), 'Malformed CSV')
        return rows


def write_csv(path, rows):
    require(bool(rows), 'Empty table')
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    plan = json.loads(PLAN.read_bytes())
    out, study, diagnosis = (ROOT / plan[k] for k in ('freeze_root', 'source_study', 'source_bottleneck_analysis'))
    require(not out.exists(), 'Refuse to overwrite frozen plan')
    require(not (ROOT / plan['future_profile_root']).exists(), 'Profile path already exists')
    require(not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT).strip(), 'Unexpected staged changes')
    prior = json.loads((diagnosis / 'audit.json').read_bytes())
    verified = json.loads((diagnosis / 'verification.json').read_bytes())
    require(verified['status'] == 'independently_verified' and sha(diagnosis / 'audit.json') == verified['audit_sha256'], 'Prior audit changed')
    for name, digest in {**prior['protected_input_sha256'], **prior['output_sha256']}.items():
        require(sha(ROOT / name) == digest, f'Changed prior evidence: {name}')
    protected = {p.relative_to(ROOT).as_posix(): sha(p)
                 for dirname in (study, ROOT / 'data/results/usage_zstd_misses_20261031_01', diagnosis)
                 for p in sorted(dirname.rglob('*')) if p.is_file()}
    for name in (*plan['reference_sources'], 'research_protocol_v2.md'):
        protected[name] = sha(ROOT / name)
    source = (ROOT / 'src/feature_extractor.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    names = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FEATURE_NAMES' for t in n.targets))
    require(list(names) == plan['feature_contract']['names_in_order'] and len(names) == 12, 'Feature order')
    config = json.loads((ROOT / 'config/experiment_config.json').read_bytes())
    require(config['features'] == dict(duplicate_block_size=plan['feature_contract']['duplicate_block_bytes'], segment_size=plan['feature_contract']['segment_bytes']), 'Feature config changed')
    training = json.loads((study / 'training.json').read_bytes())
    require(training['feature_names'] == list(names), 'Model feature order')
    packages = {name: version(name) for name in training['packages']}
    require(platform.python_version() == training['python'] and packages == training['packages'], 'Model runtime differs; no baseline refresh allowed')
    manifest = json.loads((study / 'corpus/manifest.json').read_bytes())
    entries = sorted((r for r in manifest['candidates'] if r['selection_status'] == 'selected'), key=lambda r: (r['origin_group_id'], r['sample_id']))
    require(len(entries) == len({r['sample_id'] for r in entries}) == 60, 'Corpus coverage')
    samples = read_csv(study / 'predictions/samples.csv')
    require(len(samples) == len({r['sample_id'] for r in samples}) == len(entries), 'Saved feature coverage')
    by_sample = {r['sample_id']: r for r in samples}
    require(set(by_sample) == {r['sample_id'] for r in entries}, 'Saved feature keys')
    canonical, inventory = [], []
    for entry in entries:
        r = by_sample[entry['sample_id']]
        require(r['input_sha256'] == entry['input_sha256'] and int(r['original_size']) == entry['original_size'], 'Saved feature input mismatch')
        inventory.append({k: entry[k] for k in ('sample_id', 'candidate_id', 'relative_path', 'input_sha256', 'original_size', 'format', 'origin_group_id')})
        for name in names:
            integer = name in plan['feature_contract']['integer_features']
            value = int(r[name]) if integer else float(r[name])
            require(math.isfinite(value), 'Nonfinite stored feature')
            canonical.append(dict(sample_id=entry['sample_id'], feature=name, builtin_type='int' if integer else 'float',
                                  canonical_value=str(value) if integer else value.hex(), stored_decimal=r[name]))
    models = training['models']
    require(len(models) == len({(m['scenario_id'], m['kind']) for m in models}) == 18, 'Model coverage')
    model_inventory = []
    for item in models:
        require(sha(study / item['file']) == item['sha256'], 'Model bytes changed')
        model_inventory.append(dict(scenario_id=item['scenario_id'], model=item['kind'], relative_path=item['file'], sha256=item['sha256'],
                                    classes=';'.join(item['classes'])))
    predictions = read_csv(study / 'predictions/frozen_predictions.csv')
    expected = {(e['sample_id'], m['scenario_id'], m['kind']) for e in entries for m in models}
    require(len(predictions) == len(expected) and {(r['sample_id'], r['scenario_id'], r['model']) for r in predictions} == expected, 'Prediction coverage')
    schedule = []
    timing = plan['timing']
    require(timing['warmup_calls_per_file_per_mode'] == 1 and timing['recorded_repeats'] == 5, 'Timing slot definition')
    for mode_index, mode in enumerate(timing['modes_in_order']):
        for round_index in range(6):
            shuffled = list(entries)
            random.Random(timing['schedule_seed'] + 1000*mode_index + round_index).shuffle(shuffled)
            for position, entry in enumerate(shuffled, 1):
                schedule.append(dict(mode=mode, round_index=round_index, is_warmup=round_index == 0,
                                     order_in_round=position, sample_id=entry['sample_id']))
    runner_source = (ROOT / 'research_log/run_usage_model_study_20261031.py').read_text(encoding='utf-8')
    frame = next(n for n in ast.parse(runner_source).body if isinstance(n, ast.FunctionDef) and n.name == 'feature_frame')
    frame_source = ast.get_source_segment(runner_source, frame) + '\n'
    require(isinstance(ast.parse(frame_source).body[0], ast.FunctionDef), 'Frame snapshot syntax')
    out.mkdir(parents=True)
    for name in plan['reference_sources']:
        path = out / 'reference' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write((ROOT / name).read_bytes())
        require(sha(path) == protected[name], 'Reference snapshot mismatch')
    for name, value in (('plan.json', plan), ('input_root.json', dict(original_input_root=manifest['input_root'], original_bytes_verified=False))):
        write_json(out / name, value)
    with (out / 'reference/feature_frame.py').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(frame_source)
    write_csv(out / 'input_inventory.csv', inventory)
    write_csv(out / 'expected_features.csv', canonical)
    write_csv(out / 'model_inventory.csv', model_inventory)
    write_csv(out / 'schedule.csv', schedule)
    with (out / 'expected_predictions.csv').open('xb') as stream:
        stream.write((study / 'predictions/frozen_predictions.csv').read_bytes())
    for name, digest in protected.items():
        require(sha(ROOT / name) == digest, f'Protected file changed: {name}')
    fixtures = plan['fixture_plan']
    coverage = dict(corpus_files=len(entries), feature_values=len(canonical), model_files=len(models), frozen_predictions=len(predictions),
                    scheduled_measurements=sum(not r['is_warmup'] for r in schedule), scheduled_warmups=sum(r['is_warmup'] for r in schedule),
                    planned_valid_fixtures=len(fixtures['lengths'])*len(fixtures['patterns'])+len(fixtures['extra_valid_cases']),
                    planned_invalid_fixtures=len(fixtures['invalid_cases']))
    clock = time.get_clock_info('perf_counter')
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', DESIGN.read_text(encoding='utf-8'))
    require(all((DESIGN.parent / name).resolve().is_file() for name in links if not name.endswith('/freeze.json')), 'Broken design link')
    write_json(out / 'freeze.json', dict(status='plan_and_references_frozen_before_implementation_and_measurement',
               created_at_utc=datetime.now(timezone.utc).isoformat(), source_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               python=sys.version, platform=platform.platform(), packages=packages,
               timer=dict(implementation=clock.implementation, monotonic=clock.monotonic, resolution=clock.resolution),
               plan_sha256=sha(PLAN), design_sha256=sha(DESIGN), preparation_source_sha256=sha(Path(__file__)), coverage=coverage,
               protected_input_sha256=protected, original_bytes_verified=False, feature_execution=False, model_deserialization=False,
               prediction_execution=False, profile_measurement=False, optimization_implemented=False,
               checks=['Prior verified evidence chain', 'AST feature contract and config', 'Original model runtime/bytes without loading',
                       'Saved features canonicalized without recomputation', 'Complete all-model prediction keys',
                       'Deterministic complete schedule', 'Byte-identical reference source snapshots', 'Protected hashes unchanged', 'Design links'],
               artifact_sha256={p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(status='plan_frozen', coverage=coverage, protected_files=len(protected)), ensure_ascii=False))


if __name__ == '__main__':
    main()
