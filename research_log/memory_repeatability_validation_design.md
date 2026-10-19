# 동일 환경 memory·timing 반복 검증 설계

작성일: 2026-10-19. 설계 ID: `memory_repeatability_v1`.
상태: 사용자 승인 변경을 새 실측 전에 고정 / `validation_only` / `score_inclusion=false`.

사용자는 고정 시각을 맞추는 대신 전처럼 진행할 수 있는지 물었고, 동일 환경 반복 검증으로 변경하는 설명 뒤
“지금으로 진행. run 1 진행하자”라고 지시했다. 이 문서는 그 변경을 실행 전에 명시한다.
공식 기준 [프로토콜 v2](../research_protocol_v2.md)와 공식 3지표 config는 변경하지 않는다.

## 1. 질문·변경 이유·해석 범위

관측한 같은 컴퓨터·코드·패키지·압축 설정에서 반복 run의 memory 대표값·timing·후보 선택이 얼마나 변하는지 확인한다.
현재 사용자 운영 방식에서는 [기존 3일 설계](memory_stability_validation_design.md)의 특정 시각·날짜·30~90분 간격을
유지하기 어렵다. 이는 측정 데이터 삭제나 가중치 조정 사유가 아니라 별도 운영 프로토콜을 만드는 이유다.

연속 세 날짜, 같은 시각 ±60분, 날짜별 두 run, 종료 후 30~90분, 같은 로컬 날짜 요구를 적용하지 않는다.
Run은 1~6 순서로 겹치지 않게 실행한다. 앞 run 종료 직후 다음 run을 실행할 수 있고 늦게 이어도 시간 차이만으로
실패시키지 않는다. 실제 시작·종료·간격·날짜를 보존하고 해석에 사용한다. 같은 실제 세션·일자였다고 가정하지 않는다.
결과는 관측한 환경과 run들의 반복 검증이며, 날짜 간 안정성·미래 오차 상한·다른 hardware 일반화의 증명이 아니다.

## 2. 변경하지 않는 측정·입력·저장 계약

[새 runner](../src/memory_repeatability_validation.py)는 기존 runner `82041e8`의 수집 구현을 별도 파일로 고정해 파생했다.
기존 runner·설계·audit·분석기는 수정하지 않는다. 두 프로토콜을 실수로 혼용하지 않도록 study ID와 경로를 분리한다.

- 같은 원래 명세의 핵심 입력과 작은 입력, seed·generator·크기·매개변수·중복 보존, 네 압축기·압축 수준을 유지한다.
- 여섯 run의 전체 입력 행렬·job 순서 seed·memory/timing 분리·각 phase 5회·중앙값·memory phase 중앙값의 최댓값을 유지한다.
- 부모의 실제 참조 복원 bytes 비교, worker의 hash·검증·양수 값·응답·종료 코드 검사, 타이머 범위·timeout·bytecode 옵션을 유지한다.
- 실패·미실행 key·부분 timing 원시값·원래 예외·종료 오류를 보존한다. 자동 job retry·sample 삭제·보간·중단 run 재개는 없다.
- 입력·plan 불변, run별 별도 부모, 배타적 claim, 소스·환경·HEAD·원시 산출물 hash 검사, 기존 경로 덮어쓰기 거부를 유지한다.
- 전원·게임·일반 활동·업데이트·통신 등 실제 사건과 불확실성을 기록한다. 다른 연구 benchmark·학습·worker는 동시에 실행하지 않는다.

기존 timing worker의 응답은 그대로 `memory_stability_v1` **worker wire protocol**을 쓴다.
새 plan의 `timing_worker_design_id`가 이를 명시하고 adapter는 그 응답만 검증한다. 새 study ID는 별도로
`memory_repeatability_v1`이며 이전 3일 검증을 수행했다고 주장하지 않는다. Memory worker와 codec도 변경하지 않는다.
Sample ID의 `stability_` 접두사는 동일 입력 명세의 식별자이며 study ID와 구분한다.

새 경로는 `data/results/memory_repeatability_v1_<UTC timestamp>_<attempt_id>/`이고
layout·CSV 열·원시값·실패 및 환경 provenance는 기존 수집 계약을 따른다. 예전 attempt01의 측정값을 복사하지 않는다.
Init은 깨끗한 Git 상태에서 수행하고 동일 HEAD로 여섯 run을 진행한다. 중간 사건·상태 기록은 attempt 안에 남긴다.

### Collector revision 2: metadata 파일 I/O 보완

Revision 1의 새 attempt01은 metadata 원자 교체에서 Windows 접근 거부로 중단됐다. 그 원시값과 오류를
실패 증거로 보존하고 이어 쓰지 않는다. 측정 정의는 유지하며 revision 2의 새 HEAD·새 attempt로 전체 run을 실행한다.
Plan과 metadata에 `collector_revision=2`와 `metadata_io_policy`를 기록한다.

새 runner의 Windows JSON 조회는 `CreateFileW`의 read/write/delete 공유를 허용한다.
[Microsoft API 문서](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)의 공유 규칙을 따른다.
다만 실제 임시 fixture에서 열린 대상에 대한 `os.replace`는 삭제 공유가 있어도 실패했다.
[CPython 이슈의 Windows 구현 설명](https://bugs.python.org/issue46003)과 일치하며, 공유 설정만으로 교체 성공을 보장하지 않는다.
조회 핸들은 문자열을 읽은 즉시 닫고 JSON 해석은 그 뒤에 한다. 짧은 조회와의 교체 경합은 아래 저장 재시도로 처리한다.
Metadata 저장에만 WinError 5·32·33인 경우 최대 5번, 대기 0.05·0.10·0.15·0.20초로 재시도한다.
각 실패 시각·대상·순번·코드·오류를 metadata의 `metadata_save_retry_events`에 남긴다.
영구 실패 시 첫 예외를 다시 발생시키고 기존 파일을 보존한다. 저장 자체가 끝내 실패하면 새 사건 목록도
디스크에 반영되지 않을 수 있으므로 stderr와 마지막 성공 checkpoint를 함께 확인한다.
다른 오류·중단은 즉시 전파한다. 이 제한적 저장 재시도는 압축기·worker·측정 job·중단 run 재시도가 아니다.
측정 중 상태 조회에도 새 runner의 공유 조회 함수를 사용한다. 잠금 경합 fixture는 임시 파일에서만 재현한다.

## 3. 사전 후보 계산과 판단 범위

후보 weight·score 식·reference anchor·memory_only/timing_only/joint 시나리오·정확한 tie order·방향 있는 run 쌍 regret은
기존 설계 6절과 같다. 수치 budget `delta=0.01`, `epsilon=0.005`, `w_memory_max=0.20` 및
`L <= epsilon/(2*w_memory_max)`의 원래 식, memory-only/joint regret 한계를 그대로 고정한다.
날짜·시각 조건만 제외하고, 완전한 행렬·복원 검증·유한 양수 값·순서/비겹침·환경/소스/입력 불변·종료와 독립 audit를 요구한다.
관측된 조건 만족은 공학적 후보 판단이며 과학적 채택이나 공식 4지표 전환이 아니다.

새 프로토콜 전용 독립 audit·분석 연결은 후속 구현이다. 기존 3일 audit를 완화하거나 새 결과를 기존 ID로 바꾸어 통과시키지 않는다.
현재 Run 1에서는 저장 수량·flag·원시 중앙값·hash 등 제한된 검사를 수행하고 전체 audit·후보 판단 완료를 주장하지 않는다.

## 4. 실행 방식과 이번 사용자 요청

`python -B -m src.memory_repeatability_validation init --attempt-id <id> --reason <reason>`으로 새 입력·plan을 준비하고,
`run --study-dir <new-study-dir> --events-file <actual-event-json>`은 다음 예정 run 한 개만 실행한다.
시간을 기다리거나 자동 예약하지 않는다. 이어지는 run도 같은 CLI를 바로 호출할 수 있다.
이번 요청 범위는 **새 설계의 Run 1 한 번**이다. 나머지 run과 전체 audit·분석은 미완료로 남긴다.

기존 `memory_stability_v1` attempt01은 당시 설계에서 Run 2 시작 창이 지난 미완료 증거로 계속 보존한다.
이번 변경을 과거에 소급 적용해 그 attempt를 통과시키거나 과거 결론을 바꾸지 않는다.
