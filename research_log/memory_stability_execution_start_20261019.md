# Memory 안정성 후속 검증 착수 기록

2026-10-19 사용자가 “지금 작업 시작해줘”라고 지시했다. 이전 18시 제안 대신 지금 착수하며,
연속 세 날짜는 10월 19~21일로 준비한다. 실제 측정 기준 시각 `t0`는 아직 없고 run 1 부모 metadata의
실제 시작으로 정한다. Run 3·5는 실제 `t0+24/48시간±60분`, run 2·4·6은 해당 첫 run 종료
30~90분 후 같은 로컬 날짜에 시작한다. 둘째 run의 운영 목표는 종료 +60분이다.

근거: [사전 설계](memory_stability_validation_design.md), [실행 준비안](memory_stability_execution_preparation_20261016.md).
시작 HEAD는 `103d1cbf66497692e92be646e8e867791b7079ea`이며 사용자 권한 Git 상태는 깨끗했다.
이 착수 기록·진행 문서를 commit한 HEAD에서 init하고, 이후 여섯 run과 audit·분석까지 HEAD를 유지한다.

## 읽기 전용 점검 — 2026-10-19 10:20경 KST

- Windows·Python 3.14.4·패키지·설정은 고정 설계와 일치했고 `pip check`는 `No broken requirements found.`였다.
- GetSystemPowerStatus의 ACLineStatus=1, 배터리 60%였다. 전원 구성표는 균형 조정이었다.
- 실제 AC 전원 모드는 `PowerGetUserConfiguredACPowerMode`로 Best Power Efficiency,
  GUID `961cc777-2547-4f9d-8174-7d86181b8a7a`임을 확인했다. 모드 해석은
  [Microsoft API 문서](https://learn.microsoft.com/en-us/windows/win32/api/powrprof/nf-powrprof-powergetuserconfiguredacpowermode)를 따른다.
  전원 구성표 이름과 실제 모드를 혼동하지 않으며 설정을 변경하지 않았다.
- 자동 절전 설정은 AC 18,000초·DC 180초, 최대 절전은 AC 0초·DC 57,600초였다.
- CIM으로 확인한 `python.exe`·`pythonw.exe` 목록은 비어 있었다. 이 관측만으로 다른 종류·원격 연구 작업의 부재나 사용자 보고를 대체하지 않는다.
- Python으로 C: 여유 25,677,258,752 bytes와 기존 추적 파일의 시작 SHA-256을 기록했다. 가용 자원은 실행 직전에 다시 확인한다.

## 허용된 착수와 아직 필요한 사건 기록

사용자 시작 지시에 따라 새 `attempt01`의 init을 진행한다. Init은 입력 생성·hash·계획 저장이며,
memory/timing worker 실측은 아니다. 실제 생성 경로와 성공·실패는 반환값 및 새 attempt의 metadata로 판단한다.

Run 1의 사건 기록을 위해 다른 연구 실험·학습·worker 실행 여부, 일반 동시 작업·OS 업데이트·기타 사건,
AC 연결 유지 가능 여부를 사용자에게 요청했다. 아직 답변을 받지 않았으므로 `none`이나
`no_research_jobs_running=true`를 사용자 확인 값으로 만들지 않는다. 실행용 사건 파일과 측정 run은 답변 뒤에 진행한다.
첫 run의 `manual_reboot_since_previous_run`은 init과 run 직전 부팅 시각 대조 및 이전 run 없음의 설명을 함께 기록한다.

새 폴더를 기존 결과에 이어 쓰지 않는다. Init 이후 사건 기록·실행 결과는 attempt 안에만 남기고,
측정 중 진행 문서 수정이나 commit을 하지 않는다. 실제 init·run 결과를 이 사전 기록에서 완료로 주장하지 않는다.
공식 score는 v2의 3지표, memory는 `validation_only`, `score_inclusion=false`로 유지한다.
