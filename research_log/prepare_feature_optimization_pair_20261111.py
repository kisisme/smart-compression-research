"""Freeze candidate designs/schedule only; no candidate, features or model runs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r

PLAN = ROOT / 'research_log/feature_optimization_pair_plan_20261111.json'
DESIGN = ROOT / 'research_log/feature_optimization_pair_design_20261111.md'


def write_csv(path, rows):
    import csv
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    plan = json.loads(PLAN.read_bytes())
    out = ROOT / plan['freeze_root']
    r.require(not out.exists() and not (ROOT / plan['future_result_root']).exists(), 'Refuse to overwrite plan/run')
    ctx = r.load_context()  # Hash/runtime checks only. No feature or prediction calls.
    prior_path = ROOT / plan['bottleneck_analysis']
    prior = json.loads(prior_path.read_bytes())
    r.require(prior['status'] == 'saved_profile_and_disjoint_partition_verified', 'Unverified baseline diagnosis')
    profile = ROOT / plan['observed_baseline']
    completed = json.loads((profile / 'complete.json').read_bytes())
    r.require(completed['status'] == 'profile_independently_verified' and r.sha(profile / 'verification.json') == completed['verification_sha256'], 'Baseline completion mismatch')
    protected = dict(prior['protected_source_sha256'])
    for name, value in prior['profile_file_sha256'].items():
        path = profile / name
        r.require(r.sha(path) == value, 'Profile evidence changed')
        protected[path.relative_to(ROOT).as_posix()] = value
    for name, value in prior['output_sha256'].items():
        r.require(r.sha(ROOT / name) == value, 'Prior diagnosis changed')
        protected[name] = value
    protected[prior_path.relative_to(ROOT).as_posix()] = r.sha(prior_path)
    prior_source = 'research_log/analyze_feature_profile_baseline_20261111.py'
    r.require(r.sha(ROOT / prior_source) == prior['analysis_source_sha256'], 'Prior analysis source changed')
    protected[prior_source] = r.sha(ROOT / prior_source)
    for name, value in protected.items():
        r.require(r.sha(ROOT / name) == value, f'Protected input changed: {name}')
    comparison = plan['comparison']
    variants = comparison['comparisons_in_order']
    r.require(variants == ['bigram_numpy', 'run_numpy', 'both_numpy'] and comparison['primary_candidate'] == 'both_numpy', 'Candidate definition/order')
    r.require(comparison['primary_mode'] == 'extract_and_frame' and comparison['modes_in_order'] == ['extract_only', 'extract_and_frame'], 'Mode definition/order')
    r.require(comparison['measured_pairs_per_file_mode_comparison'] == 6 and comparison['warmup_pairs_per_file_mode_comparison'] == 1, 'Repeat balance')
    r.require(plan['candidate_designs']['bigram_numpy']['replace_only'] == ['_bigram_diversity'] and plan['candidate_designs']['run_numpy']['replace_only'] == ['_run_statistics'], 'Helper allowlist')
    r.require(plan['candidate_designs']['both_numpy']['replace_only'] == ['_bigram_diversity', '_run_statistics'], 'Combined allowlist')
    entries = sorted(ctx['inventory'], key=lambda row: (row['origin_group_id'], row['sample_id']))
    r.require(len(entries) == 60, 'Complete corpus required')
    base_index = {row['sample_id']: i for i, row in enumerate(entries)}
    schedule = []
    for c, candidate in enumerate(variants):
        for m, mode in enumerate(comparison['modes_in_order']):
            for round_index in range(7):
                order = list(entries)
                random.Random(comparison['schedule_seed']+10000*c+1000*m+round_index).shuffle(order)
                for position, entry in enumerate(order, 1):
                    ref_first = (base_index[entry['sample_id']]+round_index+c+m) % 2 == 0
                    schedule.append(dict(comparison=candidate, mode=mode, round_index=round_index, is_warmup=round_index == 0,
                                         order_in_round=position, sample_id=entry['sample_id'],
                                         first='reference' if ref_first else candidate, second=candidate if ref_first else 'reference'))
    import numpy as np
    r.require(np.__version__ == ctx['frozen']['packages']['numpy'], 'NumPy version changed')
    apis = ('frombuffer', 'bincount', 'count_nonzero', 'flatnonzero', 'diff', 'concatenate', 'left_shift', 'bitwise_or')
    docs = {name: dict(first_line=getattr(np, name).__doc__.strip().splitlines()[0],
                       doc_sha256=hashlib.sha256(getattr(np, name).__doc__.encode('utf-8')).hexdigest()) for name in apis}
    dtype_info = {name: dict(itemsize=np.dtype(name).itemsize, minimum=int(np.iinfo(name).min), maximum=int(np.iinfo(name).max)) for name in ('uint8', 'uint16', 'intp')}
    r.require(dtype_info['uint16']['maximum'] == 65535 and dtype_info['intp']['minimum'] < 0, 'Required dtype ranges')
    out.mkdir(parents=True)
    r.write_json(out / 'plan.json', plan)
    r.write_json(out / 'numpy_api.json', dict(numpy_version=np.__version__, local_module_path=np.__file__,
                 local_module_sha256=r.sha(Path(np.__file__)), apis=docs, dtypes=dtype_info,
                 scope='Installed documentation/dtype metadata only; no candidate feature computations.'))
    write_csv(out / 'input_inventory.csv', entries)
    write_csv(out / 'pair_schedule.csv', schedule)
    measured = sum(not row['is_warmup'] for row in schedule)
    warmups = len(schedule)-measured
    coverage = dict(corpus_files=len(entries), origin_groups=len({e['origin_group_id'] for e in entries}),
                    candidates=len(variants), compared_variants=len(variants)+1, modes=len(comparison['modes_in_order']),
                    planned_measured_pairs=measured, planned_timed_calls=measured*2,
                    planned_warmup_pairs=warmups, planned_warmup_calls=warmups*2,
                    planned_feature_value_checks=len(ctx['contract']['names_in_order'])*len(entries)*(len(variants)+1),
                    planned_single_row_prediction_checks=ctx['frozen']['coverage']['frozen_predictions']*(len(variants)+1),
                    planned_valid_public_fixtures=ctx['frozen']['coverage']['planned_valid_fixtures']+2,
                    planned_invalid_public_fixtures=ctx['frozen']['coverage']['planned_invalid_fixtures'], planned_short_private_helper_checks=4)
    for name, value in protected.items():
        r.require(r.sha(ROOT / name) == value, f'Input changed during preparation: {name}')
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', DESIGN.read_text(encoding='utf-8'))
    r.require(all((DESIGN.parent / link).resolve().is_file() for link in links if not link.endswith(('/freeze.json', '/verification.json'))), 'Design link')
    r.write_json(out / 'freeze.json', dict(status='candidate_design_and_paired_schedule_frozen_before_implementation',
                 created_at_utc=datetime.now(timezone.utc).isoformat(), source_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                 python=sys.version, platform=platform.platform(), packages=ctx['frozen']['packages'],
                 plan_sha256=r.sha(PLAN), design_sha256=r.sha(DESIGN), preparation_source_sha256=r.sha(Path(__file__)),
                 reference_freeze_sha256=r.sha(r.FREEZE / 'freeze.json'), coverage=coverage,
                 candidate_implemented=False, candidate_feature_execution=False, model_prediction_execution=False,
                 paired_measurement=False, fixture_tests_executed=False, protected_input_sha256=protected,
                 reference_artifacts={name: dict(path=(r.FREEZE / name).relative_to(ROOT).as_posix(), sha256=r.sha(r.FREEZE / name))
                                      for name in ('expected_features.csv', 'expected_predictions.csv', 'model_inventory.csv', 'reference/src/feature_extractor.py', 'reference/feature_frame.py', 'reference/config/experiment_config.json')},
                 artifact_sha256={p.name: r.sha(p) for p in out.iterdir() if p.is_file()}))
    print(json.dumps(dict(status='paired_plan_frozen', coverage=coverage, protected_files=len(protected))))


if __name__ == '__main__':
    main()
