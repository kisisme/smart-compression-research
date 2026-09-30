# 작은 파일의 runtime baseline 검증 설계

작성일: 2026-09-22. 설계 ID: `memory_runtime_baseline_v1`.

**상태: 설계·worker·별도 runner·별도 audit·진단 분석 구현 검증 완료 / 전체 실험 미착수 / `validation_only` / `score_inclusion=false`.**
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

별도 runner에서 아래 경로 형식을 사용한다. 실제 연구 실행 경로는 아직 생성하지 않았다.

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

별도 [worker](../src/memory_runtime_worker.py)와 [전용 테스트](../tests/test_memory_runtime_worker.py),
[runner](../src/memory_runtime_validation.py)와 [runner 테스트](../tests/test_memory_runtime_validation.py)를
구현했다. 저장 계약을 검사하는 [별도 audit](verify_memory_runtime_validation.py)와
[전용 테스트](../tests/test_verify_memory_runtime_validation.py)도 구현했다.
paired 대비·run 간 진단 분석과 fixture 검증도 아래와 같이 완료했다. 다음 단일 작업은 전체 실측과 저장 기록 검증이며
위 연구 결과 경로는 아직 계획이다.

구현 검증에는 control에서 압축기 호출 금지, 실제 phase 입력 사용, codec 호출 1회,
원본/복원 불일치·잘못된 hash 거부, 측정 전후 처리 순서, arm별 null 규칙,
seed/schedule 재현, timeout·중단·종료 저장 실패 및 기존 출력 덮어쓰기 거부를 포함한다.
테스트 fixture의 memory 값은 실험 결과와 구분한다.

최초 설계 문서 작업에서는 행렬 규모만 Python으로 계산하고 근거 코드·공식 API 문서·링크·diff를
확인했다. memory 실측, 단위 테스트, 모델 학습, 공식 score 변경은 실행하지 않았다.
관련 구현 기준은 `3e9b267`, 기존 전체 행렬 결과 보존 commit은 `3ad85c9`이다.

### Worker 구현·검증 — 2026-09-22

설계 commit `584fc68`을 기준으로 공통 CLI와 `measure_arm`을 추가했다.
기존 `memory_benchmark.py`·`compressors.py`·config는 변경하지 않았다.
CLI 호출 형식은 다음과 같다. 아래는 형식 설명이며 실행된 연구 명령이 아니다.

```text
python -B -m src.memory_runtime_worker --request-id <unique-request-id> --arm <arm> --phase <phase> --algorithm <algorithm> --input <phase-input-path> --input-sha256 <phase-input-digest> --expected-output-sha256 <reference-output-digest>
```

모든 arm에서 두 digest 인자를 받아 같은 요청 검증 경로를 사용한다. 공통 설정 파일을
읽어 import된 설정·설계의 압축 수준·memory 설정과 대조한 후 arm을 실행한다.
`import_only`는 지정한 phase 입력 경로를 열거나 stat하지 않는다.
`codec`은 출력 hash만 검사하고 `input_only`는 입력 hash만 검사한다.
Windows와 bytecode 쓰기 비활성화 조건도 검사한다.

응답은 `design_id`, `schema_version`, `measurement_status`, `score_inclusion`,
`measurement_method`, `request_id`, `arm`, `phase`, `algorithm`,
`peak_process_working_set_bytes`, `observed_input_size`, `verified`, `input_verified`,
`status`, `error`를 포함한다. `observed_input_size`는 import_only에서 null이다.
부모의 `reference_roundtrip_verified`는 worker가 생성하거나 대신 인증하지 않는다.
부모가 요청 ID·arm·phase·알고리즘·응답 타입·종료 코드·검증 필드 조합을 검사하고
참조 복원 검증 결과와 합쳐 원시 기록을 저장해야 한다.

정상 응답은 종료 코드 0, hash 불일치는 측정 peak와 false 검증값을 보존하고 코드 2,
처리 가능한 실행 오류는 `worker_failed`·null peak의 JSON과 코드 1을 반환한다.
인자 파싱 오류는 argparse의 stderr·코드 2, import 단계 오류나 강제 종료는 JSON이
없을 수 있으므로 부모가 그대로 실패 기록으로 보존해야 한다. KeyboardInterrupt와
SystemExit는 삼키지 않는다. 이 worker 자체는 subprocess 생성·timeout·결과 저장을 하지 않는다.

실행한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_worker.py -v
13 tests: OK
```

인위적 peak fixture로 control의 입력/압축기 호출 제한, 실제 phase 입력,
선택한 codec 호출 1회, 잘못된 복원 결과·hash·요청·설정·peak 거부,
hash → peak → JSON 순서 및 중단 전파를 확인했다. 임시 입력을 쓰는 Windows
subprocess smoke test로 모든 arm·알고리즘·phase의 성공 경로와 일반/`-O`/`-OO`의
hash 불일치 거부를 실제 실행했다. smoke test의 메모리는 실제 backend를 사용했지만
연구 결과로 저장·집계하지 않았다. 전체 suite와 계획된 baseline 전체 행렬은 실행하지 않았다.

### Runner 구현·검증 — 2026-09-30

worker 구현 commit `018758c`를 기준으로 별도 실행 기능을 추가했다. 기존 worker·공식
config·schema-v1 audit·기존 결과 파일은 변경하지 않았다. 아래는 사용 형식이며 전체
연구 실험을 실행한 명령이 아니다.

```text
python -B -m src.memory_runtime_validation --output-dir data/results/memory_runtime_baseline_v1_<UTC timestamp>_<attempt_id> --attempt-id <attempt_id> --reason <attempt reason>
```

- 출력 경로는 배타적으로 새로 생성한다. attempt ID는 ASCII 영숫자로 시작하는
  영숫자·밑줄·하이픈 1~64자로 제한한다. 재시도 사유는 `--reason`으로 기록한다.
- coordinator가 입력 규칙과 세 run의 전체 schedule을 `plan.json`에 먼저 저장한다.
  각 run은 같은 Python의 별도 부모 subprocess로 순차 실행한다. 부모·worker 모두
  `-B`와 `PYTHONDONTWRITEBYTECODE=1`을 사용한다. 축소 행렬 CLI 옵션은 없다.
- 각 부모는 전체 입력·참조 압축물을 임시 디렉터리에 준비하고 실제 복원 bytes 및
  저장된 phase 입력 bytes를 확인한 뒤 worker를 호출한다. 준비 실패는 영향을 받는
  모든 예정 key의 `preparation_failed` 행으로 보존하며 해당 worker를 실행하지 않는다.
- `samples.csv`는 입력 생성 명세이다. 각 run의 추가 `references.csv`에 실제 원본·압축물
  SHA-256, 압축 크기, 참조 복원 결과와 준비 실패를 기록한다. 각 원시 반복 행에도
  phase 입력 크기·hash와 기대 출력 hash를 기록한다. 임시 입력 파일은 종료 후 정리한다.
- worker 응답의 설계·요청 식별자, 타입, phase 입력 크기, arm별 null/boolean 규칙,
  양수 정수 peak, 상태·종료 코드 조합을 검사한다. timeout은 120초이며 worker 오류와
  잘못된 JSON도 stdout·stderr·종료 코드와 함께 남긴다. 유효한 hash 불일치 응답의
  peak·false를 보존하고, 계약에 어긋난 payload는 원본 stdout에 보존한다.
- `repeats.csv`는 매 행 flush한다. `summary.csv`는 run별 sample·algorithm·phase·arm의
  예정 반복이 모두 기록·검증된 경우에만 중앙값·min/max·population std·CV를 저장한다.
  실패한 조건은 집계값을 null(CSV의 빈 필드)로 남긴다. 중단된 run에서는 summary가
  없을 수 있으며 원시 CSV와 종료 metadata를 증거로 사용한다.
- 각 run과 최상위에 `metadata.json`을 둔다. 시작·종료 환경과 가용 물리 메모리,
  Git·소스·설정, 산출물 hash, 종료 상태·오류를 저장한다. run 도중 plan 또는 소스가
  바뀌면 완료 결과를 무효화한다. 종료 metadata는 같은 디렉터리의 임시 파일을
  flush·fsync 후 원자적으로 교체하며, 추가 종료 오류가 원래 예외를 대체하지 않는다.
- 최상위 `run_XX_stdout.txt`·`run_XX_stderr.txt` 및 부모 종료 코드를 보존한다.
  예정 행렬이 끝난 worker 실패 run은 다음 run으로 진행하지만 부모 자체의 중단·종료
  실패는 attempt를 중단한다. 기존 출력에 이어 쓰거나 실패 조건만 재실행하지 않는다.
- `completed`는 runner 실행·저장 완료만 의미한다. 독립 audit 또는 과학적 합격 판정이
  아니다. `analysis_status=pending_independent_audit_and_diagnostics`로 남기며 아직
  `diagnostic_summary.json`은 생성하지 않는다. 위 5절의 paired 대비·음수 차이 보존·
  run 간 범위·순위 진단은 별도 구현 후 실측 전에 검증해야 한다.

검증 명령과 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_validation.py -v
19 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_worker.py -v
13 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_validation.py -v
17 tests: OK
```

runner 테스트는 임시 폴더·인위적 peak fixture로 schedule 완전성·재현성, 실제 참조
압축·복원, 잘못된 응답·timeout·준비 실패, 중단·저장 실패·소스/plan 변경, 기존 경로
보존을 확인했다. 축소 fixture를 실제 별도 부모 프로세스에서 실행하여 CLI와 저장
계약도 검증했다. worker 연결 smoke test는 임시 입력과 실제 Windows backend를
사용했지만 연구 결과로 저장·집계하지 않았다. 전체 테스트 suite, 독립 audit 및 전체
baseline 실측은 실행하지 않았다. 샌드박스의 사용자 Python 접근 제한 때문에 테스트는
사용자 권한으로 실행했다.

### 별도 audit 구현·fixture 검증 — 2026-09-30

runner 구현 commit `9d3f120`을 기준으로 읽기 전용 audit를 추가했다. 기존 schema-v1
audit나 runner·worker의 검증 함수를 재사용하거나 완화하지 않았다. 새 audit는 표준
라이브러리만 사용하며 runner·worker·압축 모듈을 import하지 않는다.

```text
python -B -m research_log.verify_memory_runtime_validation --experiment-dir <completed-study-directory> --output <new-audit-json>
```

- 지원 범위는 `memory_runtime_baseline_v1`의 세 run 전체가 `completed`이고 종료 처리가
  완료된 저장 기록이다. 실패·미완료·소스 변경 상태는 성공 보고서를 만들지 않는다.
- 고정된 입력 명세·seed와 run별 전체 schedule을 별도로 재생성하여 순서까지 대조한다.
  입력 bytes의 SHA-256을 재계산하고 sample·참조·원시 행·집계의 고유성 및 완전성을 검사한다.
- 실제 phase 입력 크기·입력/출력 hash·참조 복원 flag·arm별 null/boolean 규칙·양수 정수
  peak·종료 코드와 저장 worker JSON을 대조한다. 압축물 hash·크기는 run 간 일관성만 확인한다.
- 저장 원시값에서 중앙값·min/max·population std·CV를 독립 재계산한다. 정수 통계는
  정확히 비교하고 부동소수 통계는 상대·절대 허용오차 각각 `1e-12`로 비교한다.
  비유한 수, JSON 중복 key, CSV 열 누락·추가·중복 header를 거부한다.
- 최상위/각 run의 상태·수량·설정·Git·환경·실행 시간 순서·부모 출력, 완전한 source 및
  artifact hash manifest를 확인한다. 당시 소스·설정 바이트가 현재 checkout과 같아야 한다.
  과거 소스 불일치는 기록된 checkout에서 확인해야 하며 검사를 생략하지 않는다.
- 읽은 파일의 바이트 snapshot을 검증 종료 때 다시 대조하여 감사 도중 변경을 거부한다.
  보고서에는 감사 코드 hash와 읽은 증거 파일 hash를 남긴다. 기본 출력은 stdout이며
  `--output`은 감사 통과 후 새 파일만 생성한다. 오류 시 비정상 종료하고 성공 JSON을 출력하지 않는다.

**해석 한계:** 저장된 복원 flag는 독립 복원 재검증이 아니며 압축물 hash도 재압축해서
확인하지 않는다. hash는 바이트 일관성 확인이며 증거 진위의 서명이나 조작 불가능성 보장이
아니다. Audit 통과는 과학적 memory 검증 완료·공식 score 편입을 의미하지 않는다.
paired 대비·run 간 진단은 이 audit의 산출물에 포함하지 않는다.

실행한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_runtime_validation.py -v
15 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_validation.py -v
11 tests: OK
```

새 테스트는 전체 예정 행렬 크기의 임시 fixture에 인위적 peak와 테스트용 Git 정보를
사용했다. Fixture 준비 시 runner의 실제 입력 생성·참조 압축·복원·저장을 사용하고
worker와 부모 호출을 mock했다. Audit 중에는 압축·복원·측정 호출을 금지하여 독립성을
확인했다. hash를 다시 맞춘 잘못된 증거, 누락·중복·순서 변경, 비유한 통계, 미완료 상태,
동시 파일 변경, 일반/`-O`/`-OO` CLI 실패 거부, 출력 덮어쓰기 거부 및 입력 바이트 보존을
검증했다. 테스트는 사용자 Python 접근이 가능한 권한으로 실행했다. 실제 연구 기록 대상
audit·baseline 전체 실측·전체 테스트 suite는 실행하지 않았다.

### 진단 분석 구현·fixture 검증 — 2026-09-30

audit 구현 commit `c9bf6e6`을 기준으로 [분석기](analyze_memory_runtime_validation.py)와
[전용 테스트](../tests/test_analyze_memory_runtime_validation.py)를 추가했다.
기존 runner·worker·audit·config·연구 결과는 변경하지 않았다.

```text
python -B -m research_log.analyze_memory_runtime_validation --experiment-dir <completed-study-directory> --output <new-diagnostic-summary-json>
```

위는 CLI 사용 형식이며 연구 실행 기록이 아니다. 분석기는 기존 audit를 직접 실행하고,
그 audit가 확인한 원시 CSV 바이트의 hash를 다시 대조한 뒤 메모리의 snapshot으로 계산한다.
분석 종료 시 전체 감사 입력과 분석기·audit·측정 소스의 변경을 검사한다. 실패·미완료
기록이나 감사 후 변경을 거부하며 성공 JSON을 만들지 않는다. 기본 출력은 stdout이고
`--output`은 새 파일만 생성한다. 기존 metadata의 분석 대기 상태도 덮어쓰지 않는다.

JSON schema v1의 주요 필드:

- `audit`: 실행한 독립 감사 보고서, 원시 증거 hash·측정 commit·감사 코드 hash.
- `analysis_script_sha256`, `samples`: 분석 코드 hash와 입력 생성 명세.
- `peak_by_run`: round 순서 원시 peak 5개·중앙값·min/max·population std·CV. 단위는 bytes이며 CV는 비율이다.
- `paired_by_run`: 동일 run·round·block의 `D_input`, `D_codec`, `R_input` 원시 대비와 중앙값·min/max.
- `arm_pairs_by_run`, `algorithm_pairs_by_run`: 각 arm 쌍과 알고리즘 6쌍의 left 중앙값 − right 중앙값, 부호·동점·양쪽 반복 범위와 겹침.
- 대응하는 `*_across_runs`: run 1·2·3 각각의 중앙값 또는 쌍별 차이, 그 min/max·부호·부호 일치 여부. 반복을 run 간 합치지 않는다.

알고리즘 비교는 차감하지 않은 codec peak를 사용한다. Arm 쌍의 중앙값 차이는 paired
차이의 중앙값과 별도 필드로 구분한다. 겹침은 양끝을 포함한 관측 min/max 범위로 정의하며
경계가 같아도 겹침이다. 동점은 정확한 동일값이며 부호 0으로 보존한다. 차이의 부호 기준은
0, `R_input`의 run 간 부호 기준은 1이다. 음수 차이와 1 초과 비율을 보존한다.
자동 인과 해석·과학적 합격 판정·공식 score 변경은 하지 않는다.

전용 테스트는 인위적 peak의 계산 fixture와 기존 audit 테스트의 전체 행렬 저장 fixture를
사용한다. 짝지은 차이의 중앙값, 음수·비율·동점·범위 경계·순위 역전, run 분리, 실제 audit
연동과 원본 바이트 보존, 감사 후/분석 중 변경 거부, CLI 출력 독점 생성 및 일반/`-O`/`-OO`
오류 거부를 검증했다. Fixture 준비에만 실제 참조 압축·복원을 사용하며 분석 중에는
압축·복원·측정을 금지했다. 아래 전용 테스트가 통과했다.

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_analyze_memory_runtime_validation.py -v
7 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_runtime_validation.py -v
15 tests: OK
```

기존 audit 회귀 테스트도 위와 같이 통과했다. 두 모듈만 실행했으며 전체 suite는 실행하지 않았다.
실제 baseline 전체 실측·연구 기록 대상 audit/진단 분석·공식 4지표 전환은 미완료다.
