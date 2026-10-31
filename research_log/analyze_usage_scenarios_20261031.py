"""Freeze hypothetical scenarios, reanalyse stored Pilot values, verify and report."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from research_log.analyze_pilot_tradeoffs_20261029 import load_inputs, read_csv, write_csv, write_json
from src.usage_objectives import ALGORITHMS, LifetimePolicy, evaluate_lifetime_cost, select_under_deadlines

PLAN = ROOT/'research_log/usage_scenarios_plan_20261031.json'
FROZEN = ROOT/'research_log/usage_scenarios_frozen_20261031.json'
REPORT = ROOT/'research_log/usage_scenarios_20261031.md'


def check(ok,message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def scenarios(plan):
    costs,deadlines = [],[]
    for profile in plan['profiles']:
        for multiplier in plan['time_cost_multipliers']:
            policy = dict(retention_days=profile['retention_days'],expected_restorations=profile['expected_restorations'],
                          storage_cost_per_byte_day=plan['base_costs']['storage_cost_per_byte_day'],
                          compression_cost_per_ms=str(Decimal(plan['base_costs']['compression_cost_per_ms'])*Decimal(multiplier)),
                          decompression_cost_per_ms=str(Decimal(plan['base_costs']['decompression_cost_per_ms'])*Decimal(multiplier)))
            LifetimePolicy(**policy)
            costs.append({'id':profile['id']+'_t'+multiplier.replace('.','p'),'profile':profile['id'],
                          'time_multiplier':multiplier,'policy':policy})
    for tc in plan['deadline_compression_ms']:
        for td in plan['deadline_decompression_ms']:
            select_under_deadlines([],compression_limit_ms=tc,decompression_limit_ms=td)
            deadlines.append({'id':'deadline_c'+tc.replace('.','p')+'_d'+td.replace('.','p'),
                              'compression_limit_ms':tc,'decompression_limit_ms':td})
    check(costs and deadlines,'Both candidate scenario sets must be non-empty')
    check(len({r['id'] for r in costs+deadlines})==len(costs)+len(deadlines),'Duplicate scenario ID')
    return costs,deadlines


def cost_summary(rows):
    n=len(rows)
    check(n>0,'Empty cost scenario')
    counts=Counter(r['selected_algorithm'] for r in rows)
    base=math.fsum(r['cost_zstd'] for r in rows)
    selected=math.fsum(r['selected_cost'] for r in rows)
    return {'sample_count':n,'selected_counts':{a:counts[a] for a in ALGORITHMS},
            'non_zstd_selected_pct':100*(n-counts['zstd'])/n,
            'strict_gain_count':sum(r['selected_cost']<r['cost_zstd'] for r in rows),
            'non_zstd_tie_only_count':sum(r['selected_algorithm']!='zstd' and r['selected_cost']==r['cost_zstd'] for r in rows),
            'fixed_zstd_cost_sum':base,'selected_cost_sum':selected,'total_cost_saving_pct':100*(base-selected)/base,
            'mean_per_file_cost_saving_pct':math.fsum(r['relative_cost_saving_pct'] for r in rows)/n,
            'size_saved_bytes_sum':sum(r['size_saved_bytes'] for r in rows),
            'compression_delta_ms_sum':math.fsum(r['compression_delta_ms'] for r in rows),
            'decompression_delta_ms_sum':math.fsum(r['decompression_delta_ms'] for r in rows)}


def deadline_summary(rows):
    n=len(rows)
    check(n>0,'Empty deadline scenario')
    chosen=[r for r in rows if r['selected_algorithm'] is not None]
    counts=Counter(r['selected_algorithm'] for r in chosen)
    feasible=[r for r in rows if r['zstd_feasible']]
    return {'sample_count':n,'selected_count':len(chosen),'constraint_unsatisfied_count':n-len(chosen),
            'selected_counts':{a:counts[a] for a in ALGORITHMS},
            'non_zstd_selected_pct_all':100*sum(r['selected_algorithm']!='zstd' for r in chosen)/n,
            'non_zstd_selected_pct_feasible':100*sum(r['selected_algorithm']!='zstd' for r in chosen)/len(chosen) if chosen else None,
            'zstd_feasible_count':len(feasible),
            'feasibility_recovery_count':sum(not r['zstd_feasible'] for r in chosen),
            'strict_size_improvement_with_feasible_zstd_count':sum(r['size_saved_vs_feasible_zstd']>0 for r in feasible),
            'size_saved_vs_feasible_zstd_sum':sum(r['size_saved_vs_feasible_zstd'] for r in feasible)}


def calculate(samples,grouped,expanded):
    check(set(samples)==set(grouped),'Sample/measurement coverage mismatch')
    costs,deadlines=expanded
    cost_rows,deadline_rows,summaries=[],[],{'cost':{},'deadline':{}}
    for scenario in costs:
        rows=[]
        for sid in sorted(samples):
            measured=grouped[sid]
            result=evaluate_lifetime_cost(measured.values(),policy=LifetimePolicy(**scenario['policy']))
            check(result['status']=='selected','Incomplete lifetime measurement')
            a=result['selected_algorithm']; selected=measured[a]; z=measured['zstd']
            best=result['selection_value']; ref=result['values']['zstd']
            record={'scenario_id':scenario['id'],'profile':scenario['profile'],'time_multiplier':scenario['time_multiplier'],
                    'sample_id':sid,'generator':samples[sid]['generator'],'size':int(samples[sid]['size']),
                    'status':result['status'],'selected_algorithm':a,'tied_algorithms':'|'.join(result['tied_algorithms']),
                    **{'cost_'+b:result['values'][b] for b in ALGORITHMS},'selected_cost':best,
                    'relative_cost_saving_pct':100*(ref-best)/ref,
                    'selected_bytes':int(selected['compressed_size']),'zstd_bytes':int(z['compressed_size']),
                    'size_saved_bytes':int(z['compressed_size'])-int(selected['compressed_size']),
                    'compression_delta_ms':float(selected['compression_time_ms'])-float(z['compression_time_ms']),
                    'decompression_delta_ms':float(selected['decompression_time_ms'])-float(z['decompression_time_ms']),
                    **{'selected_'+k+'_cost':v for k,v in result['components'][a].items()},
                    **{'zstd_'+k+'_cost':v for k,v in result['components']['zstd'].items()}}
            rows.append(record)
        cost_rows.extend(rows); summaries['cost'][scenario['id']]=cost_summary(rows)
    for scenario in deadlines:
        rows=[]
        for sid in sorted(samples):
            measured=grouped[sid]
            result=select_under_deadlines(measured.values(),compression_limit_ms=scenario['compression_limit_ms'],
                                          decompression_limit_ms=scenario['decompression_limit_ms'])
            check(result['status'] in ('selected','constraint_unsatisfied'),'Incomplete deadline measurement')
            a=result['selected_algorithm']; z_ok='zstd' in result['feasible_algorithms']
            record={'scenario_id':scenario['id'],'compression_limit_ms':scenario['compression_limit_ms'],
                    'decompression_limit_ms':scenario['decompression_limit_ms'],'sample_id':sid,
                    'generator':samples[sid]['generator'],'size':int(samples[sid]['size']),
                    'status':result['status'],'selected_algorithm':a,'selected_bytes':result['selection_value'],
                    'tied_algorithms':'|'.join(result['tied_algorithms']),
                    'feasible_algorithms':'|'.join(result['feasible_algorithms']),'zstd_feasible':z_ok,
                    'size_saved_vs_feasible_zstd':int(measured['zstd']['compressed_size'])-result['selection_value'] if z_ok else None,
                    'violations_json':json.dumps(result['violations'],sort_keys=True,separators=(',',':'))}
            rows.append(record)
        deadline_rows.extend(rows); summaries['deadline'][scenario['id']]=deadline_summary(rows)
    group_rows=[]
    for kind,records in (('cost',cost_rows),('deadline',deadline_rows)):
        buckets=defaultdict(list)
        for r in records:
            for group,value in (('generator',r['generator']),('size',str(r['size'])),
                                ('generator_size',r['generator']+'/'+str(r['size']))):
                buckets[(r['scenario_id'],group,value)].append(r)
        for (sid,group,value),items in sorted(buckets.items()):
            counts=Counter(r['selected_algorithm'] for r in items if r['selected_algorithm'] is not None)
            group_rows.append({'kind':kind,'scenario_id':sid,'group_kind':group,'group':value,'sample_count':len(items),
                               **{a+'_selected':counts[a] for a in ALGORITHMS},
                               'constraint_unsatisfied_count':sum(r['status']=='constraint_unsatisfied' for r in items)})
    return summaries,{'lifetime_results.csv':cost_rows,'deadline_results.csv':deadline_rows,'group_summary.csv':group_rows}


def freeze():
    check(not FROZEN.exists(),'Frozen plan already exists')
    plan=json.loads(PLAN.read_bytes()); expanded=scenarios(plan)
    check(not (ROOT/plan['output_root']).exists(),'Cannot freeze after an existing result')
    paths=[PLAN,Path(__file__),ROOT/'tests/test_usage_scenarios.py',ROOT/'src/usage_objectives.py',
           ROOT/'research_log/analyze_pilot_tradeoffs_20261029.py',ROOT/'src/scoring.py',ROOT/'config/experiment_config.json']
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths}
    test_cmd=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_usage_scenarios.py','-v']
    tested=subprocess.run(test_cmd,cwd=ROOT,capture_output=True,text=True,timeout=60)
    check(tested.returncode==0,'Scenario fixture tests failed:\n'+tested.stderr)
    check(all(sha(ROOT/k)==v for k,v in hashes.items()),'Source changed during tests')
    frozen={'status':'frozen_before_analysis','created_at_utc':datetime.now(timezone.utc).isoformat(),
            'preparation_git_head':git('rev-parse','HEAD'),'plan':plan,'expanded_cost_scenarios':expanded[0],
            'expanded_deadline_scenarios':expanded[1],'source_sha256':hashes,
            'tests':{'command':test_cmd,'returncode':tested.returncode,'stdout':tested.stdout,'stderr':tested.stderr}}
    write_json(FROZEN,frozen)
    print(json.dumps({'freeze_sha256':sha(FROZEN),'cost_scenarios':len(expanded[0]),'deadline_scenarios':len(expanded[1]),
                      'tests':tested.stderr.strip()},ensure_ascii=False))


def read_frozen(expected):
    check(expected and sha(FROZEN)==expected,'Expected external freeze hash differs')
    frozen=json.loads(FROZEN.read_bytes())
    for path,value in frozen['source_sha256'].items():
        check(sha(ROOT/path)==value,'Frozen source/plan changed: '+path)
    return frozen


def protected_inputs():
    path=ROOT/'research_log/usage_objectives_validation_20261031.json'
    prior=json.loads(path.read_bytes())
    protected={**prior['protected_after_sha256'],**prior['source_sha256'],path.relative_to(ROOT).as_posix():sha(path)}
    for name,value in protected.items():
        check(sha(ROOT/name)==value,'Prior protected input changed: '+name)
    return protected


def run(expected):
    frozen=read_frozen(expected); plan=frozen['plan']; out=ROOT/plan['output_root']
    check(out.resolve().is_relative_to((ROOT/'data/results').resolve()),'Output escapes results root')
    check(not out.exists(),'Existing result must not be overwritten')
    out.mkdir(parents=True,exist_ok=False)
    try:
        before=protected_inputs()
        samples,grouped,labels,metadata=load_inputs(ROOT/plan['input_root'],json.loads((ROOT/'config/experiment_config.json').read_bytes()))
        expanded=(frozen['expanded_cost_scenarios'],frozen['expanded_deadline_scenarios'])
        summaries,tables=calculate(samples,grouped,expanded)
        for name,rows in tables.items():
            write_csv(out/name,rows)
        after={k:sha(ROOT/k) for k in before}; check(before==after,'Protected input changed')
        read_frozen(expected)
        summary={'status':'exploratory_completed','created_at_utc':datetime.now(timezone.utc).isoformat(),
                 'git_head':git('rev-parse','HEAD'),'git_status':git('status','--short'),
                 'python':platform.python_version(),'platform':platform.platform(),'sample_count':len(samples),
                 'freeze_sha256':expected,'plan':plan,'historical_measurement_metadata':metadata,
                 'cost_summaries':summaries['cost'],'deadline_summaries':summaries['deadline'],
                 'protected_before_sha256':before,'protected_after_sha256':after,'source_sha256':frozen['source_sha256'],
                 'output_sha256':{name:sha(out/name) for name in tables},
                 'scope':'Stored measured codec data under hypothetical policies; offline oracle, no achieved model performance.',
                 'new_codec_runs':False,'new_memory_or_models':False,'official_definition_changed':False}
        write_json(out/'summary.json',summary)
    except Exception as exc:
        write_json(out/'failure.json',{'status':'failed','error':repr(exc),'created_at_utc':datetime.now(timezone.utc).isoformat()})
        raise
    print(json.dumps({'output':str(out),'cost_summaries':summary['cost_summaries'],
                      'deadline_summaries':summary['deadline_summaries']},ensure_ascii=False))


def verify(expected):
    frozen=read_frozen(expected); out=ROOT/frozen['plan']['output_root']
    check(not (out/'verification.json').exists(),'Existing verification must not be overwritten')
    summary=json.loads((out/'summary.json').read_bytes())
    check(not (out/'failure.json').exists() and summary['freeze_sha256']==expected,'Incomplete or mismatched publication')
    for path,value in summary['protected_before_sha256'].items():
        check(sha(ROOT/path)==value,'Protected input changed: '+path)
    for name,value in summary['output_sha256'].items():
        check(sha(out/name)==value,'Output changed: '+name)
    source=defaultdict(dict)
    for r in read_csv(ROOT/frozen['plan']['input_root']/'compression_results.csv'):
        source[r['sample_id']][r['algorithm']]=r
    costs={r['id']:r for r in frozen['expanded_cost_scenarios']}; deadlines={r['id']:r for r in frozen['expanded_deadline_scenarios']}
    seen_cost,seen_deadline=set(),set(); counts=defaultdict(Counter); totals=defaultdict(lambda:[[],[]])
    tolerance=frozen['plan']['comparison_policy']['verification_numeric_tolerance']
    cost_rows=read_csv(out/'lifetime_results.csv'); deadline_rows=read_csv(out/'deadline_results.csv')
    for r in cost_rows:
        key=(r['scenario_id'],r['sample_id']); check(key not in seen_cost,'Duplicate cost result'); seen_cost.add(key)
        p=costs[key[0]]['policy']; data=source[key[1]]; values={}
        for a in ALGORITHMS:
            row=data[a]; ks,h,kc,kd,n=(float(p[k]) for k in ('storage_cost_per_byte_day','retention_days','compression_cost_per_ms','decompression_cost_per_ms','expected_restorations'))
            value=math.fsum(((ks*h)*int(row['compressed_size']),kc*float(row['compression_time_ms']),(kd*n)*float(row['decompression_time_ms'])))
            f=Fraction
            exact=(f(p['storage_cost_per_byte_day'])*f(p['retention_days'])*int(row['compressed_size'])
                   +f(p['compression_cost_per_ms'])*f(row['compression_time_ms'])
                   +f(p['decompression_cost_per_ms'])*f(p['expected_restorations'])*f(row['decompression_time_ms']))
            check(float(r['cost_'+a])==value and math.isclose(value,float(exact),rel_tol=tolerance['relative'],abs_tol=tolerance['absolute']),'Independent cost mismatch')
            values[a]=value
        chosen=min(ALGORITHMS,key=values.__getitem__)
        check(r['selected_algorithm']==chosen and float(r['selected_cost'])==values[chosen],'Cost winner mismatch')
        check(r['tied_algorithms']=='|'.join(a for a in ALGORITHMS if values[a]==values[chosen]),'Tie mismatch')
        check(int(r['size_saved_bytes'])==int(data['zstd']['compressed_size'])-int(data[chosen]['compressed_size']),'Cost size saving mismatch')
        for phase in ('compression','decompression'):
            check(float(r[phase+'_delta_ms'])==float(data[chosen][phase+'_time_ms'])-float(data['zstd'][phase+'_time_ms']),'Cost time delta mismatch')
        counts[key[0]][chosen]+=1; totals[key[0]][0].append(values['zstd']); totals[key[0]][1].append(values[chosen])
    for r in deadline_rows:
        key=(r['scenario_id'],r['sample_id']); check(key not in seen_deadline,'Duplicate deadline result'); seen_deadline.add(key)
        p=deadlines[key[0]]; data=source[key[1]]
        feasible=[a for a in ALGORITHMS if float(data[a]['compression_time_ms'])<=float(p['compression_limit_ms']) and float(data[a]['decompression_time_ms'])<=float(p['decompression_limit_ms'])]
        chosen=min(feasible,key=lambda a:int(data[a]['compressed_size'])) if feasible else None
        check(r['feasible_algorithms']=='|'.join(feasible) and r['selected_algorithm']==(chosen or ''),'Deadline oracle mismatch')
        check(r['status']==('selected' if feasible else 'constraint_unsatisfied'),'Deadline status mismatch')
        check((r['zstd_feasible']=='True')==('zstd' in feasible),'Deadline reference scope mismatch')
        check(r['size_saved_vs_feasible_zstd']==(str(int(data['zstd']['compressed_size'])-int(data[chosen]['compressed_size'])) if 'zstd' in feasible else ''),'Deadline comparison denominator mismatch')
        counts[key[0]][chosen]+=1
    check(seen_cost=={(s,sid) for s in costs for sid in source},'Cost coverage mismatch')
    check(seen_deadline=={(s,sid) for s in deadlines for sid in source},'Deadline coverage mismatch')
    for kind,items in (('cost',summary['cost_summaries']),('deadline',summary['deadline_summaries'])):
        for sid,item in items.items():
            check(item['selected_counts']=={a:counts[sid][a] for a in ALGORITHMS},'Summary count mismatch')
            if kind=='cost':
                base,best=map(math.fsum,totals[sid])
                check(item['fixed_zstd_cost_sum']==base and item['selected_cost_sum']==best and item['total_cost_saving_pct']==100*(base-best)/base,'Cost summary totals mismatch')
            else:
                check(item['constraint_unsatisfied_count']==counts[sid][None],'Unsatisfied denominator mismatch')
    by_scenario=defaultdict(list)
    for r in cost_rows+deadline_rows:
        by_scenario[r['scenario_id']].append(r)
    for r in read_csv(out/'group_summary.csv'):
        entries=[v for v in by_scenario[r['scenario_id']] if (v['generator'] if r['group_kind']=='generator' else v['size'] if r['group_kind']=='size' else v['generator']+'/'+v['size'])==r['group']]
        c=Counter(v['selected_algorithm'] for v in entries)
        check(len(entries)==int(r['sample_count']) and all(c[a]==int(r[a+'_selected']) for a in ALGORITHMS),'Grouped count mismatch')
    write_json(out/'verification.json',{'status':'verified_against_original_measurements','created_at_utc':datetime.now(timezone.utc).isoformat(),
               'cost_rows':len(cost_rows),'deadline_rows':len(deadline_rows),'protected_file_count':len(summary['protected_before_sha256']),
               'freeze_sha256':expected,'summary_sha256':sha(out/'summary.json'),'source_sha256':sha(Path(__file__)),
               'checks':['Every candidate cost with exact Fraction oracle and binary64 operation order','All cost/deadline winners and sample-scenario coverage',
                         'Deadline feasibility and zstd-comparable denominator','Aggregate cost/counts and group counts','Prior input/output/source hashes'],
               'official_or_model_evaluation':False})
    print((out/'verification.json').read_text(encoding='utf-8'))


def publish(expected):
    frozen=read_frozen(expected); out=ROOT/frozen['plan']['output_root']
    check(not REPORT.exists() and not (out/'publication.json').exists(),'Existing report must not be overwritten')
    summary=json.loads((out/'summary.json').read_bytes()); checked=json.loads((out/'verification.json').read_bytes())
    check(checked['summary_sha256']==sha(out/'summary.json'),'Verified summary changed')
    lines=['# 가상 사용 시나리오별 Pilot 탐색 — 2026-10-31','',
           '**상태: 가상 정책 아래 기존 실측값의 offline oracle 탐색 완료. 공식 설정·모델 채택 결과가 아니다.**','',
           '[사전 계획](usage_scenarios_plan_20261031.json) · [실행 전 고정 근거](usage_scenarios_frozen_20261031.json) · '
           '[분석/독립 검증 코드](analyze_usage_scenarios_20261031.py) · [원시 파생표/요약](../data/results/usage_scenarios_20261031_01/summary.json) · '
           '[검증](../data/results/usage_scenarios_20261031_01/verification.json)','',
           '## 가정과 실행 범위','',
           f'분석 HEAD `{summary["git_head"]}`, 입력 {summary["sample_count"]:,}개 전체. 실행 전 고정 파일 SHA-256: `{expected}`. '
           '원래 Pilot의 hash·설정·공식 점수/라벨을 확인하고 기존 중앙값만 사용했다. 새 압축·복원·특징·모델 예측/학습·memory 측정·실제 파일 평가는 하지 않았다.','',
           '저장 비용은 1 MiB·day당 1 정책점수, 시간 비용은 기본 1 ms당 1 정책점수다. 실제 요금/사용량 근거가 없는 설명용 교환비다. '
           'Archive는 365일/전체 복원 1회, Balanced는 30일/30회, Fast Access는 1일/100회를 가정했다. '
           '각 profile에서 압축/해제 시간 계수를 함께 0.1·1·10배로 바꾼 전체 조합을 사전에 정했다. 운영 기본값을 채운 것이 아니다.','',
           '## 총비용 후보 전체 결과','',
           '| 가상 profile | 시간 비용 배수 | gzip / bz2 / LZMA / zstd | 비-zstd 선택 | zstd 고정 대비 총비용 절감 | 압축 bytes 절감 합 |',
           '|---|---:|---|---:|---:|---:|']
    for s in frozen['expanded_cost_scenarios']:
        r=summary['cost_summaries'][s['id']]
        lines.append(f'| {s["profile"]} | {s["time_multiplier"]} | '+ ' / '.join(str(r['selected_counts'][a]) for a in ALGORITHMS)+
                     f' | {r["non_zstd_selected_pct"]:.2f}% | {r["total_cost_saving_pct"]:.2f}% | {r["size_saved_bytes_sum"]:,} |')
    lines += ['', '총비용 절감률은 `(ΣJ_zstd − ΣJ_oracle)/ΣJ_zstd × 100`이다. 파일별 절감률의 단순 평균과 다르다. '
              '음수 bytes 절감은 더 큰 압축 결과를 선택했다는 뜻이며 시간 비용 절감으로 종합 비용이 낮을 수 있다. '
              '시나리오별 비용 단위/사용 조건이 다르므로 절대 비용의 크기를 시나리오 간 순위로 비교하지 않는다. '
              '비-zstd 선택과 정확 동점만의 선택, 각 압축/해제 시간 증감도 summary/파일별 CSV에 보존했다.','',
              '## 시간 제한 후보 전체 결과','',
              '| 압축 제한 ms | 해제 제한 ms | 선택 가능 / 전체 | gzip / bz2 / LZMA / zstd | 제약 미충족 | zstd 위반을 다른 후보가 충족 |',
              '|---:|---:|---:|---|---:|---:|']
    for s in frozen['expanded_deadline_scenarios']:
        r=summary['deadline_summaries'][s['id']]
        lines.append(f'| {s["compression_limit_ms"]} | {s["decompression_limit_ms"]} | {r["selected_count"]} / {r["sample_count"]} | '+
                     ' / '.join(str(r['selected_counts'][a]) for a in ALGORITHMS)+f' | {r["constraint_unsatisfied_count"]} | {r["feasibility_recovery_count"]} |')
    lines += ['', '시간 제한은 모든 크기에 동일한 가상 절대 ms 값이다. 크기별 선택/미충족은 그룹 표에서 확인한다. '
              'zstd도 같은 제한을 만족한 파일에서만 압축 크기 절감을 비교했다. zstd가 제한을 어긴 파일은 별도의 충족 회복 수로 기록했다. '
              '어느 후보도 만족하지 못한 파일은 삭제하거나 fallback으로 바꾸지 않았다. 저장된 중앙값의 제한 충족은 실제 tail latency 보장이 아니다.','',
              '[총비용 파일별 표](../data/results/usage_scenarios_20261031_01/lifetime_results.csv) · '
              '[시간 제한 파일별 표](../data/results/usage_scenarios_20261031_01/deadline_results.csv) · '
              '[generator/크기/교차 그룹 표](../data/results/usage_scenarios_20261031_01/group_summary.csv)','',
              '## 해석과 검증','',
              '이 결과는 모든 압축기의 실측을 알고 있는 oracle의 선택 가능성을 보여 준다. 새 모델이 이 선택을 예측했거나 '
              '특징 추출/추론/I/O 비용까지 포함해 zstd보다 개선됐다는 결과는 아니다. 특정 다른 알고리즘 비율을 달성한 조합을 추천하거나 채택하지 않는다. '
              '시나리오는 실제 사용량과 독립적으로 선언한 가정이므로 후속 실제 용도에서는 그 근거부터 확보해야 한다.','',
              f'독립 검증은 총비용 {checked["cost_rows"]:,}행·시간 제한 {checked["deadline_rows"]:,}행 전체를 원래 측정값에 대조했다. '
              f'기존 보호 파일 {checked["protected_file_count"]}개와 분석/입력/source/output hash는 그대로다. '
              '비용은 독립 Fraction 식과 대조하고 binary64 표현의 정확한 동점/순위도 확인했다. '
              '사전 고정 단계의 전용 fixture 테스트 결과는 frozen 파일에 보존했다. 기존 전체 suite나 압축 실험은 재실행하지 않았다.','',
              'Pilot 전체와 이전 test를 개발 탐색에 사용했으므로 이 수치를 최종 일반화 성능으로 주장하지 않는다. '
              '다음은 실제 적용 목적·계수 근거와 후속 평가 정의를 정리하는 결정 기록이다. 공식 3지표와 memory 참고 방침을 유지하며, '
              'GUI 수동 Compare 저장 검증/전체 QA·실제 corpus 선정/동결·독립 평가·새 모델은 별도 미완료다.','']
    with REPORT.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(lines))
    for target in re.findall(r'\]\(([^)]+)\)',REPORT.read_text(encoding='utf-8')):
        check((REPORT.parent/target).exists(),'Broken report link')
    write_json(out/'publication.json',{'report_sha256':sha(REPORT),'summary_sha256':sha(out/'summary.json'),
               'verification_sha256':sha(out/'verification.json'),'source_sha256':sha(Path(__file__))})
    print(str(REPORT))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','run','verify','publish'))
    parser.add_argument('--expected-freeze-sha256')
    args=parser.parse_args()
    if args.action=='freeze': freeze()
    else: {'run':run,'verify':verify,'publish':publish}[args.action](args.expected_freeze_sha256)
