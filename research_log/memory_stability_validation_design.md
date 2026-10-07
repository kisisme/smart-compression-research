# Memory 대표값·정답 안정성 후속 검증 사전 설계

작성일: 2026-10-07. 설계 ID: `memory_stability_v1`.
시작 HEAD: `d8b329ad4305322a3bf49aa21d680585220cbb73`.
근거: [채택 검토](memory_adoption_review_20261007.md), [초기 memory 정의](peak_memory_measurement_design.md),
[runtime baseline 결과](memory_runtime_baseline_results_20260930.md).

**상태: 사전 설계 작성 / 구현·실측·판정 미착수 / `validation_only` / `score_inclusion=false`.**
아래 행렬·seed·가중치·허용 기준은 앞으로 사용할 검증 조건이다. 연구 측정값이나
공식 채택 기준의 검증 완료를 뜻하지 않는다. 새 실측 전에 사용자 확인과 설계 commit을
거쳐 고정한다. 현재 [프로토콜 v2](../research_protocol_v2.md)·[활성 config](../config/experiment_config.json)의
3지표 score는 유지한다. 이 문서는 후속 검증의 구현·실측 자체를 수행하지 않는다.

## 1. 질문과 적용 범위

같은 Windows 기계·Python·패키지·압축 설정에서 다른 날짜에 같은 입력을 다시
측정했을 때, 최종 memory 대표값과 후보 4지표 선택의 손실이 사전 허용 범위에
있는지 확인한다. Memory 변동과 timing 변동의 영향을 별도로 기술한다.

연구 대상은 worker의 전체 프로세스 peak working set이다. 순수 압축기 할당량,
Smart Mode의 모델 로딩·특징 추출을 포함한 end-to-end peak나 메모리 상한의 보장은
아니다. 같은 기계의 여러 날짜는 다른 hardware·OS에 대한 일반화 근거가 아니다.
작은 입력을 제외해 통과시키거나 특정 알고리즘 독점을 줄이는 것을 목표로 삼지 않는다.

## 2. 후보 측정 경로 고정

Memory는 기존 [src/memory_benchmark.py](../src/memory_benchmark.py)의 `_worker`와
[src/compressors.py](../src/compressors.py)를 그대로 실행한다. 새 runner가 아래 형태의
CLI를 각 반복마다 새 subprocess로 호출한다. 이는 예정 호출 계약이며 실행 기록이 아니다.

```text
<same-python> -B -m src.memory_benchmark worker --operation <compress|decompress> --algorithm <algorithm> --input <phase-file> --expected-sha256 <digest>
```

같은 worker 모듈의 import·인자 파싱·설정 로딩→phase 입력 읽기→codec 한 번 실행→
출력 SHA-256 확인→peak 조회→응답 JSON 생성 순서를 유지한다. 입력·출력 bytes는
조회 때 살아 있다. 부모는 원본과 실제 복원 bytes가 일치하는 참조 압축물을 먼저
준비한다. Compress 입력은 원본, decompress 입력은 해당 알고리즘의 실제 압축물이다.
파일 경로·크기·hash를 부모가 확인하며 동일 임시 입력은 run 종료까지 변경하지 않는다.

기존 `run_memory_worker()`의 argv에는 `-B`가 없다. 부모의 `-B`만으로 자식도 bytecode
쓰기를 끈다고 가정하지 않는다. 새 launcher는 위 argv와 `PYTHONDONTWRITEBYTECODE=1`을
모든 자식에 명시하고 metadata에 기록한다. 부모도 `-B`로 실행한다. 이는 새 검증의
고정 조건이며 과거 실행의 옵션이나 바이트를 소급 변경하지 않는다. Warm-up·강제 GC·
working set 축소·baseline 차감은 수행하지 않는다.

Baseline worker의 세 arm을 다시 실행하거나 두 worker의 수치적 동등성을 가정하지
않는다. 실제 공식 후보 경로를 직접 반복 검증하는 설계이다. 소스·실행 옵션·공통
import 경로를 바꾸면 설계 버전을 바꾸고 별도 검증한다. 공식 runner가 훗날 다른
측정 경로를 쓰면 이 결과를 그대로 이전하지 않는다.

Timing은 **별도 신규 timing worker**가 sample×algorithm마다 새 subprocess에서
측정한다. 구현은 아직 없다. 현재 `benchmark_compressor()`의 압축 5회→해제 5회
계약을 유지하되 기존 API가 버리는 원시 ns를 반환하도록 별도 진입점을 만든다.
파일 읽기·참조 준비·hash·bytes 비교·응답 직렬화는 timed 구간 밖이다.
`time.perf_counter_ns()`로 `compress_data()` 또는 `decompress_data()` 호출만 감싼다.
압축 출력 5개는 기존 함수처럼 모두 보유하며 각각 참조 bytes와 비교한다. 해제도
각 호출 결과를 원본 bytes와 비교한다. Warm-up은 없다. 부모는 timing worker의 원시
10개 기록을 저장한다. Timing worker의 peak를 memory로 사용하지 않는다.

Memory와 timing은 같은 입력·run의 별도 측정이며 같은 순간의 측정이 아니다.
반복 index가 같다는 이유로 각 timing과 memory 값을 시간적으로 짝지어 분석하지 않는다.

### 다음 구현에 사용할 timing worker 계약 — 예정

신규 모듈명은 `src.memory_stability_timing_worker`로 정한다. CLI는
`--request-id`, `--algorithm`, `--original`, `--reference-compressed`,
`--original-sha256`, `--compressed-sha256`을 필수로 받는다. 알고리즘은 위 네 개,
digest는 소문자 SHA-256이며 원본·압축물은 비어 있지 않아야 한다. 입력을 모두 읽고
두 hash를 검증한 뒤 timed 호출을 시작한다. 입력이 잘못되면 codec을 호출하지 않는다.
설정 일치, Windows 환경, `sys.dont_write_bytecode=True`도 확인한다.

응답 JSON의 필드는 `schema_version=1,design_id=memory_stability_v1,measurement_status=
validation_only,score_inclusion=false,request_id,algorithm,timer=time.perf_counter_ns,
original_size,compressed_size,original_sha256,compressed_sha256,records,status,error`이다.
알 수 없는 입력 또는 읽기 실패로 확인할 수 없는 size/hash는 null이다. 성공 응답은
압축→해제 순서의 records 10개이며 각 record에 `phase,repeat_index,elapsed_ns,
actual_output_sha256,verified,status,error`를 기록한다. 압축 결과는 참조 압축 bytes와,
해제 결과는 원본 bytes와 정확히 비교하며 output hash는 timed 구간 밖에서 계산한다.

성공 종료는 code 0·`status=ok`·모든 record `verified=true`·양수 정수 ns를 요구한다.
출력 bytes 불일치는 그 반복을 `verification_failed`로 기록하고 나머지 예정 호출도
수행하여 code 2·bundle `verification_failed`로 반환한다. 호출 예외·잘못된 ns 등은
code 1·`worker_failed`이며 확보한 record를 보존하고 미실행 반복은 결과를 만들지 않는다.
부모는 빠진 예정 key를 실패 행으로 기록한다. Argument parsing 실패와 비정상 종료의
stdout·stderr도 부모가 보존한다. Fixture로 이 계약을 검증하되 연구 결과로 집계하지 않는다.

## 3. 사전 고정 입력과 규모

### 입력 명세

- 핵심 층: 현재 config 크기 `[16384, 65536, 262144, 1048576]` bytes와 generator
  `[random, small_alphabet, repeated_pattern, long_runs, structured, mixed]`를 사용한다.
  각 조합의 replicate index는 `[0, 1, 2]`이다. 크기→generator→replicate 순서로
  sample index를 부여하고 `src.data_generator.generate_sample(generator, size, seed)`를
  호출한다. Seed는 `20261007 + sample_index`이다.
- 작은 입력 층: 크기 `[64, 256, 1024, 4096]` bytes, family
  `[zero_bytes, periodic_16, uniform_random]`를 크기→family 순서로 핵심 층 뒤에 붙인다.
  `zero_bytes=bytes(size)`, `periodic_16=(bytes(range(16))*ceil(size/16))[:size]`,
  `uniform_random=random.Random(20261007 + sample_index).randbytes(size)`이다.
  결정적 두 family의 seed는 null이다. 결정적 입력을 seed만 바꾸어 중복 확장하지 않는다.
- Sample ID: `stability_<zero-based index:06d>`. 같은 입력 bytes·생성 매개변수·hash를
  모든 run에서 유지한다. 생성 결과가 중복되어도 행을 삭제하지 않고 중복 관계를 기록한다.
  이 입력은 기존 Pilot에서 가져오지 않으며 모델 학습·시험용으로 사용하지 않는다.
- 알고리즘 순서 `[gzip, bz2, lzma, zstd]`, phase 순서 `[compress, decompress]`.
  설정은 gzip 9, bz2 9, LZMA preset 6, zstd 3이다. 현재 config와 일치해야 한다.

### 예정 수량 — Python 계산, 실측 아님

| 항목 | 예정 수 |
|---|---:|
| 핵심 / 작은 입력 sample | 72 / 12 |
| 전체 sample | 84 |
| Run당 sample×algorithm pair | 336 |
| Run당 memory 자식 / 원시 반복 | 3360 |
| Run당 timing 자식 | 336 |
| Run당 timing 원시 호출 | 3360 |
| 전체 run | 6 |
| 전체 memory 자식 / 원시 반복 | 20160 |
| 전체 timing 자식 | 2016 |
| 전체 timing 원시 호출 | 20160 |
| Run당 / 전체 예정 자식 job | 3696 / 22176 |

부모의 입력 생성·참조 압축·복원과 부모 프로세스 시작은 자식 job 수에 포함하지 않는다.
각 phase의 memory와 timing은 각각 5회이며 중앙값을 run별 대표값으로 쓴다.
소요 시간·성공 수·측정값은 아직 없다.

## 4. 날짜·환경·순서 고정

같은 기계에서 Asia/Seoul 기준 연속 세 날짜에 두 run씩, run ID 1~6 순서로 실행한다.
첫 run 시작을 `t0`로 기록한다. 각 날짜 첫 run(1, 3, 5)은 각각 `t0`, `t0+24시간±60분`,
`t0+48시간±60분`에 시작하며 실제 로컬 날짜가 연속이어야 한다. 날짜별 두 번째 run은
첫 run 종료 후 30~90분에 시작한다. 자동 실행·장시간 대기는 이번 문서 작업에 포함하지 않는다.
각 run은 별도 부모 subprocess이며 동시에 실행하지 않는다. 정해진 여섯 run으로
끝내고 결과를 보고 run을 추가하거나 일부만 다시 실행하지 않는다.

OS·architecture·CPU·물리 메모리 총량·Python 실행 파일과 버전·패키지·압축 설정·
소스 hash는 같은 값을 요구한다. 시작·종료 시각, 가용 메모리·메모리 부하, 전원 모드,
수동 reboot 여부, 사용자 확인한 동시 작업·OS 업데이트 등의 사건은 run마다 기록한다.
가용 메모리 값의 동일성을 요구하지는 않는다. 연구 benchmark·학습·다른 본 연구 worker는
동시에 실행하지 않는다. 일반 OS 활동은 완전 통제되지 않는 한계로 남긴다.
일정 위반이나 지정 환경 변경은 기록을 보존하고 전체 사전 판정을 `inconclusive`로 만든다.
위반 run을 누락하거나 사후에 날짜 조건을 완화하지 않는다.

Run별 `random.Random(20262007 + run_id)`를 사용한다. 다음 canonical job 목록을
먼저 만든 뒤 RNG로 한 번 shuffle하여 전체 schedule을 저장한다.

1. Sample ID 순서→위 algorithm 순서→위 phase 순서→repeat 1~5 순서의 memory job.
2. Sample ID 순서→algorithm 순서의 timing job. Timing job 내부는 압축 1~5→해제 1~5.

종류가 섞인 전체 schedule을 실행 전에 고정하고 `schedule_index`를 부여한다.
모든 job은 순차 실행하고 timeout은 memory·timing 각각 120초다. Job 실패에 대한
자동 retry는 없다. 같은 job을 성공할 때까지 반복하지 않는다.

## 5. 원시 저장·실패·재현성 계약

새 경로 `data/results/memory_stability_v1_<UTC timestamp>_<attempt_id>/`를 배타적으로
생성한다. 기존 경로 덮어쓰기와 과거 실행 이어쓰기는 금지한다. 다음은 예정 layout이다.

```text
plan.json
samples.csv
metadata.json
run_01/ ... run_06/
  references.csv
  memory_repeats.csv
  timing_repeats.csv
  measurements.csv
  metadata.json
run_01_stdout.txt / run_01_stderr.txt ... run_06_stdout.txt / run_06_stderr.txt
audit.json
candidate_labels.csv
transfer_regrets.csv
stability_summary.json
```

`plan.json`에는 설계 ID·이 문서 hash·입력 명세·전체 schedule·예정 key·config snapshot·
후보 weight·7절 기준의 원래 숫자와 식·후속 구현 commit 및 소스 hash를 저장한다.
계획은 불변이다. 첫 실행은 출력 폴더 생성 전 깨끗한 Git 상태에서 시작한다.
측정 중에는 해당 attempt 산출물의 생성만 허용하고 관련 소스·설정·설계를 수정하지 않는다.

`samples.csv`는 `sample_id,stratum,generator,family,replicate_index,size,seed,
generation_parameters,input_sha256,duplicate_of,status,error`를 저장한다.
해당하지 않는 generator/family/replicate/seed/duplicate 필드는 null 계약을 따른다.
준비 실패도 sample 행을 남기며 중복은 최초 같은 hash의 sample ID를 가리킨다.
`references.csv`는 sample×algorithm마다 original/compressed size와 hash,
부모의 실제 `restored == original` 결과·status·error를 저장한다.
같은 sample×algorithm의 참조 압축 bytes·hash는 run 간 같아야 한다.

원시 key는 `(attempt_id,run_id,sample_id,algorithm,phase,repeat_index)`이며 memory와
timing 파일을 구분한다. 두 원시 파일에는 `schedule_index`, 요청 ID, 시작·종료 UTC,
실제 argv, 실행 파일·환경 옵션 식별자, 실제 phase 입력 크기·hash, 기대 출력 hash,
부모 참조 복원 결과, worker의 `verified,status,error,return_code,stdout,stderr`를 남긴다.
Memory에는 정수 `peak_process_working_set_bytes`와 method, timing에는 정수
`elapsed_ns`와 timer를 추가한다. Timing은 같은 bundle의 stdout·종료 증거를 각 반복
행에 연결한다. 실패 전 확보한 원시 ns·검증 결과는 보존하되 실패 bundle을 정상 집계에 쓰지 않는다.

부모는 duplicate JSON key·잘못된 타입·비유한 수·operation/algorithm/요청 불일치·
종료 코드와 verified 불일치·stderr 오류를 거부한다. 기존 memory CLI는 요청 ID나
입력 hash를 응답하지 않으므로 부모가 요청·argv·불변 입력·응답을 기록해 묶는다.
Timing worker는 요청 ID와 input/output hash·10개 반복 결과를 응답해야 한다.
입력 hash는 각 호출 전후 부모가 확인한다. 잘못된 응답을 성공으로 바꾸지 않는다.

준비 실패는 해당 sample의 예정 job마다 `preparation_failed`로 남기고 자식을 실행하지
않는다. Worker 실패·timeout·복원 실패·양수가 아닌 peak 또는 ns는 실패 행으로 보존한다.
참조 또는 timing 압축 hash의 불일치도 실패다. 실패 후 예정 다음 job을 진행하되,
명시적 중단은 `interrupted`/`aborted`로 기록한다. 종료 오류·소스 변경도 별도 실패 상태다.
원시 행은 즉시 flush하고 metadata는 원자적으로 저장한다. 예외 원인과 종료 처리의
추가 오류를 모두 보존한다. 실패값·누락값을 삭제·보간·0으로 대체하지 않는다.

`measurements.csv`는 유효한 각 sample×algorithm에 ratio·phase별 timing 중앙값(ms)·
phase별 memory 중앙값(bytes)·그 최댓값과 검증 상태를 저장한다. Phase의 예정 5회가
모두 성공해야 그 phase를 정상 집계한다. 하나라도 실패한 pair의 정상 4지표 집계는 null이다.
Run·최상위 metadata에는 환경·Git·시각·예정/기록/실패 수·완료 상태·종료 오류·
소스 시작/종료 hash·파일 hash를 기록한다. 실행 완료와 audit 통과·판정 만족을 구분한다.

독립 audit는 runner·worker·compressors·scoring을 import하거나 측정·압축·복원을
재실행하지 않는다. Source hash를 확인한 `src.data_generator`의 순수 입력 재생성은
허용하고 tiny 입력은 위 식으로 재생성한다. Schedule·key·input hash·참조 일관성·
응답·원시값·집계·환경/날짜·종료·소스/산출물 hash를 독립 확인한다.
새 설계 전용 audit를 구현하며 기존 schema-v1 또는 baseline audit를 완화하지 않는다.
분석도 감사한 바이트와 묶고 증거 변경을 거부한다. Audit/분석은 새 출력만 만들고
원시 파일을 수정하지 않는다. 저장 hash·복원 flag 감사는 독립 복원 재검증이 아니다.

## 6. 대표값·후보 score·분리 분석

아래 정의는 새 입력의 **검증용 후보 계산**에만 사용한다. 공식 label·모델에는 편입하지 않는다.
Mode 순서는 `[archive, balanced, fast_access]`이고 기존 [초기 설계의 후보 weight](peak_memory_measurement_design.md)를
그대로 사용한다. 결과를 본 뒤 weight·tie·epsilon을 바꾸지 않는다.

| Mode | size | compress | decompress | memory |
|---|---:|---:|---:|---:|
| archive | 0.65 | 0.10 | 0.10 | 0.15 |
| balanced | 0.40 | 0.20 | 0.20 | 0.20 |
| fast_access | 0.20 | 0.20 | 0.45 | 0.15 |

Sample 표기는 생략하고 run `r`, algorithm `a`에 대해 다음을 계산한다.

```text
C_a = compressed_size / original_size  (모든 run의 참조가 같아야 함)
Tc_ra, Td_ra = 각각 5개 elapsed_ns의 median / 1_000_000
Mc_ra, Md_ra = 각각 5개 memory peak bytes의 median
M_ra = max(Mc_ra, Md_ra)
S_m(r,a) = wC*ln(C_a/min_b C_b)
         + wTc*ln(Tc_ra/min_b Tc_rb)
         + wTd*ln(Td_ra/min_b Td_rb)
         + wM*ln(M_ra/min_b M_rb)
```

각 지표의 최솟값은 같은 sample·scenario·run의 네 알고리즘 사이에서 구한다.
양수·유한 값과 유효한 네 algorithm이 모두 있어야 계산한다. 정확한 동점은
`gzip,bz2,lzma,zstd` 순서로 선택하고 원래 score와 동점 집합도 보존한다.
근사 동점을 만들거나 score에 epsilon을 넣지 않는다.

진단 anchor는 각 알고리즘의 **여섯 run 대표값의 중앙값** `Tc_ref,Td_ref,M_ref`이다.
짝수 run의 median은 가운데 두 대표값의 평균이며 반올림하지 않는다. 원시 반복을
합쳐 표본 수를 늘리는 방식이 아니며 anchor는 실측 run이나 외부 oracle가 아니다.
학습·시험 분할에도 쓰지 않는다. 다음 시나리오를 모두 계산한다.

| Scenario | Timing | Memory | 해석 |
|---|---|---|---|
| `reference` | ref | ref | 진단 anchor 후보 score |
| `memory_only` | ref | run r | Timing을 고정했을 때 memory 변동의 선택 영향 |
| `timing_only` | run r | ref | Memory를 고정했을 때 timing 변동의 선택 영향 |
| `joint` | run r | run r | 같은 run에서 별도로 측정한 두 변동의 종합 영향 |

Reference와 세 run별 시나리오 모두 고정 ratio와 같은 후보 weight를 쓴다. Run별 score·
label·최저/차선 gap, Mc/Md/M의 값·범위·CV·최댓값을 결정한 phase 및 동점을 보존한다.
M에 대해 모든 algorithm 쌍의 차이·동점·run 간 부호도 공개한다. Phase 순위가 바뀌거나
최댓값 phase가 바뀌었다는 이유만으로 실패시키지 않는다. 범위 겹침은 기술적 진단이다.

각 run별 시나리오 `q`의 선택을 `A_q(r)`라 할 때 모든 **방향 있는 run 쌍**에 대해
`G_q(r→t)=S_q(t,A_q(r))−min_a S_q(t,a)`를 계산한다. 여섯 run의 모든 36개 쌍을
보존하고 대각선은 0이다. Scenario별 sample×mode 252조건, regret 행 9072개가
예정되어 있다. Regret은 score 차이이며 실제 모델 예측 성능이나 확률이 아니다.
Anchor 선택의 run별 regret도 별도 보고하되 위 전체 쌍 평가를 대신하지 않는다.

공식 v2 weight의 같은 새 입력 3지표 선택은 별도 비교용으로만 계산한다. Memory가
선택에 기여했는지 보기 위해, 후보 weight의 non-memory 항만으로 고른 `A_noM(r)`도
기록한다. 그 non-memory 합은 공식 v2 score가 아니며 공식 weight 차이와 memory 추가를
혼동하지 않는다. Joint 선택 `A_joint(r)` 대비 weighted memory 차이는
`B_m(r)=wM*ln(M_r,A_noM(r)/M_r,A_joint(r))`이다. 0·음수도 원래 값으로 보존한다.
모든 run에서 `B_m(r)>delta`(7절의 0.01)인 sample×mode를 선택 영향의 제한된 근거로 보고한다.
해당 조건이 없다면 안정성 만족과 memory의 선택 효용은 구분한다. Model 학습이나
baseline 대비 최종 시스템 개선은 이 검증으로 주장하지 않는다.

## 7. 사전 판단 규칙 — 검증용 공학 기준 제안

허용 regret budget `delta=0.01`, 알고리즘별 memory score 변동 budget `epsilon=0.005`를
고정한다. 이는 사용 목적의 확정된 요구사항이나 기존 결과에서 입증한 과학적 허용값이
아니다. 작은 weighted log-loss 차이까지 선택 오류로 요구하는 보수적인 검증용 정책
제안이다. `exp(delta)=1.010050167084168`은 weighted 지표 비율의 곱에서 약 1% 수준의
변화를 뜻하며, 실제 파일 크기·시간·메모리가 각각 1% 이내라는 의미가 아니다.
값을 바꾸려면 **새 실측 전에** 별도 설계 버전·이유·사용자 확인이 필요하다.

Memory span을 `L_a=ln(max_r M_ra/min_r M_ra)`로 정의하고 모든 sample×algorithm에서
`L_a <= epsilon/(2*wM_max) = 0.0125`를 요구한다. `wM_max=0.20`이며 대응하는
ratio 한계 `exp(0.0125)=1.0125784515406344`이다. 비교는 반올림한 표시값이 아니라
원래 식으로 수행한다. 핵심 층·작은 층을 각각 판정하고 전체를 만족시키려면 둘 다
만족해야 한다. 사후 크기 제외·조건 삭제·평균값만으로 통과시키지 않는다.

이 조건의 이유는 모든 algorithm의 run 간 log 변동이 L 이하이면, sample 내 최솟값의
log 변동도 L 이하이므로 normalized memory loss의 run 간 차이는 2L 이하라는 점이다.
따라서 weighted memory 항의 차이는 epsilon 이하이고, 고정 timing의 한 run 선택을
다른 run에 적용한 regret은 최악의 두 score 차이 합인 `2*epsilon=delta` 이하로 제한된다.
이는 **관측된 여섯 run에 대한 충분조건**이다. 미래 실행의 오차 상한·신뢰구간·통계적
유의성이나 모든 알고리즘 순위 고정의 증명은 아니다. 분석기는 실제 regret도 계산해
이 산술적 관계와 검사 구현의 일관성을 확인한다.

| 판정 단계 | 사전 조건 | 만족하지 않을 때 |
|---|---|---|
| 기술적 유효성 | 예정 key 전체 완료·고유, 모든 참조/반복 검증 성공, 양수/유한 값, 일정·환경·소스 불변, 종료 및 독립 audit 성공 | `inconclusive`; 부분 성공을 전체 만족으로 처리하지 않음 |
| Memory 안정성 | 모든 층의 모든 M span이 위 한계 이내이고 `memory_only` 전체 G가 delta 이하 | `memory_stability_not_satisfied`; 공식 채택 보류 유지 |
| 종합 정답 안정성 | `joint` 전체 G가 delta 이하 | `joint_stability_not_satisfied`; timing_only와 memory_only로 진단하고 공식 채택 보류 유지 |
| 관측 범위 조건 만족 | 위 단계 모두 만족 | `observed_conditions_satisfied`; 공식 전환이나 과학적 보편성의 판정이 아님 |

작은 gap의 label 변경은 delta 이내 regret이라면 허용한다. Label 일치율만으로 판정하지
않는다. 반대로 dominant algorithm 때문에 joint label이 고정돼도 memory span 조건을
면제하지 않는다. Memory 조건은 만족하나 joint 조건이 불만족이면 두 결과를 분리하고,
time-only 분석만으로 원인을 확정하거나 memory 채택을 자동 승인하지 않는다.
성공한 조건의 기술적 요약은 실패 run에서도 별도 표시할 수 있으나 전체 판정은 기술적
유효성 실패를 우선한다. 기준과 관측 결과의 차이·실패·동점은 모두 보고한다.

## 8. 구현·실행 전 검증과 다음 작업

신규 runner·timing worker·전용 audit·분석기는 아직 없다. 기존 memory worker와
공식 scoring API를 수정해 4지표를 끼워 넣지 않는다. 다음 단일 작업 제안은
**별도 timing worker의 원시 ns·bytes 검증·응답 계약 구현과 fixture 검증**이다.
그 후 runner·독립 audit·분석기를 각각 단일 기능으로 구현·검증한다.

실측 전 검사에는 고정 계획·seed/schedule 재현, 정확한 호출 횟수, timed 구간 밖의
검증·파일 읽기, bytecode 옵션 전달, 10개 raw timing 보존, bool/0/비유한 값·중복 JSON
거부, timeout/중단/저장 실패 보존, 일반·`-O`·`-OO`의 명시적 오류 거부, 덮어쓰기
거부와 audit/분석 중 codec 호출 금지를 포함한다. Threshold 경계·동점·낮은 gap의
label 변화·방향 있는 regret·memory/timing 영향 분리도 인위적 fixture로 검증한다.
Fixture 수치는 실제 연구 측정값과 구분한다.

일정과 환경을 준비한 전체 attempt의 실측은 후속 사용자 확인 후 진행한다. 중단 후
재시도하려면 사유를 기록한 새 attempt에서 전체 계획을 시작하고 모든 이전 시도를
보존한다. 만족한 attempt만 골라 대표 결과로 내지 않고 attempt별 판정을 함께 보고한다.
이 조건을 만족해도 v3·공식 weight·runner 전환·새 Pilot은 [채택 검토의 단계](memory_adoption_review_20261007.md)에
따른 별도 작업이다. 기존 3지표 실험·label·모델과 Smart Mode의 단일 codec 선택을 유지한다.

## 9. 설계 산술 재현과 이번 작업 검증

아래 코드는 예정 규모·가중치 합·budget 식만 계산한다. 입력 생성·압축·측정은 하지 않는다.
저장소 루트의 가상환경 Python을 `-B`로 실행하여 확인한다.

```python
import math

core = 4 * 6 * 3
tiny = 4 * 3
n, algorithms, phases, repeats, runs = core + tiny, 4, 2, 5, 6
memory_per_run = n * algorithms * phases * repeats
timing_per_run = n * algorithms
weights = [(0.65,0.10,0.10,0.15), (0.40,0.20,0.20,0.20), (0.20,0.20,0.45,0.15)]
epsilon, delta = 0.005, 0.01
print(core, tiny, n, n * algorithms)
print(memory_per_run, timing_per_run, timing_per_run * phases * repeats, runs)
print(memory_per_run * runs, timing_per_run * runs, timing_per_run * phases * repeats * runs)
print(memory_per_run + timing_per_run, (memory_per_run + timing_per_run) * runs)
print(n * len(weights), runs * runs, n * len(weights) * runs * runs)
print([math.fsum(w) for w in weights])
print(epsilon / (2 * max(w[3] for w in weights)), math.exp(epsilon / (2 * max(w[3] for w in weights))))
print(2 * epsilon, math.exp(delta))
```

이번 수치는 Python으로 계산한 예정 조건이며 측정 결과가 아니다.
예정 수량 표·재현 코드·기존 후보 weight 일치와 schedule key의 고유성·재현성을 Python으로
확인했다. 로컬 링크 9개가 존재했고 기존 보호 대상 증거·소스·설정·설계·검토 문서 54개의
SHA-256이 같았다. 문서 근거·식·diff도 검토하며 새 실측·단위 테스트는 실행하지 않는다.
