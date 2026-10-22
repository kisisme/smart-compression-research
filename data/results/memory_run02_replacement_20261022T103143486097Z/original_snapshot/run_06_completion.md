# 동일 환경 반복 검증 Run 6 완료

**마지막 Run 6 실측·종료·제한된 저장 검사 완료. Run 6 새 실패 0건.**

- 측정 commit: `a8c3e47edc4f9d231605434c464b036240b7b2ed`, 설계 `memory_repeatability_v1`, collector revision 2.
- 실제 시작 KST: 2026-10-22T16:00:45.777913+09:00.
- 실제 종료 KST: 2026-10-22T16:27:29.070826+09:00.
- 부모 wall 시간 1603.292913초, Run 5 이후 간격 83631.368218초. 고정 시각·날짜·간격 제한은 없다.
- Job 3,696개, memory 3,360행, timing 3,360행, 최종 336쌍. 모두 저장 상태 `ok`·`verified=True`, 실패·metadata 저장 재시도 0건.
- 부모 `completed`, 종료 처리 완료·소스 불변·활성 claim 없음.
- Coordinator는 여섯 run을 종료한 `completed_with_failures`이며 누적 실패 3건은 기존 Run 2의 기록이다. Coordinator CLI 종료 코드 1은 이 최종 상태를 반영하며 새 Run 6 실패나 parent crash가 아니다.

[제한 검사](limited_record_check_run_06.json)는 [검사 코드](check_saved_run_06.py)를 실제 Python으로 실행해 생성했다.
원시 행렬·검증 표시·양수 값·중앙값·ns→ms·phase memory 최댓값·ratio·소스/산출물 hash를 대조했다.
Run 6 이전 파일 중 갱신되는 coordinator metadata를 제외한 81개 파일은 hash 불변이다.
기존 Run 2 timeout을 재실행·대체·보충하지 않았다.

[원시 memory](run_06/memory_repeats.csv), [원시 timing](run_06/timing_repeats.csv), [최종 집계](run_06/measurements.csv),
[부모 metadata](run_06/metadata.json), [운영 사건](operator_events_run_06.json), [사전 관측](operator_context_run_06.json),
[자동 상태 기록](run_06_monitor.jsonl), [전원 사건](windows_power_events_run_06.json), [조회 범위](windows_power_query_run_06.json)를 보존한다.

사전 관측 UTC 2026-10-22T07:00:42.340171+00:00에 외부 전원 미연결·배터리 62%였다. 실제 시작까지 3.437742초 간격이 있으므로 이를 연속 관측으로 표현하지 않는다.
전원 로그 조회 상태는 `queried`이고 실제 이벤트 ID별 수량은 {"105":1}이다. 전원·절전·덮개 설정은 바꾸지 않았다.
게임·통신·업데이트 등 기존 사용자 보고와 직접 관측을 구분한다.

[전체 수집 마감](collection_completion.md)과 [마감 집계](collection_summary.json)에 여섯 run의 최종 상태를 정리한다.
현재 `validation_only`·`score_inclusion=false`이며 독립 프로토콜 audit·후보 분석·공식 4지표 전환은 미완료다.
이번에는 단위 테스트·모델 학습을 실행하지 않았다. 추가 run이나 실패 반복 재측정은 하지 않았다.

