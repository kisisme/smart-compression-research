# Attempt01: Run 1 완료·Run 2 실행 창 경과

상태 확인: 2026-10-19 15:01 KST. **Run 1 측정·저장 완료 / 전체 attempt 미완료 / 고정 일정에 따른 후속 실행 불가.**

실행 기준 commit은 `f66f5c0b7e1a41ffb1af66f42d961451e5bf8ac7`이며,
[계획](plan.json)과 [Run 1 metadata](run_01/metadata.json)는 원본대로 보존한다.
[제한된 저장 기록 검증·후속 실행 가능성 평가](run_01_saved_record_review.json)에 계산 결과와 기존 증거 13개의 SHA-256을 남겼다.

## 실제 Run 1 결과

- 시작: 2026-10-19 10:29:03.899448 KST.
- 종료: 2026-10-19 10:54:05.908610 KST. 경과 1,502.009162초.
- Job 3,696개, memory 원시 반복 3,360개·timing 원시 호출 3,360개 모두 `ok`.
- 저장 참조·pair 집계 각각 336개, 실패 반복 0개. 저장 검증 flag와 양수 원시값을 확인했다.
- 원시 key의 전체 수량·고유성·예정 집합, 원시 중앙값의 ms 변환·phase memory 중앙값·최종 최댓값, 산출물 hash를 Python으로 재확인했다.
- Runner의 `completed`, 종료 처리 `completed`, `recording_checks_passed=true`, `provenance_unchanged=true`, `validity_issues=[]`와 종료 오류 부재를 확인했다.

이는 Run 1의 제한된 저장 기록 검증이다. 전체 여섯 run 독립 audit·후보 분석·사전 안정성 판정은 수행하지 않았다.
복원 flag·hash는 저장 증거이며 압축·해제를 새로 실행해 독립 복원 인증한 것이 아니다.

## 이어서 실행하지 않은 이유

[고정 설계](../../../research_log/memory_stability_validation_design.md)는 날짜별 둘째 run을 첫 run 종료 후 30~90분에 시작하도록 한다.
Run 1 실제 종료에서 계산한 Run 2 시작 창은 **2026-10-19 11:24:05.908610~12:24:05.908610 KST**였다.
15:01 확인 시 Run 2는 실행되지 않았고 창이 경과했다. 늦은 Run 2를 정상 일정처럼 실행하거나 기준을 완화하지 않는다.
미실행의 구체적 원인을 인터넷 단절 등으로 단정하지 않는다.

최상위 metadata의 `awaiting_next_run`과 `pending_independent_audit`는 Run 1 종료 당시 저장 상태로 유지한다.
현재 일정 적격성이나 전체 검증 통과를 뜻하지 않는다. 새로운 측정 실패 행·누락 행을 사후 생성하지 않았다.

## 보존과 후속 계획

기존 입력·계획·원시값·metadata·사건 파일·부모 출력 13개를 수정하지 않고 함께 보존한다.
기존 실패나 이번 일정 경과를 숨기지 않는다. 전체 사전 검증을 다시 진행하려면 사유와 사용자 확인을 남긴
별도 새 attempt에서 여섯 run 전체를 시작해야 한다. 이 문서 작업에서 새 attempt나 후속 run을 실행하지 않았다.
기존 입력 일부나 Run 1 수치를 새 attempt의 측정값으로 복사하지 않는다.

공식 score는 v2의 3지표이며 memory는 `validation_only`, `score_inclusion=false`이다.
