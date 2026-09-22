# 작은 파일의 runtime baseline 검증 설계

작성일: 2026-09-22. 설계 ID: `memory_runtime_baseline_v1`.

**상태: 설계 완료 / 구현·측정 미착수 / `validation_only` / `score_inclusion=false`.**
아래 크기·seed·반복 수는 앞으로 실행할 조건이며 측정 결과가 아니다.
공식 기준은 [프로토콜 v2](../research_protocol_v2.md), 압축 설정은
[현재 config](../config/experiment_config.json)이다. 공식 설정과 score는 변경하지 않는다.

## 1. 질문과 해석 범위

작은 입력에서 전체 프로세스 peak working set의 상당 부분이 공통 실행 환경에서
발생하는지, 그 환경의 반복 변동과 비교해 압축기 간 차이를 구별할 수 있는지 조사한다.
Python 자체의 순수 할당량이나 압축 라이브러리의 순수 heap 사용량을 추정하지 않는다.

Windows는 `PeakWorkingSetSize`를 bytes 단위의 최대 working set으로 정의하고,
working set은 프로세스에 물리적으로 매핑된 메모리이다.
근거: [PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters),
[Working Set Information](https://learn.microsoft.com/en-us/windows/win32/psapi/working-set-information)
(2026-09-22 확인).

기존 [측정 설계](peak_memory_measurement_design.md)의 전체 프로세스 peak 정의를
유지한다. 서로 다른 프로세스의 peak 차이는 두 최고값의 대비일 뿐, 같은 시점의
메모리 구성요소를 뺀 값이 아니다. 아래 baseline 대비 차이는 진단용으로만 사용한다.

현재 [worker](../src/memory_benchmark.py)의 `_worker`는 입력 읽기 → 압축 또는 해제
→ 출력 SHA-256 검증 → peak 조회 순서이다. 입력·출력 bytes를 조회 시점까지 보유한다.
검증용 hash 계산과 라이브러리 import도 측정 범위에 들어간다. 이 순서를 설계 근거로 삼되,
새 worker와 기존 worker의 모듈 구조가 다를 수 있으므로 과거 측정값을 새 대조군과 합쳐 분석하지 않는다.

## 2. 대조군과 실험군

모든 arm은 **동일한 새 worker 진입점·공통 import·인자 파싱 경로**를 사용한다.
네 압축 라이브러리와 동일 backend를 모두 import한 뒤 arm만 분기한다.
worker에는 부모의 전체 행렬이나 통계 분석 자료를 올리지 않는다.
각 arm의 각 반복마다 새 subprocess를 사용하고, 측정은 순차 실행한다.

| arm | peak 조회 전 수행 | 조회 시 유지하는 데이터 | 검증 |
|---|---|---|---|
| `import_only` | 공통 import·인자 파싱 후 바로 조회. 입력 파일을 열거나 압축기를 호출하지 않음 | 공통 runtime·모듈·인자 | 정상 worker 응답·양수 peak·요청 식별자 확인 |
| `input_only` | 해당 phase 입력 파일을 읽고 SHA-256을 부모의 입력 hash와 대조 | 입력 bytes | 입력 hash 일치 |
| `codec` | 해당 phase 입력을 읽고 선택한 압축기 하나로 압축/해제한 뒤 출력 SHA-256 대조 | 입력 및 출력 bytes | 출력 hash 일치 및 부모의 사전 round-trip 일치 |

`compress`의 phase 입력은 원본, `decompress`의 phase 입력은 해당 알고리즘의
사전 압축 bytes이다. 해제 대조군도 알고리즘별 실제 compressed size를 반영한다.
부모가 모든 참조 압축물을 준비하고 `restored == original`을 확인한 후 측정을 시작한다.
원본/압축물 hash·크기 및 생성 조건을 기록한다. worker 안에서 참조 압축물을 만들지 않는다.

동일 block의 arm들은 같은 sample·algorithm·phase 인자와 경로를 받는다.
`import_only`도 해당 문맥을 가지지만 실제 파일을 읽지 않는다. 이를 알고리즘별
runtime이라는 뜻으로 해석하지 않는다. 압축 설정은 gzip 9, bz2 9, LZMA preset 6,
zstd 3이며 실행 시 config 일치를 검사한다.

peak 조회 후에 JSON을 직렬화·출력한다. 측정 전 warm-up, 강제 GC, working set 축소,
캐시 비우기, 이전 peak 차감은 하지 않는다. 부모와 worker 모두 bytecode 쓰기를 끄고
동일 Python 실행 파일·환경을 사용한다. 해당 옵션도 metadata에 남긴다.

**한계:** `input_only`와 `codec`의 hash 대상과 보유 bytes가 다르다. 따라서 둘의 차이에는
출력 버퍼·hash 작업·라이브러리 실행과 OS 변동이 함께 반영된다. `import_only` 역시
Python·가져온 라이브러리·측정 코드 전체의 baseline이며 순수 Python runtime 값이 아니다.
출력 버퍼만의 영향을 분리하려면 별도 후속 대조군이 필요하다.

## 3. 측정 전 고정할 행렬

- 입력 크기(bytes): `[64, 256, 1024, 4096, 16384]`. 마지막 크기는 기존 검증 범위와
  연결되는 기준점이다. 빈 입력은 기존 benchmark가 거부하므로 포함하지 않는다.
- 입력 유형 순서: `zero_bytes`, `periodic_16`, `uniform_random`.
  각각 `bytes(size)`, `bytes(range(16))`을 길이에 맞게 반복한 값,
  `random.Random(seed).randbytes(size)`로 정의한다.
- size를 바깥 순서로 하여 sample index를 0부터 부여한다. 난수 sample의 seed는
  `20260922 + sample_index`이며, 결정적 두 유형의 seed는 null로 기록한다.
  입력 bytes·hash·생성 매개변수는 모든 run에서 동일하다.
- 알고리즘: `[gzip, bz2, lzma, zstd]`, phase: `[compress, decompress]`,
  arm: `[import_only, input_only, codec]`.
- 한 run에서 각 조건을 5회 측정한다. 같은 입력으로 별도 부모 프로세스의 전체 run을
  3회 실행한다. run ID는 1, 2, 3이며 순서대로 실행하고 reboot는 요구하지 않는다.
  이는 동일 환경에서의 실행 간 확인이며 서로 독립된 기계·날짜의 표본으로 취급하지 않는다.

Python으로 위 조건의 곱을 계산해 예정 규모를 확인했다. sample 15개,
sample × algorithm × phase block 120개, run당 worker 시도 1,800개,
전체 3개 run에서 5,400개이다. 부모의 준비용 압축·복원은 이 worker 수에 포함하지 않는다.
기존 `sample_sizes`나 generator 목록을 이 진단용 행렬에 맞추어 변경하지 않는다.

실행 순서는 다음과 같이 사전 고정한다.

1. run별 `random.Random(20260922 + run_id - 1)`를 하나 생성한다.
2. round 1~5마다 정렬된 block 목록을 새로 만들고 그 RNG로 shuffle한다.
3. 각 block에서 위 arm 목록을 새로 만들어 같은 RNG로 shuffle하고 세 worker를
   연속 실행한다. block 내부의 시간적으로 가까운 대조만 짝으로 삼는다.
4. 완성된 전체 schedule과 순서 index를 실행 전에 저장한다. Python 버전·seed와
   실제 schedule을 함께 보존해 RNG 구현 차이에도 순서를 추적할 수 있게 한다.

다른 benchmark·학습을 동시에 실행하지 않는다. 일반 OS 활동은 통제되지 않는 한계로
남기고 각 run 시작·종료 시 환경과 가용 메모리를 기록한다. 실패를 이유로 조건을
선택 재실행하거나 좋은 run만 채택하지 않는다. 외부 중단 후 재시도가 필요하면 기존
시도를 그대로 보존하고 새 attempt ID에서 전체 계획을 시작해 사유를 기록한다.

## 4. 저장·실패·재현성 계약

향후 별도 runner에서 아래 경로 형식을 사용한다. 이 문서 작성 시에는 생성하지 않았다.

```text
data/results/memory_runtime_baseline_v1_<UTC timestamp>_<attempt_id>/
  plan.json
  samples.csv
  run_01/{repeats.csv, summary.csv, metadata.json}
  run_02/{repeats.csv, summary.csv, metadata.json}
  run_03/{repeats.csv, summary.csv, metadata.json}
  diagnostic_summary.json
```

최상위 경로는 배타적으로 새로 생성한다. `plan.json`에 이 문서의 hash, 설계 ID,
입력 생성 규칙, 전체 schedule·예정 key, 실행 설정 snapshot을 저장한다.
metadata에는 실제 실행 Git commit·dirty 상태, Python·패키지·OS·CPU·메모리·backend,
시작/종료 시각, 소스·설정의 시작/종료 hash, 산출물 hash와 완료 상태를 보존한다.
로컬 경로가 포함될 수 있으므로 저장은 로컬 Git까지이며 외부 공개는 별도 작업이다.

반복 행은 최소 `attempt_id, run_id, round_index, schedule_index, sample_id, family,
size, seed, algorithm, phase, arm, input_size, input_sha256, expected_output_sha256,
peak_process_working_set_bytes, verified, input_verified, reference_roundtrip_verified,
status, error, return_code, stdout, stderr`를 기록한다.

`verified`는 codec의 출력 검증에만 boolean을 쓰고 controls에는 null을 쓴다.
`input_verified`는 input_only에서만 boolean, 나머지는 null이다.
`reference_roundtrip_verified`는 부모 준비 결과를 나타내며 arm의 무손실 검증과 구분한다.
import_only의 `status=ok`는 프로세스 응답 확인일 뿐 무손실 검증 성공이 아니다.

0 이하/비정수 peak, hash 불일치, worker 오류·timeout·누락 key는 모두 실패다.
worker timeout은 기존 runner와 같은 120초로 고정하고 원래 stdout·stderr·종료 코드를
보존한다. worker 실패는 기록 후 다음 예정 key로 진행하며, 실행 자체의 중단은
`interrupted`/`aborted`로 표시한다. 실패값을 삭제·보간·0으로 대체하지 않는다.
준비 실패도 예정 key마다 `preparation_failed`로 남기고 worker를 실행하지 않는다.

원시 행은 즉시 flush하고 종료 metadata는 원자적으로 저장한다. 종료 중 오류가 원래
예외를 가리지 않게 한다. 해당 조건의 예정 5개 반복이 모두 유효해야 정상 집계를 만들고,
paired 대비는 양쪽이 모두 유효한 완전한 조건에서만 계산한다. 불완전 조건의 정상 집계는
null로 두되 원시 증거와 실패 수는 남긴다. 전체 행렬이 완료되지 않으면 성공 보고서를 만들지 않는다.

기존 schema-v1 audit는 고정된 generator·크기·phase 행렬을 검사하므로 이 설계에는
적용하지 않는다. 구현 단계에서 설계 ID·arm·schedule·null 규칙·행렬 완전성을 검증하는
별도 audit가 필요하다. 기존 audit의 검사를 완화해 통과시키지 않는다.

## 5. 사전 분석 규칙

`P(run, round, sample, algorithm, phase, arm)`을 원시 peak bytes로 정의한다.
조건별 5개 원시값, 중앙값, min/max, population std, CV를 run별로 공개한다.
bytes가 원본 단위이며 KiB·백분율은 Python으로 계산한 표시값만 사용한다.

진단 대비는 동일 run·round·block에서 다음과 같이 계산한다.

```text
D_input  = P(input_only) - P(import_only)
D_codec  = P(codec) - P(input_only)
R_input  = P(input_only) / P(codec)
```

반복별 signed 차이와 비율, 각각의 run별 중앙값·min/max를 저장한다.
`median(D_codec)`와 `median(P(codec)) - median(P(input_only))`를 혼동하지 않는다.
음수 차이 또는 1보다 큰 비율을 자르지 않으며, 비율을 runtime의 확정적 점유율로 부르지 않는다.
세 run은 별도로 보고하고 run별 중앙값의 범위·부호 일치를 요약한다.
서로 다른 run의 반복들을 한 집단으로 합쳐 독립 표본 수가 늘어난 것처럼 분석하지 않는다.

알고리즘 간 비교는 같은 sample·phase·run의 **차감하지 않은 codec peak 중앙값**으로
수행하고 6개 알고리즘 쌍 모두의 signed 차이를 공개한다. 중앙값 완전 동점은 동점으로
보존한다. 각 쌍의 반복 범위가 겹치는지, run별 차이의 부호가 유지되는지도 기록한다.
arm간 비교도 같은 방식으로 반복 범위의 겹침 여부를 기록한다.

관측 반복 범위의 겹침은 기술적 진단이며 신뢰구간·동등성 검정이 아니다.
대조군과 codec의 값이 가까우면서 반복 범위와 알고리즘 순위가 불안정하다면
"이 조건에서 전체 프로세스 peak로 차이를 명확히 구별하지 못했다"고 기술한다.
분리된 범위와 일관된 순위도 해당 환경·입력에서의 관측으로 한정한다.
가까움에 임의의 사후 합격 임계값을 부여하거나 baseline 원인을 확정하지 않는다.

기술적 완료 조건은 전체 예정 key의 고유성·완전성, arm별 검증, 양수 peak,
종료 처리 성공, 소스 불변성과 저장값 재계산 일치이다. 이는 메모리 가중치 도입의
과학적 합격 기준이 아니다. 진단 결과가 어느 쪽이든 기존 3지표 라벨·모델을 바꾸지 않고,
공식 전환은 별도 프로토콜·설정·이유 기록 및 사용자 확인을 거친다.

## 6. 구현 전후 확인 항목과 현재 상태

다음 단일 작업은 이 설계의 별도 worker와 단위 테스트 구현이다.
이후 runner·별도 audit·인위적 실패 fixture를 구현하고 검증한 뒤 새 실측을 진행한다.
현재 새 worker·runner·audit는 존재하지 않으며 위 경로는 계획이다.

구현 검증에는 control에서 압축기 호출 금지, 실제 phase 입력 사용, codec 호출 1회,
원본/복원 불일치·잘못된 hash 거부, 측정 전후 처리 순서, arm별 null 규칙,
seed/schedule 재현, timeout·중단·종료 저장 실패 및 기존 출력 덮어쓰기 거부를 포함한다.
테스트 fixture의 memory 값은 실험 결과와 구분한다.

본 문서 작업에서는 행렬 규모만 Python으로 계산하고 근거 코드·공식 API 문서·링크·diff를
확인했다. memory 실측, 단위 테스트, 모델 학습, 공식 score 변경은 실행하지 않았다.
관련 구현 기준은 `3e9b267`, 기존 전체 행렬 결과 보존 commit은 `3ad85c9`이다.
