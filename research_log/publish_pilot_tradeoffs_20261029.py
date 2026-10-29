"""Render the verified exploratory analysis; preserve all original score definitions."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'data/results/pilot_tradeoff_20261029_01'
REPORT = ROOT/'research_log/pilot_tradeoffs_20261029.md'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    with (OUT/name).open(encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    if REPORT.exists() or (OUT/'publication.json').exists() or (OUT/'size_weight_sensitivity.png').exists():
        raise FileExistsError('Existing publication must not be overwritten')
    summary = json.loads((OUT/'summary.json').read_bytes())
    verification = json.loads((OUT/'verification.json').read_bytes())
    if verification['summary_sha256'] != sha(OUT/'summary.json'):
        raise ValueError('Verified summary changed')
    if sha(ROOT/'research_log/verify_pilot_tradeoffs_20261029.py') != verification['verifier_sha256']:
        raise ValueError('Verifier source changed')
    for name,digest in summary['output_sha256'].items():
        if sha(OUT/name) != digest:
            raise ValueError('Verified table changed: '+name)
    n = summary['sample_count']
    path = read('equal_time_path.csv')
    groups = read('group_summary.csv')
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'data/temp/matplotlib_pilot_tradeoff_20261029'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax = plt.subplots(figsize=(9,5),layout='constrained')
    ax.plot([float(r['w_size']) for r in path],[float(r['strict_non_zstd_gain_pct']) for r in path],color='#06746c',linewidth=2.5)
    ax.axhline(10,color='#a96416',linestyle='--',linewidth=1,label='10% reference; not an optimization target')
    ax.axvline(.70,color='#667085',linestyle=':',label='Official Archive size weight: 0.70')
    ax.set(xlim=(0,1),ylim=(0,60),xlabel='Size weight r; each time weight = (1-r)/2',
           ylabel='Samples strictly improved over fixed zstd (%)',
           title=f'Existing synthetic Pilot (n={n:,}) — exploratory sensitivity')
    ax.grid(axis='y',alpha=.2)
    ax.legend(loc='upper left',frameon=False,fontsize=9)
    fig.savefig(OUT/'size_weight_sensitivity.png',dpi=180)
    plt.close(fig)
    lines = ['# 기존 Pilot: 압축기별 우세 조건과 점수 민감도 — 2026-10-29','',
             '**판정: 다른 압축기의 압축 크기 이점은 존재하지만, 현재 로그 점수에서는 시간 차이가 크게 작용한다. 공식 가중치 채택·라벨 변경은 수행하지 않았다.**','',
             '## 범위와 재현 근거','',
             f'- 입력: 기존 합성 Pilot {n:,}개. 과거 측정 실행 commit `{summary["historical_measurement_metadata"]["git"]["commit_hash"]}`.',
             f'- 이번 분석 시작/실행 HEAD: `{summary["git_head"]}`. 당시 commit 전 분석 source의 정확한 SHA-256은 summary에 보존했다.',
             '- [분석 전 고정 계획](pilot_tradeoff_plan_20261029.json), [분석기](analyze_pilot_tradeoffs_20261029.py), [저장 결과 독립 검증기](verify_pilot_tradeoffs_20261029.py), [문서·그래프 생성기](publish_pilot_tradeoffs_20261029.py).',
             '- [결과/환경/입력·source·보호 hash](../data/results/pilot_tradeoff_20261029_01/summary.json), [독립 검증](../data/results/pilot_tradeoff_20261029_01/verification.json).',
             '- gzip 9 / bz2 9 / LZMA preset 6 / zstd 3과 기존 5회 중앙값을 사용한다. 새 압축·복원·특징 추출·모델 학습/예측은 실행하지 않았다.',
             '- 기존 Pilot 전체에는 이전 train/test가 포함된다. 이번 결과는 기술적 탐색이며 새 일반화 성능이나 모델 정확도가 아니다. 수집한 실제 unseen 후보는 사용하지 않았다.',
             '- Memory 값은 기존 Pilot에 없다. 추정·보충·4지표 점수 생성 없이 `validation_only`와 참고 지표 방침을 유지한다.','',
             '## 지표별 실제 우세','',
             '| 단일 지표 | gzip 단독 최저 | bz2 단독 최저 | LZMA 단독 최저 | zstd 단독 최저 | 동점 |',
             '|---|---:|---:|---:|---:|---:|']
    for metric,label in zip(('compression_ratio','compression_time_ms','decompression_time_ms'),('압축률','압축 시간','해제 시간')):
        counts = summary['metrics'][metric]['exact_minima_sets']
        lines.append('| '+label+' | '+' | '.join(str(counts.get(a,0)) for a in ('gzip','bz2','lzma','zstd'))+f' | {sum(v for k,v in counts.items() if "|" in k)} |')
    size = summary['metrics']['compression_ratio']
    gain = size['best_saving_pct_strict_improvements_only']
    lines += ['',f'압축 크기에서는 zstd보다 좋은 파일이 {size["zstd_strictly_beaten_count"]:,}개({100*size["zstd_strictly_beaten_count"]/n:.2f}%)다. '
              f'이 파일들에서 그때의 최소 크기 압축기를 선택하면 zstd 대비 크기 절감률은 중앙값 {gain["median"]:.2f}%, 최대 {gain["max"]:.2f}%다. '
              '이 수치는 압축률만의 oracle이며 공식 종합 점수의 정답/모델 성능과 구분한다.','',
              '| 비교 대상 | zstd보다 작은 파일 | 작을 때 크기 절감률 중앙값 | 작을 때 절감 bytes 중앙값 | 압축이 더 빠른 파일 | 해제가 더 빠른 파일 |',
              '|---|---:|---:|---:|---:|---:|']
    for a in ('gzip','bz2','lzma'):
        v = summary['pairwise_vs_zstd'][a]
        lines.append(f'| {a} | {v["compression_ratio"]["better"]} | {v["compression_ratio"]["saving_pct_when_better"]["median"]:.2f}% | '
                     f'{v["bytes_saved_when_smaller"]["median"]:,.1f} | {v["compression_time_ms"]["better"]} | {v["decompression_time_ms"]["better"]} |')
    lines += ['', '각 행은 해당 압축기와 zstd의 pairwise 비교다. 한 파일이 여러 행에 포함될 수 있으며 단독 최저 빈도와 다르다.','',
              '## 어떤 데이터에서 차이가 나는가','',
              '| Generator | 파일 수 | zstd보다 작게 압축 가능 | zstd보다 빠르게 해제 가능 | Archive 비-zstd 선택 |',
              '|---|---:|---:|---:|---:|']
    for r in groups:
        if r['group_kind']=='generator':
            lines.append(f'| {r["group"]} | {r["sample_count"]} | {r["compression_ratio_zstd_strictly_beaten_count"]} | '
                         f'{r["decompression_time_ms_zstd_strictly_beaten_count"]} | {int(r["sample_count"])-int(r["archive_zstd_selected"])} |')
    lines += ['', 'structured·mixed에서 다른 압축기의 크기 이점이 자주 나타나지만, 그 사실만으로 종합 선택이 바뀌지는 않는다. Generator 이름은 실험 조건이며 실제 파일 형식/특징에 대한 일반화 규칙이 아니다.','',
              '| 원본 bytes | 파일 수 | zstd보다 작게 압축 가능 | Archive 비-zstd 선택 |',
              '|---|---:|---:|---:|']
    for r in sorted((r for r in groups if r['group_kind']=='size'),key=lambda r:int(r['group'])):
        lines.append(f'| {int(r["group"]):,} | {r["sample_count"]} | {r["compression_ratio_zstd_strictly_beaten_count"]} | '
                     f'{int(r["sample_count"])-int(r["archive_zstd_selected"])} |')
    lines += ['', '[Generator×size 전체 표](../data/results/pilot_tradeoff_20261029_01/group_summary.csv), '
              '[파일별 조건/선택/Pareto](../data/results/pilot_tradeoff_20261029_01/per_sample.csv), '
              '[전체 pairwise 절감값](../data/results/pilot_tradeoff_20261029_01/pairwise_vs_zstd.csv)을 보존했다.','',
              '## 공식 점수와 개선 폭','',
              '| 모드 | gzip | bz2 | LZMA | zstd | 비-zstd 비율 | zstd 고정 사용의 평균 regret | 최대 regret |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for mode,v in summary['official'].items():
        lines.append(f'| {mode} | '+' | '.join(str(v['selected_counts'][a]) for a in ('gzip','bz2','lzma','zstd'))+
                     f' | {v["non_zstd_pct"]:.2f}% | {v["zstd_regret"]["mean"]:.8f} | {v["zstd_regret"]["max"]:.8f} |')
    lines += ['', 'Regret는 `zstd 점수 − 해당 모드 최소 점수`이며 무차원 로그 점수 차이다. 속도 개선률이나 정확도가 아니다. '
              'Archive에서 고정 zstd 대신 oracle 선택을 했을 때 전체 파일 평균 압축 bytes 절감은 '
              f'{summary["official"]["archive"]["size_saved_bytes"]["mean"]:.2f} bytes이고, 압축 시간 절감은 '
              f'{summary["official"]["archive"]["compress_saved_ms"]["mean"]:.6f} ms다. 음수 절감은 비용 증가를 뜻한다. '
              '선택 비율과 각 비용의 변화는 함께 평가해야 한다.','',
              'Pareto front 포함 빈도: '+', '.join(f'{a} {v}개' for a,v in summary['pareto']['front_inclusion_counts'].items())+'. '
              f'zstd가 다른 모든 압축기를 지배한 파일은 {summary["pareto"]["zstd_dominates_all_others_count"]}개다. '
              'Pareto 포함은 어떤 가중치에서 반드시 선택된다는 뜻이 아니다. 지배 관계는 양의 가중치에서의 개선 가능성만 제한하며 가중치 0의 동점은 별도다.','',
              '## 가중치 민감도: 채택안이 아닌 탐색','',
              r'기존 식 $S=w_C\ln(C/C_{min})+w_c\ln(T_c/T_{c,min})+w_d\ln(T_d/T_{d,min})$을 유지했다. '
              r'전체 단체 격자는 $w_C+w_c+w_d=1$, 간격 0.05이고, 별도 경로는 $(r,(1-r)/2,(1-r)/2)$, $r=0,0.01,\ldots,1$이다.','',
              '모든 격자점을 보존했으며 특정 결과를 얻은 가중치를 추천/채택하지 않았다. 10%는 설명용 참고선이다. '
              '선택 순서는 정확 동점에서 `gzip,bz2,lzma,zstd`이며 epsilon을 넣지 않았다. 엄격 개선은 선택 점수가 zstd 점수보다 작은 경우다. '
              '`>1e-12` count도 별도 저장했지만 이 값은 시간 측정 오차나 통계적 유의성 기준이 아니다.','',
              '| 압축률 가중치 r | 각 시간 가중치 | 비-zstd 엄격 개선 비율 | gzip / bz2 / LZMA 선택 수 |',
              '|---:|---:|---:|---|']
    for r in path:
        if round(float(r['w_size']),2) in (.70,.75,.80,.85,.87,.88,.90,.95,1):
            lines.append(f'| {float(r["w_size"]):.2f} | {float(r["w_compress"]):.3f} | {float(r["strict_non_zstd_gain_pct"]):.2f}% | '
                         f'{r["gzip_selected"]} / {r["bz2_selected"]} / {r["lzma_selected"]} |')
    first = next(r for r in path if float(r['strict_non_zstd_gain_pct'])>=10)
    lines += ['', f'이 경로의 0.01 간격 격자에서 10%를 처음 넘은 지점은 `({float(first["w_size"]):.2f}, '
              f'{float(first["w_compress"]):.2f}, {float(first["w_decompress"]):.2f})`이고 비율은 {float(first["strict_non_zstd_gain_pct"]):.2f}%다. '
              '이는 연속 구간의 정확한 경계나 최적 가중치라는 뜻이 아니다. 현재 Archive보다 시간 합계 비중을 크게 줄인 경우다. '
              '예컨대 0.75/0.125/0.125에서는 변화가 작았다. 앞서 제안한 memory 포함 식의 성능으로 해석할 수 없다.','',
              f'전체 0.05 격자 {summary["simplex"]["grid_point_count"]}개 중 엄격 개선 비율이 10% 이상인 점은 '
              f'{summary["simplex"]["points_with_strict_non_zstd_gain_at_least_10pct"]}개, 모든 가중치가 양수인 점에서는 '
              f'{summary["simplex"]["positive_points_with_strict_non_zstd_gain_at_least_10pct"]}개다. '
              '영 가중치 경계와 동점만으로 비-zstd가 선택된 수를 CSV에서 구분한다. 유한 격자 결과로 전체 연속 가중치 공간을 단정하지 않는다.','',
              '![압축률 비중에 따른 zstd 대비 엄격 개선 비율](../data/results/pilot_tradeoff_20261029_01/size_weight_sensitivity.png)','',
              '[전체 0.05 격자](../data/results/pilot_tradeoff_20261029_01/weight_simplex.csv), '
              '[전체 0.01 경로](../data/results/pilot_tradeoff_20261029_01/equal_time_path.csv).','',
              '## 검증·한계·다음 결정','',
              f'- 원래 실험 metadata의 입력 hash·설정·성공 상태·전체 sample/알고리즘 coverage와 모든 공식 점수/정답을 재계산했다. '
              f'기존 Pilot/모델/config/공식 점수 코드 등 보호 파일 {verification["protected_file_count"]}개의 SHA-256이 그대로다.',
              f'- 독립 저장 검증에서 pairwise {verification["pair_rows"]:,}행과 가중치 조건 {verification["sensitivity_points"]}개 전체의 선택·엄격 개선·평균 regret, 파일별 지표/Pareto 및 그룹 선택 수를 원래 측정값과 대조했다.',
              '- 인위적 수학 fixture 전용 테스트 8개 통과(0.034초). 최초 제한 실행에서는 임시 폴더 접근 거부로 2개가 오류였고 승인 실행에서 모두 통과했다. 분석 오류를 수정하거나 연구 값을 변경한 사례는 아니다. 기존 전체 suite는 재실행하지 않았다.',
              '- 과거 반복 원시 시간은 이 분석에서 확보하지 않았다. 저장 중앙값의 작은 차이를 통계적 유의성으로 판단하거나 절전·스케줄링 영향을 배제할 수 없다.',
              '- 압축 수준별 효과, 새 실제 자료, memory, 특징·추론·검증·I/O를 포함한 전체 시간 및 최종 일반화 성능은 이번 결과로 입증하지 않는다.',
              '- 다음 연구 결정은 보관 기간·복원 빈도·허용 지연·메모리 제한 등 실제 요구를 먼저 명시하고 후속 목적 함수/검증 계획을 별도 버전으로 정하는 것이다. 탐색에 쓴 Pilot을 최종 독립 평가 자료로 주장하지 않는다.',
              '- 사용자 수동 Compare는 화면상 완료를 확인했지만 원시 반복/점수/Demo/로그의 정식 저장 검증과 GUI 전체 시각 QA는 별도 미완료다. 실제 corpus 선정/동결·평가도 미수행이다.','']
    with REPORT.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(lines))
    # Validate local report references before publishing the provenance record.
    for target in re.findall(r'\]\(([^)]+)\)',REPORT.read_text(encoding='utf-8')):
        if not target.startswith(('https://','http://')) and not (REPORT.parent/target).exists():
            raise ValueError('Broken report link: '+target)
    publication = {'created_at_utc':datetime.now(timezone.utc).isoformat(),
                   'publisher_sha256':sha(Path(__file__)),
                   'artifacts_sha256':{REPORT.relative_to(ROOT).as_posix():sha(REPORT),
                                       (OUT/'size_weight_sensitivity.png').relative_to(ROOT).as_posix():sha(OUT/'size_weight_sensitivity.png'),
                                       (OUT/'verification.json').relative_to(ROOT).as_posix():sha(OUT/'verification.json')}}
    with (OUT/'publication.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(publication,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    print(json.dumps(publication,ensure_ascii=False))


if __name__=='__main__':
    main()
