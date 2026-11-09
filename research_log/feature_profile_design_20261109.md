# 특징 계산 프로파일링·정확 동등성 검증 계획 — 2026-11-09

**단계: 사전 계획 고정. 함수별 실측·최적화·모델 재학습은 아직 수행하지 않았다.**

[기계 판독 계획](feature_profile_plan_20261109.json) · [준비/검증 코드](prepare_feature_profile_20261109.py) · [동결 근거](../data/results/feature_profile_plan_20261109_01/freeze.json) · [직전 병목 분석](pipeline_bottlenecks_20261109.md)

## 목적과 작업 범위

직전 분석은 특징 계산과 입력 frame 준비를 합친 시간만 알고 있었다. 이번 계획은 현재 구현에서 어느 함수가 시간을 쓰는지 구분하기 위한 기준선 측정이다. 기존 공식 특징·모델·정답·score는 유지한다. 관찰된 실제 파일은 개발 자료이고 최종 일반화 검증 자료로 재해석하지 않는다.

이번 준비에서는 계획·원본 코드 사본·기존 저장 특징의 정규 표현·모델 목록·측정 순서만 동결한다. 실제 파일의 특징 재계산, 모델 로딩/예측, 시간 측정은 후속 실행부 검증 후 별도 경로에서 수행한다. 원본 bytes 검증도 실행 전 필수이며, 이번 준비의 manifest/hash 연결 확인과 구분한다.

## 입력과 참조 보존

- 직전 후보 실험에서 고정한 실제 60개 파일 전체를 사용한다. 특징·압축 결과·속도를 보고 파일을 빼거나 대체하지 않는다.
- 기존 `predictions/samples.csv`의 12개 특징과 `frozen_predictions.csv`의 9개 조건×DT/RF 출력을 기준으로 연결한다. 정수는 정수값, 실수는 기존 CSV를 binary64로 읽은 `float.hex()`를 보존한다. 새 기대값을 추정하지 않는다.
- `src/feature_extractor.py`, config, 기존 특징 테스트와 study runner를 bytes 그대로 복사한다. 참조 모듈은 별도 디렉터리의 원래 상대 구조에서 복사 config를 읽는다. `feature_frame`은 동결 runner의 해당 함수 정의를 추출한 사본과 명시적 pandas/numpy/FEATURE_NAMES/require 문맥으로 재현한다. 전체 study runner의 기존 phase를 호출하지 않는다.
- 모델 18개는 학습 기록의 hash·클래스·설정·Python/패키지 버전·특징 순서를 확인한 뒤 기존 파일을 그대로 사용한다. 모델을 학습하거나 재저장하지 않는다.

## 정확한 동등성 통과 기준

| 대상 | 통과 기준 |
|---|---|
| 특징 schema | 기존 12개 이름·순서가 정확히 같음 |
| 정수 특징 | `file_size`, `unique_byte_count`, `max_run_length`는 builtin int와 값이 같음; bool/float 대체 불허 |
| 실수 특징 | builtin float·유한값이며 `float.hex()`가 같음; 음의 0도 구분 |
| 입력 frame | 한 행, 기존 열 순서·float64·정확한 값, 기존 schema/유한값 검사 보존 |
| 입력 처리 | nonempty bytes와 기존 bytes subclass 허용을 보존; 잘못된 입력의 예외 종류/메시지 보존 |
| 모델 출력 | 기존 1,080개 단일 행 예측·클래스 순서·네 압축기 확률 필드·confidence가 정확히 같음 |

먼저 복사한 **기존 참조 코드 자체가** 저장 특징 60행과 일치하는지 확인한다. 이후 계측 wrapper와 향후 최적화 구현을 같은 기준으로 검사한다. 실수의 수학적 근삿값만 같거나 예측만 같은 것은 특징 동등성 통과가 아니다. epsilon 완화·반올림·기대값 갱신으로 차이를 없애지 않는다. confidence는 보정된 정답 확률이 아니다.

바이트 빈도의 삽입 순서, `math.fsum`/표준편차의 계산 순서, 마지막 짧은 블록/구간도 실수 결과에 영향을 줄 수 있다. 계산식을 바꾸는 최적화는 이 기준을 먼저 만족해야 한다. 특징 의미를 바꾸려면 별도 연구 버전·학습·평가 설계가 필요하다.

## 측정 범위와 순서

각 모드는 별도 worker에서 실행한다. import·모델 로딩·파일 읽기/hash는 timer 밖이고 입력은 메모리에 있는 원본 bytes다. 파일별 모드당 warmup 1회와 본 측정 5회를 모두 기록한다. 파일 순서는 전체 목록을 정렬한 뒤 고정 seed/모드/round로 셔플하며 동결 CSV에 원래 ID·모드·round·순서를 저장한다. 일부 파일만 앞서 시험한 뒤 순서를 바꾸지 않는다.

| 모드 | timer 범위 | 해석 |
|---|---|---|
| extract_only | 수정하지 않은 참조 `extract_features(data)` | 전체 특징 계산 기준선 |
| frame_only | 검증한 특징에서 기존 frame 생성·schema/유한값 검사 | 입력 준비 비용 |
| extract_and_frame | 특징 계산과 기존 frame 준비 전체 | 과거 feature timer와 논리적 범위 비교; 같은 시점의 paired 성능은 아님 |
| instrumented_extract | 참조 함수에 process-local wrapper를 씌운 전체 실행 | 함수별 원인 진단; 실제 성능 기준선과 구분 |

함수별 wrapper 대상은 `extract_features`, `Counter`, `_run_statistics`, `_segment_entropy_statistics`, `_entropy_from_counts`, `_duplicate_block_ratio`, `_bigram_diversity`다. 원본 파일을 수정하지 않고 예외가 나도 `finally`에서 원래 함수를 복구한다. 호출 parent/depth, inclusive ns, self ns와 호출 수를 보존한다. Counter/entropy는 전체 파일에서 호출됐는지 구간 통계 안에서 호출됐는지 구분한다.

구간 엔트로피 시간에는 내부 Counter/entropy가 포함된다. 부모와 자식의 inclusive 시간을 합쳐 별도 작업량인 것처럼 보고하지 않는다. 직접 자식 시간만 빼서 self 시간을 구하고 wrapper/기록 overhead가 남는다는 한계를 표시한다. 계측값은 병목 후보를 찾기 위한 값이며, 비계측 모드와의 차이도 전체 파일에서 그대로 보고한다.

각 파일/모드의 5회 중앙값과 모든 raw ns를 보존한다. 독립 모드들의 중앙값을 더해 결합 시간으로 만들지 않는다. 고정 모드 순서·OS cache·다른 프로세스 영향·새 실행 환경의 한계를 남긴다. 전원/우선순위/affinity를 임의 변경하지 않는다. Python 시작·파일 I/O·codec·새 모델 예측/로딩 시간·memory·GUI 전체 성능 측정은 이번 profile 범위 밖이다. 모델 예측 호출은 동등성 확인용이다.

## 인위적 검증 입력

작은 길이, 16 bytes 블록과 4096 bytes 구간의 직전/동일/직후 길이, 65,536 bigram 분모 경계를 고정했다. 0/A 반복·0~255 순환·0/255 교대·고정 seed 전체 byte 난수·4개 byte 알파벳을 길이 목록과 전조합한다. 긴 run, 마지막 짧은 중복 블록, 모든 순서쌍을 포함하는 bigram 포화 입력, 엔트로피가 다른 구간과 짧은 꼬리, bytes subclass를 별도 추가한다. 빈 bytes와 잘못된 타입도 확인한다. 정확한 생성식과 seed는 JSON에 있다.

이 입력들은 `test_fixture`이며 실제 연구 파일/평가 표본과 섞지 않는다. 기대 특징은 후속 실행 때 고정 참조 코드로만 생성한다. 이번 단계에서 실제 특징값이나 시간값을 만들지 않았다.

## 보고·오류 처리와 후속 단계

전체 파일과 형식/원본 그룹·고정 크기 구간별 시간을 보고한다. 빈 그룹/실패도 표시한다. 원시 slot·호출 tree·정확 동등성 결과·입력/코드/모델 hash·runtime·실행 commit을 새 출력에 남긴다. 실패/중단은 그대로 보존하며 실패 slot을 덮어 재시도하거나 부분 결과끼리 합쳐 완료로 처리하지 않는다. 재실행은 새 attempt 경로와 전체 순서를 사용한다.

순서는 **계획 동결/commit → 격리된 실행부·검증기 구현/fixture·commit → 기준선 실측/독립 검증 → 실제 병목에 근거한 별도 최적화 계획**이다. 향후 최적화의 속도 비교는 같은 시점의 reference/candidate를 균형 있게 배치한 새 paired 계획을 쓴다. 과거 시간만 기준 삼아 속도 향상을 확정하지 않는다.

zstd 비율 목표나 원하는 성능값에 맞춰 특징·가중치·표본을 바꾸지 않는다. 이번 기준선 계획은 공식 시스템 채택이나 배포를 뜻하지 않는다. Memory 참고 지표 보류 방침과 GUI 미완료 항목도 그대로 유지한다.
