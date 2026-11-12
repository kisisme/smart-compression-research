"""Independent saved-record audit and full descriptive paired reports; no timing calls."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics as st
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_log import feature_profile_runtime_20261111 as r
from research_log import run_feature_pairs_20261111 as runner


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def table(path, rows):
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def audit_calls(slots, rows, expected, inventory):
    r.require(len(rows) == len(slots)*2, 'Incomplete/extra calls')
    deltas = []
    previous_end = 0
    for index, slot in enumerate(slots):
        pair = rows[2*index:2*index+2]
        for position, row in zip(('first', 'second'), pair, strict=True):
            r.require(all(row[k] == v for k, v in slot.items()), 'Schedule mismatch')
            r.require(row['position'] == position and row['variant'] == slot[position], 'Order mismatch')
            r.require(row['status'] == 'ok' and row['data_kind'] == 'observed_development_corpus', 'Call failed/wrong scope')
            r.require(row['input_sha256'] == inventory[slot['sample_id']]['input_sha256'], 'Input hash mismatch')
            r.require(row['features'] == expected[slot['sample_id']], 'Feature mismatch')
            wanted = [float(int(v) if kind == 'int' else float.fromhex(v)).hex()
                      for _, kind, v in expected[slot['sample_id']]] if slot['mode'] == 'extract_and_frame' else None
            r.require(row['frame'] == wanted, 'Frame mismatch')
            r.require(all(type(row[k]) is int for k in ('start_ns', 'end_ns', 'elapsed_ns')), 'Timer type')
            r.require(previous_end <= row['start_ns'] < row['end_ns'], 'Overlapping/reversed calls')
            r.require(row['end_ns']-row['start_ns'] == row['elapsed_ns'], 'Elapsed mismatch')
            previous_end = row['end_ns']
        values = {v['variant']: v['elapsed_ns'] for v in pair}
        deltas.append(dict(slot, delta_ns=values[slot['comparison']]-values['reference'],
                           reference_ns=values['reference'], candidate_ns=values[slot['comparison']]))
    return deltas


def summary(files):
    groups = defaultdict(list)
    for row in files:
        groups[row['origin_group_id']].append(row['paired_median_delta_ns'])
    reference = sum(row['reference_median_ns'] for row in files)
    candidate = sum(row['candidate_median_ns'] for row in files)
    return dict(files=len(files), origins=len(groups),
                equal_origin_mean_paired_delta_ns=st.fmean(st.fmean(v) for v in groups.values()),
                pooled_median_ratio=reference/candidate, saving_percent=100*(reference-candidate)/reference,
                reference_mean_file_median_ms=reference/len(files)/1e6,
                candidate_mean_file_median_ms=candidate/len(files)/1e6,
                improved=sum(v['paired_median_delta_ns'] < 0 for v in files),
                regressed=sum(v['paired_median_delta_ns'] > 0 for v in files),
                tied=sum(v['paired_median_delta_ns'] == 0 for v in files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.input.resolve(), args.output.resolve()
    ctx, plan, schedule = runner.context()
    r.require(not output.exists(), 'Refuse overwrite')
    r.require(not (source/'failure.json').exists(), 'Failed run')
    before = {p.name:r.sha(p) for p in source.iterdir() if p.is_file()}
    complete = json.loads((source/'complete.json').read_bytes())
    verification = json.loads((source/'verification.json').read_bytes())
    r.require(complete['status'] == 'paired_run_verified' and complete['verification_sha256'] == r.sha(source/'verification.json'), 'Completion mismatch')
    r.require(verification['status'] == 'all_pairs_verified', 'Unverified pair run')
    r.require(set(before) == set(verification['artifact_sha256']) | {'verification.json','complete.json'}, 'Run file set mismatch')
    for name, digest in verification['artifact_sha256'].items():
        r.require(before[name] == digest, 'Run artifact mismatch')
    lock = json.loads(runner.LOCK.read_bytes())
    protected = {**lock['protected_input_sha256'], **lock['source_sha256']}
    for name, digest in protected.items():
        r.require(r.sha(ROOT/name) == digest, 'Protected input changed: '+name)
    started = json.loads((source/'started.json').read_bytes())
    r.require(started['implementation_sha256'] == r.sha(runner.LOCK), 'Start lock differs')
    frozen_predictions = r.read_csv(r.FREEZE/'expected_predictions.csv')
    expected_predictions = {}
    for v in frozen_predictions:
        key = (v['sample_id'], v['scenario_id'], v['model'])
        item = {k:float(v[k]).hex() for k in ('uncalibrated_confidence', 'probability_gzip', 'probability_bz2', 'probability_lzma', 'probability_zstd')}
        expected_predictions[key] = dict(sample_id=key[0], scenario_id=key[1], model=key[2],
                                        model_sha256=v['model_sha256'], status='ok', predicted_algorithm=v['predicted_algorithm'], **item)
    for variant in ('reference', 'bigram_numpy', 'run_numpy', 'both_numpy'):
        rows = jsonl(source/(variant+'_predictions.jsonl'))
        keys = [(v['sample_id'],v['scenario_id'],v['model']) for v in rows]
        r.require(len(rows) == len(set(keys)) == len(expected_predictions), 'Prediction coverage')
        r.require(all(v == expected_predictions[k] for k,v in zip(keys,rows)), 'Prediction mismatch')
    inventory = {v['sample_id']:v for v in ctx['inventory']}
    all_deltas, files, summaries, breakdowns, order = [], [], [], [], []
    saved_summary = json.loads((source/'summary.json').read_bytes())
    r.require(len(saved_summary) == 6 and saved_summary == verification['summaries'], 'Saved summary coverage differs')
    for candidate in ('bigram_numpy', 'run_numpy', 'both_numpy'):
        for mode in ('extract_only','extract_and_frame'):
            prefix = candidate+'__'+mode
            process = json.loads((source/(prefix+'_process.json')).read_bytes())
            r.require(process['returncode'] == 0 and process['command'][-3:] == [mode, '--output', str(source)], 'Worker failure/command mismatch')
            slots = [v for v in schedule if v['comparison'] == candidate and v['mode'] == mode]
            deltas = audit_calls(slots,jsonl(source/(prefix+'.jsonl')),ctx['expected'],inventory)
            all_deltas.extend(deltas)
            measured = [v for v in deltas if v['is_warmup'] == 'False']
            current = []
            for sample, meta in inventory.items():
                pairs = [v for v in measured if v['sample_id'] == sample]
                r.require(len(pairs) == 6 and sum(v['first'] == 'reference' for v in pairs) == 3, 'Unbalanced file pairs')
                size = int(meta['original_size'])
                current.append(dict(candidate=candidate, mode=mode, sample_id=sample,
                                    origin_group_id=meta['origin_group_id'], format=meta['format'], original_size=size,
                                    size_bin='<=64KiB' if size <= 65536 else '(64,256]KiB' if size <= 262144 else '>256KiB',
                                    paired_median_delta_ns=st.median(v['delta_ns'] for v in pairs),
                                    reference_median_ns=st.median(v['reference_ns'] for v in pairs),
                                    candidate_median_ns=st.median(v['candidate_ns'] for v in pairs)))
            result = dict(candidate=candidate,mode=mode,**summary(current))
            result['advance_to_pipeline'] = candidate == 'both_numpy' and mode == 'extract_and_frame' and result['equal_origin_mean_paired_delta_ns'] < 0 and result['pooled_median_ratio'] > 1
            original = next(v for v in saved_summary if v['candidate'] == candidate and v['mode'] == mode)
            r.require(all(result[k] == v for k,v in original.items()), 'Independent summary differs')
            summaries.append(result)
            files.extend(current)
            for dimension in ('origin_group_id','format','size_bin'):
                for value in sorted({v[dimension] for v in current}):
                    breakdowns.append(dict(candidate=candidate, mode=mode, dimension=dimension, value=value,
                                           **summary([v for v in current if v[dimension] == value])))
            for first in ('reference',candidate):
                values = [v['delta_ns'] for v in measured if v['first'] == first]
                order.append(dict(candidate=candidate,mode=mode,first=first,pairs=len(values),
                                  mean_delta_ns=st.fmean(values),median_delta_ns=st.median(values),
                                  regressed=sum(v>0 for v in values),tied=sum(v==0 for v in values)))
    r.require(before == {p.name:r.sha(p) for p in source.iterdir() if p.is_file()}, 'Run changed during audit')
    for name, digest in protected.items():
        r.require(r.sha(ROOT/name) == digest, 'Protected input changed during audit')
    output.mkdir(parents=True,exist_ok=False)
    for name,rows in (('pairs.csv',all_deltas),('files.csv',files),('summary.csv',summaries),('breakdowns.csv',breakdowns),('order.csv',order)):
        table(output/name,rows)
    primary = next(v for v in summaries if v['candidate'] == 'both_numpy' and v['mode'] == 'extract_and_frame')
    lines = ['# 정확 특징 NumPy 후보의 paired 측정 결과 — 2026-11-12', '',
             '실제 개발 corpus의 저장 기록을 Python으로 독립 검증·집계했다. 공식 특징 추출기·모델·score는 변경하지 않았다.', '',
             f"실측 실행 HEAD: `{started['git_head']}`. 보호 근거 {len(protected)}개 파일은 불변이다.", '',
             '## 전체 결과', '',
             '| 후보 | 범위 | 참조 평균 ms | 후보 평균 ms | 그룹 동일 비중 paired 차이 ms | 중앙값 합 비율 | 절감률 % | 개선/악화/동점 파일 |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for v in summaries:
        lines.append(f"| {v['candidate']} | {v['mode']} | {v['reference_mean_file_median_ms']:.6f} | {v['candidate_mean_file_median_ms']:.6f} | {v['equal_origin_mean_paired_delta_ns']/1e6:.6f} | {v['pooled_median_ratio']:.6f} | {v['saving_percent']:.4f} | {v['improved']}/{v['regressed']}/{v['tied']} |")
    lines += ['', '참조/후보 평균은 각각 파일별 6회 중앙값의 평균이다. 주 지표는 인접 pair 차이의 파일별 중앙값 → 원본 그룹 내 평균 → 그룹 동일 비중 평균이다. 두 독립 중앙값의 차이로 대체하지 않았다.', '',
              f"사전 주 비교 both_numpy/extract_and_frame의 다음 단계 조건 충족: **{primary['advance_to_pipeline']}**. 이 판정은 별도 전체 경로 검증을 진행할 근거이며 공식 채택·통계적 유의성·최종 일반화 성능을 뜻하지 않는다.", '',
              '## 검증과 범위', '',
              f"60개 원본의 hash/특징/frame 및 네 버전 각각 {len(expected_predictions)}개 기존 모델 예측·확률·비보정 confidence를 대조했다. 본 호출 {sum(v['is_warmup']=='False' for v in all_deltas)*2}회와 warmup {sum(v['is_warmup']=='True' for v in all_deltas)*2}회가 고정 일정·순서·timer·worker 종료 검증을 통과했다. 매 파일 본 pair는 참조 먼저 3회/후보 먼저 3회다. 실패/재시도·이상치 삭제·파일 교체는 없다.", '',
              '[파일별 전체 결과](files.csv) · [모든 pair와 warmup](pairs.csv) · [형식·원본 그룹·고정 크기 구간](breakdowns.csv) · [순서별 진단](order.csv) · [독립 감사 manifest](analysis.json)', '',
              '악화·동점도 전체 표에 포함했다. 기존 기준선과 다른 시점의 시간을 빼서 개선으로 해석하지 않고, 이번 paired 비교만 사용한다. 메모리 상주 bytes에서 특징과 배열/frame 할당을 측정했고 읽기/hash·모델 loading/예측·기록은 timer 밖이다.', '',
              f"실행 중 외부 사건에 관한 기록: {started['notes']}", '',
              '공식 src/feature_extractor.py, config/모델/라벨 및 기존 측정은 유지했다. Memory는 validation_only 보류 상태다. 이번 파일은 이미 사용한 개발 corpus이며 cold-start/실제 Smart 전체 경로/GUI/새 원본 그룹 holdout을 검증한 결과가 아니다.', '',
              '다음 단일 작업은 조건 충족 시 전체 경로의 추론·압축·복원·검증·저장을 포함하는 별도 비교 계획을 먼저 고정하는 것이다. 주 후보를 사후 보조 후보로 바꾸지 않는다.', '']
    with (output/'report.md').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(lines))
    r.write_json(output/'analysis.json',dict(status='independently_verified',at_utc=r.now(),
                 execution_git_head=started['git_head'],source_sha256=r.sha(Path(__file__)),input_sha256=before,
                 protected_files=len(protected),summaries=summaries,measured_calls=sum(v['is_warmup']=='False' for v in all_deltas)*2,
                 warmup_calls=sum(v['is_warmup']=='True' for v in all_deltas)*2,
                 prediction_records_per_variant=len(expected_predictions),artifact_sha256={p.name:r.sha(p) for p in output.iterdir()}))
    print(json.dumps(summaries,indent=2))


if __name__ == '__main__':
    main()
