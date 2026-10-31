# 사용 조건 기반 후보 목적 함수 계산부

2026-10-31 구현. **후보 전용·codec 측정값의 offline oracle**이며 공식 score나 Smart 실행 경로에 연결하지 않았다.
[수학 설계](usage_objective_design_v1.md)·[명세](usage_objective_spec_v1.json)를 따르는 별도
[모듈](../src/usage_objectives.py)이다. [공식 설정](../config/experiment_config.json)과 기존 모델은 그대로다.

## API와 입력

`LifetimePolicy`의 모든 수치 매개변수는 명시적으로 제공한다. 운영 모드별 기본값은 없다.
정책상 비용점수를 사용하며 실제 요금·CPU/전력 비용을 측정한 값으로 해석하지 않는다.

```python
from src.usage_objectives import (
    LifetimePolicy, evaluate_lifetime_cost, select_under_deadlines,
)

# 아래 숫자는 API 설명용 가상 정책이며 실제 사용량/운영 설정이 아니다.
policy = LifetimePolicy(
    retention_days=1,
    expected_restorations=10,
    storage_cost_per_byte_day=1,
    compression_cost_per_ms=1,
    decompression_cost_per_ms=1,
)
cost = evaluate_lifetime_cost(rows, policy=policy)
deadline = select_under_deadlines(
    rows, compression_limit_ms=25, decompression_limit_ms=10,
)
```

`rows`는 같은 원본 파일의 gzip/bz2/lzma/zstd 측정 mapping들을 담은 iterable이다.
각 행은 `algorithm, sample_id, original_size, compressed_size, compression_time_ms,
decompression_time_ms, verified`를 제공한다. 원본/압축 크기는 양의 정수 bytes이고 시간은 양의 ms다.
JSON/Python 숫자와 CSV의 숫자 문자열을 지원한다. 크기는 소수/지수 문자열과 float를 거부한다.
`verified`는 `True` 또는 정확한 문자열 `"True"`만 허용한다. 선택적 `status`가 있으면 `"ok"`여야 한다.
중복/미지원 압축기·서로 다른 sample_id/원본 크기·bool 수치·음수/NaN/무한대를 거부한다.
추가 필드는 계산에 사용하지 않고 행 사본에 보존한다. Memory 필드를 추가해도 점수에 넣지 않는다.

## 반환과 실패 구분

| 상황 | 처리 |
|---|---|
| 완전하고 유효한 측정, 선택 가능 | `status="selected"`, `selected_algorithm`, `selection_value` |
| 행/필수 측정 필드가 없거나 `None`/빈 문자열 | `measurement_required`, 선택/점수는 비움, `missing_measurements`에 전체 누락 목록 |
| 모든 후보가 시간 제한 위반 | `constraint_unsatisfied`, 선택은 null, 위반 후보/이유는 전부 보존 |
| 검증 실패·실패 status·잘못된 값/매개변수 | `ValueError`로 거부. 알려진 실패를 단순 누락으로 숨기지 않음 |
| 정책 객체 대신 다른 타입 전달 | `TypeError` |

반환에는 objective ID/version, 입력 행 사본, 명시적 매개변수, 전체 후보 값, 동점 후보,
단위·수치 표현·offline 범위도 포함한다. 입력 순서에 상관없이 기존 순서
`gzip,bz2,lzma,zstd`로 정확 동점을 결정한다. 잘못된 입력을 조용히 제외하거나 fallback 선택을 하지 않는다.
누락과 동시에 알려진 검증 실패/잘못된 값이 있으면 오류를 우선 거부한다.
출력에 보존한 임의 추가 metadata의 JSON 직렬화 가능성은 호출자가 관리한다.

## 총비용과 시간 제약

`evaluate_lifetime_cost`는 `k_s H B + k_c T_c + k_d N T_d`를 최소화한다.
`components`에는 저장·압축·복원 비용을 나눠 기록한다. 비용 계수 합을 정규화하지 않는다.
기본 `profile_kind="storage"`는 양의 유효 저장 계수를 요구한다.
저장 비용을 사용하지 않으려면 `profile_kind="time_only"`를 명시하고 유효 저장 계수를 0으로 둔다.
두 경우 모두 적어도 하나의 유효 비용 계수는 양수여야 한다. 기대 복원 횟수는 소수도 허용한다.

`select_under_deadlines`는 `T_c<=limit_c`, `T_d<=limit_d`인 후보 중 압축 bytes를 최소화한다.
허용 시간은 양의 유한 값이며 경계의 같은 값도 허용한다. `values`에는 제한 밖 후보의 크기도 남기고,
`violations`에는 각 후보의 압축/해제 제한 위반을 기록한다. 크기가 같으면 속도 차이로 다시 순위를 바꾸지 않는다.
네 후보의 실측을 알고 있는 oracle이므로 Smart 예측의 실제 지연 보장으로 사용할 수 없다.

## 수치와 구현 범위

버전 1은 매개변수/시간을 Python binary64 float로 변환하고, 곱은 명시한 식 순서대로 계산한다.
총비용은 세 항의 `math.fsum`이다. Bytes는 정수로 보존해 시간 제약 선택에서 큰 정수의 순서를 잃지 않는다.
epsilon·가중치 clipping·일정 클래스 비율 강제는 없다. 비유한 곱/합과 양의 값의 0 underflow를 거부한다.
문자열 변환 때의 0 underflow도 거부한다. 이미 호출자 float에서 0으로 반올림된 값의 원래 값을 복구하지 않는다.
정확 동점은 이 수치 표현에서의 equality이며 실수 수학의 동점/순위가 모든 크기/근접값에서 보장된다는 뜻은 아니다.
테스트의 단위 변환 사례는 식의 검산용이다. 실제 API 입력 단위는 bytes/ms/day/count로 고정한다.

모듈은 표준 라이브러리만 사용하고 import/호출 시 파일 읽기·설정 로딩·모델/특징 추출·압축을 하지 않는다.
공식 scoring/CLI/GUI에는 연결하지 않았고, 새 학습 라벨·모델·memory 측정도 만들지 않았다.
공급한 측정값의 계산상 검증이며 실제 원본 bytes를 다시 복원/검증하는 함수는 아니다.

## 검증과 다음 단계

[전용 테스트](../tests/test_usage_objectives.py)는 모두 인위적 fixture다.
독립 Fraction 계산 대조, 보관/복원 횟수에 따른 순위 반전, 정확/근접 동점, 계수 스케일·단위 변환,
시간 경계/빈 후보, 누락/실패/중복/다른 파일·수치 오류, 모든 입력 순서·원본 불변,
overflow/underflow와 fresh import 격리를 검증한다.
[검증 프로그램](validate_usage_objectives_20261031.py)과
[최종 실행 근거](usage_objectives_validation_20261031.json)에 테스트 출력·source/protected hash와
기존 설계의 가상 예제를 새 함수로 계산한 결과를 보존한다. 새 압축 연구 결과가 아니다.

다음은 가상 사용 scenario의 매개변수·단위·범위를 먼저 고정하고, 기존 Pilot을 별도 출력에서
탐색하는 단계다. 과거 전체 Pilot을 개발에 사용했다는 한계를 유지하고 실제 unseen 결과를
보면서 계수/파일을 고르지 않는다. 운영 계수 채택·모델 전환·공식 평가와 GUI QA는 별도 과제다.
