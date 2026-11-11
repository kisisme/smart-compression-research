"""Four fresh workers, preflight exact gates, append-only trials, no retries."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r


def profile_output(path):
    path = Path(path).resolve()
    r.require(path.parent == (ROOT / 'data/results').resolve() and path.name.startswith('feature_profile_baseline_'), 'Output must be a new feature_profile_baseline_* directory directly under data/results')
    return path


def worker(mode, output):
    r.check_implementation()
    ctx = r.load_context()
    r.require(mode in r.MODES, 'Unknown worker mode')
    r.require((output / 'started.json').is_file() and not (output / 'failure.json').exists(), 'Controller not active')
    inputs = r.read_corpus(ctx)
    reference = r.load_reference()
    r.reference_gate(ctx, inputs, reference)
    frame = r.load_frame_factory(ctx['contract']['names_in_order'])
    slots = [s for s in ctx['schedule'] if s['mode'] == mode]
    r.run_mode(mode, slots, inputs, ctx['expected'], reference, frame, output / 'modes' / mode,
               ctx['contract'], ctx['plan']['timing']['instrumented_targets'], data_kind='observed_development_corpus')


def execute_worker(mode, output):
    command = [sys.executable, str(Path(__file__).resolve()), '--worker', mode, '--output', str(output)]
    with (output / (mode+'.log')).open('xb') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            code = process.wait()
        except BaseException:
            # Only the child created here is terminated; partial files stay intact.
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            r.write_json(output / (mode+'_process.json'), dict(command=command, pid=process.pid,
                         returncode=process.returncode, status='interrupted'))
            raise
    r.write_json(output / (mode+'_process.json'), dict(command=command, pid=process.pid,
                 returncode=code, status='exited'))
    r.require(code == 0, f'Worker failed: {mode}; partial output/log preserved')


def run(output, notes):
    # Validate implementation before creating output or reading corpus/model bytes.
    lock = r.check_implementation()
    output = profile_output(output)
    output.mkdir(parents=True, exist_ok=False)
    clock = time.get_clock_info('perf_counter')
    r.write_json(output / 'started.json', dict(started_at_utc=r.now(), pid=os.getpid(), notes=notes,
                 python=sys.version, platform=platform.platform(), implementation_sha256=r.sha(r.IMPLEMENTATION),
                 source_sha256=lock['source_sha256'], data_kind='observed_development_corpus',
                 git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                 timer=dict(implementation=clock.implementation, resolution=clock.resolution, monotonic=clock.monotonic)))
    phase = 'preflight'
    try:
        ctx = r.load_context()
        inputs = r.read_corpus(ctx)
        reference = r.load_reference()
        features = r.reference_gate(ctx, inputs, reference)
        frame = r.load_frame_factory(ctx['contract']['names_in_order'])
        count = r.prediction_gate(ctx, features, frame, output / 'predictions.jsonl')
        r.write_json(output / 'preflight.json', dict(status='exact_reference_and_predictions_verified',
                    input_files=len(inputs), feature_values=sum(len(v) for v in features.values()), predictions=count,
                    plan_freeze_sha256=r.sha(r.FREEZE / 'freeze.json'), implementation_sha256=r.sha(r.IMPLEMENTATION)))
        for mode in r.MODES:
            phase = mode
            print(json.dumps(dict(phase=mode, status='starting_fresh_worker')), flush=True)
            execute_worker(mode, output)
        r.write_json(output / 'measurements_completed.json', dict(status='all_workers_completed', modes=list(r.MODES)))
        phase = 'independent_audit'
        from research_log.verify_feature_profile_run_20261111 import audit_run
        audit = audit_run(output, ctx)
        r.write_json(output / 'complete.json', dict(status='profile_independently_verified', at_utc=r.now(),
                     verification_sha256=r.sha(output / 'verification.json'), coverage=audit['coverage']))
        print(json.dumps(dict(status='profile_independently_verified', coverage=audit['coverage'])), flush=True)
    except BaseException as exc:
        r.failure(output / 'failure.json', exc, phase)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', choices=r.MODES)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/results/feature_profile_baseline_20261109_01')
    parser.add_argument('--notes', default='No user-observed interruption report supplied; runner does not infer absence of interruptions.')
    args = parser.parse_args()
    output = profile_output(args.output)
    if args.worker:
        worker(args.worker, output)
    else:
        run(output, args.notes)


if __name__ == '__main__':
    main()
