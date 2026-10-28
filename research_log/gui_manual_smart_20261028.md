# 수동 Smart 압축·실제 화면 스크롤 확인 — 2026-10-28

상태: **사용자 native Smart 실행·저장 검증 및 제한된 agent 화면 조작 완료 / 수동 GUI 복원·Compare는 미완료**.
실제 Smart 실행과 이번 검증 HEAD는 `508aec2184ec4a95b3987cee3a0e373d2292f809`이다.
[고정 수동 계획](gui_manual_qa_plan_20261028.json), [검증 프로그램](verify_manual_smart_20261028.py),
[실제 저장 검증 근거](gui_manual_smart_verified_20261028.json)를 함께 보존한다.

## 실제 실행·검증 결과

사용자가 긴 한글/공백/ampersand/emoji 경로의 README 사본을 native 파일 선택창에서 선택하고
archive / Random Forest / `manual_smart_20261028_01`로 Smart 압축했다. 사용자에게 표시된 ‘완료 · 검증 통과’를
현재 observer와 실제 package·로그에 대조했다. 이 입력은 GUI 동작 확인용이며 실제 연구 holdout 후보가 아니다.

| 항목 | 저장 파일을 Python으로 읽어 확인한 값 |
|---|---|
| 선택 알고리즘 | zstd |
| 원본 bytes | 4,433 |
| 압축 bytes | 2,147 |
| 압축률 (압축/원본) | 0.48432212948342 |
| 저장 payload를 메모리에서 복원해 원본 bytes와 대조 | 일치 |
| 복원 SHA-256 | `391345c9f5dd176f9a7e61c1e567075b9f0c00f723386905f77ce91020409a71` |
| manifest와 대조한 GUI 표시 행 | 20개 |
| 기존 보호 파일 hash 불변 | 250개 |

실제 payload 크기/hash와 manifest, 현재 원본 bytes/hash, 모델 pkl·summary hash와 기록된 training output hash,
현재 config·가중치·압축/특징/모델 설정, 관련 소스·Python/package 버전이 일치했다.
성공 로그 한 건의 request/status/return code/원래 stdout/manifest snapshot 및 실행 전 입력·모델·source snapshot도 현재 파일과 일치했다.
표시 문자열은 GUI의 저장 상태에서 전 행을 manifest와 대조했다. 특징을 재계산하거나 pkl을 다시 읽어 예측하지 않았다.
이미 저장된 zstd payload만 메모리에서 해제했으며 새 복원 폴더/파일을 게시하지 않았다.

## 실제로 확인한 화면·입력과 한계

이번 cua_repl 캡처에서는 GUI가 왼쪽에 보였고 PyCharm이 오른쪽을 가렸다.
그 보이는 결과 표 안으로 실제 스크롤 입력을 보내 행이 바뀌는 것을 관찰했다.
상단의 성공 상태·선택 알고리즘·모드/모델·크기와 일부 중간 특징, 마지막 `bigram_diversity`,
`segment_entropy_mean`, `segment_entropy_std` 및 요청 출력 경로 행을 확인했다.
표의 클릭으로 한 특징 행이 선택되는 것도 캡처에서 확인했다.
모든 20행을 픽셀로 하나씩 확인한 주장은 아니며, 전체 행 문자열의 일치는 observer 기록으로 검증한 것이다.

키보드 End는 `user input was detected in this window; call get_window_state before continuing`으로 차단됐다.
새 상태를 읽고 한 차례 재시도해도 같아 성공으로 기록하지 않았고, 다시 screenshot을 확인한 뒤 scroll로 하단에 도달했다.
다른 앱/터미널에 좌표 입력을 하지 않았다. Screenshot payload는 저장하지 않았다.
이전 ‘전혀 GUI가 보이지 않는’ 상태와 달리 일부 화면 캡처/scroll/click은 확인했지만,
전체 가림 없는 화면·모든 DPI·키보드 입력·이전 capture 문제의 근본 해결을 완료했다고 기록하지 않는다.

Confidence 1은 기존 표시대로 보정되지 않은 모델 출력이며 정답 확률 검증이 아니다.
이 단일 파일은 일반화 성능이나 baseline 개선을 평가한 결과가 아니다.
새 압축/benchmark·예측·학습·memory 측정·unseen 연구 평가나 테스트 suite 재실행은 하지 않았다.

## 다음 단일 작업

사용자가 Smart 탭의 `이 결과 복원`으로 package 입력을 준비하고, 출력 부모 기본값 아래 새 결과 폴더
`manual_restore_20261028_01`에 `검증해 복원`을 실행한다. 계획된 복원/Compare 경로는 이번 기록 시점에 존재하지 않았다.
실제 저장된 원래 이름/bytes/hash와 manifest·작업 로그를 확인한 뒤 Compare를 이어간다.
고정 계획의 초기 `awaiting_user_smart_action`은 작성 당시 상태로 보존하고 이번 완료 근거를 새로 연결했다.
