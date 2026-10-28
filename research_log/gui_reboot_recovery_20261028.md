# 재부팅 후 GUI 검증 재개 — 2026-10-28

상태: **새 연결/GUI 실행 확인 / 실제 화면 캡처·native QA 미완료**.
시작 HEAD는 `6f4743f319c509b97ef741ed705a9d57859e1296`이다. [실제 근거 JSON](gui_reboot_recovery_20261028.json)에 실행·중단·관찰 상태와 보호 hash를 보존한다.

사용자가 컴퓨터 재부팅을 알려 줘 새로 시작했다. 기존 `gui_native_20261028_01`은 launch와 초기 관찰까지만 기록된 상태에서
daemon recovery로 직전 tool 호출이 끊겼다. 재조회에서 GUI/프로세스가 없고 completed 기록도 없었다.
정확한 process 종료 원인은 남지 않았으므로 단정하지 않는다. 연구 자식 작업이 시작된 흔적은 없고 이 시도의 원본은 보존했다.

새 `gui_native_20261028_02`에서 기존 읽기 전용 observer와 README 사본을 사용해 GUI를 별도로 표시했다.
제품 GUI/연구 엔진·모델/config를 수정하지 않았다. 새 fixture 입력은 연구 후보가 아니며 원래 실행/결과와 섞지 않는다.
Sky 초기화·창 조회·GUI 접근성 정보는 정상이나 screenshot은 PyCharm이었다.
기존 플러그인으로 진행할 수 없어 내장 `cua_repl` 인터페이스도 확인했다. 첫 inventory timeout 후 재시도는 성공했고,
정확한 GUI window ID로 선택했지만 screenshot은 다시 PyCharm이었다. 내장 도구 문서에 Windows screenshot도 Sky를 통한다고 명시되므로
이를 독립적인 두 capture 구현의 검증으로 해석하지 않는다. 이후 UI 입력은 새 도구 지침에 따라 cua_repl에서만 시도했다.

이름이 확인된 제목 표시줄 최대화 입력은 `user input was detected`로 차단됐고 성공으로 기록하지 않았다.
사용자가 직접 최대화하고 잠시 입력을 멈추는 확인에 응답했다. 그 뒤 capture 요청은 timeout됐고,
창 목록/바인딩을 갱신한 한 차례 복구에서는 최대화에 따른 ‘복원’ 버튼을 확인했지만 screenshot은 여전히 PyCharm이었다.
GUI 본문 좌표를 추측해 클릭하지 않았고 다른 앱/터미널 UI를 자동 조작하지 않았다. 화면 도구의 정확한 내부 원인은 아직 미확인이다.
이미 시도한 창 전환·커널 reset·재부팅을 효과가 입증된 해결책이라고 기록하지 않는다.

현재 저장 기록에서 압축/복원/Compare 작업은 0개이고, 두 시도의 보호 파일 합집합 250개 hash가 일치한다.
이전 실제 Tk callback/backend 검증은 기존 완료 근거 그대로이며 이번에 테스트 suite를 다시 실행한 것은 아니다.
연구 데이터셋 선정/동결·특징/모델 평가·memory 측정도 하지 않았다. Screenshot payload는 저장하지 않았다.

같은 실패를 반복하지 않고 사용자에게 진행 방식을 요청했다.
수동 GUI 검증을 선택하면 사용자가 실제 버튼/선택창을 조작하고 observer 및 저장 package/log와 복원 hash를 검사하며,
자동 native/픽셀 QA 완료와 구분해 기록한다. 화면 검증 보류를 선택하면 외부 도구 blocker를 명시적으로 남긴 채
다음 단일 연구 작업인 후보 선정/실제 corpus 동결을 기존 notice/citation/review/overlap 근거와 연결한다.
아직 선택 전이므로 어느 쪽도 실행/완료로 기록하지 않았다.

## 사용자 선택: 수동 GUI 검증 후 연구 계속

사용자가 ‘수동 GUI 검증 후 연구 계속’을 명시적으로 선택했다.
[고정 수동 계획](gui_manual_qa_plan_20261028.json)은 README 긴 경로 사본·archive/Random Forest·새 출력 이름과 검증 순서를 보존한다.
먼저 사용자가 native 파일 선택창을 통해 Smart 작업 한 건을 실행하도록 안내하고, 결과를 assistant가 확인한 뒤 복원/Compare를 순서대로 진행한다.
작업 성공·복원 hash·원시 결과는 파일/로그로 검증하고 화면 잘림/가독성 보고는 사용자 관찰로 구분한다.
계획 작성 시 세 출력은 모두 존재하지 않았으며 아직 Smart도 실행하지 않았다. 사용자 동작이나 화면 도구 문제를 해결 완료로 소급 기록하지 않는다.
