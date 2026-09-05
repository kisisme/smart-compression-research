# Smart Compression Research Protocol v2

## 1. 연구 주제

**데이터의 통계적 특성을 이용한 무손실 압축 알고리즘 자동 선택 시스템 연구**

이 연구 주제는 특별한 문제가 발견되지 않는 한 변경하지 않는다.

본 연구는 단순히 여러 압축 알고리즘의 압축률을 비교하는 연구가 아니다.

최종 목표는 파일을 모든 알고리즘으로 직접 압축해 보기 전에 데이터의 통계적 특징을 계산하고, 그 특징만을 이용하여 사용 목적에 적합한 무손실 압축 알고리즘을 예측하는 시스템을 구현하는 것이다.

---

## 2. 핵심 연구 질문

데이터의 통계적 특성과 사용 목적을 이용하여, 새로운 파일을 실제로 여러 압축 알고리즘으로 모두 시험하지 않고도 가장 적합한 무손실 압축 알고리즘을 예측할 수 있는가?

또한 자동 선택 시스템이 하나의 압축 알고리즘만 항상 사용하는 기준 방법보다 실제 종합 성능을 개선할 수 있는가?

---

## 3. 비교 압축 알고리즘

비교 대상은 다음 네 알고리즘으로 고정한다.

- gzip
- bz2
- LZMA
- zstd

기본 압축 설정:

- gzip: level 9
- bz2: level 9
- LZMA: preset 6
- zstd: level 3

실험 도중 결과를 보고 유리한 방향으로 설정을 임의 변경하지 않는다.

압축 수준 자체를 연구 변수로 다루는 경우 본 연구의 기본 실험과 분리된 후속 실험으로 기록한다.

실제 설정값은 `config/experiment_config.json`을 기준으로 한다.

---

## 4. 실제 연구 데이터 원칙

연구 결과로 사용하는 모든 수치는 Python 프로그램이 실제 생성하거나 측정한 값이어야 한다.

AI가 임의로 생성한 수치를 연구 데이터로 사용하지 않는다.

다음 값은 반드시 실제 Python 실행으로 얻는다.

- 데이터 생성 결과
- 통계적 특징
- 압축 크기
- 압축률
- 압축 시간
- 압축 해제 시간
- 복원 검증
- 종합 점수
- 머신러닝 학습 결과
- 정확도
- F1 점수
- 혼동행렬
- 특성 중요도
- 그래프와 통계량

예상 결과를 실제 실험 결과처럼 기록하지 않는다.

실험이 예상과 다르게 나와도 삭제하거나 조작하지 않는다.

---

## 5. 무손실 검증

모든 압축 결과는 압축 해제 후 원본과 완전히 같은지 검사한다.

```python
verified = restored_data == original_data
```

`verified=False`인 결과는 정상적인 무손실 압축 결과로 사용하지 않는다.

실패 원인은 별도로 기록하고 분석한다.

---

## 6. 압축 실험 기본 측정값

각 `sample_id × algorithm` 조합에 대해 최소 다음을 기록한다.

```text
sample_id
algorithm
original_size
compressed_size
compression_ratio
compression_time_ms
decompression_time_ms
verified
```

압축률은 다음과 같이 정의한다.

```text
compression_ratio = compressed_size / original_size
```

값이 작을수록 저장 공간 측면에서 좋은 결과이다.

---

## 7. 시간 측정

압축 시간과 압축 해제 시간은 한 번만 측정하지 않는다.

기본 조건:

```text
repeats = 5
timer = time.perf_counter_ns
aggregate = median
```

각 조건을 5회 반복하고 중앙값을 대표값으로 사용한다.

기본 benchmark는 이미 메모리에 올라온 `bytes`에 대해 실시하여 파일 읽기와 쓰기 시간을 압축 알고리즘 자체의 실행 시간에 섞지 않는다.

최종 프로그램의 end-to-end 실행 시간이 필요하면 별도의 지표로 측정한다.

---

## 8. 최적 알고리즘의 정의

기존의 다음 정의는 사용하지 않는다.

> 압축률이 가장 좋은 알고리즘 = 최적 알고리즘

본 연구에서는 다음 세 성능 요소를 함께 고려한다.

- 압축률
- 압축 시간
- 압축 해제 시간

따라서 최적 알고리즘은 사용 목적에 따라 저장 공간과 처리 속도를 종합적으로 고려했을 때 가장 적합한 알고리즘으로 정의한다.

---

## 9. 사용 목적 모드

### Archive

장기 보관을 가정하며 압축률을 가장 중요하게 고려한다.

```text
compression_ratio       0.70
compression_time        0.15
decompression_time      0.15
```

### Balanced

저장 공간과 처리 속도의 균형을 고려한다.

```text
compression_ratio       0.50
compression_time        0.25
decompression_time      0.25
```

### Fast Access

빠른 복원과 사용을 중요하게 고려한다.

```text
compression_ratio       0.30
compression_time        0.20
decompression_time      0.50
```

실제 값은 `config/experiment_config.json`을 기준으로 한다.

대규모 실험 결과를 본 뒤 원하는 결과를 만들기 위해 가중치를 수정하지 않는다.

변경이 필요하면 별도 버전과 Git commit으로 이유를 기록한다.

---

## 10. 다목적 점수

알고리즘마다 단위가 다른 압축률과 시간을 원시 값 그대로 더하지 않는다.

한 sample에서 알고리즘 `a`의 측정값을 다음과 같이 정의한다.

```text
C_a  = compression_ratio
Tc_a = compression_time_ms
Td_a = decompression_time_ms
```

해당 sample에서 각 지표의 최솟값:

```text
C_best  = min(C_a)
Tc_best = min(Tc_a)
Td_best = min(Td_a)
```

상대 손실:

```text
R_size(a)       = ln(C_a / C_best)
R_compress(a)   = ln(Tc_a / Tc_best)
R_decompress(a) = ln(Td_a / Td_best)
```

mode `m`의 종합 점수:

```text
Score_m(a)
= w_size * R_size(a)
+ w_compress * R_compress(a)
+ w_decompress * R_decompress(a)
```

점수가 가장 작은 알고리즘을 해당 mode의 정답으로 사용한다.

수치적으로 0에 가까운 시간 때문에 문제가 생기는 경우 epsilon을 사용할 수 있으나 그 값과 이유를 반드시 설정 및 연구 기록에 남긴다.

---

## 11. 특정 알고리즘 독점 문제

특정 알고리즘이 대부분의 sample에서 선택된다면 머신러닝 자동 선택의 의미가 약해질 수 있다.

그러나 이를 막기 위해 결과를 조작하면 안 된다.

다음 사항을 먼저 점검한다.

- 데이터 생성 유형이 편향되어 있는가
- 파일 크기 범위가 너무 좁은가
- 통계적 특징 범위가 좁은가
- 특정 generator의 sample 수가 과도한가
- 시간 측정 코드에 오류가 있는가
- 점수 계산 코드에 오류가 있는가
- 압축 설정이 의도한 값인가

설계가 정상인데도 하나의 알고리즘이 실제로 지배한다면 그것 자체를 연구 결과로 분석한다.

클래스 비율을 맞추기 위해 데이터를 삭제하거나 점수를 임의 조정하지 않는다.

---

## 12. Pareto 분석

다목적 성능의 trade-off를 분석하기 위해 Pareto 분석을 보조적으로 사용할 수 있다.

알고리즘 A가 B보다 압축률, 압축 시간, 압축 해제 시간에서 모두 같거나 우수하고 적어도 하나에서 더 좋다면 A가 B를 지배한다고 정의한다.

Pareto-optimal 알고리즘의 분포는 결과 해석에 사용한다.

Pareto 분석은 머신러닝 정답을 대신하는 것이 아니라 보조 분석이다.

---

## 13. 초기 통계적 특징

초기 ML 입력 특징은 다음을 우선 사용한다.

### file_size

```text
len(data)
```

### entropy

Shannon entropy.

```text
H = - Σ p_i log2(p_i)
```

등장하지 않는 byte는 합에서 제외한다.

### unique_byte_count

0~255 중 한 번 이상 등장한 byte 종류 수.

### most_common_byte_ratio

```text
최빈 byte 등장 횟수 / 전체 byte 수
```

### zero_byte_ratio

```text
0x00 등장 횟수 / 전체 byte 수
```

### adjacent_repeat_ratio

```text
count(data[i] == data[i-1]) / (n - 1)
```

### average_run_length

동일 byte의 최대 연속 구간들을 run으로 정의하고 다음을 사용한다.

```text
전체 byte 수 / run 개수
```

### max_run_length

가장 긴 run의 길이.

### duplicate_block_ratio

기본 block 크기:

```text
16 bytes
```

비중첩 block들 중 앞에서 이미 동일 block이 등장한 block의 비율.

실제 block size는 config를 기준으로 한다.

### bigram_diversity

```text
고유 인접 2-byte 조합 수 / min(n - 1, 65536)
```

### segment_entropy_mean
### segment_entropy_std

기본 segment 크기:

```text
4096 bytes
```

비중첩 구간별 entropy를 계산하여 평균과 population standard deviation을 사용한다.

실제 segment size는 config를 기준으로 한다.

---

## 14. 특징 검증

특징 추출 코드는 사람이 예상할 수 있는 데이터로 먼저 검증한다.

예:

```text
AAAAAAAA...
ABCABCABC...
모두 0인 데이터
순차 byte 데이터
난수 데이터
작은 byte 집합 데이터
```

특징 테스트가 정상 동작하기 전에는 대규모 실험으로 넘어가지 않는다.

---

## 15. 합성 데이터

Python이 직접 합성 데이터를 생성한다.

초기 generator:

```text
random
small_alphabet
repeated_pattern
long_runs
structured
mixed
```

모든 난수 기반 generator에는 seed를 사용한다.

같은 조건과 seed에서 동일한 데이터를 재생성할 수 있어야 한다.

기본 파일 크기:

```text
16 KiB  = 16384 bytes
64 KiB  = 65536 bytes
256 KiB = 262144 bytes
1 MiB   = 1048576 bytes
```

실제 크기 후보는 config를 기준으로 한다.

생성 매개변수는 재현 가능한 형태로 기록한다.

## 16. 실제 파일 데이터

합성 데이터만으로 최종 결론을 내리지 않는다.

추후 실제 파일도 별도의 검증 데이터로 포함한다.

후보:

```text
txt
csv
json
Python source
log
binary
```

저작권, 개인정보, 비밀정보가 포함된 데이터는 사용하지 않는다.

동일 원본에서 만들어진 매우 유사한 파생 데이터가 학습용과 시험용에 동시에 들어가지 않도록 한다.

---

## 17. 실험 규모

처음부터 수천~수만 sample을 실행하지 않는다.

진행 순서:

```text
50~100개 구현 검증
→ 약 1,000개 Pilot
→ 약 5,000개
→ 약 10,000개
→ 필요 시 확대
```

초기 검증과 Pilot의 주요 목적은 프로그램 오류와 설계 문제를 발견하는 것이다.

검사 항목:

```text
verified=False
NaN
중복 sample_id
original size 0
compressed size 0
비정상 실행 시간
특징 추출 실패
CSV 열 누락
score 계산 오류
```

---

## 18. 결과 저장

원본 sample 특징과 압축 결과를 분리한다.

### data/results/samples.csv

```text
sample_id
generator
seed
size
generation_parameters
file_size
entropy
unique_byte_count
most_common_byte_ratio
zero_byte_ratio
adjacent_repeat_ratio
average_run_length
max_run_length
duplicate_block_ratio
bigram_diversity
segment_entropy_mean
segment_entropy_std
```

### data/results/compression_results.csv

```text
sample_id
algorithm
original_size
compressed_size
compression_ratio
compression_time_ms
decompression_time_ms
verified
```

### data/results/selection_labels.csv

```text
sample_id
mode
best_algorithm
best_score
score_gzip
score_bz2
score_lzma
score_zstd
```

원시 측정값과 계산된 정답을 가능한 한 분리하여 보존한다.

---

## 19. 재현성 기록

가능한 모든 실험에서 다음을 기록한다.

```text
random seed
sample_id
generator
generation parameters
file size
compression settings
timing repeats
Python version
package versions
OS
실험 시각
Git commit hash
```

필요하면 다음 파일을 사용한다.

```text
config/experiment_config.json
data/results/experiment_metadata.json
```

---

## 20. 통계 분석

대규모 실험 이후 최소 다음 관계를 분석한다.

```text
entropy ↔ compression ratio
반복 관련 특징 ↔ compression ratio
duplicate block ratio ↔ compression ratio
file size ↔ compression time
file size ↔ decompression time
```

기본 통계:

```text
평균
표준편차
Pearson 상관계수
Spearman 상관계수
```

추가 분석:

```text
mode별 compressor win rate
generator별 win rate
file size별 win rate
label distribution
Pareto-optimal 빈도
```

---

## 21. 머신러닝 정답

압축률이 가장 작은 알고리즘만을 정답으로 사용하는 기존 규칙은 폐기한다.

각 sample에서 실제 네 알고리즘의 측정 결과를 이용해 Archive, Balanced, Fast Access 각각의 종합 점수를 계산한다.

각 mode에서 점수가 가장 낮은 알고리즘을 해당 mode의 정답으로 사용한다.

한 sample에서도 mode에 따라 정답이 달라질 수 있다.

---

## 22. 머신러닝 모델

먼저 단순 기준 모델을 만든다.

```text
training set에서 가장 자주 선택되는 알고리즘을 항상 선택
```

그다음 우선 다음을 사용한다.

```text
Decision Tree
Random Forest
```

기본적으로 mode별 모델을 별도로 학습한다.

필요할 경우 이후 mode를 입력 feature로 포함하는 단일 모델을 추가 실험할 수 있다.

---

## 23. Train/Test 분할

기본 후보:

```text
Train 80%
Test 20%
```

random_state를 고정하고 기록한다.

같은 seed 또는 같은 실제 원본에서 파생된 매우 유사한 sample이 train/test 양쪽에 섞이지 않도록 group 단위 분할을 우선 고려한다.

---

## 24. 머신러닝 평가

각 mode별 최소 평가 지표:

```text
accuracy
macro F1
confusion matrix
feature importance
misclassified samples
```

특정 class가 적을 수 있으므로 accuracy만으로 평가하지 않는다.

항상 baseline과 비교한다.

추가로 자동 선택이 실제 oracle보다 얼마나 나쁜 선택을 했는지 다음과 같은 regret 관점으로 분석한다.

```text
predicted score - oracle best score
```

---

## 25. 최종 성능 비교

새로운 시험 데이터에서 다음을 비교한다.

```text
항상 gzip
항상 bz2
항상 LZMA
항상 zstd
자동 선택 시스템
oracle
```

oracle은 실제 네 알고리즘의 결과를 모두 알고 있다고 가정했을 때 각 mode에서 가장 좋은 선택이다.

자동 선택 시스템은 압축 전에 계산한 데이터 특징만으로 알고리즘을 선택해야 한다.

비교 지표:

```text
평균 compression ratio
평균 compression time
평균 decompression time
평균 total score
oracle 대비 regret
prediction accuracy
macro F1
```

---

## 26. 최종 프로그램

최종적으로 다음 파일을 구현한다.

```text
smart_compress.py
smart_decompress.py
models/compressor_selector...
```

### Smart Mode

```text
파일 입력
→ 특징 추출
→ 사용 목적 선택
→ ML 모델 예측
→ 알고리즘 1개 선택
→ 해당 알고리즘으로 압축
→ 결과 저장
```

Smart Mode에서는 선택을 위해 네 압축 알고리즘을 전부 미리 실행하면 안 된다.

### Compare / Demo Mode

발표와 연구 검증용이다.

```text
파일 입력
→ 네 알고리즘 실제 실행
→ 압축률/시간/해제시간 표시
→ mode별 실제 best 표시
→ ML prediction과 비교
```

---

## 27. GUI 및 시각화

핵심 연구 엔진과 검증을 먼저 완성한 뒤 GUI를 구현한다.

GUI 1차 후보는 Python에서 재현하기 쉬운 Tkinter이다.

최종 화면에는 가능한 범위에서 다음을 포함한다.

```text
파일 선택
파일 이름/크기/형식
Archive / Balanced / Fast Access 선택
주요 통계 특징 표시
추천 알고리즘 표시
예측 confidence 표시
진행 단계 표시
압축 진행 상태
```

Compare Mode에서는 gzip, bz2, LZMA, zstd 각각의 상태를 별도로 표시한다.

예:

```text
대기
실행 중
완료
```

비교 결과에는 다음 시각화를 고려한다.

```text
압축률 비교
압축 시간 비교
압축 해제 시간 비교
종합 점수 비교
```

표시되는 선택 이유는 실제 feature 또는 모델 출력에 근거해야 하며 AI가 임의의 설명을 만들어 모델 판단처럼 보여주면 안 된다.

## 28. 후속 연구 발전 방향

본 연구는 다음 방향으로 발전할 수 있다.

```text
Brotli, LZ4, Snappy 등 압축 알고리즘 추가
압축 알고리즘과 compression level 동시 선택
peak memory 사용량 추가
CPU 사용량 추가
에너지 소비량 추가
사용자 직접 가중치 설정
파일 block별 다른 알고리즘을 적용하는 hybrid compression
사용자 환경 기반 개인화
hardware별 모델
confidence가 낮을 때 상위 2개 압축기만 실제 비교하는 hybrid fallback
```

---

## 29. Git 원칙

GitHub는 단순 백업이 아니라 연구 개발 과정과 재현성을 기록하는 도구로 사용한다.

기본 순서:

```text
파일 또는 하나의 논리적 기능 구현
→ 실제 실행
→ 결과 확인
→ 오류 수정
→ 테스트
→ git diff
→ git status
→ local commit
→ push
→ 다음 단계
```

관련 없는 여러 작업을 하나의 commit에 섞지 않는다.

대용량 원본 데이터, 가상환경, 임시 파일, 비밀정보는 GitHub에 올리지 않는다.

기존 사용자 변경을 임의로 삭제하거나 덮어쓰지 않는다.

`git reset --hard`, force push 등 파괴적인 명령은 사용자 명시적 승인 없이 사용하지 않는다.

---

## 30. AI / Codex 작업 원칙

Codex는 실제 구현과 실행을 보조할 수 있다.

가능한 작업:

```text
코드 작성
실행
테스트
실제 측정
오류 수정
CSV 생성
분석
그래프 생성
ML 학습
Git local commit
```

그러나 다음은 금지한다.

```text
실험하지 않은 수치를 만들어 연구 결과로 기록
결과를 좋게 보이게 하기 위한 데이터 조작
특정 알고리즘을 이기게 하기 위한 사후 점수 조정
실패 결과 은폐
사용자 기존 파일을 확인 없이 삭제
```

사용자의 로그인이 필요한 작업, 외부 공개, 학교 규정 관련 결정, GitHub push 등은 필요한 경우 사용자에게 요청한다.

---

## 31. 구현 진행 방식

한꺼번에 전체 시스템을 구현하지 않는다.

기본 흐름:

```text
파일 하나 또는 하나의 기능 구현
→ 실제 실행
→ 결과 확인
→ 오류 수정
→ 테스트
→ Git commit
→ 다음 단계
```

현재 계획된 기본 순서:

```text
compressors.py
→ compressor tests
→ feature_extractor.py
→ feature tests
→ data_generator.py
→ generator tests
→ experiment_runner.py
→ 50~100 sample 검증
→ multi-objective scoring
→ selection_labels
→ 약 1,000 sample Pilot
→ 통계 분석
→ baseline
→ Decision Tree
→ Random Forest
→ 실패 사례 분석
→ Smart Mode
→ Compare Mode
→ GUI
→ unseen test evaluation
→ 최종 정리
```

---

## 32. 현재 구현 상태

현재까지 완료된 핵심 사항:

```text
Git/GitHub 저장소 구성
.gitignore
프로젝트 기본 구조
README 최신화
Python 3.14.4 가상환경 복구
직접 의존성 버전 고정
config/experiment_config.json 작성 및 검증
```

현재 `src/compressors.py`는 첫 구현과 smoke test가 완료된 상태이나 아직 commit 전이다.

smoke test 값은 구현 검증용이며 정식 연구 데이터로 사용하지 않는다.

다음 단계는 본 프로토콜을 먼저 Git에 기록한 뒤 `compressors.py`를 재검증하고 별도 commit하는 것이다.

---

## 33. 프로토콜 우선순위

이 파일은 현재 연구의 최신 구현 기준이다.

기존 문서 또는 코드 주석에서 다음과 같이 충돌하는 규칙이 있으면 이 파일을 우선한다.

특히 다음 구버전 규칙은 폐기된 것으로 본다.

> 가장 작은 압축 결과를 낸 알고리즘을 무조건 최적 알고리즘으로 사용한다.

현재의 최적 알고리즘은 압축률, 압축 시간, 압축 해제 시간을 사용 목적별로 함께 고려해 결정한다.

실제 학교 또는 지도교사의 새로운 지시가 있으면 사용자가 확인한 뒤 이 프로토콜을 새 버전으로 갱신한다.
