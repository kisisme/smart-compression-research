# 동일 환경 반복 검증 Run 3 완료

상태: **Run 3 전체 실측·종료 기록·제한된 저장 무결성 검사 완료. Run 3 새 실패 0건.**
기존 Run 2 timeout 3건은 그대로 남으며 전체 attempt의 정상 행렬·독립 audit·후보 판단·공식 4지표 전환을 통과한 것은 아니다.

- 설계: `memory_repeatability_v1`, collector revision 2, `validation_only`, `score_inclusion=false`.
- 실행 commit: `a8c3e47edc4f9d231605434c464b036240b7b2ed`.
- 실제 시작 KST: 2026-10-20T18:50:55.742492+09:00.
- 실제 종료 KST: 2026-10-20T19:23:24.717879+09:00.
- 부모 wall 시간: 1948.975387초. 개별 codec 시간과 구분한다.
- Run 2 종료 이후 실제 간격: 36091.562069초. 고정 날짜·시각·간격 제한은 없다.
- 전체 job 3696개 완료. Memory 3360행, timing 3360행 모두 `ok`·`verified=True`.
- 최종 336쌍 모두 `verified=True`, 실패 반복·실패 pair 0. Metadata 저장 재시도 사건도 없다.
- 부모 `completed`·`recording_checks_passed=true`, 종료 처리 완료·소스 불변·활성 claim 없음.
- Coordinator `awaiting_next_run`·누적 실패 3건·`recording_checks_passed=false`. 현재 성공과 전체 attempt 상태를 구분한다.

## 보존·검증 근거

[제한 검사 보고서](limited_record_check_run_03.json)는 [검사 코드](check_saved_run_03.py)를 Python으로 실행해 생성했다.
예정 원시 key·job·반복 수, 입력/참조 identity·검증 표시·양수 값, 원시 phase 중앙값·ns→ms·최종 memory 최댓값·ratio, 소스/산출물 hash·전 run 참조 동일성을 대조했고 실패 항목은 없다.
검사 결과 `record_integrity_checks_passed=true`, `run_successful=true`이며 기존 누적 실패 수는 별도로 보존했다.

Run 3 직전 존재한 파일 중 매번 갱신되는 최상위 coordinator metadata를 제외한 30개 파일은 hash 불변이다.
Run 1·2 원시값과 부모 metadata·검사·완료 기록을 수정하지 않았다. Run 2 timeout을 Run 3 값으로 대체하거나 정상 정답 생성에 포함하지 않는다.

[부모 metadata](run_03/metadata.json), [coordinator metadata](metadata.json), [원시 memory](run_03/memory_repeats.csv),
[원시 timing](run_03/timing_repeats.csv), [최종 집계](run_03/measurements.csv)에 실제 결과를 보존한다.
[운영 사건](operator_events_run_03.json), [실행 전 관측·원본 hash](operator_context_run_03.json), [사전 점검 코드](preflight_run_03.py)도 함께 남겼다.
사전 auxiliary boot JSON의 BOM 읽기 오류는 기존 파일을 바꾸지 않고 읽기 방식만 보완했으며 측정 시작 전 해결했다. 그 경위는 context에 기록했다.

## 환경·운영 사건

[자동 상태 기록](run_03_monitor.jsonl)은 [가벼운 조회 코드](monitor_run_03.py)로 생성했다. 측정 job을 실행하거나 재시도하는 기능은 없다.
시작 직전 외부 전원 연결·배터리 80%·균형 조정 전원 계획을 실제 관측했다. 게임·통신·일반 활동에 대한 기존 사용자 보고와 관측은 구분한다.

[실제 전원 이벤트](windows_power_events_run_03.json)와 [조회 범위·상태](windows_power_query_run_03.json)는 측정 시작~종료 구간의 System 로그를 사후 조회한 기록이다.
조회한 provider에서 전원 공급원 변경 이벤트 105가 1건 있었으므로 연속 AC 유지로 단정하지 않는다.
이 조회 구간에 Modern Standby 진입/재개 이벤트는 없었다. 이는 지정한 로그 조회 범위의 관측이며 모든 전원 상태를 연속 인증하는 것은 아니다.
전원·절전·덮개 설정은 변경하지 않았다.

## 다음 단일 작업·미완료

사용자가 이어서 진행할 때 같은 HEAD·소스·설정·환경과 실제 사건을 확인한 뒤 **Run 4 한 번**을 실행한다.
이번 요청 범위인 Run 3만 실행했고 Run 4는 시작하지 않았다. 고정 시작 시각 제한은 없다.
독립 프로토콜 audit·후보 분석·공식 4지표 전환은 미완료다. 이번에는 단위 테스트·모델 학습을 실행하지 않았다.

여섯 run 동안 같은 HEAD를 유지하는 사전 설계에 따라 중간 완료 기록은 이 attempt 안에 둔다.
루트 `research_progress.md`와 결과 commit은 전체 종료 또는 attempt 종료 결정 때 반영하며 이번에는 변경하지 않았다.

