# 동일 환경 반복 검증 여섯 run 수집 마감

**예정한 여섯 run의 실행·종료 기록을 완료했고 원시 기록을 보존했다. 전체 정상 성공이나 memory 공식 채택을 의미하지 않는다.**

- 설계 `memory_repeatability_v1`, collector revision 2. 실행 commit `a8c3e47edc4f9d231605434c464b036240b7b2ed`.
- 최종 상태 `completed_with_failures`, `validation_only`, `score_inclusion=false`.
- 동일 입력 84개를 6회 측정했다. 서로 다른 새 학습 sample이 늘어난 실험이 아니다.
- 전체 job 22176개, memory 20160행, timing 20160행, 총 원시 40320행.
- Pair 기록 2016개 중 정상 flag 2013개·실패 3개. 모든 실패는 기존 Run 2 timeout 3건이다.

| Run | 상태 | Job | Memory 원시 행 | Timing 원시 행 | 실패 반복 | 검증 통과 pair / 전체 |
|---|---|---:|---:|---:|---:|---:|
| 1 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |
| 2 | completed_with_failures | 3696 | 3360 | 3360 | 3 | 333 / 336 |
| 3 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |
| 4 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |
| 5 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |
| 6 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |

## 완료한 제한 검사

[마감 집계](collection_summary.json)는 [수정된 마감 점검 코드](check_collection_closure_v2.py)를 실제 Python으로 실행해 생성했다.
`limited_record_integrity_checks_passed=true`이며 미충족 항목은 없다. 이는 실패 원시값과 공란 pair 집계가 일관되게 보존됐다는 뜻이며 `all_repeats_successful=false`와 구분한다.
전체 원시 key·수량·정상 검증 flag·실패 수·공란 pair·run 순서/비겹침·소스·참조·산출물 hash·최종 누적 상태를 대조했다.
Run별 제한 검사 JSON이 묶은 파일도 재대조했다. 과거 보고서의 최상위 coordinator metadata hash만은 당시 checkpoint로 취급하고, 이후 정상 갱신되는 현재 값과 동일하다고 요구하지 않았다. 원시 파일·부모 metadata·그 밖의 결합 파일은 불변이다.

첫 [마감 점검 코드](check_collection_closure.py)는 중복 `run_id` 키워드 때문에 결과 파일 생성 전 TypeError가 발생했다.
[오류 기록](collection_closure_check_error.json)과 첫 코드를 그대로 남기고 별도 v2에서 합치기만 고쳐 점검을 통과했다. 실측 job·원시값·이전 보고서를 바꾸거나 재시도하지 않았다.

## 판단 범위·다음 단일 작업

Run 2의 실패와 Windows Modern Standby 관련 근거는 [Run 2 기록](run_02_completion.md)에 보존돼 있다.
이 기록을 정상값으로 메우거나 나머지 run의 값으로 대체하지 않았다. 이번 수집은 완전한 정상 행렬 조건을 충족하지 못한다.
새 프로토콜 전용 독립 audit·후보 score/선택 변화/regret 분석·memory 공식 채택 여부 판단은 미완료다.
기존 3일 audit를 완화해 이 결과를 통과시키지 않는다. 공식 v2의 3지표 정의는 유지한다.

다음 단일 작업은 **새 동일 환경 반복 설계 전용 독립 감사 구현·검증**이다. 이후 분석과 채택 검토를 별도 단계로 진행한다.
이번에는 별도 새 attempt나 Run 7을 생성하지 않았고 단위 테스트·모델 학습도 실행하지 않았다.
여섯 run이 끝났으므로 측정 HEAD 고정을 마감하고 진행 문서와 이 attempt의 원본 증거를 로컬 Git에 보존한다. 기록한 실행 commit은 이후 증거 보존 commit과 구분한다. Push는 하지 않는다.

