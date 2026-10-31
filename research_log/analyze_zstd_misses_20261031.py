"""Exhaustive, read-only diagnosis of frozen predictions; no codecs or models run."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
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
sys.path.insert(0, str(ROOT))
from src.usage_objectives import ALGORITHMS, LifetimePolicy, evaluate_lifetime_cost

STUDY = ROOT / 'data/results/usage_candidate_study_20261031_01'
OUT = ROOT / 'data/results/usage_zstd_misses_20261031_01'
REPORT = ROOT / 'research_log/zstd_misses_20261031.md'
FREEZE = ROOT / 'research_log/usage_scenarios_frozen_20261031.json'
MODELS = ('decision_tree', 'random_forest')


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


def index_unique(rows, keys):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        require(key not in result, f'Duplicate key: {key}')
        result[key] = row
    return result


def classify(costs):
    """Strict binary64 comparisons, including non-best but better alternatives."""
    require(set(costs) == set(ALGORITHMS), 'All four codecs required')
    require(all(math.isfinite(v) and v > 0 for v in costs.values()), 'Invalid cost')
    best = min(ALGORITHMS, key=costs.__getitem__)
    better = [a for a in ALGORITHMS if costs[a] < costs['zstd']]
    equal = [a for a in ALGORITHMS if a != 'zstd' and costs[a] == costs['zstd']]
    return best, better, equal


def independent_components(row, policy):
    """Recompute from serialized measurements, separate from production scorer."""
    p = {k: float(v) for k, v in policy.items()}
    parts = dict(storage=(p['storage_cost_per_byte_day'] * p['retention_days']) * int(row['compressed_size']),
                 compression=p['compression_cost_per_ms'] * float(row['compression_time_ms']),
                 restoration=(p['decompression_cost_per_ms'] * p['expected_restorations']) * float(row['decompression_time_ms']))
    f = Fraction
    exact = (f(policy['storage_cost_per_byte_day']) * f(policy['retention_days']) * int(row['compressed_size'])
             + f(policy['compression_cost_per_ms']) * f(row['compression_time_ms'])
             + f(policy['decompression_cost_per_ms']) * f(policy['expected_restorations']) * f(row['decompression_time_ms']))
    require(math.isclose(math.fsum(parts.values()), float(exact), rel_tol=1e-12, abs_tol=1e-12), 'Fraction audit')
    return parts


def validate_choice(row, costs, prediction, metadata):
    best, _, _ = classify(costs)
    require(row['true_algorithm'] == best, 'Frozen oracle mismatch')
    require(row['chosen_algorithm'] == prediction['predicted_algorithm'], 'Frozen prediction mismatch')
    require(row['format'] == metadata['format'] and row['origin_group_id'] == metadata['origin_group_id'], 'Metadata mismatch')
    # Serialized floats round-trip exactly; tolerance is not used for selection.
    for field, value in (('policy_cost', costs[row['chosen_algorithm']]), ('oracle_cost', costs[best]),
                         ('zstd_cost', costs['zstd']), ('regret', costs[row['chosen_algorithm']] - costs[best])):
        require(float(row[field]) == value, f'Saved {field} mismatch')


def write_csv(path, rows, fields=None):
    require(bool(rows) or fields, 'Empty output needs explicit schema')
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def pct(n, d):
    return 100 * n / d if d else None


def validate_repeat_status(row, phase, input_sha256):
    require(row['status'] == 'ok' and not row['error'], 'Failed repeat')
    if phase == 'compress':
        require(row['consistent_with_reference'] == 'True', 'Inconsistent compressed output')
    elif phase == 'decompress':
        require(row['verified'] == 'True' and row['output_sha256'] == input_sha256, 'Restored identity')
    else:
        raise ValueError('Unknown repeat phase')


def render_report(cases, alternatives, summaries, files, metadata, repeat_stats, coverage):
    prefix = '../data/results/' + OUT.name + '/'
    lines = ['# zstd 선택의 누락 사례 전수 분석 — 2026-10-31', '',
             f"후보 모델의 사전 동결 예측 {coverage['prediction_count']}건을 모두 대조했다. zstd 선택 {coverage['zstd_choices']}건 중 다른 압축기의 가상 정책 비용이 엄격히 낮았던 경우는 **{len(cases)}건**이다. 중복을 제거하면 **파일 {len(files)}개·파일×시나리오 {coverage['missed_file_scenarios']}개**다. 같은 파일을 두 모델/여러 시나리오가 반복 평가하므로 독립적인 파일 수와 구분한다.", '',
             '범위는 직전 실험의 실제 파일 60개×가상 비용 시나리오 9개×DT/RF다. ‘다른 모델’은 비교 압축기 gzip/bz2/LZMA로 해석했다. 공식 v2 저장 모델의 별도 외부 평가가 아니다. 새 압축·학습·예측은 수행하지 않았다.', '',
             f"[전체 누락 {len(cases)}건]({prefix}missed_cases.csv) · [더 좋았던 대안 전부 {len(alternatives)}건]({prefix}better_alternatives.csv) · [중복 제거 파일]({prefix}unique_files.csv) · [18개 조건 요약]({prefix}scenario_model_summary.csv) · [원시 반복 범위]({prefix}timing_repeat_summary.csv) · [검증 근거]({prefix}audit.json)", '',
             '## 판정과 비용', '',
             '`J = k_s H B + k_c T_c + k_d N T_d`를 고정된 정책과 저장된 크기/압축 시간/복원 시간 중앙값으로 재계산했다. `모델 예측=zstd`이고 `J(대안)<J(zstd)`일 때만 누락이다. 최저 비용이 아닌 대안도 zstd보다 좋으면 전부 포함한다. 정확 동점은 누락에서 제외하며 작은 차이를 지우는 epsilon은 쓰지 않는다. 이 비율은 압축률이나 실제 요금이 아니라 가상 정책 비용 절감률이다.', '',
             'Archive는 365일 보관·1회 복원, Balanced는 30일·30회, Fast Access는 1일·100회다. `t0p1/t1/t10`은 압축·복원 시간 비용의 0.1/1/10배다. 공식 가중치·memory·모델을 변경하지 않았다.', '',
             '## 전체 조건', '',
             '| 조건 | 모델 | zstd 선택/60 | zstd 누락/선택 | zstd 최저 비용 동점 | 잘못 바꾼 비-zstd |',
             '|---|---|---:|---:|---:|---:|']
    for r in summaries:
        lines.append(f"| {r['scenario_id']} | {r['model']} | {r['zstd_choices']} | {r['missed_cases']} | {r['zstd_optimal_tie_cases']} | {r['non_zstd_strictly_worse_than_zstd']} |")
    lines += ['', '‘잘못 바꾼 비-zstd’는 모델이 다른 압축기를 선택했지만 고정 zstd보다 비용이 큰 경우다. zstd 비중을 낮추기만 하면 이 손실도 늘 수 있다. 조건별 절대 비용 합계는 서로 다른 정책끼리 더하지 않는다.', '',
              '## 중복 제거 파일 전체', '',
              '| 파일 ID / 이름 | 형식 | 놓친 예측 수 | 최저 비용 압축기 | 파일별 절감 범위 |', '|---|---|---:|---|---:|']
    for r in files:
        lines.append(f"| {r['candidate_id']} / {r['original_filename']} | {r['format']} | {r['missed_cases']} | {r['best_algorithms']} | {r['min_saving_pct']:.4f}~{r['max_saving_pct']:.4f}% |")
    lines += ['', '같은 이름의 package.json/log는 파일 ID가 다르다. CSV의 상대 경로·full SHA-256·고정 source locator로 구분한다.', '',
              '## 누락 57건의 전체 목록', '',
              '절감률은 해당 파일에서 `(J(zstd)−J(최저 비용))/J(zstd)×100`이다. 더 좋았던 대안은 최저 비용 순서가 아니라 고정 압축기 순서로 나열했다. 원래 float 정밀도 비용과 압축 크기/시간/성분별 차이는 CSV에 보존했다.', '',
              '| 조건 | 모델 | 파일 ID | 최저 비용 | 더 좋은 대안 전부 | 절감률 |', '|---|---|---|---|---|---:|']
    for r in cases:
        lines.append(f"| {r['scenario_id']} | {r['model']} | {r['candidate_id']} | {r['best_algorithm']} | {r['better_algorithms']} | {r['saving_pct']:.4f}% |")
    lines += ['', '## 읽을 수 있는 패턴과 한계', '']
    archive = [r for r in cases if r['scenario_id'] == 'archive_t0p1']
    lines.append(f"Archive 시간 비용 0.1배에서 누락 {len(archive)}건이 발생했다. 여기서 최저 비용 압축기별 누락은 {dict(Counter(r['best_algorithm'] for r in archive))}이다. 이는 저장 크기의 이득으로 시간 손실을 상쇄하는 경우를 포함한다. 나머지 Archive 조건에서는 더 나은 비-zstd가 없었다.")
    lines += ['', '여러 조건에서 반복된 아래 두 파일은 크기만으로 설명되지 않는다. 아래 표는 측정 중앙값이며, 시간의 단위는 ms다.', '',
              '| 파일 | 압축기 | 압축 bytes | 압축 ms | 복원 ms |', '|---|---|---:|---:|---:|']
    for candidate in ('curl_01', 'mlperf_inference_03'):
        sample = next(s for s, m in metadata.items() if m['candidate_id'] == candidate)
        for alg in ALGORITHMS:
            c = next(r for r in repeat_stats if r['sample_id'] == sample and r['algorithm'] == alg and r['phase'] == 'compress')
            d = next(r for r in repeat_stats if r['sample_id'] == sample and r['algorithm'] == alg and r['phase'] == 'decompress')
            lines.append(f"| {candidate} | {alg} | {c['output_size']} | {c['median_ms']:.4f} | {d['median_ms']:.4f} |")
    lines += ['', '특히 반복 복원이 많은 정책에서는 측정된 복원 시간 차이가 누적된다. 이 두 파일의 정확한 차이는 대안 CSV와 원시 반복 범위에서 확인할 수 있다. 저장된 5회 반복 중앙값 기준의 기술적 결과이며, 측정 순서/OS cache·작은 시간 차이의 재현성·통계적 유의성은 이 분석만으로 확정하지 않는다. 원시 반복을 삭제하거나 재선별하지 않았다.', '',
              '이 목록은 모델이 놓친 **관측 사례**다. 파일 형식/통계 특징이 예측 실패의 원인이라는 인과 증명이나 모델 경로/특징 중요도 분석은 하지 않았다. Confidence는 보정되지 않은 기존 출력을 참고용으로만 연결했다. 모델을 다시 학습하거나 zstd에 벌점을 주는 근거로 자동 적용하지 않는다.', '',
              '순수 codec 선택의 개선 여지이며 특징 추출/추론/검증/저장 비용까지 회복한다는 뜻은 아니다. 기존 전체 경로 평가의 모든 후보 조건에서 비용이 증가한 결과는 그대로다. 이후 이 60개를 이용해 튜닝하면 개발 자료이며 새 원본 그룹의 최종 holdout이 필요하다.', '',
              '## 검증', '',
              f"선택 기록 4,320행 중 두 모델 {coverage['prediction_count']}행을 사전 동결 예측과 대조했다. 네 압축기 측정 240행을 모두 verified/status 확인했고, 2,400개 원시 시간 슬롯에서 5회 중앙값을 다시 계산했다. 540개 파일×정책의 네 비용은 기존 계산부와 별도 Fraction 계산을 대조했다. 선택/정답/비용/동점 판정과 모든 대안의 누락·중복을 검사했다. Fraction 대조의 허용 오차는 산술 검증용이며 사례 선정에는 쓰지 않았다.", '',
              '기존 study 전체 파일의 실행 전후 SHA-256을 대조했다. 새 분석·시나리오 원문·공식 protocol/config·실행 환경과 Git HEAD는 audit에 남겼다. 원시 연구 파일과 기존 보고서는 덮어쓰지 않았다.', '']
    return '\n'.join(lines).replace('## 누락 57건의 전체 목록', f'## 누락 {len(cases)}건의 전체 목록')


def main():
    require(not OUT.exists() and not REPORT.exists(), 'Refuse to overwrite analysis')
    protected = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(STUDY.rglob('*')) if p.is_file()}
    require(bool(protected), 'Study missing')
    for p in (FREEZE, ROOT / 'src/usage_objectives.py', ROOT / 'research_protocol_v2.md', ROOT / 'config/experiment_config.json'):
        protected[p.relative_to(ROOT).as_posix()] = sha(p)
    manifest = json.loads((STUDY / 'corpus/manifest.json').read_bytes())
    metadata = {r['sample_id']: r for r in manifest['candidates'] if r['selection_status'] == 'selected'}
    require(len(metadata) == 60, 'Expected frozen 60 files')
    definitions = {s['id']: s['policy'] for s in json.loads(FREEZE.read_bytes())['expanded_cost_scenarios']}
    require(len(definitions) == 9, 'Expected frozen 9 scenarios')
    samples = index_unique(read_csv(STUDY / 'predictions/samples.csv'), ('sample_id',))
    predictions = index_unique(read_csv(STUDY / 'predictions/frozen_predictions.csv'), ('sample_id', 'scenario_id', 'model'))
    measurements = index_unique(read_csv(STUDY / 'benchmark/compression_results.csv'), ('sample_id', 'algorithm'))
    choices = index_unique(read_csv(STUDY / 'evaluation/strategy_choices.csv'), ('sample_id', 'scenario_id', 'strategy'))
    keys = {(s, sid, m) for s in metadata for sid in definitions for m in MODELS}
    require(set(predictions) == keys, 'Incomplete/extra predictions')
    require(set(samples) == {(s,) for s in metadata}, 'Sample coverage')
    require(set(measurements) == {(s, a) for s in metadata for a in ALGORITHMS}, 'Codec coverage')
    require(set(choices) == {(s, sid, m) for s in metadata for sid in definitions for m in (*ALGORITHMS, *MODELS, 'train_majority', 'oracle')}, 'Choice coverage')
    for s, meta in metadata.items():
        require(samples[(s,)]['input_sha256'] == meta['input_sha256'] and int(samples[(s,)]['original_size']) == meta['original_size'], 'Sample identity')
        for alg in ALGORITHMS:
            row = measurements[(s, alg)]
            require(row['verified'] == 'True' and row['status'] == 'ok' and not row['error'], 'Failed codec')
            require(int(row['original_size']) == meta['original_size'], 'Original size')
    raw = read_csv(STUDY / 'benchmark/timing_repeats.csv')
    raw_index = index_unique(raw, ('sample_id', 'algorithm', 'phase', 'repeat_index'))
    require(set(raw_index) == {(s, a, ph, str(i)) for s in metadata for a in ALGORITHMS for ph in ('compress', 'decompress') for i in range(1, 6)}, 'Raw repeat coverage')
    repeat_stats = []
    for s in sorted(metadata):
        for alg in ALGORITHMS:
            for phase, field in (('compress', 'compression_time_ms'), ('decompress', 'decompression_time_ms')):
                rows = [raw_index[(s, alg, phase, str(i))] for i in range(1, 6)]
                for row in rows:
                    validate_repeat_status(row, phase, metadata[s]['input_sha256'])
                require(len({r['output_sha256'] for r in rows}) == 1, 'Inconsistent repeat output')
                size = int(measurements[(s, alg)]['compressed_size']) if phase == 'compress' else metadata[s]['original_size']
                require(all(int(r['output_size']) == size for r in rows), 'Repeat output size')
                ns = [int(r['elapsed_ns']) for r in rows]
                require(min(ns) > 0 and statistics.median(ns) / 1e6 == float(measurements[(s, alg)][field]), 'Saved median mismatch')
                repeat_stats.append(dict(sample_id=s, candidate_id=metadata[s]['candidate_id'], algorithm=alg, phase=phase,
                                         repeats=5, output_size=size, min_ms=min(ns)/1e6, median_ms=statistics.median(ns)/1e6,
                                         max_ms=max(ns)/1e6, elapsed_ns=';'.join(map(str, ns))))
    values, components = {}, {}
    for s in metadata:
        for sid, policy in definitions.items():
            result = evaluate_lifetime_cost([measurements[(s, a)] for a in ALGORITHMS], policy=LifetimePolicy(**policy))
            costs, parts = {}, {}
            for a in ALGORITHMS:
                parts[a] = independent_components(measurements[(s, a)], policy)
                costs[a] = math.fsum(parts[a].values())
                require(costs[a] == result['values'][a] and parts[a] == result['components'][a], 'Independent cost mismatch')
            best, _, _ = classify(costs)
            require(best == result['selected_algorithm'], 'Oracle mismatch')
            for a in (*ALGORITHMS, 'oracle'):
                r = choices[(s, sid, a)]
                expected = best if a == 'oracle' else a
                require(r['chosen_algorithm'] == expected and float(r['policy_cost']) == costs[expected], 'Fixed strategy cost mismatch')
            values[(s, sid)], components[(s, sid)] = costs, parts
    cases, alternatives, ties, summaries = [], [], [], []
    for sid in definitions:
        for model in MODELS:
            zstd = missed = optimal_ties = pair_ties = wrong_switches = opportunities = 0
            scenario_cases = []
            for s in sorted(metadata, key=lambda k: metadata[k]['candidate_id']):
                costs, parts = values[(s, sid)], components[(s, sid)]
                best, better, equal = classify(costs)
                pred, row, meta = predictions[(s, sid, model)], choices[(s, sid, model)], metadata[s]
                validate_choice(row, costs, pred, meta)
                chosen = row['chosen_algorithm']
                opportunities += bool(better)
                if chosen != 'zstd':
                    wrong_switches += costs[chosen] > costs['zstd']
                    continue
                zstd += 1
                if equal:
                    pair_ties += 1
                    optimal_ties += costs['zstd'] == costs[best]
                    ties.append(dict(sample_id=s, scenario_id=sid, model=model, equal_to_zstd=';'.join(equal), zstd_is_optimal=costs['zstd'] == costs[best]))
                if not better:
                    continue
                missed += 1
                base = dict(sample_id=s, scenario_id=sid, model=model, candidate_id=meta['candidate_id'],
                            original_filename=meta['original_filename'], relative_path=meta['relative_path'],
                            format=meta['format'], origin_group_id=meta['origin_group_id'], input_sha256=meta['input_sha256'],
                            source_locator=meta['source_locator'], original_size=meta['original_size'])
                case = dict(**base, chosen_algorithm='zstd', best_algorithm=best, better_algorithms=';'.join(better),
                            equal_to_zstd=';'.join(equal), uncalibrated_confidence=float(pred['uncalibrated_confidence']),
                            zstd_cost=costs['zstd'], oracle_cost=costs[best], regret=costs['zstd'] - costs[best],
                            saving_pct=pct(costs['zstd'] - costs[best], costs['zstd']),
                            **{a + '_cost': costs[a] for a in ALGORITHMS if a != 'zstd'})
                for a in ALGORITHMS:
                    for field in ('compressed_size', 'compression_time_ms', 'decompression_time_ms'):
                        case[a + '_' + field] = measurements[(s, a)][field]
                cases.append(case)
                scenario_cases.append(case)
                for a in better:
                    alt = dict(**base, alternative=a, is_oracle_tie=costs[a] == costs[best], zstd_cost=costs['zstd'],
                               alternative_cost=costs[a], saving=costs['zstd'] - costs[a], saving_pct=pct(costs['zstd'] - costs[a], costs['zstd']))
                    for component in ('storage', 'compression', 'restoration'):
                        alt['zstd_' + component + '_cost'] = parts['zstd'][component]
                        alt['alternative_' + component + '_cost'] = parts[a][component]
                        alt[component + '_saving'] = parts['zstd'][component] - parts[a][component]
                    for field, kind in (('compressed_size', int), ('compression_time_ms', float), ('decompression_time_ms', float)):
                        alt['zstd_' + field] = measurements[(s, 'zstd')][field]
                        alt['alternative_' + field] = measurements[(s, a)][field]
                        alt[field + '_saving'] = kind(measurements[(s, 'zstd')][field]) - kind(measurements[(s, a)][field])
                    alternatives.append(alt)
            all_zstd = math.fsum(values[(s, sid)]['zstd'] for s in metadata)
            summaries.append(dict(scenario_id=sid, model=model, total_files=len(metadata), zstd_choices=zstd,
                                  missed_cases=missed, missed_pct_of_zstd_choices=pct(missed, zstd),
                                  oracle_non_zstd_strict_opportunities=opportunities, zstd_optimal_tie_cases=optimal_ties,
                                  zstd_any_pair_tie_cases=pair_ties, non_zstd_strictly_worse_than_zstd=wrong_switches,
                                  missed_regret_sum=math.fsum(r['regret'] for r in scenario_cases),
                                  missed_gain_pct_of_fixed_zstd_total=pct(math.fsum(r['regret'] for r in scenario_cases), all_zstd)))
    # Independent exhaustive set construction: catches lost joins and omitted non-oracle alternatives.
    expected_pairs = {(s, sid, m, a) for s, sid, m in keys if predictions[(s, sid, m)]['predicted_algorithm'] == 'zstd'
                      for a in ALGORITHMS if values[(s, sid)][a] < values[(s, sid)]['zstd']}
    actual_pairs = {(r['sample_id'], r['scenario_id'], r['model'], r['alternative']) for r in alternatives}
    require(actual_pairs == expected_pairs and len(actual_pairs) == len(alternatives), 'Alternative enumeration')
    case_keys = {(s, sid, m) for s, sid, m, a in expected_pairs}
    require(case_keys == {(r['sample_id'], r['scenario_id'], r['model']) for r in cases} and len(case_keys) == len(cases), 'Case enumeration')
    grouped = defaultdict(list)
    for r in cases:
        grouped[r['sample_id']].append(r)
    files = []
    for s in sorted(grouped, key=lambda k: metadata[k]['candidate_id']):
        rows, meta = grouped[s], metadata[s]
        files.append(dict(sample_id=s, candidate_id=meta['candidate_id'], original_filename=meta['original_filename'],
                          relative_path=meta['relative_path'], input_sha256=meta['input_sha256'], source_locator=meta['source_locator'],
                          format=meta['format'], origin_group_id=meta['origin_group_id'], original_size=meta['original_size'],
                          missed_cases=len(rows), scenarios=';'.join(sorted({r['scenario_id'] for r in rows})),
                          models=';'.join(sorted({r['model'] for r in rows})), best_algorithms=';'.join(a for a in ALGORITHMS if any(r['best_algorithm'] == a for r in rows)),
                          min_saving_pct=min(r['saving_pct'] for r in rows), max_saving_pct=max(r['saving_pct'] for r in rows)))
    coverage = dict(prediction_count=len(predictions), choices_count=len(choices), measurement_count=len(measurements),
                    raw_repeat_count=len(raw), cost_file_scenarios=len(values), zstd_choices=sum(r['zstd_choices'] for r in summaries),
                    missed_cases=len(cases), missed_files=len(files), missed_file_scenarios=len({(s, sid) for s, sid, m in case_keys}),
                    better_alternative_pairs=len(alternatives), unique_better_pairs=len({(s, sid, a) for s, sid, m, a in expected_pairs}),
                    ties=len(ties), best_codec_case_counts=dict(Counter(r['best_algorithm'] for r in cases)),
                    alternative_codec_pair_counts=dict(Counter(r['alternative'] for r in alternatives)))
    OUT.mkdir(parents=True)
    for name, rows in (('missed_cases.csv', cases), ('better_alternatives.csv', alternatives), ('unique_files.csv', files),
                       ('scenario_model_summary.csv', summaries), ('timing_repeat_summary.csv', repeat_stats)):
        write_csv(OUT / name, rows)
    write_csv(OUT / 'ties.csv', ties, ('sample_id', 'scenario_id', 'model', 'equal_to_zstd', 'zstd_is_optimal'))
    with REPORT.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(render_report(cases, alternatives, summaries, files, metadata, repeat_stats, coverage))
    for name, digest in protected.items():
        require(sha(ROOT / name) == digest, f'Input modified: {name}')
    require({p.relative_to(ROOT).as_posix() for p in STUDY.rglob('*') if p.is_file()} == {n for n in protected if n.startswith(STUDY.relative_to(ROOT).as_posix() + '/')}, 'Study file set changed')
    write_json(OUT / 'audit.json', dict(status='verified_read_only_diagnostic', created_at_utc=datetime.now(timezone.utc).isoformat(),
               source_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               python=sys.version, platform=platform.platform(), analyzer_sha256=sha(Path(__file__)),
               selection='strict binary64 alternative cost < zstd cost; no selection tolerance; exact ties separate',
               scope='Frozen candidate models and 60 observed real files; developmental codec-only analysis; no new runs',
               coverage=coverage, protected_input_sha256=protected,
               output_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in (*sorted(OUT.glob('*.csv')), REPORT)},
               checks=['Unique and complete sample/scenario/model/codec/repeat keys', 'Frozen prediction/metadata/exact saved costs',
                       'Verified codecs and restoration hashes', 'All raw medians', 'Separate components and Fraction arithmetic',
                       'Exhaustive case and better-alternative set equality', 'All source study files unchanged']))
    print(json.dumps(coverage, ensure_ascii=False))


if __name__ == '__main__':
    main()
