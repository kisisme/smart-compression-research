# Peak memory measurement design

작성일: 2026-09-12

상태: `validation_only`

이 문서는 최대 메모리 사용량을 정식 다목적 점수에 포함하기 전에 측정 방법을
사전 정의한다. 기존 72개 검증 실험과 1,008개 Pilot은 메모리를 측정하지 않은
protocol v2 결과이므로 수정하거나 새 정의로 소급 labeling하지 않는다.

## 1. 측정값 정의

Windows의 `GetProcessMemoryInfo`가 제공하는 `PeakWorkingSetSize`를 사용한다.
Microsoft는 이 값을 프로세스의 최대 working set 크기(바이트)로 정의한다.
working set은 특정 시점에 프로세스에 물리적으로 매핑된 메모리이다.

본 연구에서 기록할 원시 지표 이름은 다음과 같다.

```text
peak_process_working_set_bytes
```

Python `tracemalloc`은 Python allocator가 추적하는 메모리 블록을 대상으로 한다.
C extension은 별도의 domain으로 명시적으로 등록할 수 있으므로, 네이티브
라이브러리의 모든 할당이 자동으로 포함된다고 가정할 수 없다. gzip, bz2, LZMA,
zstd를 같은 기준으로 비교하기 위해 운영체제 수준의 working set을 선택한다.

근거 문서:

- Microsoft `PROCESS_MEMORY_COUNTERS`: https://learn.microsoft.com/ko-kr/windows/win32/api/psapi/ns-psapi-process_memory_counters
- Microsoft process memory usage: https://learn.microsoft.com/en-us/windows/win32/psapi/process-memory-usage-information
- Python `tracemalloc`: https://docs.python.org/3/library/tracemalloc.html

## 2. 격리 단위

`PeakWorkingSetSize`는 프로세스 수명 동안의 최고값이므로 같은 프로세스에서 여러
알고리즘을 차례로 측정하면 이전 최고값이 남는다. 따라서 다음 단위마다 새로운
Python subprocess를 시작한다.

```text
sample × algorithm × phase(compress/decompress) × repeat
```

각 worker는 동일한 `src.compressors` 모듈을 import하여 네 압축 라이브러리의
초기화 조건을 같게 한다. 입력 파일 읽기는 압축 또는 해제 호출 전에 끝낸다.
시간은 기존 in-memory benchmark가 별도로 측정하므로 subprocess 시작 및 파일
읽기 시간은 `compression_time_ms`나 `decompression_time_ms`에 포함하지 않는다.

## 3. 반복과 대표값

압축과 압축 해제를 각각 독립 subprocess에서 5회 측정한다.

```text
compression_peak_memory_bytes
    = median(5 compression PeakWorkingSetSize values)

decompression_peak_memory_bytes
    = median(5 decompression PeakWorkingSetSize values)

peak_memory_bytes
    = max(compression_peak_memory_bytes,
          decompression_peak_memory_bytes)
```

정식 실험에서는 집계값뿐 아니라 5회 원시값도 별도의 long-form CSV에 보존한다.

```text
sample_id
algorithm
phase
repeat_index
peak_process_working_set_bytes
verified
measurement_method
```

`compression_results.csv`에는 이후 protocol v3 전환 시 다음 집계 열을 추가한다.

```text
compression_peak_memory_bytes
decompression_peak_memory_bytes
peak_memory_bytes
```

KiB 표시는 GUI나 보고서 표시 단계에서 `bytes / 1024`로 계산하며 원시 CSV는
반올림하지 않은 bytes를 보존한다.

## 4. 검증

worker는 압축 결과 또는 복원 결과의 SHA-256을 부모 프로세스가 계산한 기대값과
비교한다. 모든 repeat가 검증된 경우에만 `verified=True`로 집계한다.

정식 실험 전 다음을 수행한다.

1. 사람이 예측 가능한 작은 데이터로 worker 오류와 digest 검증을 시험한다.
2. 네 알고리즘과 네 파일 크기에서 5회 원시값의 변동을 공개한다.
3. 아주 작은 파일에서 Python runtime baseline이 차이를 가리는지 확인한다.
4. 50~100개 검증 실험을 새 protocol로 다시 실행한다.
5. 검증을 통과한 뒤에만 메모리 가중치를 활성화하고 새 Pilot을 실행한다.

측정 실패, 0 이하 값, worker 실패, `verified=False`는 삭제하거나 대체하지 않고
실패 결과로 기록한다.

## 5. 점수에 반영할 후보 정의

검증 후 protocol v3에서 다음 상대 손실을 추가한다.

```text
M_best = min_a peak_memory_bytes(a)
R_memory(a) = ln(peak_memory_bytes(a) / M_best)
```

사전 등록할 mode별 후보 가중치는 다음과 같다.

| Mode | ratio | compression time | decompression time | memory |
|---|---:|---:|---:|---:|
| Archive | 0.65 | 0.10 | 0.10 | 0.15 |
| Balanced | 0.40 | 0.20 | 0.20 | 0.20 |
| Fast Access | 0.20 | 0.20 | 0.45 | 0.15 |

이 가중치는 새 실험 결과를 본 뒤 유리하게 바꾸지 않는다. 활성화 시점과 이유는
`research_protocol_v3.md`와 별도 Git commit으로 기록한다.

## 6. 해석 제한

- 이 값은 압축 라이브러리만의 순수 heap 할당량이 아니라 Python runtime, 입력,
  출력 및 네이티브 라이브러리를 포함한 전체 프로세스 peak working set이다.
- working set은 OS의 page residency와 시스템 상태의 영향을 받을 수 있다.
- Python runtime baseline이 고정적으로 포함되므로 작은 데이터에서는 알고리즘 간
  차이가 작게 보일 수 있다.
- 값은 hardware, OS, Python 및 package 버전에 종속적이다. 서로 다른 환경의 값을
  하나의 label dataset에 섞지 않는다.
- 현재 backend는 Windows 전용이다. 다른 OS backend를 추가하면 같은 단위 이름을
  쓰더라도 별도 실험으로 취급하고 교차 비교하지 않는다.

따라서 정식 metadata에는 기존 항목과 함께 architecture, total physical memory,
measurement method 및 memory repeat 설정을 기록한다.
