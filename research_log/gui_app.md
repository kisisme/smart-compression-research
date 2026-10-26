# Tkinter GUI 연결 및 검증 — 2026-10-24~26 (KST)

`gui_app.py`는 기존 [GUI 작업 계층](gui_jobs.md)을 이용하는 로컬 Tkinter/ttk 창이다.
작업 시작 HEAD는 `ea3892d`이며 [최소 설계](gui_demo_design_v1.md)의 세 탭을 연결했다.
공식 기준·설정·CLI·특징·측정·점수·저장 모델을 변경하지 않았다.
Memory는 참고 지표이고 추가 구현·측정·공식 점수 편입은 계속 보류한다.

## 실행과 동작

프로젝트 루트에서 실행한다.

```powershell
.\.venv\Scripts\python.exe -B gui_app.py
```

- **Smart 압축:** 파일·출력 부모·새 결과 폴더 이름·사용 목적·모델을 명시한다.
  모델 폴더를 비워 두면 기존 Pilot 모델을 사용한다. 다른 모델은 직접 만든 신뢰 가능한 것만
  선택한다. 검증된 manifest의 알고리즘·크기·ratio·통계 특징·보정되지 않은 모델 출력을 표시한다.
- **복원:** manifest가 있는 package를 선택하고 package 밖의 새 폴더에 복원한다.
  원래 파일명·크기·SHA-256과 검증 상태를 표시한다.
- **실제 비교:** 파일을 네 압축기로 실제 비교하고 검증·bytes·ratio·압축/해제 ms·선택한 mode의
  점수와 세 mode의 best를 표시한다. 작은 값이 유리하며 표시 자릿수로 동점을 다시 판정하지 않는다.

`이 결과 복원`과 `사용한 파일 실제 비교`는 해당 입력을 준비한다. 각 탭의 실행 버튼을 별도로
눌러야 작업하며 창 생성·탭 이동·mode별 점수 보기로 모델이나 비교를 자동 실행하지 않는다.
Smart와 Compare가 모두 정상이고 입력 hash·config hash·압축 설정·해당 mode의 가중치가 일치할 때만
예측/실측 best와 해당 파일의 `예측 알고리즘 점수 - 실측 best 점수`를 대조한다.
모델·입력·사용 목적 변경 및 실패 뒤에는 이전 Demo 대조를 해제한다.
이 차이는 단일 파일의 동작 확인이며 accuracy·Macro F1·일반화 평가가 아니다.

Tk thread는 `after()`로 queue를 확인하고 계산·자식 프로세스 대기를 하지 않는다.
모든 탭은 하나의 JobRunner를 공유한다. 실행 중 입력·중복 실행·다른 탭과 닫기를 잠그고
불확정 진행 표시를 사용한다. 취소나 백분율·codec별 실시간 진행은 제공하지 않는다.
완료 뒤 제어를 복구하고, 종료 0만으로 성공을 만들지 않으며 계층이 확인한 상태를 사용한다.
부분/무효/실패 결과에는 정상 점수·best·추천을 표시하지 않는다.

`실행 기록`에는 요청·명령·시각·상태·결과·stdout/stderr·로그 경로가 있다.
로그만 실패하면 실제 파일 처리 성공을 유지하고 별도 경고한다.
기존 출력·Windows 예약 이름·경로 탈출·빈 입력·필수 선택 누락은 실행 전 차단한다.
로그와 package/보고서는 새 경로에 보존하고 실패 결과를 삭제하거나 자동 재시도하지 않는다.

## 자동 검증 완료

전용 [Tk 위젯 테스트](../tests/test_gui_app.py) 15개와 기존 계층 회귀 18개를 합친
다음 최종 실행에서 **33개가 9.402초에 통과**했다. 인위적 queue/측정값은 표시·오류 계약용
fixture이며 연구 데이터가 아니다. 실제 Tk 창을 생성해 최소 크기 960×720에서 세 탭의 주요
버튼·표·상태 영역이 창 안에 들어오는지 좌표로 확인했다. 픽셀/스크린샷 검증과는 구분한다.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_gui*.py' -v
```

필수 입력·새 출력·예약 이름·중복/닫기 차단·queue ID·정상/부분/무효/오류·로그 경고·
상태 복구·수동 입력 준비·Demo 일치/불일치와 오래된 대조 해제를 검증했다.
전체 저장소 suite는 실행하지 않았다.

[실제 창 검증 도구](../tests/validate_gui_app.py)는 새 출력과 새 JSON만 생성한다.
다음 명령의 실제 결과를 [완료 기록](gui_validation_20261026.json)에 보존했다.
다시 실행하려면 아직 존재하지 않는 record 경로를 지정해야 한다.

```powershell
.\.venv\Scripts\python.exe -B tests/validate_gui_app.py --record research_log/gui_validation_20261026.json
```

실제 창을 매핑하고 애플리케이션 callback을 호출하면서 Tk 이벤트를 처리했다.
README 사본을 한국어·공백·`&`·emoji가 있는 새 입력 경로에 저장해 사용했다.
저장된 두 Pilot 모델×세 mode의 Smart→복원 12개 작업과 Compare 1개가 정상 완료됐다.
별도 새 복사본의 payload만 의도적으로 손상시킨 복원 1개는 `failed`로 판정됐고
출력 생성 없이 손상본과 기존 정상 package를 보존했다. 총 자식 작업은 14개다.
기존 Compare 출력 요청 1개는 자식 실행 전 차단했으며 기존 bytes가 유지됐다.

각 실제 작업 동안 Tk heartbeat가 계속 실행됐고 중복/닫기 차단·완료 뒤 제어 복구·
queue 결과와 저장 로그 일치를 확인했다. Tk callback 오류는 없었다.
Compare 원시 반복 40개·집계 4개·정답 3개의 중앙값과 기존 공식 scorer의 점수를
저장 CSV에서 Python으로 다시 계산했다. 입력·설정·소스·기존 모델·새 정상 package 등
35개 보호 파일의 SHA-256도 불변이었다. 실제 원시 산출물 원문·표시 행·Demo·테스트 출력을
완료 JSON에 포함했다. 실제 파일은 다음 Git 제외 경로에 보존한다.

```text
data/temp/gui_app_validation_20261025T234658401068Z/
```

이는 파일 동작·화면 callback/이벤트 검증이다. 시간 측정값을 end-to-end 성능이나
모델 일반화 성능으로 해석하지 않으며 새 Pilot·재학습·memory 측정을 수행하지 않았다.
프로그램은 파일 전체를 메모리에 읽는 기존 backend를 사용한다.

## 중단된 시도와 미완료 검증

2026-10-24의 첫 실제 창 검증은 첫 Smart 작업 대기 중 harness의 120초 deadline에서
`TimeoutError`로 중단됐고 완료된 화면 흐름은 기록되지 않았다. Backend의 후속 로그는
`succeeded`이며 검증된 package를 남겼다. 긴 시각 공백의 원인을 절전이라고 확정하지 않는다.
[중단 근거](gui_validation_interrupted_20261024.json)에 partial record·뒤늦은 backend 로그를
보존했고 원래 디렉터리 `data/temp/gui_app_validation_20261024T091306290446Z/`를 변경하지 않았다.
완료 실행은 새 경로에서 별도로 수행했다.

Windows 화면 자동화 도구는 `failed to write kernel assets` / `os error 3`로 초기화되지 않았다.
세션 reset 뒤 재시도와 10월 26일 재연결에서도 실패했다. 적용한
[computer-use SKILL.md](C:/Users/s0109/.codex/plugins/cache/openai-bundled/computer-use/26.1021.31345/skills/computer-use/SKILL.md)는
“Import it directly by package name from the JavaScript session”을 지시하고
자체 helper client를 금지한다. 따라서 다른 OS 입력/캡처 수단으로 우회하지 않았다.

**미완료:** 실제 마우스·키보드 입력, 파일/폴더 선택 대화상자 및 OS 메시지창 조작,
스크린샷으로 한국어 글꼴·잘림·긴 경로·DPI/배율 점검. 자동 테스트의 실제 Tk 매핑/좌표·상태 확인과
이 시각/입력 QA를 구분하며, GUI의 모든 사용 환경이 검증됐다고 기록하지 않는다.
다음 단일 작업은 이 Windows 입력·시각 QA와 발견된 UI 문제 수정이다.
