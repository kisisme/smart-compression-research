# Runtime baseline 전체 실측 및 진단 — 2026-09-30

상태: 전체 실행·저장 기록 audit·진단 분석 완료. `validation_only`, `score_inclusion=false`.
공식 score는 계속 프로토콜 v2의 3지표이며, 과학적 memory 검증 완료나 4지표 전환을 뜻하지 않는다.

## 실행 및 증거

- [결과 폴더](../data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/)
- [고정 계획](../data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/plan.json), [종료 metadata](../data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/metadata.json)
- [독립 audit](../data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/audit.json), [진단 보고서](../data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/diagnostic_summary.json)
- [사전 설계](memory_runtime_baseline_design.md), [runner](../src/memory_runtime_validation.py), [audit](verify_memory_runtime_validation.py), [분석기](analyze_memory_runtime_validation.py)

실행 commit은 `729b97b09771ea2a50e955b22f5023d49b61733a`이고 시작 작업 트리는 깨끗했다.
UTC 시작은 `2026-09-30T12:01:31.276279+00:00`, 종료는 `2026-09-30T12:23:43.063204+00:00`이다.
Python 3.14.4, Windows 11 AMD64, `PeakWorkingSetSize` backend를 사용했다.
구체적인 패키지·환경·run별 가용 메모리·소스와 설정 hash는 metadata에 보존했다.

사전 고정된 입력 15개, 알고리즘 4개, phase 2개, arm 3개, 반복 5회, 별도 부모 run 3회를
전체 실행했다. 총 5,400개 반복이 모두 `ok`이고 실패 수는 0이다. 최상위와 각 run은
`completed`이며 종료 처리도 `completed`, `finalization_errors=[]`, `provenance_unchanged=true`다.
Codec 출력 검증, input_only 입력 검증, 부모 참조 복원 검증은 audit에서 arm별 계약에 맞게 확인했다.
Import_only의 성공을 무손실 복원 성공으로 해석하지 않는다.

실제 실행한 명령은 아래와 같다. 모두 사용자 Python 접근이 가능한 권한으로 실행했고 종료 코드 0이다.

```text
.venv\Scripts\python.exe -B -m src.memory_runtime_validation --output-dir data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01 --attempt-id attempt01 --reason "First full runtime baseline study after diagnostic fixture validation at 729b97b"
.venv\Scripts\python.exe -B -m research_log.verify_memory_runtime_validation --experiment-dir data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01 --output data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/audit.json
.venv\Scripts\python.exe -B -m research_log.analyze_memory_runtime_validation --experiment-dir data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01 --output data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/diagnostic_summary.json
```

별도 audit와 분석기가 내부 실행한 audit 모두 통과했고 두 보고서의 감사 입력 hash manifest는
Python으로 비교해 동일함을 확인했다. Audit/분석에서는 memory·압축·복원을 재실행하지 않는다.
저장 복원 flag와 hash의 일관성을 검사하며 증거 진위 인증이나 독립 복원 재검증은 아니다.
기존 metadata의 `analysis_status=pending_independent_audit_and_diagnostics`는 runner 종료 시점의
원시 기록으로 유지한다. 후속 완료 상태는 별도 audit와 진단 보고서에 있다.

## 실제 저장값에서 계산한 진단

아래 값은 Python으로 `diagnostic_summary.json`을 읽어 계산했다. 조건 수는 기술적 집계이며
서로 다른 sample·phase·run을 독립 표본으로 합쳐 통계 검정한 결과가 아니다.

| Run | D_codec 중앙값이 음수인 조건 / 120 | 알고리즘 쌍의 반복 범위 겹침 / 180 | 알고리즘 쌍 중앙값 동점 / 180 |
|---|---:|---:|---:|
| 1 | 16 | 121 | 1 |
| 2 | 17 | 116 | 2 |
| 3 | 14 | 120 | 2 |

`D_codec`는 같은 run·round·block의 codec − input_only이고 위 표는 그 paired 차이의
중앙값을 사용한다. 알고리즘 비교는 차감하지 않은 codec peak 중앙값을 사용하며
각 sample·phase에서 여섯 쌍을 모두 비교한다. 반복 범위는 min/max이고 경계가 같아도 겹침이다.

동일 sample·phase·알고리즘 쌍의 run 간 비교 180조건 중 차이 부호가 세 run 모두 같은 것은
113조건이다. 양수와 음수가 모두 관측된 조건은 64개다. 0을 포함하는 부호 변화와 실제
양·음 역전은 구분한다. 동점은 임의로 깨지 않는다.

| 알고리즘 쌍 | 세 run 부호 일치 / 30 |
|---|---:|
| gzip / bz2 | 22 |
| gzip / lzma | 19 |
| gzip / zstd | 17 |
| bz2 / lzma | 23 |
| bz2 / zstd | 12 |
| lzma / zstd | 20 |

위 집계를 재계산하는 예시(저장 결과를 읽기만 함):

```python
import json
from pathlib import Path

p = Path("data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01")
d = json.loads((p / "diagnostic_summary.json").read_text(encoding="utf-8"))
for run in (1, 2, 3):
    paired = [x for x in d["paired_by_run"] if x["run_id"] == run and x["contrast"] == "D_codec"]
    pairs = [x for x in d["algorithm_pairs_by_run"] if x["run_id"] == run]
    print(run, sum(x["median"] < 0 for x in paired), len(paired),
          sum(x["ranges_overlap"] for x in pairs), sum(x["tied"] for x in pairs), len(pairs))
cross = d["algorithm_pairs_across_runs"]
print(sum(x["sign_consistent"] for x in cross), len(cross),
      sum(-1 in x["signs"] and 1 in x["signs"] for x in cross))
for a, b in sorted({(x["left"], x["right"]) for x in cross}):
    pair = [x for x in cross if (x["left"], x["right"]) == (a, b)]
    print(a, b, sum(x["sign_consistent"] for x in pair), len(pair))
```

## 해석과 미완료

작은 입력의 일부 조건에서는 관측 반복 범위가 겹치고 run 간 알고리즘 순위가 바뀌었다.
전체 프로세스 peak로 모든 조건의 압축기 차이를 안정적으로 구별했다고 볼 수 없다.
음수 차이와 1보다 큰 비율도 그대로 보존했으며 이를 오류라는 이유로 삭제하지 않았다.

서로 다른 프로세스의 peak 차이는 순수 압축기 메모리나 Python runtime 점유율이 아니다.
반복 범위 겹침은 신뢰구간·동등성 검정이 아니다. 같은 기계에서 연속 실행한 run이므로
독립된 기계·날짜에 대한 재현성이나 일반화를 주장하지 않는다. 사후 합격 임계값이나
가중치를 도입하지 않는다.

이번 작업은 실제 전체 실행·audit·진단으로 검증했고 단위 테스트는 재실행하지 않았다.
앞선 commit의 인위적 fixture 테스트 통과와 이번 실제 연구 실행을 구분한다.
기존 연구 결과·설정·소스·3지표 라벨·모델은 변경하지 않았다. 새 결과 폴더의
`.gitattributes`는 원시값과 보고서의 Git 줄바꿈 변환을 막는다.

다음 제안은 이 결과에 근거한 memory 지표 채택·추가 검증 필요성·공식 전환 조건의 검토 문서 작성이다.
공식 4지표 전환 및 그 정의에 따른 새 실험은 사용자 확인과 버전·설정·이유 기록 이후의 별도 작업이다.
