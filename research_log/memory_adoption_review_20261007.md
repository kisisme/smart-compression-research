# Memory 지표 채택 및 공식 전환 조건 검토

작성일: 2026-10-07. 검토 ID: `memory_adoption_review_v1`.
시작 HEAD와 실제 결과 보존 commit: `3f7e91ff36266cf2c0271a8ffc3b6a9d5edcafa4`.
Runtime baseline 실행 코드 commit: `729b97b09771ea2a50e955b22f5023d49b61733a`.

**검토 결론: 현재 memory의 공식 score 채택은 보류한다.** 전체 실행·저장 기록의
일관성 검증은 완료됐지만, 목표 실험 범위에서 최종 memory 대표값과 그에 따른
정답의 안정성을 확인한 근거는 부족하다. 추가 검증 설계를 먼저 작성할 것을 제안한다.
이는 검토 권고이며 공식 프로토콜 전환이나 새 실험의 실행 승인이 아니다.

현재 공식 기준은 [프로토콜 v2](../research_protocol_v2.md)의 압축률·압축 시간·해제 시간이다.
[활성 config](../config/experiment_config.json)의 memory는 `validation_only`이고,
보존 실험은 `score_inclusion=false`이다. 기존 3지표 결과·라벨·모델은 그대로 보존한다.

## 1. 근거와 확인 범위

| 근거 | 확인한 내용 | 해석 범위 |
|---|---|---|
| [초기 memory 설계](peak_memory_measurement_design.md) | 전체 프로세스 peak, phase별 반복 중앙값의 최댓값, 후보 memory loss와 weight | 사전 정의·후보이며 공식 활성 설정이 아님 |
| [기존 전체 memory 검증](../data/results/memory_validation_20260922/audit.json) | 저장된 완료 실행·audit 기록 존재 | 다른 worker 경로의 기존 측정이며 runtime baseline 대조군과 합치지 않음 |
| [Runtime baseline 사전 설계](memory_runtime_baseline_design.md) | 공통 import, 세 arm, 고정 schedule, signed 차이·범위·순위 진단 | 기술적 진단이며 과학적 합격 임계값 없음 |
| [실제 결과 기록](memory_runtime_baseline_results_20260930.md) | 전체 실측·audit·진단 완료와 해석 한계 | 같은 Windows 기계의 연속 실행에 한정 |
| [원시 반복 및 metadata 폴더](../data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/) | Python으로 원시 CSV 상태를 다시 집계: 5,400회 모두 `ok` | arm별 성공 계약을 따름. Controls의 성공은 무손실 검증 성공이 아님 |
| [저장 audit](../data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/audit.json)·[진단 JSON](../data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/diagnostic_summary.json) | 감사 입력 hash manifest 일치와 현재 입력 바이트의 hash 확인, 진단 JSON 재집계 | 저장 증거의 일관성 확인. 이번 검토에서 audit·측정을 재실행한 것은 아님 |

사전 baseline 설계 문서의 전체 실험 미착수 표시는 실행 전 상태이다. 이 문서는 실행
소스 hash에 포함되어 있으므로 수정하지 않는다. 최신 완료 상태는 실제 결과와
[진행 기록](../research_progress.md)을 따른다.

## 2. 크기별 실제 관측과 해석

아래 표는 이번 검토에서 Python으로 저장 진단 JSON을 읽어 계산했다. 각 크기의
알고리즘 쌍 조건 수는 JSON에서 집계했다. 압축·해제 phase를 구분한 쌍별 관측이며,
최종 `max_of_phase_medians` 대표값의 순위 안정성 결과가 아니다.

| 원본 크기(bytes) | 조건 수 | 관측 반복 범위 겹침: run 1 / 2 / 3 | 세 run 차이 부호 일치 | 양·음 부호 역전 |
|---:|---:|---|---:|---:|
| 64 | 36 | 21 / 22 / 22 | 22 | 13 |
| 256 | 36 | 23 / 24 / 24 | 23 | 13 |
| 1024 | 36 | 27 / 24 / 26 | 19 | 16 |
| 4096 | 36 | 26 / 21 / 23 | 27 | 8 |
| 16384 | 36 | 24 / 25 / 25 | 22 | 14 |

범위는 각 run의 관측 min/max이며 경계가 같아도 겹침이다. 부호는 차감하지 않은
codec peak의 알고리즘별 중앙값 차이에 대해 계산한다. 양·음 역전은 같은 조건에서
음수와 양수가 모두 관측된 경우다. 0을 포함한 변화와 완전 동점은 따로 보존한다.
부호 일치와 양·음 역전 외에 동점을 포함하는 변화가 있으므로 두 수의 합은 전체 조건 수와 다를 수 있다.

모든 크기에서 순위 역전이 관측됐다. 따라서 입력이 커지면 자동으로 안정된다고
단정하거나, 관측 후 특정 크기만 제외해 채택 조건을 만들 수 없다. 일부 안정된 쌍이
있어도 이 입력·환경 범위를 넘는 일반화 근거는 아니다. 범위 겹침은 신뢰구간이나
동등성 검정이 아니며, 모든 알고리즘이 동등하다는 결론도 아니다.

음수 `D_codec`가 저장되어 있다는 기존 결과도 보존한다. 다른 프로세스들의 peak
차이에 출력 버퍼·hash 작업·OS 변동 등이 함께 반영되므로, 음수를 실제 압축기의
음수 메모리 사용으로 해석하거나 0으로 보정하지 않는다. 차이의 원인을 이 기록만으로
특정하지 않는다. 기존 3지표 Pilot의 실제 timing과 이 진단 입력은 동일 실험이 아니므로
결합하여 4지표 score·정답·모델 성능을 계산하지 않는다.

## 3. 무엇을 memory로 평가할 것인가

Microsoft는 `PeakWorkingSetSize`를 bytes 단위 최대 working set으로 정의하며,
working set은 프로세스에 물리적으로 매핑된 메모리다.
[PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters),
[Working Set Information](https://learn.microsoft.com/en-us/windows/win32/psapi/working-set-information)
(2026-10-07 확인).

현 [memory worker](../src/memory_benchmark.py)와 [baseline worker](../src/memory_runtime_worker.py)는
공통 압축 라이브러리를 import하고 phase 입력을 읽은 뒤, 선택한 codec 실행·출력 hash 검증
후 peak를 조회한다. 입력·출력 bytes는 조회 때 유지하고 응답 JSON은 이후 생성한다.
이에 따라 현재 정의의 대상은 이 worker 실행 경로의 전체 프로세스 peak다. 압축기만의
순수 할당량, Smart Mode의 특징 추출·모델 로딩까지 포함한 end-to-end peak,
사용자 프로그램이 확보해야 하는 전체 메모리의 상한과 구분해야 한다.

| 사용 방안 | 현재 판단 | 후속 조건 |
|---|---|---|
| 전체 프로세스 peak를 참고 지표로 보고 | 유지 가능 | 측정 경로·환경·변동·한계를 함께 제시 |
| 현재 peak를 공식 4지표 score에 편입 | 보류 | 대표값·정답 안정성의 사전 설계 및 검증, 공식 정의 승인 필요 |
| Baseline 차감값을 공식 memory로 사용 | 이번 전환 후보에서 제외 | 서로 다른 peak의 차이로 순수 할당량을 추정하지 않음 |
| 압축기 순수 할당량 또는 end-to-end memory로 목표 변경 | 별도 연구 설계 필요 | 측정 대상·도구·대조군을 새 버전으로 정의하고 새 결과로 검증 |

현재 후보는 phase별 중앙값을 구한 뒤 그 최댓값을 memory 대표값으로 쓰는 정의다.
가까운 phase 값 사이에서 최댓값의 phase가 바뀌어도 그 자체로 실패는 아니다.
실제 대표값과 선택에 미치는 영향을 확인해야 한다. 모든 쌍의 순위가 항상 같다는
조건을 채택의 필요조건으로 임의 설정하지 않으며, 높은 실행 성공률만으로 채택하지도 않는다.

## 4. 필요한 추가 검증 — 제안/미착수

**다음 단일 작업 제안은 측정 안정성 후속 검증의 사전 설계 문서 작성이다.** 기존 값을
판정할 사후 임계값을 추가하는 작업이 아니다. 새로운 설계는 아래 사항을 측정 전에
정하고 commit하며, 실패·중단·불리한 결과를 포함한 모든 attempt를 보존해야 한다.

| 확인할 질문 | 사전 설계에 포함할 내용 | 아직 없는 근거 |
|---|---|---|
| 향후 공식 runner와 진단 worker의 측정 대상이 같은가 | worker 진입점·import·입출력 보유·hash·조회 순서를 비교하고 공식 후보 경로를 고정. 경로를 바꾸면 별도 버전으로 검증 | Baseline worker와 기존 worker의 수치적 동등성 |
| 목표 입력 범위에서 대표값이 안정적인가 | 공식 후보 크기·데이터 유형 범위, sample 생성 조건, 반복·run·실행 간격·일자, 환경 통제와 순서 무작위화 계획 | 작은 입력을 넘어서는 실행 간 안정성. 다른 날·환경에 대한 재현성 |
| 최종 memory 대표값이 선택에 어떤 영향을 주는가 | 원시 phase 반복→run별 중앙값→phase 중앙값의 최댓값→memory 상대 손실을 각각 보존하고, run별 대표값·차이·순위·동점 분석 | Phase별 진단에서 최종 대표값으로 넘어가는 안정성 |
| 측정 변동이 정답을 바꾸는가 | 동일 새 입력의 3지표·memory를 함께 측정할 계획, timing 원시 반복 및 무손실 검증, 고정 후보 score의 별도 검증 계산과 정답·score gap·regret 변동 분석 | 같은 입력·정의에서의 4지표 정답 안정성 |
| 채택할 정도의 차이를 구별하는가 | 허용할 측정 오차·선택 영향과 판단 규칙의 수치·단위·근거를 새 측정 전에 명시. 만족·불만족·판단 불가의 처리도 고정 | 사전 과학적 판단 기준. 이번 검토에서는 수치 임계값을 정하지 않음 |

Timing 변동과 memory 변동의 효과를 구분할 분석 계획도 필요하다. 예를 들어 고정한
timing에 대한 memory 변동의 영향과, 실제 함께 측정한 run의 변동은 분석 목적을
구분하여 사전에 정한다. 서로 다른 실행의 원시값을 편의상 합쳐 하나의 실측으로
표시하지 않는다. 같은 기계의 연속 run은 독립된 환경 표본으로 취급하지 않는다.

순수 할당량을 목표로 삼지 않는다면 출력 버퍼를 분리하는 대조군은 현재 채택의
자동 필수조건이 아니다. 해당 원인을 설명하거나 측정 정의를 바꾸려는 경우에만
별도 대조군을 사전 설계한다. 반복 수·크기·실행 횟수 확대도 원하는 결과를 얻을 때까지
계속하는 방식으로 정하지 않는다. 추가 검증이 불충분하면 보류 또는 참고 지표 유지를
결과로 인정한다. 특정 알고리즘 독점을 줄이는 것은 채택의 합격 기준이 아니다.

## 5. 공식 전환의 단계별 조건 — 모두 계획/미완료

1. 측정 대상과 후속 검증 설계를 사용자 확인 후 확정한다. 새 실측은 새 attempt 경로에
   저장하고 검증 전용 상태를 유지한다. 실제 측정 결과·실패·환경·소스 hash와 독립 audit를
   보존한 뒤 사전 판단 규칙에 따라 채택·보류를 검토한다.
2. 채택 근거가 확보되면 `research_protocol_v3.md` 초안에 적용 환경·입력 범위,
   memory 대표값·loss·동점 처리·실패 처리·정답 계산을 명시한다. 기존 후보 weight를
   채택하거나 변경하는 이유는 새 공식 실험 전에 기록하고 사용자 확인을 받는다.
   이 검토는 기존 [후보 weight](peak_memory_measurement_design.md)를 승인하지 않는다.
3. 승인한 정의를 별도 버전의 runner·schema·score 계산에 구현하고 검증한다. 현재
   `memory_benchmark._memory_config()`는 `validation_only`를 요구하므로 config의
   status 변경만으로 공식 편입이 완료되는 구조가 아니다. 코드·설정의 계약, 반복 원시값·
   실패 보존·독립 audit·재현성 metadata와 필요한 테스트를 함께 준비한다.
4. 새 입력으로 소규모 4지표 후보 검증을 수행한다. 규모는 [초기 설계](peak_memory_measurement_design.md)의
   50~100개 검증 단계에 맞춰 사전 확정한다. 후보 score·라벨은 별도 검증 산출물로 표시하고,
   측정·정답 안정성과 구현 검증을 마치기 전에는 공식 score 활성화나 새 Pilot으로 넘어가지 않는다.
5. 검증 근거와 한계를 사용자에게 제시해 공식 전환을 확인받고, 버전·config·이유·관련 commit을
   기록한 뒤 별도 경로에서 새 Pilot을 시작한다. 기존 v2 원시값에 memory를 보충하거나
   라벨·모델을 소급 변경하지 않는다. 학습 입력은 압축 전 통계적 특징만 유지하며,
   새 정의의 baseline·모델을 분리하여 accuracy·Macro F1·oracle regret·평가 범위를 보고한다.

Smart Mode에서는 새 모델이 준비되더라도 예측 전에 모든 codec을 실행하지 않는다.
공식 모델·설정·score 버전의 호환성을 확인하는 작업은 후속 구현 범위이다.

## 6. 집계 재현 및 이번 작업 검증

저장소 루트의 가상환경 Python으로 `-B`를 붙여 다음 코드를 실행하면 2절 표를
재계산할 수 있다. 기존 파일을 읽기만 하고 측정·압축·복원을 실행하지 않는다.

```python
import json
from pathlib import Path

p = Path("data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01")
d = json.loads((p / "diagnostic_summary.json").read_text(encoding="utf-8"))
sizes = {x["sample_id"]: int(x["size"]) for x in d["samples"]}
for size in sorted(set(sizes.values())):
    cross = [x for x in d["algorithm_pairs_across_runs"] if sizes[x["sample_id"]] == size]
    overlap = []
    for run in (1, 2, 3):
        pairs = [x for x in d["algorithm_pairs_by_run"]
                 if x["run_id"] == run and sizes[x["sample_id"]] == size]
        overlap.append(sum(x["ranges_overlap"] for x in pairs))
    print(size, len(cross), overlap, sum(x["sign_consistent"] for x in cross),
          sum(-1 in x["signs"] and 1 in x["signs"] for x in cross))
```

Python으로 표의 수치와 위 재현 코드의 출력 일치를 확인했다. 로컬 링크 14개가 존재하며,
검토 전후 보호 대상 기존 증거·소스·설정·설계 및 결과 문서 53개의 SHA-256이 일치했다.
문서의 근거와 Git diff도 검토한다.
새 측정·압축·복원·audit 재실행·모델 학습·단위 테스트·공식 설정 변경은 수행하지 않는다.
