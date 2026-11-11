"""Read saved verified profile only; disjoint raw-call partition and report."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'data/results/feature_profile_baseline_20261109_01'
OUT = ROOT / 'data/results/feature_profile_baseline_analysis_20261111_01'
REPORT = ROOT / 'research_log/feature_profile_baseline_results_20261111.md'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    with (PROFILE / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    require(not OUT.exists() and not REPORT.exists(), 'Refuse to overwrite diagnosis')
    complete = json.loads((PROFILE / 'complete.json').read_bytes())
    verification = json.loads((PROFILE / 'verification.json').read_bytes())
    require(complete['status'] == 'profile_independently_verified' and sha(PROFILE / 'verification.json') == complete['verification_sha256'], 'Profile not verified')
    before = {p.relative_to(PROFILE).as_posix(): sha(p) for p in PROFILE.rglob('*') if p.is_file()}
    for name, digest in verification['artifact_sha256'].items():
        require(sha(PROFILE / name) == digest, f'Changed profile evidence: {name}')
    lock_path = ROOT / 'data/results/feature_profile_implementation_20261111_01/implementation.json'
    lock = json.loads(lock_path.read_bytes())
    protected = {**lock['protected_input_sha256'], **lock['source_sha256']}
    for name, digest in protected.items():
        require(sha(ROOT / name) == digest, f'Prior protected/source change: {name}')
    start = json.loads((PROFILE / 'started.json').read_bytes())
    require(start['source_sha256'] == lock['source_sha256'], 'Measured source mismatch')
    modes = [r for r in read('summary.csv') if r['group_kind'] == 'all']
    require(len(modes) == 4 and all(int(r['count']) == 60 for r in modes), 'Mode summary coverage')
    for m in modes:
        values = [float(r['median_ms']) for r in read('file_medians.csv') if r['mode'] == m['mode']]
        require(statistics.fmean(values) == float(m['mean_ms']) and statistics.median(values) == float(m['median_ms']), 'Mode summary mismatch')
    partitions, totals = [], Counter()
    by_file = defaultdict(Counter)
    raw_roots = 0
    with (PROFILE / 'modes/instrumented_extract/trials.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['is_warmup'] == 'True':
                continue
            roots = [c for c in row['calls'] if c['parent_id'] is None]
            require(len(roots) == 1 and roots[0]['function'] == 'extract_features', 'Wrong call root')
            root = roots[0]
            parts = {'extract_features_self': root['self_ns']}
            for c in row['calls']:
                if c['parent_id'] == root['call_id']:
                    require(c['function'] not in parts, 'Duplicate top-level helper')
                    parts[c['function']] = c['elapsed_ns']
            require(sum(parts.values()) == root['elapsed_ns'] and all(type(v) is int and v >= 0 for v in parts.values()), 'Raw partition does not close')
            raw_roots += root['elapsed_ns']
            totals.update(parts)
            by_file[row['sample_id']].update(parts)
            for name, value in parts.items():
                partitions.append(dict(sample_id=row['sample_id'], round_index=row['round_index'],
                                       function=name, elapsed_ns=value, root_elapsed_ns=root['elapsed_ns']))
    require(len(by_file) == 60 and len(partitions) == 300*7 and sum(totals.values()) == raw_roots, 'Partition coverage')
    helper_values = defaultdict(list)
    for row in read('call_medians.csv'):
        if row['parent_function'] == 'extract_features':
            helper_values[row['function']].append(float(row['median_inclusive_ms']))
        elif row['parent_function'] == '<root>':
            helper_values['extract_features_self'].append(float(row['median_self_ms']))
    require(set(helper_values) == set(totals) and all(len(v) == 60 for v in helper_values.values()), 'Helper median coverage')
    helpers = [dict(function=name, raw_total_ns=ns, raw_share_pct=100*ns/raw_roots,
                    mean_of_file_helper_medians_ms=statistics.fmean(helper_values[name])) for name, ns in totals.most_common()]
    require(abs(sum(r['raw_share_pct'] for r in helpers)-100) < 1e-12, 'Partition percentages do not close')
    combined = 100*(totals['_bigram_diversity']+totals['_run_statistics'])/raw_roots
    overhead = [float(r['difference_ms']) for r in read('observer_overhead.csv')]
    OUT.mkdir(parents=True)
    write_csv(OUT / 'helper_summary.csv', helpers)
    write_csv(OUT / 'raw_disjoint_partition.csv', partitions)
    profile_link = '../data/results/' + PROFILE.name + '/'
    analysis_link = '../data/results/' + OUT.name + '/'
    lines = ['# 실제 60개 파일의 특징 기준선 측정 결과 — 2026-11-11', '',
             '**기준선 측정·독립 감사 완료. 최적화 구현/속도 개선 실험은 아직 없다.**', '',
             '[사전 계획](feature_profile_design_20261109.md) · [구현/fixture](feature_profile_implementation_20261111.md) · '
             f'[원시 독립 감사]({profile_link}verification.json) · [완료 기록]({profile_link}complete.json) · '
             f'[함수별 집계]({analysis_link}helper_summary.csv) · [비중복 분해 원시값]({analysis_link}raw_disjoint_partition.csv) · '
             f'[추가 집계 감사]({analysis_link}analysis.json)', '',
             f"실행 source HEAD는 `{start['git_head']}`다. 기존 원본 60개 full hash/크기를 확인하고 저장 특징 720개와 기존 모델의 단일 행 예측·확률/비보정 confidence 1,080개를 정확히 대조했다. 네 fresh worker에서 본 측정 1,200회와 warmup 240회를 수행했고 모든 slot·호출 tree·raw 기록의 독립 검증을 통과했다. 실패/중단·재시도·파일/반복 교체는 없었다.", '',
             '## 비계측 시간과 계측 시간', '',
             '| 모드 | 파일별 5회 중앙값의 평균 ms | 파일별 중앙값들의 중앙값 ms | p90 ms |', '|---|---:|---:|---:|']
    for row in modes:
        lines.append(f"| {row['mode']} | {float(row['mean_ms']):.6f} | {float(row['median_ms']):.6f} | {float(row['p90_ms']):.6f} |")
    lines += ['', 'extract_only는 통계 특징 계산, frame_only는 검증한 특징에서 pandas 입력 준비, extract_and_frame은 두 작업의 결합 범위다. 입력은 메모리의 bytes이고 읽기/hash·사전 검증·model load는 timer 밖이다. 각 모드는 별도 프로세스이므로 독립 중앙값을 더하거나 결합−특징 차이를 입력 준비의 직접 시간으로 해석하지 않는다.', '',
              f"계측−비계측의 파일별 중앙값 차이 평균은 {statistics.fmean(overhead):.6f}ms, 범위는 {min(overhead):.6f}~{max(overhead):.6f}ms였다. wrapper 비용과 고정 mode 순서·OS cache·실행 간 변동이 함께 들어 있다. 음의 차이도 삭제하지 않았다. 과거 54~66ms 결과와 이번 수치만 비교해 속도 개선/악화를 주장하지 않는다.", '',
              '## 함수별 병목', '',
              '| 구간 | 파일별 helper 중앙값의 평균 ms | 계측 raw root 시간의 비중 |', '|---|---:|---:|']
    for row in helpers:
        lines.append(f"| {row['function']} | {row['mean_of_file_helper_medians_ms']:.6f} | {row['raw_share_pct']:.4f}% |")
    lines += ['', f"바이트 쌍 다양성(`_bigram_diversity`)과 연속값 통계(`_run_statistics`)가 합쳐 **{combined:.4f}%**를 차지했다. 다음 최적화 후보는 이 두 구간을 우선 검토하는 것이 타당하다. 함수별 계측 시간 비중이며, 이만큼 프로그램을 빠르게 만들 수 있다는 뜻은 아니다.", '',
              '비중의 분모는 warmup을 제외한 300개 계측 trial의 root inclusive ns 합이다. 분자는 root의 직접 자식 시간과 root self 시간을 trial마다 먼저 분해한 뒤 정수 ns로 합쳤다. 모든 trial에서 합계가 root와 정확히 일치했다. 구간 엔트로피 안의 Counter/entropy는 그 구간 안에 포함하므로 이 표에 다시 합산하지 않는다. 전체 histogram Counter와 전체 entropy만 root 직접 자식으로 표시했다. Self에는 wrapper/기록 overhead와 나머지 계산이 들어 있다.', '',
              '표의 평균 helper 중앙값은 별도의 기술 통계다. helper의 독립 중앙값들을 더해 root 중앙값을 만들거나 그 비율을 100%로 맞추지 않았다. 모든 형식/원본 그룹과 ≤64KiB,(64,256]KiB,>256KiB 집계는 원래 summary.csv에 보존했다.', '',
              '## 검증·해석과 다음 작업', '',
              '사전 계획/코드·모델/runtime hash, 원본 bytes, 정확 feature/frame/prediction gate, full schedule, 호출 구간 포함/직접 자식 비중복/self 합·helper 횟수와 raw ns를 검증했다. 새 계산부는 기존 verification manifest의 모든 파일을 다시 hash 확인하고, 함수별 비중복 분해를 독립 집계했다. 기존 보호 근거와 source도 그대로다. 새 연구 숫자는 모두 저장 raw를 Python으로 읽어 계산했다.', '',
              '관찰된 60개 파일은 개발 자료다. 이번 profile은 선택 정확도 개선·전체 비용 이득·실제 GUI/CLI·cold start·memory·모집단 성능을 입증하지 않는다. 사용자 동시 작업/전원 사건의 부재는 확인하지 않았으며 notes에 미제공 상태를 남겼다. 전원 설정을 바꾸지 않았다. 공식 score/라벨/모델/config·memory 보류 방침을 유지했다.', '',
              '다음 단일 작업은 bigram/run 통계를 우선 대상으로 한 **기존 특징값 보존 최적화 후보와 같은 시점의 reference/candidate paired 검증 계획**이다. 정수 count와 나눗셈 정의·dtype/float.hex·전체 frame/예측을 그대로 보존하고, 새 source/계획을 고정한 뒤 새 경로에서 실측한다. 이 기준선만으로 예상 향상률이나 zstd 선택 비율을 정하지 않는다.', '']
    with REPORT.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines))
    for name, digest in before.items():
        require(sha(PROFILE / name) == digest, 'Profile modified during analysis')
    for name, digest in protected.items():
        require(sha(ROOT / name) == digest, 'Protected input modified during analysis')
    value = dict(status='saved_profile_and_disjoint_partition_verified', created_at_utc=datetime.now(timezone.utc).isoformat(),
                 analysis_source_sha256=sha(Path(__file__)), measurement_git_head=start['git_head'],
                 profile_file_sha256=before, protected_source_sha256=protected,
                 coverage=complete['coverage'], raw_partition_trials=300, raw_partition_rows=len(partitions),
                 raw_root_ns=raw_roots, raw_partition_sum_ns=sum(totals.values()), bigram_plus_run_share_pct=combined,
                 output_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in (*OUT.glob('*.csv'), REPORT)},
                 limitations=['Development corpus', 'Instrumented raw shares are not uninstrumented speedups',
                              'Separate mode medians not additive', 'Fixed order/cache/runtime variability'])
    with (OUT / 'analysis.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=value['status'], coverage=value['coverage'], bigram_plus_run_share_pct=combined,
                         helper_summary=helpers), ensure_ascii=False))


if __name__ == '__main__':
    main()
