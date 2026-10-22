# 동일 환경 반복 검증 Run 2 실행 종료 — 실패 포함

상태: **전체 예정 job 실행·종료 기록·실패 보존 확인 완료. 정상 성공 조건 미충족.**

- 설계 `memory_repeatability_v1`, collector revision 2, `validation_only`, `score_inclusion=false`.
- 측정 commit: `a8c3e47edc4f9d231605434c464b036240b7b2ed`.
- 실제 시작 KST: 2026-10-19T22:45:37.935528+09:00.
- 실제 종료 KST: 2026-10-20T08:49:24.180423+09:00.
- 실제 부모 wall 시간: 36226.244895초. 절전·대기 구간을 포함하므로 codec 실행 시간이나 정상 소요 시간으로 해석하지 않는다.
- Run 1 종료 후 실제 시작 간격: 1611.617333초. 이 설계에는 시각·날짜·간격 제한이 없다.
- 예정 job 3696개 전체 종료. Memory 3360행: `ok` 3357·`timeout` 3. Timing 3360행: 모두 `ok`·`verified=True`.
- 최종 336쌍 중 333쌍 `verified=True`, 3쌍 `verified=False`. 실패 조합의 모든 수치 집계는 공란이며 정상 정답 생성에 사용할 수 없다.
- 부모 `completed_with_failures`, coordinator `awaiting_next_run`, 양쪽 `recording_checks_passed=false`. 종료 처리 완료·소스 불변·활성 claim 없음. Coordinator 대기 상태는 정상 성공 판정이 아니다.

## 실제 오류와 시스템 로그

실패는 모두 memory의 decompress worker timeout이다.

| sample | algorithm | repeat | schedule index |
|---|---|---|---|
| stability_000023 | zstd | 1 | 3295 |
| stability_000009 | bz2 | 4 | 3313 |
| stability_000027 | bz2 | 1 | 3320 |

두 timeout의 stdout에는 worker가 출력한 `verified=true`와 peak 값이 있었지만, 정상 종료 계약을 충족하지 않아 원시 측정값으로 채택하지 않았다. Worker나 실패 반복을 재실행·보충·삭제하지 않았다.

[Windows 전원 로그](windows_power_events_run_02.json)는 System 채널의 Kernel-Power·Power-Troubleshooter를 UTC 2026-10-19 13:40~2026-10-20 00:00 범위로 조회한 실제 event 시각·ID·provider·message다. 측정 종료 후 사건도 포함되며 측정 중 사건과 구분한다.
로그에 덮개(Lid)로 인한 Modern Standby 진입과 이후 재개가 있고 긴 timeout 구간과 겹친다. 이는 절전의 영향을 지지하는 근거다. 특정 codec의 복원 불일치가 확인됐다는 뜻이나 모든 지연의 원인이 확정됐다는 뜻은 아니다.
측정 시간이 두 날짜에 걸쳤다는 사실 자체를 실패 원인으로 삼지 않는다.

Metadata 저장 접근 경합 1건은 사전 고정한 저장 전용 재시도로 복구됐고 사건이 기록됐다. 측정 job 재시도는 아니다.

## 완료한 검증과 근거

[실패 보존·저장 무결성 보고서](limited_record_check_run_02.json)는 [검사 코드](check_saved_run_02.py)를 Python으로 실행해 생성했다.
보고서는 `record_integrity_checks_passed=true`와 `run_successful=false`를 구분한다.
예정 원시 key·job·반복 수, 정상 행의 검증 표시·양수 값·중앙값·단위 변환·phase memory 최댓값, 실패 행·공란 pair 집계·오류 전파, 소스·산출물 hash·전 run 참조 동일성을 대조했다.
Run 2 직전 존재한 파일 중 runner가 매번 갱신하는 최상위 metadata를 제외한 15개 파일은 hash 불변이다. Run 1 원시값·부모 metadata·제한 검사·완료 기록은 그대로 보존돼 있다.

[부모 metadata](run_02/metadata.json), [최상위 metadata](metadata.json), [운영 사건](operator_events_run_02.json),
[실행 전 관측·기존 증거 hash](operator_context_run_02.json), [부팅 시각 대조](preflight_boot_run_02.json)에 근거를 남겼다.
이번 작업에서 단위 테스트·모델 학습·독립 프로토콜 audit·후보 분석은 수행하지 않았다. 공식 3지표 정의를 바꾸지 않았다.

## 현재 진행 위치와 다음 단일 작업

요청한 Run 2 한 번은 실패를 포함해 종료했고 Run 3는 실행하지 않았다.
현재 attempt는 완전한 정상 행렬을 요구하는 후보 채택 조건을 충족하지 못한다. 기존 run을 수정하거나 실패 sample을 제외해서 통과시킬 수 없다.
다음 단일 작업은 절전·덮개 닫기 중 실행 조건과 현재 attempt의 후속 처리 방침을 정하는 것이다. 전원 설정을 임의 변경하지 않았다.
CLI는 실패를 포함한 기록의 후속 수집을 허용하므로 여기서 attempt를 임의 폐기하거나 새 attempt를 생성하지 않는다.

여섯 run 동안 동일 HEAD를 유지하는 설계에 따라 중간 상태는 이 attempt 안에 기록한다.
루트 `research_progress.md`·commit을 지금 변경하지 않았다. 전체 종료 또는 이 attempt 종료 결정 시 근거와 함께 반영한다.

