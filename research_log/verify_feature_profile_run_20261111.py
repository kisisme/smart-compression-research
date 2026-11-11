"""Audit saved trials/call trees independently of the timing wrapper."""
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def call_tree(events, trial, size, contract, targets):
    require = r.require
    ids = {e['call_id']: e for e in events}
    require(len(ids) == len(events) and set(ids) == set(range(1, len(events)+1)), 'Call IDs differ')
    roots = [e for e in events if e['parent_id'] is None]
    require(len(roots) == 1 and roots[0]['function'] == 'extract_features', 'Call root differs')
    children = defaultdict(list)
    for e in events:
        require(e['status'] == 'ok' and e['function'] in targets, 'Failed/unknown call')
        require(all(type(e[k]) is int for k in ('call_id', 'depth', 'start_ns', 'end_ns', 'elapsed_ns', 'self_ns')), 'Noninteger call timer')
        require(e['elapsed_ns'] == e['end_ns']-e['start_ns'] > 0 and e['self_ns'] >= 0, 'Call duration differs')
        require(trial['start_ns'] <= e['start_ns'] < e['end_ns'] <= trial['end_ns'], 'Call outside trial')
        if e['parent_id'] is None:
            require(e['depth'] == 0 and e['parent_function'] is None, 'Root depth differs')
        else:
            require(type(e['parent_id']) is int, 'Noninteger parent ID')
            require(e['parent_id'] in ids, 'Missing parent')
            p = ids[e['parent_id']]
            require(e['depth'] == p['depth']+1 and e['parent_function'] == p['function'], 'Parent context differs')
            require(p['start_ns'] <= e['start_ns'] < e['end_ns'] <= p['end_ns'], 'Invalid nesting')
            children[e['parent_id']].append(e)
    for ident, e in ids.items():
        direct = sorted(children[ident], key=lambda c: c['start_ns'])
        require(all(a['end_ns'] <= b['start_ns'] for a, b in zip(direct, direct[1:])), 'Overlapping direct children')
        require(e['self_ns'] == e['elapsed_ns']-sum(c['elapsed_ns'] for c in direct), 'Inclusive/self accounting differs')
    require(sum(e['self_ns'] for e in events) == roots[0]['elapsed_ns'], 'Call tree not connected')
    segments = (size+contract['segment_bytes']-1)//contract['segment_bytes']
    expected = Counter({name: 1 for name in targets})
    expected['Counter'] = expected['_entropy_from_counts'] = segments+1
    require(Counter(e['function'] for e in events) == expected, 'Helper call coverage differs')
    for name in ('Counter', '_entropy_from_counts'):
        counts = Counter(e['parent_function'] for e in events if e['function'] == name)
        require(counts == Counter(extract_features=1, _segment_entropy_statistics=segments), 'Global/segment helper contexts differ')


def audit_mode(mode, schedule, records, expected, inventory, contract, targets, data_kind):
    r.require(len(records) == len(schedule), 'Incomplete/extra trial slots')
    for slot, row in zip(schedule, records, strict=True):
        r.require(all(row[k] == v for k, v in slot.items()), 'Trial schedule/order differs')
        sample = slot['sample_id']
        r.require(row['status'] == 'ok' and row['data_kind'] == data_kind, 'Failed/wrong-kind trial')
        r.require(row['input_sha256'] == inventory[sample]['input_sha256'], 'Trial input hash differs')
        r.require(all(type(row[k]) is int for k in ('start_ns', 'end_ns', 'elapsed_ns')), 'Noninteger trial timer')
        r.require(row['end_ns']-row['start_ns'] == row['elapsed_ns'] > 0, 'Trial duration differs')
        r.require(row['features'] == expected[sample], 'Trial exact features differ')
        if mode in ('frame_only', 'extract_and_frame'):
            wanted = [float(int(v) if kind == 'int' else float.fromhex(v)).hex() for _, kind, v in expected[sample]]
            r.require(row['frame'] == wanted, 'Trial frame values differ')
        else:
            r.require(row['frame'] is None, 'Unexpected frame')
        if mode == 'instrumented_extract':
            call_tree(row['calls'], row, int(inventory[sample]['original_size']), contract, targets)
        else:
            r.require(row['calls'] == [], 'Uninstrumented mode has calls')


def distribution(values):
    values = sorted(values)
    r.require(bool(values), 'Empty distribution')
    pos = (len(values)-1)*.9
    low, high = math.floor(pos), math.ceil(pos)
    return dict(count=len(values), min_ms=values[0], median_ms=statistics.median(values),
                mean_ms=statistics.fmean(values), p90_ms=values[low]+(values[high]-values[low])*(pos-low), max_ms=values[-1])


def write_csv(path, rows):
    r.require(bool(rows), 'Empty report table')
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def audit_run(output, ctx):
    output = Path(output)
    r.require(not (output / 'verification.json').exists(), 'Refuse to overwrite verification')
    r.require(not (output / 'failure.json').exists(), 'Failed run cannot verify')
    started = json.loads((output / 'started.json').read_bytes())
    preflight = json.loads((output / 'preflight.json').read_bytes())
    lock = r.check_implementation()
    r.require(started['source_sha256'] == lock['source_sha256'] and started['implementation_sha256'] == r.sha(r.IMPLEMENTATION), 'Run implementation differs')
    r.require(preflight['status'] == 'exact_reference_and_predictions_verified' and preflight['input_files'] == 60 and preflight['feature_values'] == 720 and preflight['predictions'] == 1080, 'Preflight incomplete')
    r.require(preflight['plan_freeze_sha256'] == r.sha(r.FREEZE / 'freeze.json') and preflight['implementation_sha256'] == r.sha(r.IMPLEMENTATION), 'Preflight identities differ')
    frozen = r.read_csv(r.FREEZE / 'expected_predictions.csv')
    predictions = read_jsonl(output / 'predictions.jsonl')
    r.require(len(predictions) == len(frozen) == 1080, 'Prediction log incomplete')
    for expected, actual in zip(frozen, predictions, strict=True):
        r.require(actual['status'] == 'ok' and all(actual[k] == expected[k] for k in ('sample_id', 'scenario_id', 'model', 'model_sha256', 'predicted_algorithm')), 'Prediction identity differs')
        for key in ('uncalibrated_confidence', *('probability_'+a for a in r.ALGORITHMS)):
            r.require(actual[key] == float(expected[key]).hex(), 'Prediction exact probability differs')
    inventory = {e['sample_id']: e for e in ctx['inventory']}
    medians, call_rows = [], []
    raw_count = warmups = 0
    for mode in r.MODES:
        directory = output / 'modes' / mode
        r.require(not (directory / 'failure.json').exists(), 'Worker failure preserved')
        completed = json.loads((directory / 'complete.json').read_bytes())
        process = json.loads((output / (mode+'_process.json')).read_bytes())
        r.require(completed == dict(status='mode_completed', mode=mode, slots=360, data_kind='observed_development_corpus') and process['returncode'] == 0, 'Mode incomplete')
        records = read_jsonl(directory / 'trials.jsonl')
        slots = [s for s in ctx['schedule'] if s['mode'] == mode]
        audit_mode(mode, slots, records, ctx['expected'], inventory, ctx['contract'], ctx['plan']['timing']['instrumented_targets'], 'observed_development_corpus')
        raw_count += len(records)
        warmups += sum(row['is_warmup'] == 'True' for row in records)
        for sample, meta in inventory.items():
            trials = [row for row in records if row['sample_id'] == sample and row['is_warmup'] == 'False']
            r.require(len(trials) == 5, 'Median repeat count differs')
            medians.append(dict(sample_id=sample, mode=mode, candidate_id=meta['candidate_id'], format=meta['format'],
                                origin_group_id=meta['origin_group_id'], original_size=int(meta['original_size']),
                                size_bin='le_64KiB' if int(meta['original_size']) <= 65536 else '64_to_256KiB' if int(meta['original_size']) <= 262144 else 'gt_256KiB',
                                median_ms=statistics.median(row['elapsed_ns'] for row in trials)/1e6))
            if mode == 'instrumented_extract':
                per_context = defaultdict(lambda: [[], []])
                for trial in trials:
                    sums = defaultdict(lambda: [0, 0])
                    for call in trial['calls']:
                        key = (call['parent_function'] or '<root>', call['function'])
                        sums[key][0] += call['elapsed_ns']
                        sums[key][1] += call['self_ns']
                    for key, (inclusive, own) in sums.items():
                        per_context[key][0].append(inclusive)
                        per_context[key][1].append(own)
                for (parent, name), (inclusive, own) in sorted(per_context.items()):
                    r.require(len(inclusive) == len(own) == 5, 'Missing call context repeat')
                    call_rows.append(dict(sample_id=sample, parent_function=parent, function=name,
                                          median_inclusive_ms=statistics.median(inclusive)/1e6, median_self_ms=statistics.median(own)/1e6))
    write_csv(output / 'file_medians.csv', medians)
    write_csv(output / 'call_medians.csv', call_rows)
    summaries = []
    for field in ('all', 'format', 'origin_group_id', 'size_bin'):
        buckets = defaultdict(list)
        for row in medians:
            buckets[(row['mode'], 'all' if field == 'all' else row[field])].append(row['median_ms'])
        for (mode, group), values in sorted(buckets.items()):
            summaries.append(dict(group_kind=field, group=group, mode=mode, **distribution(values)))
    write_csv(output / 'summary.csv', summaries)
    by_key = {(row['sample_id'], row['mode']): row['median_ms'] for row in medians}
    overhead = [dict(sample_id=s, extract_ms=by_key[(s, 'extract_only')], instrumented_ms=by_key[(s, 'instrumented_extract')],
                     difference_ms=by_key[(s, 'instrumented_extract')]-by_key[(s, 'extract_only')]) for s in inventory]
    write_csv(output / 'observer_overhead.csv', overhead)
    lines = ['# 참조 특징 기준선 profile', '', '**관찰된 개발 corpus의 새 기준선이다. 최적화 성능 결과가 아니다.**', '',
             '| 모드 | 파일별 중앙값의 평균 ms | 중앙값 ms | p90 ms |', '|---|---:|---:|---:|']
    for row in summaries:
        if row['group_kind'] == 'all':
            lines.append(f"| {row['mode']} | {row['mean_ms']:.6f} | {row['median_ms']:.6f} | {row['p90_ms']:.6f} |")
    lines += ['', '함수별 inclusive/self는 call_medians.csv에 보존했다. 부모/자식 inclusive 값을 중복 합산하지 않는다. 계측 observer overhead는 별도 프로세스·고정 순서/cache 변동도 포함하므로 실제 성능 차이로 확정하지 않는다. 각 모드 중앙값을 더해 결합 시간을 만들지 않는다.', '',
              '전체 raw·warmup·원본/모델 hash·정확 feature/frame/prediction gate를 보존했다. Memory/codec/실제 GUI·cold start·최종 일반화 성능은 평가하지 않았다.', '']
    with (output / 'report.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines))
    # Recheck source/input hashes without re-running feature or model code.
    r.load_context()
    value = dict(status='independently_verified', verified_at_utc=r.now(), verifier_sha256=r.sha(Path(__file__)),
                 coverage=dict(corpus_files=len(inventory), modes=4, raw_slots=raw_count, warmups=warmups,
                               measurements=raw_count-warmups, predictions=len(predictions), file_medians=len(medians)),
                 artifact_sha256={p.relative_to(output).as_posix(): r.sha(p) for p in sorted(output.rglob('*')) if p.is_file()},
                 scope='Saved-trace exact gates and timing arithmetic, not a population or speedup certification')
    r.write_json(output / 'verification.json', value)
    return value


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_run(args.output, r.load_context())['coverage']))
