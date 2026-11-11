# 특징 profile 실행부 구현·fixture 검증 — 2026-11-11

[사전 계획](feature_profile_design_20261109.md) · [공통 실행/동등성 검사](feature_profile_runtime_20261111.py) · [controller/worker](run_feature_profile_20261111.py) · [독립 감사](verify_feature_profile_run_20261111.py) · [구현 검증 도구](validate_feature_profile_implementation_20261111.py) · [검증·source lock](../data/results/feature_profile_implementation_20261111_01/implementation.json)

상태는 위 lock의 실제 테스트 결과로 확인한다. 이 단계는 인위적 입력에 대한 구현 검증이며 실제 corpus의 새 특징·예측·시간 결과가 아니다. 기존 공식 특징/모델/score·memory 참고 지표 방침을 유지했다.

## 구현한 동작

- 고정된 plan/source/config/입력 metadata/모델 bytes·runtime·전체 schedule의 hash를 확인한다. 구현 source와 검증 lock이 HEAD에 commit되지 않았으면 실제 corpus를 읽기 전에 중단한다.
- 참조 feature 모듈을 별도 namespace에서 실행하고 복사 config를 사용한다. 원본 파일을 수정하거나 참조 디렉터리에 `__pycache__`를 만들지 않는다. 원래 frame 함수 정의와 기존 검사를 재사용한다.
- 실제 실행 시 원본 60개 bytes/hash·저장 특징 720개·기존 모델 18개의 단일 행 예측/확률 1,080개가 정확히 일치해야 측정으로 넘어간다. 정수/builtin type·float.hex·열 순서/dtype·confidence를 검사한다. confidence는 보정된 정답 확률이 아니다.
- 네 모드는 각각 새 hidden worker에서 실행한다. 읽기/hash/사전 동등성 확인은 타이머 밖이고, 원래 warmup/전체 순서의 각 slot과 호출 tree를 즉시 flush한다. 함수 wrapper는 inclusive/self·parent/depth·호출 수를 남기고 예외에도 원래 callable로 복구한다.
- 기존 출력은 거부한다. 실패한 slot·worker stderr/log·반환 코드·실패 phase를 남기고 재시도하지 않는다. controller 중단 시 자신이 만든 child만 종료하며 부분 기록을 보존한다. 새 attempt는 새 flat results 경로를 사용한다.
- 독립 감사는 호출 구간 포함 관계·직접 자식의 비중복·self 합·전체/구간별 helper 호출 수·모든 slot·정확 특징/frame/예측을 검사한다. 비계측 파일 중앙값과 nested context별 중앙값, 형식/원본 그룹/크기 집계와 observer 차이를 저장한다. 모드 중앙값을 더하거나 부모/자식 inclusive를 중복 합산하지 않는다.

## 검증 범위

고정한 정상 인위적 입력 131개와 오류 입력 5개로 참조/계측의 정확 특징·frame·호출 tree 및 예외 종류/메시지를 확인한다. 정수↔float/bool, 실수 한 단계/음의 0, 잘못된 열·dtype·값·예측/확률·부분/중복 slot, 원본 hash·timer·call tree 변조, wrapper 복구, 실패 보존/덮어쓰기 방지와 실제 자식 프로세스 smoke를 검증한다. 예측은 가짜 모델을 사용하고 저장 연구 모델을 역직렬화하지 않는다.

첫 샌드박스 실행은 새 TemporaryDirectory의 ACL 접근 거부로 파일 관련 검사 6개가 중단됐다. 권한을 허용한 재실행에서 통과했으며 OS 권한을 코드로 완화하지 않았다. 추가한 중단/반환 코드 검사까지 포함한 최종 결과는 별도 `tests.log`와 lock에 기록한다. 원본 연구 실험의 실패/재시도로 해석하지 않는다. 실패한 이전 임시 폴더는 임의 삭제하지 않았다.

## 이후 실행

이번 source/lock을 commit한 다음 실제 파일의 기준선 profile을 실행한다. 아래 명령은 이 문서 작성 단계에서 실행하지 않았다.

```powershell
.\.venv\Scripts\python.exe research_log/run_feature_profile_20261111.py --notes "실행 당시 관찰한 작업/절전/중단 상황"
```

기본 출력은 고정 계획의 `data/results/feature_profile_baseline_20261109_01`이다. 실패 후에는 같은 경로를 재사용하지 않고 `--output data/results/feature_profile_baseline_20261111_attempt02`처럼 새 경로에서 전체 일정을 실행한다. 완료는 `complete.json`과 독립 `verification.json`이 함께 생성된 경우다. 부분 `started.json`/raw 파일만으로 완료 처리하지 않는다.

계측 observer 비용·고정 mode 순서·cache/새 환경의 한계가 있으며 함수별 계측이 실제 프로그램 속도를 보장하지 않는다. 실제 profile·최적화·paired 성능 비교·최종 holdout은 후속 작업이다. GUI/codec/파일 I/O/memory/새 예측 시간 연구는 이번 구현 검증 범위에 포함하지 않는다.
