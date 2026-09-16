# 연구 진행 상태

최초 전체 확인일: 2026-09-15. Memory 검증 증거 보존 갱신: 2026-09-16.

공식 기준: [research_protocol_v2.md](research_protocol_v2.md)

실제 설정: [config/experiment_config.json](config/experiment_config.json)

이 문서는 저장소의 코드·테스트·실험 결과·연구 로그·Git 이력을 조사한 상태 기록이다. 결과 CSV의 행 수와 평가 수치를 Python으로 읽고, 원시 결과 및 모델 평가 summary에 기록된 산출물 SHA-256을 대조했다. 문서 작성 과정에서 압축 실험·학습·테스트를 재실행하지 않았다.

## 1. 연구 목표

「데이터의 통계적 특성을 이용한 무손실 압축 알고리즘 자동 선택 시스템 연구」

파일을 모든 압축 알고리즘으로 시험하기 전에 통계적 특징을 계산하고, 그 특징만으로 사용 목적에 적합한 압축 알고리즘을 예측한다. 항상 하나의 알고리즘을 사용하는 기준 방법보다 실제 종합 성능을 개선하는지 검증한다. 단순 압축률 비교가 목표는 아니다.

## 2. 현재 완료된 구현

| 기능 | 근거 파일 및 상태 |
|---|---|
| 압축·해제·시간 측정·무손실 검증 | `src/compressors.py` |
| 통계적 특징 추출 | `src/feature_extractor.py` |
| seed 기반 6종 합성 데이터 생성 | `src/data_generator.py` |
| 실험 실행, 원시 CSV와 재현성 metadata 저장 | `src/experiment_runner.py` |
| 3지표 종합 점수와 mode별 정답 생성 | `src/scoring.py`, `src/selection_labels.py` |
| 통계 요약, Pearson/Spearman 상관관계, 선택 비율, Pareto 분석 | `src/analysis.py` |
| 최빈 baseline, Decision Tree, Random Forest 학습·평가 | `src/train_model.py` |
| 저장 예측의 오류·confidence·regret 기여 분석 | `src/failure_analysis.py` |
| 최소 Smart Mode CLI | `smart_compress.py`: 특징 기반 예측 후 선택한 압축기 하나를 한 번 실행하고, 한 번 해제하여 검증 후 저장 |
| 독립 memory 측정 | `src/memory_benchmark.py`: 검증 전용 구현이며 공식 실험 파이프라인 편입은 미완료 |
| Memory 검증 기록 저장 | `src/memory_validation.py`: 반복 원시값·pair 집계·실패·환경 metadata 저장 구현 (`c54b8f5`). 아래 실제 검증 실행은 미완료 |

Smart Mode는 Decision Tree 또는 Random Forest를 명시적으로 지정한다. 모델·설정·소스·환경의 일치와 모델 해시를 검사하며, 기존 출력 경로를 덮어쓰지 않는다. 선택 전에 benchmark나 네 압축기 비교를 실행하지 않는다.

2026-09-15 최초 상태 조사에서는 테스트 소스 파일 12개와 `test_` 메서드 72개를 기록했다. 이후 `c54b8f5`에서 `tests/test_memory_validation.py`가 추가되었으므로 이전 개수를 현재 전체 개수로 취급하지 않는다. [Smart Mode 연구 로그](research_log/smart_mode.md)에 전체 72개 테스트 통과 및 두 모델 × 세 mode의 README 처리 성공 기록이 있다. 이는 과거 실행 기록이며 이번 증거 보존 작업에서는 테스트를 재실행하지 않았다. README 처리 성공은 일반화 성능 평가가 아니다.

## 3. 현재 실험 규모

| 구분 | 경로 | Sample | 압축 결과 행 | 정답 행 | verified=False |
|---|---|---:|---:|---:|---:|
| 초기 3지표 검증 | `data/results/` | 72 | 288 | 216 | 0 |
| 기존 3지표 Pilot | `data/results/pilot_1008/` | 1,008 | 4,032 | 3,024 | 0 |

- 두 실험 모두 `samples.csv`, `compression_results.csv`, `selection_labels.csv`, `experiment_metadata.json`을 보존한다.
- generator: `random`, `small_alphabet`, `repeated_pattern`, `long_runs`, `structured`, `mixed`.
- Pilot은 generator별 168개, 파일 크기별 252개이다.
- 파일 크기: 16,384 / 65,536 / 262,144 / 1,048,576 bytes.
- 초기 검증 base seed는 `20260911`, Pilot base seed는 `20260983`이다. sample별 seed는 base seed + sample index이다.
- 현재 저장된 정식 실험 결과는 합성 데이터이다. 실제 unseen 파일 평가 결과는 없다.
- **기존 72개와 1,008개 결과에는 memory 열·측정값이 없다. 이 결과는 계속 3지표 결과로 보존한다.**

## 4. 현재 사용 중인 특징

ML 입력은 `FEATURE_NAMES`의 다음 12개뿐이다.

```text
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

중복 block 크기는 16 bytes, entropy segment 크기는 4,096 bytes이다. segment entropy 표준편차는 population standard deviation이다. sample_id·seed·generator·압축 측정값·score는 모델 입력이 아니다.

## 5. 현재 압축 알고리즘과 측정 설정

| 알고리즘 | 설정 |
|---|---|
| gzip | level 9 |
| bz2 | level 9 |
| LZMA (`lzma`) | preset 6 |
| zstd | level 3 |

압축 시간과 해제 시간은 메모리의 `bytes`에 대해 `time.perf_counter_ns`로 각각 5회 측정하고 중앙값을 사용한다. 파일 입출력·특징 추출·모델 예측 시간은 이 측정값에 포함되지 않는다.

## 6. 현재 공식 score 정의

**공식 score는 압축률·압축 시간·압축 해제 시간의 3지표이다. Memory는 정식 score에 포함되지 않는다.** 프로토콜 v2, config의 `selection_modes`, `src/scoring.py`, 결과 CSV가 이 정의를 사용한다.

```text
C_a  = compressed_size / original_size
Tc_a = compression_time_ms
Td_a = decompression_time_ms

C_best  = min_a C_a
Tc_best = min_a Tc_a
Td_best = min_a Td_a

Score_m(a) = w_size       * ln(C_a / C_best)
           + w_compress   * ln(Tc_a / Tc_best)
           + w_decompress * ln(Td_a / Td_best)
```

최솟값은 같은 sample의 네 압축기 사이에서 구한다. mode별 최저 score 알고리즘이 정답이며, 완전 동점은 `gzip, bz2, lzma, zstd` 순서로 결정한다. 현재 epsilon은 사용하지 않으며 양수가 아닌 시간·비유한 값·복원 실패 등은 score 계산에서 거부한다.

`regret = predicted score - oracle best score`이며 작을수록 좋다.

## 7. 현재 mode별 weight

| Mode | 압축률 | 압축 시간 | 해제 시간 |
|---|---:|---:|---:|
| Archive | 0.70 | 0.15 | 0.15 |
| Balanced | 0.50 | 0.25 | 0.25 |
| Fast Access | 0.30 | 0.20 | 0.50 |

이 표는 현재 활성 설정이다. 아래 memory 후보 weight와 구분한다.

## 8. 현재 모델과 분할

- **Baseline:** mode별 training 정답의 최빈 알고리즘. 현재 세 mode 모두 zstd이다.
- **Decision Tree:** mode별 별도 모델. gini, splitter=best, max_depth=None, min_samples_split=2, min_samples_leaf=1, class_weight=None, ccp_alpha=0, random_state=42.
- **Random Forest:** mode별 별도 모델. n_estimators=100, gini, max_depth=None, max_features=sqrt, bootstrap=True, class_weight=None, random_state=42, n_jobs=1. 전체 매개변수는 config 및 평가 summary에 기록되어 있다.
- **공통 분할:** seed 그룹 기준 `GroupShuffleSplit`, test_size=0.20, random_state=42. 학습 806개 / 시험 202개이며 baseline의 저장 분할을 두 학습 모델도 사용한다.
- 루트 `models/`는 비어 있다. 저장 모델은 `data/results/pilot_1008/decision_tree/decision_tree_<mode>.pkl`과 `data/results/pilot_1008/random_forest/random_forest_<mode>.pkl`에 있다. 각 디렉터리에 평가 summary가 함께 있다.
- Smart Mode의 기본 모델 디렉터리도 위 Pilot 경로이다. 단일 최종 모델을 자동 채택한 상태는 아니다.

## 9. 현재 평가 결과 요약

근거: [model_summary.csv](data/results/pilot_1008/failure_analysis/model_summary.csv), 각 모델의 `metrics.csv`와 `strategy_comparison.csv`. 아래는 저장된 Python 계산 결과를 소수점 6자리로 표시한 것이다.

| 모델 | Mode | Accuracy | Macro F1 | 평균 regret |
|---|---|---:|---:|---:|
| Baseline | Archive | 0.995050 | 0.249380 | 0.000435 |
| Baseline | Balanced | 0.995050 | 0.249380 | 0.000326 |
| Baseline | Fast Access | 0.990099 | 0.248756 | 0.001932 |
| Decision Tree | Archive | 0.980198 | 0.247500 | 0.002999 |
| Decision Tree | Balanced | 0.995050 | 0.249380 | 0.000326 |
| Decision Tree | Fast Access | 0.970297 | 0.246231 | 0.009081 |
| Random Forest | Archive | 0.990099 | 0.248756 | 0.001788 |
| Random Forest | Balanced | 0.995050 | 0.249380 | 0.000326 |
| Random Forest | Fast Access | 0.985149 | 0.248130 | 0.004662 |

이번 Pilot에서 두 학습 모델의 baseline 대비 개선은 확인되지 않았다. Balanced에서는 세 방법이 같고, Archive·Fast Access에서는 baseline이 더 좋다.

Macro F1은 네 알고리즘을 고정하고 `zero_division=0`으로 계산한다. 실제·예측에 없는 클래스도 F1=0으로 포함한다. 높은 accuracy와 약 0.25의 Macro F1을 함께 해석해야 한다.

## 10. 현재 알려진 문제와 한계

- 정답이 zstd에 집중된다. Pilot의 zstd 정답 수는 Archive 1,000개, Balanced 1,003개, Fast Access 996개이다. 나머지는 gzip이며 bz2·LZMA 정답은 없다. 분포를 맞추기 위한 데이터 삭제나 점수 조정은 하지 않는다.
- 실패 분석은 model × sample × mode 기준 21개 오류 행, 고유 sample 7개를 기록했다. 두 학습 모델이 baseline의 오류를 바로잡은 사례는 없다.
- Decision Tree 오류 11건 모두 confidence=1이며 Random Forest 오류 6건 중 4건도 confidence=1이다. confidence는 보정된 정답 확률이 아니다.
- seed 그룹 분할은 서로 다른 seed에서 생성된 유사 데이터까지 탐지하지 않는다. 실제 파일에는 원본 단위 분할 정책이 필요하다.
- 기존 결과에는 시간 반복별 원시 분포가 없다. 중앙값만으로 시간 변동·통계적 유의성·정답 안정성을 판정할 수 없다.
- 기존 전략 비교의 시간에는 특징 추출·예측 비용이 없다. end-to-end 성능과 실제 unseen 파일 일반화 성능은 미검증이다.
- baseline의 작은 소수 압축률 파싱 오류는 `6898bc8`에서 수정되었다. 현재 미해결 오류로 취급하지 않으며 실패 기록은 `research_log/baseline_evaluation.md`에 남아 있다.
- 프로토콜 v2의 32절은 초기 구현 현황이며 실제 진행 상태보다 오래되었다. 연구 기준은 v2를 따르되 현재 완료 상태는 이 문서와 실제 저장소를 대조한다.

## 11. Memory 관련 구현 상태와 계획/미완료

근거: [측정 설계](research_log/peak_memory_measurement_design.md), `src/memory_benchmark.py`, `src/memory_validation.py`, `tests/test_memory_benchmark.py`, `tests/test_memory_validation.py`, config의 `memory`.

### 구현된 부분 — validation_only

- Windows `GetProcessMemoryInfo.PeakWorkingSetSize`를 사용하여 bytes 단위 전체 프로세스 peak working set을 측정한다.
- sample × algorithm × compress/decompress × repeat마다 새 subprocess를 시작한다.
- 압축·해제 각각 5회 값을 반환하고 각각의 중앙값을 계산한다. `peak_memory_bytes`는 두 중앙값의 최댓값이다.
- worker 출력의 SHA-256을 기대값과 대조하고 반복 검증 결과를 집계한다.
- backend의 양수 반환, gzip 반복 측정, 잘못된 입력 거부 테스트가 구현되어 있다.
- 이 값에는 Python runtime·입력·출력·네이티브 라이브러리가 포함된다. 압축 라이브러리만의 순수 할당량이 아니다.
- `c54b8f5`에서 별도 validation runner의 long-form 원시 CSV, pair 집계, worker 실패 기록, 설정·환경·소스 hash metadata 저장을 구현했다. 구현 완료와 실제 검증 실행 완료는 구분한다.

### 증거 보존 완료 — 2026-09-15 실행은 incomplete / validation_only

보존 경로: [memory_validation_20260915](data/results/memory_validation_20260915/). 성공한 공식 연구 결과나 4지표 실험이 아니다. 2026-09-16에 기존 파일을 읽기 전용 Python으로 집계했으며, 측정·복원·audit 스크립트를 재실행하지 않았다.

| 원본 파일 | 크기(bytes) | 저장 내용 |
|---|---:|---|
| [samples.csv](data/results/memory_validation_20260915/samples.csv) | 6,581 | 생성 정보·입력 hash 22행. 원본 sample bytes는 없음 |
| [memory_repeats.csv](data/results/memory_validation_20260915/memory_repeats.csv) | 276,583 | 원시 반복 기록 855행: `ok` 854행, `worker_failed` 1행 |
| [memory_summary.csv](data/results/memory_validation_20260915/memory_summary.csv) | 16,949 | 저장된 pair 집계 85행, 모두 `verified=True` |
| [memory_validation_metadata.json](data/results/memory_validation_20260915/memory_validation_metadata.json) | 8,133 | 실행 계획·설정·환경·Git·소스 hash 및 마지막 진행 checkpoint |

원본 4개 합계는 308,246 bytes이다. 보존용 `.gitattributes`는 원본 실행 산출물이 아니며 이 합계에 포함하지 않는다. 해당 파일은 이 폴더의 CSV·JSON에만 줄바꿈 변환을 비활성화하여 원본 바이트를 보존한다.

- 계획은 sample 24개 / pair 96개 / repeat 960개였으나 저장된 기록은 각각 22개 / 85개 / 855개이다. 계획된 repeat key 105개가 없으며 저장된 key의 중복·계획 외 key는 없다. `memory_000022`, `memory_000023`의 sample 기록도 없다.
- 마지막 기록은 `memory_000021`, `long_runs`, 1,048,576 bytes, seed `20260936`, `bz2`, `compress`, repeat 5의 실패이다. `return_code=4294967295`, `error="Worker exited with code 4294967295"`이며 메모리 값·`verified`·stdout·stderr는 비어 있다. 성공한 무손실 측정값으로 사용하지 않는다. 이 기록만으로 worker 종료나 전체 중단의 구체적인 원인을 확정할 수 없다.
- metadata는 `run_status="running"`, `repeat_count=850`, `failed_repeat_count=0`으로 남아 있다. 실제 원시 CSV와 다른 미완료 checkpoint이며 실패 없음 또는 현재 프로세스 실행 중이라는 근거가 아니다. runner는 pair 완료 후 metadata를 저장하므로 마지막 부분 pair의 원시 기록이 metadata보다 앞서 저장될 수 있다.
- 종료 필드 `finished_at_utc`, `repeat_status_counts`, `source_sha256_at_end`, `provenance_unchanged`, `artifact_sha256`가 없다. 종료 처리가 완료되었다고 판단할 수 없다. 원본 metadata를 사후 수정하거나 누락 행을 보충하지 않았다.
- summary의 `verified=True`는 저장된 pair에 한정된다. 전체 실행의 성공, runtime baseline 검증, 공식 memory score 편입을 의미하지 않는다.
- metadata는 시작 시각 `2026-09-15T11:02:20.343691+00:00`, 실행 commit `c54b8f5f9b7ae114206b43ce1e23fe4b69666203`, 당시 `worktree_dirty=false`를 기록한다. 현재 파일과 기록된 소스·설정 hash의 일치는 읽기 전용으로 확인했지만 실행 종료 시 소스 불변성을 소급 증명하지는 않는다.
- metadata의 `environment.python_executable`에는 로컬 계정명과 절대 경로가 있다. 원본 증거로 로컬 Git에 보존하며 이번 작업에서는 push하지 않는다. 외부 공개 전 해당 정보의 공개 여부를 검토해야 한다.

다음 SHA-256은 **2026-09-16 보존 점검 시 원본 바이트에서 계산한 값**이며, 누락된 실행 종료 hash를 대신한 당시 기록이 아니다.

| 원본 파일 | 보존 점검 SHA-256 |
|---|---|
| samples.csv | `5c3fb733f55b9134d2aeb12cdc3ef578c0ca0cf390eabdd9689f0f35cdd3d4c6` |
| memory_repeats.csv | `b1f2719175b06a4511e76ba9e9dad737775a974e3e2932abd91bdc72d41b3173` |
| memory_summary.csv | `7673b5cd0884192b5fb7d8c555f3f001eba1122d3d1c0bba2bd30b912c647f0a` |
| memory_validation_metadata.json | `1698a3b46b2cde14864a9073588e45880aedbc38640217a66361f5082d536c45` |

### 계획/미완료

- 네 압축기·네 크기 전체 행렬의 검증 완료, 반복 변동·작은 파일의 runtime baseline 영향 검증. 위 미완료 증거 보존과 구분한다.
- 공식 experiment runner 연동 및 공식 결과 schema 확장. 별도 validation runner의 원시값·집계·실패 저장은 구현되었으나 공식 파이프라인 편입은 미완료이다.
- 새 기준의 50~100개 검증 실험 후 공식 4지표 score 활성화 및 새 Pilot 실행.
- `research_protocol_v3.md` 작성 및 공식 전환 기록. 현재 해당 파일은 없다.

측정 설계 문서에는 다음 **후보 weight**가 있다. 현재 config의 활성 weight가 아니며, 검증·공식 전환을 마친 값도 아니다.

| Mode | 압축률 | 압축 시간 | 해제 시간 | Memory |
|---|---:|---:|---:|---:|
| Archive | 0.65 | 0.10 | 0.10 | 0.15 |
| Balanced | 0.40 | 0.20 | 0.20 | 0.20 |
| Fast Access | 0.20 | 0.20 | 0.45 | 0.15 |

후보 추가 항은 `w_memory * ln(peak_memory_bytes / 같은 sample의 최소 peak_memory_bytes)`이다.

**기존 1,008 sample Pilot에는 memory 측정값이 없으므로 4지표 결과로 바꾸지 않는다. 과거 CSV·라벨·모델은 보존하고, 향후 4지표 실험은 별도 버전과 경로로 기록한다.**

## 12. 아직 완료하지 않은 작업

- 위 memory 검증 및 공식 4지표 전환.
- 독립 `smart_decompress.py` CLI: 현재 빈 파일이다. `main.py`도 빈 파일이다.
- 사용자용 Compare/Demo Mode와 GUI.
- 실제 파일 데이터·원본 그룹 분할 설계·별도 unseen 평가.
- 특징 추출·예측 비용을 포함한 end-to-end 성능 평가.
- 약 5,000개·10,000개로의 실험 확대 및 최종 연구 정리.

## 13. 다음 단일 작업

**제안/미착수:** 기존 staged `research_log/verify_memory_validation.py`의 완료 실행 전용 범위와 `assert` 의존 검사를 정리하고, 별도 검증 후 독립 commit한다. 이 스크립트는 이번 증거 보존 commit 대상이 아니며 수정·실행하지 않았다. 현재 incomplete 실행을 성공한 audit 결과로 처리하지 않는다.

새 memory 측정 실행·실패 원인 수정·공식 4지표 전환은 이번 증거 보존 작업에 포함하지 않는다.

## 14. 마지막 관련 Git commit

Memory 증거 보존 작업에서 확인한 마지막 관련 구현·실행 코드 commit:

```text
c54b8f5f9b7ae114206b43ce1e23fe4b69666203
Implement persistent validation-only memory measurement matrix
```

관련 이력:

- `70294a6`: 특징 기반 Smart Mode 구현. 최초 문서 작성 당시 마지막 구현 commit.
- `811385b`: 1,008 sample Pilot 실패 분석 결과 기록.
- `81adc0d`: Random Forest 평가 결과 기록.
- `c8e18b5`: Decision Tree 평가 결과 기록.
- `6b6a7bb`: baseline 평가 결과 기록.
- `572760b`: 독립 peak memory 측정 정의.
- Pilot 원시 실험 metadata의 실행 코드 commit: `4d2d637bea96a4a1ddbbedb2c077fd0474ca8c19`.

최초 문서 작성 전 `main` 작업 트리는 깨끗했다. 샌드박스의 Pilot 하위 폴더 접근 제한으로 삭제처럼 표시된 항목은 실제 권한으로 재확인했으며 삭제가 아니었다. 2026-09-16 증거 보존 작업 시작 시에는 audit 스크립트가 staged이고 memory 결과 폴더가 untracked였다. 이후 세션은 당시 상태를 그대로 가정하지 말고 `git status`와 최근 commit을 다시 확인한다.
