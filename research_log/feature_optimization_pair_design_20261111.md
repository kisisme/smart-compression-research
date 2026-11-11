# Bigram·run 통계 최적화 후보와 같은 조건 비교 계획 — 2026-11-11

**현재 단계: 후보 설계·비교 계획 고정. 후보 코딩·동등성 실행·속도 측정 결과는 아직 없다.**

[JSON 계획](feature_optimization_pair_plan_20261111.json) · [준비 코드](prepare_feature_optimization_pair_20261111.py) · [동결](../data/results/feature_optimization_pair_plan_20261111_01/freeze.json) · [독립 계획 검증](../data/results/feature_optimization_pair_plan_20261111_01/verification.json) · [관측 병목](feature_profile_baseline_results_20261111.md)

## 후보와 정확히 유지할 값

기존 NumPy 의존성을 사용해 Python의 byte별 반복을 배열 연산으로 옮기는 후보를 정한다. 주 후보는 **두 함수 결합 버전**이고, bigram만/run만 바꾼 버전은 기여도 확인을 위한 보조 비교다. 결과를 보고 주 후보를 바꾸지 않는다. 공식 `src/feature_extractor.py` 대신 별도로 읽은 참조 namespace의 두 helper만 바인딩한다.

| 버전 | 변경 범위 |
|---|---|
| reference | 고정 참조 그대로 |
| bigram_numpy | `_bigram_diversity`만 변경 |
| run_numpy | `_run_statistics`만 변경 |
| both_numpy | 두 변경 결합 — 주 후보 |

**Bigram:** 각 인접 byte를 먼저 `uint16`으로 바꾼 후 `code=(left<<8)|right`로 묶는다. 이 코드는 가능한 byte 쌍과 일대일 대응하고 범위는 0~65,535다. 정수 histogram에서 빈도가 0이 아닌 bin 수 U를 세고, 기존과 같은 Python 정수 나눗셈 `U/min(N−1,65536)`을 사용한다. uint8 상태에서 shift하지 않는다. 가중치·표본 추출·근사 count는 쓰지 않는다. 기존 조기 종료와 달리 전체 histogram을 만들 수 있으므로 일부 입력에서 느려지는 경우도 그대로 기록한다.

**Run:** 값이 바뀌는 위치를 p로 찾으면 run 수는 `r=|p|+1`, 인접 동일 쌍 수는 `N−r`이다. 경계 `[0,*p,N]`의 차이 중 최댓값이 최장 run이다. 원래와 같은 정수 피연산자로 `(N−r)/(N−1)`, `N/r`를 계산하고 최장 run을 builtin int로 돌려준다. 경계/run 길이는 signed `intp`를 사용하며 uint8/uint16으로 축소하지 않는다.

두 helper 모두 정확한 builtin bytes의 길이 2 이상에만 배열 경로를 사용한다. 짧은 입력과 bytes subclass는 저장한 원래 helper로 돌아가 `__len__`/`__getitem__` override 등 기존 동작을 보존한다. 공개 함수의 타입/빈 입력 검사는 원래 코드 그대로다. 단일 byte·비정상 입력·private helper의 빈 입력 결과도 참조와 비교한다.

전체 Counter의 삽입 순서·entropy/fsum·segment/duplicate block·특징 이름/순서/타입·frame·모델/config/score는 그대로 둔다. 정수 count가 같아도 NumPy scalar를 그대로 반환하지 않고 builtin int/float를 유지한다. 모든 실수는 `float.hex()`까지 같아야 하며 epsilon/반올림으로 차이를 덮지 않는다. 두 변경은 이 조건에서 모델 선택 비율을 바꾸는 작업이 아니다.

입력 view에 쓰거나 원본을 바꾸지 않는다. 보조 배열/정수 histogram의 생성·해제 비용은 측정 범위 안이다. 메모리 사용량 감소나 전체 zero-copy를 주장하지 않으며 별도 memory 구현/측정·score 편입은 재개하지 않는다. 현재 설치 버전/API 문서와 dtype 범위는 준비 단계에서 확인·기록한다.

## 동등성 확인

먼저 같은 참조 코드가 원본 hash·저장 특징·기존 예측과 일치하는지 검사한다. 그다음 세 후보 모두 인위적 입력과 실제 개발 corpus 전체에서 아래 기준을 통과해야 실측한다.

- 기존 정상 fixture 131개·오류 입력 5개 전체를 재사용하고, 정수 인덱싱을 바꾸는 bytes subclass와 길이를 바꾸는 subclass를 추가한다. 기대값은 고정 참조 실행으로만 얻는다.
- 고비트 byte·전체 pair 포화·uint16보다 긴 run·마지막 짧은 구간을 포함한다. 두 private helper의 빈/단일 byte 결과와 공개 함수 예외도 확인한다.
- 원본 bytes 불변, 12개 ordered feature의 builtin type/정수/finite float.hex, 한 행 float64 frame의 열·값이 정확히 같아야 한다.
- 네 버전에서 기존 18개 모델의 단일 행 결정·클래스 순서·확률/비보정 confidence를 저장 기준과 비교한다. 모델을 재학습하지 않는다.

이번 준비에서는 원본 특징/모델을 실행하지 않는다. 입력 목록과 기존 저장값/모델의 hash만 연결한다. 실제 동등성·새 예측은 후속 실행부 검증 이후 수행한다.

## 균형 paired 일정

참조와 후보를 **같은 worker·같은 파일에서 바로 이어서** 실행한다. 비교별·mode별 worker는 새로 시작한다. 특징만 계산하는 모드와 특징+동일 frame 준비 모드를 모두 측정하며 주 비교는 **both_numpy의 결합 모드**다. import·입력 읽기/hash·모델 로딩/예측 gate·raw 저장과 사후 동등성 검사는 timer 밖이다. 특징과 배열/frame allocation은 timer 안이고 입력별 특징/중간 결과를 재사용하지 않는다.

파일마다 비교/mode별 warmup pair 1회와 본 pair 6회를 정한다. 본 측정을 짝수로 둬 각 파일에서 참조 먼저 3회·후보 먼저 3회가 되게 한다. 공식 codec 5회 설정을 바꾸는 것이 아니라 별도 특징 실험의 순서 균형이다. 각 round에서도 두 순서의 파일 수가 같다. 전체 파일 셔플 seed와 첫 실행 판정식은 JSON 및 고정 pair schedule에 남긴다. 모델·시간 결과를 보고 순서를 바꾸지 않는다.

기존 60개 파일 전체를 사용하는 개발 실험이다. 느린 파일/반복을 빼거나 실패 pair만 재시도하지 않는다. 실패/중단·partial 기록은 보존하고, 새 attempt는 새 경로에서 전체 일정을 실행한다. 전원·우선순위·affinity·GC를 variant별로 다르게 조정하지 않는다.

## 통계와 다음 단계 판정

주 지표는 각 pair의 `candidate_ns−reference_ns`를 구해 파일별 6-pair 중앙값 → 원본 그룹 안 평균 → 원본 그룹 동일 비중 평균으로 집계한다. 음수는 현재 corpus에서 결합 지연이 낮다는 뜻이다. 두 독립 중앙값을 빼서 paired 차이로 대체하지 않는다.

보조로 참조/후보의 파일별 중앙값 합 비율·절감률, 모든 파일/형식/그룹/고정 크기 구간의 차이·악화/동점·순서별 진단을 보고한다. 주 지표가 음수이고 주 비교의 중앙값 합 비율이 1보다 크며 모든 정확성/일정 검증을 통과한 경우에만 **별도 전체 경로 검증으로 진행할 근거**로 삼는다. 통계적 유의성·모집단 향상이나 자동 배포/채택을 뜻하지 않는다.

보조 후보가 더 좋아도 주 후보를 사후에 몰래 바꾸지 않는다. 필요하면 변경 이유와 새 버전/계획을 기록한다. zstd 비율이나 원하는 향상률에 맞춘 임계값·표본/가중치 변경은 하지 않는다. 이후 전체 Smart 경로의 추론·압축·복원·검증·저장 비용 비교와 다른 원본 그룹의 최종 평가가 필요하다.

순서는 **계획/순서 동결·commit → 격리 후보/paired 실행부/독립 감사 구현·fixture·commit → 새 paired 실측/검증 → 조건을 만족하면 전체 경로 비교**다. 원래 profile raw·라벨·모델·공식 시스템과 memory 보류 방침을 유지한다.
