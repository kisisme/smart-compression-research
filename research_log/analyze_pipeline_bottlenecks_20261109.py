"""Read-only trace accounting; hypothetical timer removal is not a new benchmark."""
from collections import defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'data/results/usage_candidate_study_20261031_01'
MISSES = ROOT / 'data/results/usage_zstd_misses_20261031_01'
OUT = ROOT / 'data/results/usage_pipeline_bottlenecks_20261109_01'
REPORT = ROOT / 'research_log/pipeline_bottlenecks_20261109.md'
FREEZE = ROOT / 'research_log/usage_scenarios_frozen_20261031.json'
MODELS = ('decision_tree', 'random_forest')
ALGS = ('gzip', 'bz2', 'lzma', 'zstd')
TIMES = ('compression_ns', 'restoration_ns', 'feature_ns', 'prediction_ns')
TERMS = ('codec_selection_delta', 'package_metadata_delta', 'feature_cost', 'prediction_cost',
         'compression_remainder_delta', 'median_alignment_delta', 'restoration_remainder_delta')


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
        require(all(None not in r and None not in r.values() for r in rows), 'Malformed CSV')
        return rows


def index(rows, keys):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        require(key not in result, f'Duplicate key: {key}')
        result[key] = row
    return result


def near(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-10)


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


def aggregate(rows):
    """Per-file, per-strategy five-slot medians; do not sum separate medians."""
    require(len(rows) == 5 and sorted(int(r['repeat_index']) for r in rows) == [1, 2, 3, 4, 5], 'Repeat coverage')
    for row in rows:
        require(row['verified'] is True or row['verified'] == 'True', 'Unverified pipeline')
        require(all(int(row[k]) > 0 for k in ('compression_ns', 'restoration_ns', 'package_bytes')), 'Nonpositive pipeline')
        require(all(int(row[k]) >= 0 for k in ('feature_ns', 'prediction_ns')), 'Negative nested timer')
        require(int(row['compression_ns']) >= int(row['feature_ns']) + int(row['prediction_ns']), 'Nested timers exceed parent')
    for field in ('algorithm', 'package_bytes', 'payload_sha256', 'restored_sha256'):
        require(len({str(r[field]) for r in rows}) == 1, 'Inconsistent pipeline output')
    med = {k.replace('_ns', '_ms'): statistics.median(int(r[k]) for r in rows) / 1e6 for k in TIMES}
    rest = statistics.median(int(r['compression_ns']) - int(r['feature_ns']) - int(r['prediction_ns']) for r in rows) / 1e6
    med.update(compression_remainder_ms=rest,
               median_alignment_ms=med['compression_ms'] - med['feature_ms'] - med['prediction_ms'] - rest,
               without_feature_ms=statistics.median(int(r['compression_ns']) - int(r['feature_ns']) for r in rows) / 1e6,
               without_prediction_ms=statistics.median(int(r['compression_ns']) - int(r['prediction_ns']) for r in rows) / 1e6,
               without_both_ms=rest, package_bytes=int(rows[0]['package_bytes']), algorithm=rows[0]['algorithm'])
    return med


def cost(p, size, compression_ms, restoration_ms):
    return math.fsum(((p['storage_cost_per_byte_day'] * p['retention_days']) * size,
                      p['compression_cost_per_ms'] * compression_ms,
                      (p['decompression_cost_per_ms'] * p['expected_restorations']) * restoration_ms))


def decompose(p, observed, baseline, selected_codec, zstd_codec):
    ks = p['storage_cost_per_byte_day'] * p['retention_days']
    kc = p['compression_cost_per_ms']
    kd = p['decompression_cost_per_ms'] * p['expected_restorations']
    codec = lambda r: cost(p, int(r['compressed_size']), float(r['compression_time_ms']), float(r['decompression_time_ms']))
    delta = cost(p, observed['package_bytes'], observed['compression_ms'], observed['restoration_ms']) - cost(p, baseline['package_bytes'], baseline['compression_ms'], baseline['restoration_ms'])
    terms = dict(codec_selection_delta=codec(selected_codec) - codec(zstd_codec),
                 package_metadata_delta=ks * ((observed['package_bytes'] - int(selected_codec['compressed_size'])) - (baseline['package_bytes'] - int(zstd_codec['compressed_size']))),
                 feature_cost=kc * observed['feature_ms'], prediction_cost=kc * observed['prediction_ms'],
                 compression_remainder_delta=kc * ((observed['compression_remainder_ms'] - float(selected_codec['compression_time_ms'])) - (baseline['compression_ms'] - float(zstd_codec['compression_time_ms']))),
                 median_alignment_delta=kc * observed['median_alignment_ms'],
                 restoration_remainder_delta=kd * ((observed['restoration_ms'] - float(selected_codec['decompression_time_ms'])) - (baseline['restoration_ms'] - float(zstd_codec['decompression_time_ms']))))
    require(near(delta, math.fsum(terms.values())), 'Decomposition does not close')
    return delta, terms


def summarize(rows):
    base = math.fsum(r['baseline_pipeline_cost'] for r in rows)
    actual = math.fsum(r['pipeline_cost'] for r in rows)
    compression = math.fsum(r['compression_ms'] for r in rows)
    result = dict(file_count=len(rows), fixed_zstd_pipeline_cost=base, model_pipeline_cost=actual,
                  pipeline_cost_delta=actual-base, actual_saving_pct=100*(base-actual)/base,
                  mean_compression_ms=statistics.fmean(r['compression_ms'] for r in rows),
                  mean_restoration_ms=statistics.fmean(r['restoration_ms'] for r in rows),
                  mean_feature_ms=statistics.fmean(r['feature_ms'] for r in rows),
                  mean_prediction_ms=statistics.fmean(r['prediction_ms'] for r in rows),
                  feature_share_of_compression_pct=100*math.fsum(r['feature_ms'] for r in rows)/compression,
                  prediction_share_of_compression_pct=100*math.fsum(r['prediction_ms'] for r in rows)/compression,
                  measured_better_files=sum(r['pipeline_cost'] < r['baseline_pipeline_cost'] for r in rows))
    for term in TERMS:
        result[term] = math.fsum(r[term] for r in rows)
    require(near(result['pipeline_cost_delta'], math.fsum(result[t] for t in TERMS)), 'Aggregate decomposition')
    for name in ('feature', 'prediction', 'both'):
        total = math.fsum(r['without_' + name + '_cost'] for r in rows)
        result['hypothetical_without_' + name + '_saving_pct'] = 100*(base-total)/base
    return result


def render(summaries, coverage):
    prefix = '../data/results/' + OUT.name + '/'
    lines = ['# 후보 모델 전체 경로 비용 병목 진단 — 2026-11-09', '',
             '직전 실험의 저장 기록을 재집계했다. 특징 계산/입력 frame 준비가 모델 압축 경로의 가장 큰 직접 계측 구간이었다. RF에서는 예측 비용도 컸다. zstd 선택률 조정만으로 전체 경로 손실이 해결된다는 근거는 없다.', '',
             f"[18개 조건]({prefix}summary.csv) · [파일별 1,080개 분해]({prefix}file_decomposition.csv) · [1,140개 시간 중앙값]({prefix}trace_medians.csv) · [크기별]({prefix}size_summary.csv) · [원본 그룹별]({prefix}origin_summary.csv) · [감사]({prefix}audit.json) · [검증](../research_log/verify_pipeline_bottlenecks_20261109.py)", '',
             '## 측정 범위와 식', '',
             '원본 실측 source `6a75f98`, 실측 결과 보존 `f5fcb24`, 직전 누락 분석 `eea90af`의 동일 corpus 60개·9개 가상 정책·DT/RF를 사용했다. 새 압축·특징 계산·모델 예측·학습은 실행하지 않았다. 5,700개 trial은 19개 전략(고정 zstd+18개 모델 조건)×60개×5회다. 조건별 비교는 같은 파일의 저장된 fixed_zstd를 공유한다.', '',
             '`J = S·B + C·Tc + D·Tr`, `S=k_s·H`, `C=k_c`, `D=k_d·N`이다. 가상 정책점수이며 요금/에너지/메모리 비용이 아니다. 양의 delta는 모델 손실, 양의 saving은 고정 zstd 대비 이득이다. 정책마다 단위 교환비가 달라 조건들의 절대 비용을 합치지 않았다.', '',
             '`feature_ns`는 `extract_features`와 pandas frame 생성·schema/유한값 검사를 포함한다. `prediction_ns`는 predict 호출과 결과 문자열 변환이다. 압축 전체 시간은 읽기/hash→특징→예측→선택한 압축기 하나→복원 byte 검증→payload/manifest 저장을 포함한다. 복원 전체 시간에는 manifest/payload 읽기·hash·해제·원본 hash 검사·복원 파일 저장이 포함된다. 일부 사후 saved-byte 확인은 timer 밖이다.', '',
             '**검증·hash·읽기·쓰기의 개별 시간은 저장하지 않았다.** 이 항목들은 압축/복원 나머지 시간에 합쳐져 있다. 서로 다른 실행에서 측정한 codec 중앙값을 뺀 나머지는 음수가 될 수 있고 OS cache·순서·실행 간 변동도 포함하므로 순수 I/O 비용이나 인과 효과로 해석하지 않는다.', '',
             '## 18개 조건 전부', '',
             '| 조건 | 모델 | 평균 특징 ms | 평균 예측 ms | 특징/압축 전체 | 실제 비용 절감 | 특징 시간만 0 가정 | 두 시간 0 가정 |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        lines.append(f"| {r['scenario_id']} | {r['model']} | {r['mean_feature_ms']:.3f} | {r['mean_prediction_ms']:.3f} | {r['feature_share_of_compression_pct']:.2f}% | {r['actual_saving_pct']:.2f}% | {r['hypothetical_without_feature_saving_pct']:.2f}% | {r['hypothetical_without_both_saving_pct']:.2f}% |")
    lines += ['', '**시간 0 가정은 최적화한 프로그램의 실측값이 아니다.** 원래 trial별 압축 전체 ns에서 해당 내부 timer ns를 뺀 뒤 5회 중앙값을 다시 구했다. 선택 압축기·package bytes·복원 전체 시간은 그대로 둔, 해당 timer 제거에만 한정한 낙관적 계산이다. 전역적 성능 상한이나 새 모델의 성능을 뜻하지 않는다. 구현 후 동등성 확인과 새 계획의 실측이 필요하다.', '',
              f"전체 {len(summaries)}개 조건 중 특징 시간만 0으로 두어도 가상 비용이 여전히 불리한 조건은 {sum(r['hypothetical_without_feature_saving_pct'] < 0 for r in summaries)}개, 특징·예측을 모두 0으로 두어도 불리한 조건은 {sum(r['hypothetical_without_both_saving_pct'] < 0 for r in summaries)}개였다. 일부 동일 zstd 선택 조건에서도 나머지 시간 차이만으로 부호가 바뀐다. 이 변동을 압축기 선택 이득으로 해석하지 않는다.", '',
              '## 비용 차이의 장부 분해', '',
              '모델−고정 zstd 비용 차이를 다음 항목으로 보존했다. 파일별 합계와 조건별 합계가 원래 전체 경로 차이와 일치하는지 검사했다.', '',
              '| 항목 | 정의/범위 |', '|---|---|',
              '| codec_selection_delta | 기존 Compare의 선택 압축기 비용−zstd 비용 |',
              '| package_metadata_delta | codec payload 외 package bytes 비용의 모델−zstd 차이 |',
              '| feature_cost / prediction_cost | 각 내부 timer 중앙값×압축 시간 비용 계수 |',
              '| compression_remainder_delta | trial별 내부 timer를 뺀 중앙값에서 codec 시간을 제외한 양의/음의 차이 |',
              '| median_alignment_delta | 전체 중앙값−특징 중앙값−예측 중앙값−나머지 중앙값의 보정 |',
              '| restoration_remainder_delta | 복원 전체 중앙값에서 codec 해제 중앙값을 뺀 양의/음의 차이 |', '',
              '**중앙값은 더할 수 없다.** 따라서 나머지를 trial별로 계산하고, 독립 중앙값들의 합이 전체 중앙값과 달라지는 부분을 별도 항목으로 표시했다. 실제 최적화 가정도 전체 중앙값에서 특징 중앙값을 단순히 빼지 않는다.', '',
              '## codec 이득과 특징 예산', '',
              '| 조건 | 모델 | 실제 codec 절감 | codec oracle 최대 절감 | 관측 특징 비용 / oracle 이득 | 모델 load 중앙값 ms |',
              '|---|---|---:|---:|---:|---:|']
    for r in summaries:
        ratio = '이득 0' if r['feature_cost_to_oracle_gain'] is None else f"{r['feature_cost_to_oracle_gain']:.2f}배"
        lines.append(f"| {r['scenario_id']} | {r['model']} | {r['codec_saving_pct']:.4f}% | {r['codec_oracle_saving_pct']:.4f}% | {ratio} | {r['model_load_median_ms']:.3f} |")
    lines += ['', 'oracle 이득은 모든 codec 측정값을 아는 이상적 선택의 비용 절감이다. 특징 예산 비교는 codec 범위의 낙관적 점검이며 engine에서 이득을 보장하지 않는다. Load는 기존 warm 시간 밖의 별도 5회 read/hash/deserialization 측정이다. 파일마다 load 비용을 더한 기존 proxy는 검산했지만 실제 cold start나 batch amortization을 새로 측정하지 않았다.', '',
              '## 후속 작업 판단', '',
              '우선 기존 12개 특징의 의미/순서/값을 보존하는 특징 계산 최적화를 검토할 근거가 있다. 소스에는 run/bigram/block/segment 통계 계산에 여러 순회가 있으나 개별 함수 timer가 없어 어느 함수가 가장 느린지는 이번 기록으로 순위를 확정할 수 없다. 먼저 별도 계획에서 함수별 profile과 정확한 출력 동등성을 확인하는 것이 다음 단일 작업이다. RF 예측 overhead도 함께 확인하되 모델 변경/재학습은 별도 연구 결정이다.', '',
              '기존 57개 zstd 누락과 반대 방향 74개 손실은 이전 보고서에 그대로 남긴다. 선택 비율 quota·사후 계수 조정으로 해결하지 않는다. 관찰된 60개는 후속 튜닝의 개발 자료이며 최종 성능 평가는 다른 원본 그룹의 holdout이 필요하다.', '',
              f"원본 그룹 동일 비중의 기존 주 평가량을 바꾸지 않았다. 이번 분해의 시간/비용 표는 전체 파일 합계의 기술 통계다. 크기 구간은 ≤64KiB, (64,256]KiB, >256KiB로 명시했고 빈 구간은 만들지 않았다. 저장된 원본 그룹별 분해도 보존했다. 새 평가 시나리오를 고르거나 표본을 제외하지 않았다.", '',
              '## 검증과 보존', '',
              f"원시 {coverage['trial_count']}개 trial의 고유 key·5회 완전성·verified·원본 hash·동일 출력·timer 포함 관계를 검사했다. 사전 예측과 각 trial의 압축기가 일치하고 저장 codec 측정이 정상 검증됐음을 확인했다. 기존 pipeline_metrics의 18개 조건 전체 시간/비용·load proxy를 검산했다. 파일별 1,080개와 조건별 비용 분해가 닫히고, 모든 timer 제거 가정은 trial별 계산으로 검산했다.", '',
              '기존 study·57건 분석·공식 기준/config·관련 source의 실행 전후 hash를 보존했다. 별도 독립 검증기는 저장 원시 trial에서 전체/가정 비용을 다시 계산한다. 기존 공식 모델/score·memory validation_only·실제 GUI 미완료 항목을 유지했다. 연구용 상주 엔진이며 Python 시작·cold cache·fsync·대용량/스트리밍·실제 배포 성능이나 통계적 유의성을 입증하지 않는다.', '']
    return '\n'.join(lines)


def main():
    require(not OUT.exists() and not REPORT.exists(), 'Refuse to overwrite diagnostic')
    protected = {p.relative_to(ROOT).as_posix(): sha(p) for directory in (STUDY, MISSES) for p in sorted(directory.rglob('*')) if p.is_file()}
    for name in ('research_protocol_v2.md', 'config/experiment_config.json', 'src/feature_extractor.py',
                 'research_log/run_usage_model_study_20261031.py', FREEZE.relative_to(ROOT).as_posix()):
        protected[name] = sha(ROOT / name)
    previous = json.loads((MISSES / 'audit.json').read_bytes())
    for name, digest in {**previous['protected_input_sha256'], **previous['output_sha256']}.items():
        require(sha(ROOT / name) == digest, f'Prior verified evidence changed: {name}')
    metadata = {r['sample_id']: r for r in json.loads((STUDY / 'corpus/manifest.json').read_bytes())['candidates'] if r['selection_status'] == 'selected'}
    definitions = {s['id']: {k: float(v) for k, v in s['policy'].items()} for s in json.loads(FREEZE.read_bytes())['expanded_cost_scenarios']}
    require(len(metadata) == 60 and len(definitions) == 9, 'Frozen corpus/scenario coverage')
    strategies = {'fixed_zstd'} | {s + '__' + m for s in definitions for m in MODELS}
    raw = read_csv(STUDY / 'pipeline/raw_trials.csv')
    slots = index(raw, ('sample_id', 'strategy', 'repeat_index'))
    require(set(slots) == {(s, st, str(i)) for s in metadata for st in strategies for i in range(1, 6)}, 'Trial slot coverage')
    predictions = index(read_csv(STUDY / 'predictions/frozen_predictions.csv'), ('sample_id', 'scenario_id', 'model'))
    require(set(predictions) == {(s, sid, m) for s in metadata for sid in definitions for m in MODELS}, 'Frozen prediction coverage')
    measurements = index(read_csv(STUDY / 'benchmark/compression_results.csv'), ('sample_id', 'algorithm'))
    require(set(measurements) == {(s, a) for s in metadata for a in ALGS}, 'Codec coverage')
    require(all(r['verified'] == 'True' and r['status'] == 'ok' and not r['error'] for r in measurements.values()), 'Failed codec')
    recorded = index(read_csv(STUDY / 'evaluation/pipeline_metrics.csv'), ('scenario_id', 'model'))
    require(set(recorded) == {(s, m) for s in definitions for m in MODELS}, 'Metric coverage')
    codecs = json.loads((STUDY / 'evaluation/codec_metrics.json').read_bytes())
    load_raw = index(read_csv(STUDY / 'pipeline/model_load_repeats.csv'), ('scenario_id', 'model', 'repeat_index'))
    require(set(load_raw) == {(sid, m, str(i)) for sid in definitions for m in MODELS for i in range(1, 6)}, 'Load coverage')
    medians, trace_rows = {}, []
    for s in sorted(metadata):
        for strategy in sorted(strategies):
            rows = [slots[(s, strategy, str(i))] for i in range(1, 6)]
            expected = 'zstd' if strategy == 'fixed_zstd' else predictions[(s, *strategy.split('__'))]['predicted_algorithm']
            require(all(r['algorithm'] == expected and r['restored_sha256'] == metadata[s]['input_sha256'] for r in rows), 'Trial identity/prediction drift')
            if strategy == 'fixed_zstd':
                require(all(int(r['feature_ns']) == int(r['prediction_ns']) == 0 for r in rows), 'Unexpected baseline overhead')
            value = aggregate(rows)
            require(value['package_bytes'] >= int(measurements[(s, expected)]['compressed_size']), 'Package smaller than measured payload')
            medians[(s, strategy)] = value
            trace_rows.append(dict(sample_id=s, strategy=strategy, candidate_id=metadata[s]['candidate_id'], **value))
    files, summaries = [], []
    for sid, policy in definitions.items():
        for model in MODELS:
            subset = []
            for s, meta in metadata.items():
                observed, base = medians[(s, sid + '__' + model)], medians[(s, 'fixed_zstd')]
                selected, zstd = measurements[(s, observed['algorithm'])], measurements[(s, 'zstd')]
                delta, terms = decompose(policy, observed, base, selected, zstd)
                codec_zstd = cost(policy, int(zstd['compressed_size']), float(zstd['compression_time_ms']), float(zstd['decompression_time_ms']))
                oracle = min(cost(policy, int(measurements[(s, a)]['compressed_size']), float(measurements[(s, a)]['compression_time_ms']), float(measurements[(s, a)]['decompression_time_ms'])) for a in ALGS)
                row = dict(sample_id=s, scenario_id=sid, model=model, candidate_id=meta['candidate_id'], format=meta['format'],
                           origin_group_id=meta['origin_group_id'], original_size=meta['original_size'],
                           size_bin='le_64KiB' if meta['original_size'] <= 65536 else '64_to_256KiB' if meta['original_size'] <= 262144 else 'gt_256KiB',
                           **observed, baseline_pipeline_cost=cost(policy, base['package_bytes'], base['compression_ms'], base['restoration_ms']),
                           pipeline_cost=cost(policy, observed['package_bytes'], observed['compression_ms'], observed['restoration_ms']),
                           pipeline_cost_delta=delta, codec_zstd_cost=codec_zstd, codec_oracle_gain=codec_zstd-oracle, **terms)
                for name in ('feature', 'prediction', 'both'):
                    row['without_' + name + '_cost'] = cost(policy, observed['package_bytes'], observed['without_' + name + '_ms'], observed['restoration_ms'])
                files.append(row)
                subset.append(row)
            summary = dict(scenario_id=sid, model=model, **summarize(subset))
            codec_base = math.fsum(r['codec_zstd_cost'] for r in subset)
            oracle_gain = math.fsum(r['codec_oracle_gain'] for r in subset)
            load_values = [int(load_raw[(sid, model, str(i))]['elapsed_ns']) / 1e6 for i in range(1, 6)]
            require(min(load_values) > 0, 'Invalid model load')
            summary.update(codec_saving_pct=-100*summary['codec_selection_delta']/codec_base,
                           codec_oracle_saving_pct=100*oracle_gain/codec_base,
                           feature_cost_to_oracle_gain=summary['feature_cost']/oracle_gain if oracle_gain else None,
                           model_load_median_ms=statistics.median(load_values))
            old = recorded[(sid, model)]
            for field, original in (('fixed_zstd_pipeline_cost', 'fixed_zstd_pipeline_cost_sum'), ('model_pipeline_cost', 'model_pipeline_cost_sum'),
                                    ('actual_saving_pct', 'warm_pipeline_cost_saving_pct'), ('mean_feature_ms', 'mean_feature_ms'),
                                    ('mean_prediction_ms', 'mean_prediction_ms'), ('model_load_median_ms', 'median_verified_model_load_ms')):
                require(near(summary[field], old[original]), f'Original metric mismatch: {field}')
            require(near(summary['codec_saving_pct'], codecs[sid][model]['cost_saving_pct_vs_zstd']), 'Codec metric mismatch')
            require(near(summary['model_pipeline_cost'] + policy['compression_cost_per_ms']*summary['model_load_median_ms']*len(subset), old['load_inclusive_cost_proxy_sum']), 'Original load proxy mismatch')
            summaries.append(summary)
    coverage = dict(file_count=len(metadata), scenario_count=len(definitions), model_conditions=len(summaries), trial_count=len(raw),
                    trace_medians=len(trace_rows), decomposition_rows=len(files), load_repeat_count=len(load_raw))
    require(coverage['decomposition_rows'] == 1080, 'Missing file decomposition')
    OUT.mkdir(parents=True)
    for name, rows in (('trace_medians.csv', trace_rows), ('file_decomposition.csv', files), ('summary.csv', summaries)):
        write_csv(OUT / name, rows)
    for field, name in (('size_bin', 'size_summary.csv'), ('origin_group_id', 'origin_summary.csv')):
        groups = defaultdict(list)
        for r in files:
            groups[(r['scenario_id'], r['model'], r[field])].append(r)
        write_csv(OUT / name, [dict(scenario_id=k[0], model=k[1], **{field: k[2]}, **summarize(rows)) for k, rows in sorted(groups.items())])
    with REPORT.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(render(summaries, coverage))
    for name, digest in protected.items():
        require(sha(ROOT / name) == digest, f'Protected file changed: {name}')
    write_json(OUT / 'audit.json', dict(status='trace_accounting_verified', created_at_utc=datetime.now(timezone.utc).isoformat(),
               source_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               python=sys.version, platform=platform.platform(), analyzer_sha256=sha(Path(__file__)), coverage=coverage,
               scope='Developmental reanalysis of existing warm-engine trials; no new benchmarks or optimization claims',
               limitations=['Verification/hash/read/write not separately timed', 'Median alignment explicit',
                            'Counterfactual timer removal recalculated per trial', 'Fixed order/cache confounding',
                            '60 files already observed; new groups needed for final tuning evaluation'],
               protected_input_sha256=protected,
               output_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in (*sorted(OUT.glob('*.csv')), REPORT)}))
    print(json.dumps(dict(coverage=coverage,
                         feature_mean_ms_range=[min(r['mean_feature_ms'] for r in summaries), max(r['mean_feature_ms'] for r in summaries)],
                         feature_share_pct_range=[min(r['feature_share_of_compression_pct'] for r in summaries), max(r['feature_share_of_compression_pct'] for r in summaries)],
                         negative_without_feature=sum(r['hypothetical_without_feature_saving_pct'] < 0 for r in summaries),
                         negative_without_both=sum(r['hypothetical_without_both_saving_pct'] < 0 for r in summaries)), ensure_ascii=False))


if __name__ == '__main__':
    main()
