"""Frozen paired schedule controller. Real runs require a committed source lock."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r
from research_log import feature_pair_candidates_20261111 as c

FREEZE = ROOT / 'data/results/feature_optimization_pair_plan_20261111_01'
LOCK = ROOT / 'data/results/feature_pair_implementation_20261111_01/implementation.json'


def context():
    frozen = json.loads((FREEZE / 'freeze.json').read_bytes())
    verified = json.loads((FREEZE / 'verification.json').read_bytes())
    r.require(r.sha(FREEZE / 'freeze.json') == verified['freeze_sha256'], 'Paired freeze differs')
    for name, digest in frozen['protected_input_sha256'].items():
        r.require(r.sha(ROOT / name) == digest, 'Protected source differs: '+name)
    for name, digest in frozen['artifact_sha256'].items():
        r.require(r.sha(FREEZE / name) == digest, 'Frozen artifact differs')
    lock = json.loads(LOCK.read_bytes())
    r.require(lock['status'] == 'synthetic_validation_passed', 'Implementation not validated')
    for name, digest in lock['source_sha256'].items():
        r.require(r.sha(ROOT / name) == digest, 'Changed paired source')
        r.require(r.digest(subprocess.check_output(['git', 'show', 'HEAD:'+name], cwd=ROOT)) == digest, 'Uncommitted paired source')
    r.require(subprocess.check_output(['git', 'show', 'HEAD:'+LOCK.relative_to(ROOT).as_posix()], cwd=ROOT) == LOCK.read_bytes(), 'Uncommitted paired lock')
    return r.load_context(), json.loads((FREEZE / 'plan.json').read_bytes()), r.read_csv(FREEZE / 'pair_schedule.csv')


def audit(output, ctx, schedule):
    inventory = {e['sample_id']: e for e in ctx['inventory']}
    buckets = defaultdict(list)
    summaries = []
    for candidate in c.VARIANTS[1:]:
        for mode in ('extract_only', 'extract_and_frame'):
            slots = [s for s in schedule if s['comparison'] == candidate and s['mode'] == mode]
            with (output / f'{candidate}__{mode}.jsonl').open(encoding='utf-8') as stream:
                rows = [json.loads(line) for line in stream]
            deltas = c.verify_pairs(slots, rows, ctx['expected'], inventory, data_kind='observed_development_corpus')
            groups = defaultdict(list)
            reference, proposed = [], []
            for sample, meta in inventory.items():
                sample_deltas = [d['delta_ns'] for d in deltas if d['sample_id'] == sample and d['is_warmup'] == 'False']
                r.require(len(sample_deltas) == 6, 'Six measured pairs required')
                groups[meta['origin_group_id']].append(statistics.median(sample_deltas))
                for variant, destination in (('reference', reference), (candidate, proposed)):
                    values = [v['elapsed_ns'] for v in rows if v['sample_id'] == sample and v['is_warmup'] == 'False' and v['variant'] == variant]
                    r.require(len(values) == 6, 'Variant median coverage')
                    destination.append(statistics.median(values))
            primary = statistics.fmean(statistics.fmean(v) for v in groups.values())
            ratio = sum(reference)/sum(proposed)
            summaries.append(dict(candidate=candidate, mode=mode, equal_origin_mean_paired_delta_ns=primary,
                                  pooled_median_ratio=ratio, advance_to_pipeline=candidate == 'both_numpy' and mode == 'extract_and_frame' and primary < 0 and ratio > 1))
    r.write_json(output / 'summary.json', summaries)
    context()  # Recheck immutable sources after execution, without feature calls.
    r.write_json(output / 'verification.json', dict(status='all_pairs_verified', summaries=summaries,
                 artifact_sha256={p.name: r.sha(p) for p in output.iterdir() if p.is_file()}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', nargs=2, metavar=('CANDIDATE', 'MODE'))
    parser.add_argument('--output', type=Path, default=ROOT / 'data/results/feature_optimization_pair_20261111_01')
    parser.add_argument('--notes', default='Concurrent activity/power events not reported; absence is not inferred.')
    args = parser.parse_args()
    ctx, plan, schedule = context()  # Refuse unvalidated/uncommitted code before corpus reads.
    output = args.output.resolve()
    r.require(output.parent == (ROOT / 'data/results').resolve() and output.name.startswith('feature_optimization_pair_'), 'Unsafe results path')
    if args.worker:
        candidate, mode = args.worker
        r.require(candidate in c.VARIANTS[1:] and mode in ('extract_only', 'extract_and_frame'), 'Invalid worker')
        r.require((output / 'started.json').exists() and not (output / 'failure.json').exists(), 'Inactive controller')
        inputs = r.read_corpus(ctx)
        for variant in ('reference', candidate): r.reference_gate(ctx, inputs, c.build(variant))
        with (output / f'{candidate}__{mode}.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
            c.execute_pairs([s for s in schedule if s['comparison'] == candidate and s['mode'] == mode], inputs,
                            ctx['expected'], ctx['contract'], r.load_frame_factory(ctx['contract']['names_in_order']), stream,
                            data_kind='observed_development_corpus')
        return
    output.mkdir(parents=True, exist_ok=False)
    r.write_json(output / 'started.json', dict(notes=args.notes, at_utc=r.now(), pid=os.getpid(), implementation_sha256=r.sha(LOCK),
                 git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()))
    phase = 'exact_gates'
    try:
        inputs = r.read_corpus(ctx)
        frame = r.load_frame_factory(ctx['contract']['names_in_order'])
        for variant in c.VARIANTS:
            features = r.reference_gate(ctx, inputs, c.build(variant))
            r.prediction_gate(ctx, features, frame, output / (variant+'_predictions.jsonl'))
        for candidate in c.VARIANTS[1:]:
            for mode in ('extract_only', 'extract_and_frame'):
                phase = candidate+'__'+mode
                command = [sys.executable, str(Path(__file__).resolve()), '--worker', candidate, mode, '--output', str(output)]
                with (output / (phase+'.log')).open('xb') as log:
                    child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    try: code = child.wait()
                    except BaseException:
                        child.terminate()
                        try: child.wait(timeout=5)
                        except subprocess.TimeoutExpired: child.kill(); child.wait()
                        raise
                r.write_json(output / (phase+'_process.json'), dict(returncode=code, pid=child.pid, command=command))
                r.require(code == 0, 'Worker failed; no retries: '+phase)
                print(phase+' completed', flush=True)
        phase = 'saved_pair_audit'
        audit(output, ctx, schedule)
        r.write_json(output / 'complete.json', dict(status='paired_run_verified', verification_sha256=r.sha(output / 'verification.json')))
    except BaseException as exc:
        r.failure(output / 'failure.json', exc, phase)
        raise


if __name__ == '__main__': main()
