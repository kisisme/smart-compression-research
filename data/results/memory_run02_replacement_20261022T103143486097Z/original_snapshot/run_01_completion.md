# 동일 환경 반복 검증 Run 1 완료

상태: **Run 1 실측 및 제한된 저장 기록 검사 완료**. 전체 여섯 run·독립 프로토콜 audit·후보 분석·공식 4지표 전환은 미완료.

- 설계: `memory_repeatability_v1`, collector revision 2, `validation_only`, `score_inclusion=false`.
- 실행 commit: `a8c3e47edc4f9d231605434c464b036240b7b2ed`.
- 실제 시작 UTC: 2026-10-19T12:54:20.986711+00:00.
- 실제 종료 UTC: 2026-10-19T13:18:46.318195+00:00.
- 부모 실행 시간: 1465.331484초. Agent의 후속 조회 시각이나 검사 시간을 측정 시간으로 합산하지 않는다.
- 완료 job: 3696. Memory 원시값 3360행, timing 3360행, 최종 sample×algorithm 336쌍.
- 모든 원시 행의 저장 상태 `ok`, `verified=True`; 실패 반복 0. Metadata 저장 재시도 사건도 없다.
- 부모 `completed`, coordinator `awaiting_next_run`, 종료 처리 완료, 활성 claim 없음, Run 2 미실행.

[제한 검사 보고서](limited_record_check_run_01.json)는 [검사 코드](check_saved_run_01.py)를 Python으로 실행해 생성했다.
예정 원시 key·job·phase 반복 수·입력/참조 식별자·검증 표시·양수 값·원시 중앙값·ns→ms·phase memory 최댓값·ratio·소스/산출물 hash·환경/종료 기록 flag를 대조했고 실패 항목은 없다.
코덱을 다시 실행하거나 기존 원시값을 수정하지 않았다. 이 검사는 새 프로토콜 전용 독립 audit나 후보 score 분석을 대신하지 않는다.

[계획](plan.json), [부모 metadata](run_01/metadata.json), [coordinator metadata](metadata.json),
[운영 사건](operator_events_run_01.json), [실행 직전 관측](operator_context_run_01.json)에 근거를 보존한다.
전원·게임·통신에 관한 사용자 보고와 실제 관측을 구분했으며 연속 관측했다고 주장하지 않는다.

첫 실패 attempt01은 commit `b249d53`에 보존했다. 그 일부 원시값을 이번 결과에 재사용하지 않았고 원본 12개 파일 hash 불변을 재확인했다.
Metadata I/O 수정 전용 테스트 47개는 실행 전 통과했다. 전체 저장소 테스트 통과나 날짜 간 안정성을 주장하지 않는다.

## 다음 단일 작업

사용자가 이어서 진행할 때 같은 HEAD·소스·설정·환경을 확인하고 실제 사건 JSON을 새로 기록한 뒤 **Run 2 한 번**을 실행한다.
고정 날짜·시각·종료 후 간격 제한은 없다. 이번 요청에 따라 Run 2는 자동 실행하지 않았다.

여섯 run 동안 동일 HEAD를 유지하는 사전 설계에 따라 이 중간 완료 기록은 attempt 내부에 남긴다.
루트 `research_progress.md`와 결과 commit은 여섯 run 종료 또는 terminal failure 때 갱신한다.
현재 tracked 파일은 깨끗하며 이 새 attempt만 untracked이다. 이 결과를 보존하려고 지금 HEAD를 변경하면 후속 run의 provenance 조건이 깨지므로 중간 commit을 만들지 않는다.

