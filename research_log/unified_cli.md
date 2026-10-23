# 통합 CLI

`main.py`에서 기존 세 기능을 명시적인 명령으로 선택한다. 독립 CLI도 계속 사용할 수 있다.

```powershell
.\.venv\Scripts\python.exe -B main.py --help
.\.venv\Scripts\python.exe -B main.py smart README.md --mode archive --model decision_tree --output-dir data/temp/smart_example
.\.venv\Scripts\python.exe -B main.py decompress data/temp/smart_example --output-dir data/temp/restored_example
.\.venv\Scripts\python.exe -B main.py compare README.md --output-dir data/temp/compare_example
```

각 출력은 기존에 존재하지 않는 경로여야 한다. `main.py COMMAND --help`로 해당 기능의
입력과 옵션을 확인한다. `python -B -m main COMMAND --help` 형식도 지원한다.

| 명령 | 연결된 기존 기능 | 실행 범위 |
|---|---|---|
| `smart` | `smart_compress.main()` | 지정 모델·mode의 예측 후 한 압축기 실행·복원 검증·package 저장 |
| `decompress` | `smart_decompress.main()` | 저장된 알고리즘으로 해제·크기/SHA-256 확인·원래 파일명으로 복원 |
| `compare` | `compare_compress.main()` | 네 알고리즘 실측·원시 시간·중앙값·검증·세 mode 점수 보고 |

입력/출력·모델 호환성·무결성·실패 보존·기존 출력 보호는 각 기능의 기존 검사를 따른다.
통합 진입점은 인자를 재해석하거나 검증을 우회하지 않고 선택한 CLI에 그대로 전달한다.
명령별 정상 종료 0, 작업 실패 1, argparse의 잘못된 명령/옵션 2를 유지한다.

## 연결 방식과 유지한 범위

명령을 파싱한 뒤 선택한 모듈 하나를 지연 import한다. 최상위 도움말과 잘못된 최상위
명령은 기능 모듈을 불러오지 않는다. Compare·해제 경로에 Smart 모델 의존성을 추가하지
않으며 Smart 선택 경로에서 Compare나 benchmark를 실행하지 않는다.

각 독립 CLI의 `main(arguments=None, *, prog=None)`에 선택적인 도움말 접두사만 추가했다.
기존 호출은 그대로 유효하고, 통합 진입점은 `prog`로 명령 이름을 전달한다. Python 3.14의
모듈 실행 문맥에서도 정확한 사용법을 표시하며 `sys.argv`나 전역 argparse 동작을 바꾸지 않는다.
기존 측정·점수·특징·압축 설정·모델·복원 함수의 정의는 변경하지 않았다.

공식 평가는 계속 프로토콜 v2의 3지표다. Memory는 참고 지표로 보존하고 추가 구현을
보류한다. 통합 CLI 동작 검증은 모델 정확도·baseline 개선·일반화·새 Pilot이 아니다.
GUI·스트리밍·새 모델 학습은 이번 기능 범위에 포함하지 않는다.

상세 동작: [Smart 압축·복원](smart_mode.md), [Compare](compare_mode.md).

## 구현·검증 기록 — 2026-10-23

작업 시작·실제 실행 HEAD는 `c0394a0`이다. 최종 진입점·선택적 `prog` 인자 보완은
당시 commit 전 작업 트리 상태였고 정확한 소스 hash를 실행 기록에 남겼다.

통합 전용 12개(5.936초), 기존 Smart 압축·복원 18개(10.390초), Compare 16개(2.048초),
총 46개 테스트가 통과했다. 명령별 인자 전달·정상/실패 반환·파서 오류·도움말·전역 인자 불변,
두 모델·세 mode 압축→복원, 한 압축기 실행·benchmark 차단, 부분 비교 실패 보존,
기존 출력 보호를 확인했다. Fresh Python에서 최상위 도움말의 기능 모듈 import 없음과
Compare/복원 경로의 불필요한 모델/기능 import 차단을 확인했다. 직접 파일 실행과
`python -m main`의 명령별 도움말도 확인했다. 제어 fixture는 연구 데이터가 아니며
전체 저장소 suite는 이번 작업에서 실행하지 않았다.

실제 저장된 두 Pilot 모델 × 세 mode로 README를 압축→복원한 여섯 건 모두 원본 bytes·
크기·SHA-256과 일치했다. Compare 한 건의 원시 반복 40개·집계 4개·mode 정답 3개를
원시 중앙값·공식 점수·산출물 hash로 대조했다. 도움말·정상 처리·기존 출력 거부·잘못된
명령/필수 옵션을 포함한 최종 CLI 호출 22건이 모두 기대한 종료 코드와 일치했다.
입력·모델·설정·구현 등 보호 파일 38개의 SHA-256 불변도 확인했다. 이는 해당 파일의
프로그램 동작 검증이며 모델의 우수성·일반화나 새로운 Pilot을 뜻하지 않는다.

최초 직접 실행 검증은 성공했으나 테스트에서 Python 3.14의 모듈 문맥에 따른 도움말
이름 차이를 확인해 선택적 `prog` 전달로 보완했다. 이후 최종 코드로 새 경로에서 실제
흐름을 재검증했다. 최초 결과와 최종 결과는 각각 Git 제외 경로
`data/temp/unified_cli_validation_20261023T122426688067Z/`,
`data/temp/unified_cli_validation_20261023T124503907295Z/`에 보존한다.
[실제 호출·출력·비교 원시 산출물·보호 hash·테스트 기록](unified_cli_validation_20261023.json)을
별도로 Git 보존하며 최종 구현·README·테스트와 기록된 hash의 일치를 확인했다.
