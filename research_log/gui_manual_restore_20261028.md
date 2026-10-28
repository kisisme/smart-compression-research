# 수동 GUI 복원·저장 파일 검증 — 2026-10-28

상태: **사용자 native 복원·실제 저장 파일 검증 완료 / 수동 Compare·전체 시각 QA 미완료**.
복원 실행/검증 HEAD는 `df09f49c93f66c9333aa401d5a4b0b4eb77f61de`이다.
[고정 수동 계획](gui_manual_qa_plan_20261028.json)과 [직전 Smart 검증](gui_manual_smart_20261028.md)에 이어
사용자가 `이 결과 복원`으로 입력을 준비해 `manual_restore_20261028_01`에 `검증해 복원`을 실행했다.

## 실제 확인

| 항목 | Python으로 실제 저장 파일/로그에서 확인 |
|---|---|
| 저장된 복원 파일 | `한글 공백 & 실제 GUI 입력 🧪.md` |
| 복원 bytes | 4,433 |
| 알고리즘 | zstd |
| 원본 bytes와 직접 비교 | 일치 |
| 원본 파일명 보존 | 일치 |
| 복원 SHA-256 | `391345c9f5dd176f9a7e61c1e567075b9f0c00f723386905f77ce91020409a71` |
| GUI 상태 문자열/표시 행 | 완료·검증 통과 / 6개 일치 |
| 기존 보호 파일 hash | 250개 불변 |

[검증 프로그램](verify_manual_restore_20261028.py)이 실제 원본과 저장된 복원 파일을 직접 읽어 비교했다.
[검증 근거 JSON](gui_manual_restore_verified_20261028.json)에 원래 작업 로그·현재 GUI 관찰 상태·파일 hash를 보존한다.
복원 출력은 원래 이름의 파일만 포함했다. 복원 작업 로그 한 건의 성공 상태/종료 코드/원래 stdout과 확인된 결과,
입력 package/manifest/payload hash·해제 소스와 실행 전 source/package snapshot이 현재 파일과 일치했다.
직전 Smart 검증에 고정된 입력·manifest/payload·모델/summary/config와 그 기록도 그대로였고 복원 때문에 기존 package를 바꾸지 않았다.

이는 사용자가 조작한 GUI의 단일 성공 흐름이다. Assistant는 복원/압축/예측을 다시 실행하지 않았고 모델을 역직렬화하지 않았다.
이번 복원 화면을 agent가 픽셀로 검증한 것은 아니며 사용자 성공 보고와 실제 저장/observer 확인을 구분한다.
기존 Smart의 일부 scroll/click 성공은 [직전 기록](gui_manual_smart_20261028.md) 범위이며 가림/키보드 guard가 모두 해결된 것은 아니다.
테스트 suite·memory 측정·모델 일반화/새 unseen 평가를 실행하지 않았다.

## 다음 단일 작업

사용자가 Smart 압축 탭으로 돌아가 `사용한 파일 실제 비교`를 눌러 같은 입력을 준비한다.
출력 부모 기본값 아래 새 결과 폴더 `manual_compare_20261028_01`로 `네 알고리즘 실제 비교`를 실행한다.
현재 이 출력은 존재하지 않는다. 종료 후 원시 반복·집계·정답/점수·예측/실측 Demo와 저장 로그를 검증한다.
새 연구 corpus 평가는 아니며 GUI smoke 결과를 holdout 성능으로 취급하지 않는다.
