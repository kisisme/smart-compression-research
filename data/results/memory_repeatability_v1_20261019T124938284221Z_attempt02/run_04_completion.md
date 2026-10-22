# 동일 환경 반복 검증 Run 4 완료

상태: **Run 4 전체 실측·종료 기록·제한된 저장 무결성 검사 완료. Run 4 새 실패 0건.**
기존 Run 2 timeout 3건은 그대로 남는다. 전체 attempt의 정상 행렬·독립 audit·후보 판단·공식 4지표 전환 완료를 뜻하지 않는다.

- 설계 `memory_repeatability_v1`, collector revision 2, `validation_only`, `score_inclusion=false`.
- 측정 commit: `a8c3e47edc4f9d231605434c464b036240b7b2ed`.
- 실제 시작 KST: 2026-10-20T19:32:20.768114+09:00.
- 실제 종료 KST: 2026-10-20T20:02:51.932917+09:00.
- 부모 wall 시간: 1831.164803초. 개별 codec 실행 시간과 구분한다.
- 이전 Run 3 종료 후 실제 간격: 536.050235초. 고정 날짜·시각·간격 제한은 없다.
- Job 3696개 완료. Memory 3360행, timing 3360행 모두 `ok`·`verified=True`.
- 최종 336쌍 모두 `verified=True`. 실패 반복·실패 pair·metadata 저장 재시도 사건 0건.
- 부모 `completed`·`recording_checks_passed=true`, 종료 처리 완료·소스 불변·활성 claim 없음.
- Coordinator `awaiting_next_run`·누적 실패 3건·`recording_checks_passed=false`. 이번 run 성공과 전체 attempt 상태를 구분한다.

## 보존·검증 근거

[제한 검사 보고서](limited_record_check_run_04.json)는 [검사 코드](check_saved_run_04.py)를 Python으로 실행해 생성했다.
예정 원시 key·job·반복 수, 입력/참조 identity·검증 표시·양수 값, phase 중앙값·ns→ms·최종 memory 최댓값·ratio, 소스/산출물 hash·이전 참조 동일성을 대조했고 실패 항목은 없다.
`record_integrity_checks_passed=true`·`run_successful=true`이며 기존 누적 실패 수는 별도로 남긴다.

Run 4 직전 파일 중 매번 갱신되는 최상위 coordinator metadata를 제외한 47개 파일은 hash 불변이다.
Run 1~3 원시값·부모 metadata·검사·완료 기록을 수정하지 않았다. Run 2 timeout을 이번 결과로 대체하거나 정상 정답 생성에 포함하지 않는다.

[부모 metadata](run_04/metadata.json), [coordinator metadata](metadata.json), [원시 memory](run_04/memory_repeats.csv),
[원시 timing](run_04/timing_repeats.csv), [최종 집계](run_04/measurements.csv)에 실제 결과를 보존한다.
[운영 사건](operator_events_run_04.json), [사전 관측·기존 hash](operator_context_run_04.json), [사전 점검 코드](preflight_run_04.py)에도 근거를 남겼다.

## 운영 사건

시작 직전 외부 전원 연결·배터리 37%·균형 조정 전원 계획을 실제 관측했다. 게임·통신 등 기존 사용자 보고는 실제 관측과 구분한다.
[자동 상태 기록](run_04_monitor.jsonl)은 [조회 코드](monitor_run_04.py)가 생성했으며 측정 job을 실행하거나 재시도하지 않는다.
[전원 사건 원본](windows_power_events_run_04.json)과 [조회 범위·상태](windows_power_query_run_04.json)는 측정 시작~종료 구간의 System 로그 사후 조회다.
조회 상태는 `no_matching_events`이며 지정 provider에서 일치하는 사건이 없었다. 이는 해당 로그 범위의 관측으로, 전원 상태 전체의 연속 인증이 아니다.
전원·절전·덮개 설정은 변경하지 않았다.

## 다음 단일 작업·미완료

사용자가 이어서 진행할 때 같은 HEAD·소스·설정·환경과 실제 사건을 확인하고 **Run 5 한 번**을 실행한다.
이번에는 요청한 Run 4만 실행했고 Run 5는 시작하지 않았다. 고정 시작 시각 제한은 없다.
독립 프로토콜 audit·후보 분석·공식 4지표 전환은 미완료다. 이번 작업에서 단위 테스트·모델 학습은 실행하지 않았다.

같은 HEAD를 유지하는 여섯 run의 설계에 따라 중간 완료 기록은 attempt 안에 남긴다.
루트 `research_progress.md`와 결과 commit은 전체 종료 또는 attempt 종료 결정 때 반영하며 이번에는 변경하지 않았다.

