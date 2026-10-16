# 연구 진행 상태

최초 전체 확인일: 2026-09-15. Memory 검증 증거 보존·audit 도구 갱신: 2026-09-16. 종료 처리 보강 검토·fixture 검증 및 새 전체 memory 행렬 실행·audit: 2026-09-22. Runtime baseline 구현·fixture 검증·전체 실측·audit·진단 분석: 2026-09-30. Git 증거 보존·memory 채택 검토·후속 검증 사전 설계: 2026-10-07. 후속 검증 timing worker·runner 구현 및 전용 검증: 2026-10-13. 후속 검증 독립 audit 구현·전용 fixture 검증: 2026-10-14. 후속 검증 분석기 초안 검토·전용 fixture 검증 완료: 2026-10-16.

공식 기준: [research_protocol_v2.md](research_protocol_v2.md)

실제 설정: [config/experiment_config.json](config/experiment_config.json)

이 문서는 저장소의 코드·테스트·실험 결과·연구 로그·Git 이력을 조사한 상태 기록이다. 결과 CSV의 행 수와 평가 수치를 Python으로 읽고, 원시 결과 및 모델 평가 summary에 기록된 산출물 SHA-256을 대조했다. 최초 문서 작성과 증거 보존 단계에서는 압축 실험·학습·테스트를 재실행하지 않았다. 이후 audit 도구 정리에서는 아래에 명시한 인위적 fixture 테스트만 실행했다.

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
| Memory 검증 기록 저장 | `src/memory_validation.py`: 반복 원시값·pair 집계·실패·환경 metadata 저장 및 종료 처리 보강 (`3e9b267`). 2026-09-15 실행은 미완료 보존, 2026-09-22 새 전체 행렬은 완료·audit 통과 |
| 완료 실행의 저장 기록 감사 | `research_log/verify_memory_validation.py`: 완료된 schema-v1 검증 기록의 일관성 확인. 미완료 실행 거부, 공식 검증 완료 판정과 구분 |
| Runtime baseline 진단 worker | `src/memory_runtime_worker.py`: 세 arm의 별도 CLI 및 fixture·Windows subprocess 검증 완료 |
| Runtime baseline 별도 runner | `src/memory_runtime_validation.py`: 구현·fixture 검증 및 2026-09-30 고정 전체 실측 완료 |
| Runtime baseline 저장 기록 감사 | `research_log/verify_memory_runtime_validation.py`: 구현·fixture 검증 및 2026-09-30 실제 저장 기록 audit 통과 |
| Runtime baseline 진단 분석 | `research_log/analyze_memory_runtime_validation.py`: 구현·fixture 검증 및 2026-09-30 실제 저장 기록 분석 완료. 과학적 memory 검증 완료·공식 score 편입과 구분 |
| Memory 안정성 후속 검증 timing worker | `src/memory_stability_timing_worker.py`: 원시 ns·출력 bytes 검증·응답·오류 처리 구현 및 전용 fixture·임시 Windows subprocess 검증 완료. 전체 실측은 미완료 |
| Memory 안정성 후속 검증 runner | `src/memory_stability_validation.py`: 고정 계획·별도 부모 실행·worker 응답 검증·원시 CSV·종료 metadata 구현 및 전용 fixture 검증 완료. 실제 attempt 분석·전체 실측은 미완료 |
| Memory 안정성 후속 검증 저장 기록 감사 | `research_log/verify_memory_stability_validation.py`: 독립 audit 구현·전용 fixture 검증 완료. 실제 후속 검증 attempt 대상 audit·분석·전체 실측은 미완료 |
| Memory 안정성 후속 검증 분석기 | `research_log/analyze_memory_stability_validation.py`: 기존 초안 검토·전용 fixture 검증 완료. 독립 audit와 결합한 후보 score·regret·사전 판정·진단 및 새 출력 저장 구현. 실제 attempt 분석·전체 실측은 미완료 |

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
- metadata는 시작 시각 `2026-09-15T11:02:20.343691+00:00`, 실행 commit `c54b8f5f9b7ae114206b43ce1e23fe4b69666203`, 당시 `worktree_dirty=false`를 기록한다. 2026-09-16 보존 점검 당시 파일과 기록된 소스·설정 hash의 일치는 읽기 전용으로 확인했지만 실행 종료 시 소스 불변성을 소급 증명하지는 않는다. 이후 종료 처리 보강으로 현재 runner 소스는 당시 기록과 다르다.
- metadata의 `environment.python_executable`에는 로컬 계정명과 절대 경로가 있다. 원본 증거로 로컬 Git에 보존하며 이번 작업에서는 push하지 않는다. 외부 공개 전 해당 정보의 공개 여부를 검토해야 한다.

다음 SHA-256은 **2026-09-16 보존 점검 시 원본 바이트에서 계산한 값**이며, 누락된 실행 종료 hash를 대신한 당시 기록이 아니다.

| 원본 파일 | 보존 점검 SHA-256 |
|---|---|
| samples.csv | `5c3fb733f55b9134d2aeb12cdc3ef578c0ca0cf390eabdd9689f0f35cdd3d4c6` |
| memory_repeats.csv | `b1f2719175b06a4511e76ba9e9dad737775a974e3e2932abd91bdc72d41b3173` |
| memory_summary.csv | `7673b5cd0884192b5fb7d8c555f3f001eba1122d3d1c0bba2bd30b912c647f0a` |
| memory_validation_metadata.json | `1698a3b46b2cde14864a9073588e45880aedbc38640217a66361f5082d536c45` |

### 계획/미완료

- 네 압축기·네 크기 전체 행렬 실행과 실행 내 반복 변동의 집계는 아래 2026-09-22 결과로 완료했다. 작은 파일의 runtime baseline 영향과 실행 간 안정성 검증은 미완료이다. 위 2026-09-15 미완료 증거는 별도로 보존한다.
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

### Audit 도구 정리 완료 / 인위적 fixture 검증 — 2026-09-16

근거: [audit 스크립트](research_log/verify_memory_validation.py), [전용 테스트](tests/test_verify_memory_validation.py).

- 기존 staged 스크립트의 `assert`를 명시적 `AuditError` 검사로 교체했다. `-O`·`-OO`에서도 실패 검사를 유지한다.
- 지원 범위는 `run_status=completed`, `validation_only`, `score_inclusion=false`인 schema-v1 전체 검증 행렬이다. 네 압축기·두 phase·각 5회 및 기존 generator·설정 크기·seed 계획을 확인하고, 누락된 hash manifest나 불완전한 행렬을 거부한다. `running`, `interrupted`, `aborted`, `completed_with_failures` 등은 성공 보고서를 만들지 않는다.
- 입력을 메모리에서 재생성하여 hash를 확인하고 저장 원시값으로 집계 통계를 재계산한다. 압축·해제·memory 측정은 실행하지 않는다. worker의 `verified`는 저장된 증거 확인이며 독립 복원 검증이 아니다. 압축 digest는 형식·반복 간 일관성을 확인할 뿐 재압축해 검증하지 않는다.
- 실행 당시 소스·설정 바이트와 현재 checkout이 일치해야 한다. 과거 결과의 소스 hash 불일치는 기록된 소스·설정을 갖춘 checkout에서 확인해야 하며 검사 생략으로 우회하지 않는다.
- 기본 출력은 stdout JSON이다. `--output`은 감사 통과 후 새 JSON만 생성하고 기존 경로는 덮어쓰지 않는다. 오류 시 CLI는 비정상 종료하며 성공 JSON을 출력하지 않는다. 아래 `-B`는 import에 따른 bytecode 파일 쓰기를 방지한다.

저장소 루트에서 사용하는 명령 형식(성공적으로 완료된 실행 경로에만 적용):

```text
python -B -m research_log.verify_memory_validation --experiment-dir <completed-run-directory>
```

검증 명령과 실제 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_validation.py -v
11 tests: OK
```

임시 폴더의 인위적 memory 값으로 성공 집계, 실패·미완료 거부, hash 불일치, 축소·중복 행렬, 비유한 집계값, worker 응답 형식, 일반/`-O`/`-OO` 오류 거부, 출력 생성·덮어쓰기 거부 및 입력 바이트 보존을 검증했다. fixture 값은 연구 결과가 아니다. 기존 실제 결과 대상 audit·메모리 재측정·복원 재검증은 실행하지 않았으며 전체 테스트 suite를 통과했다고 주장하지 않는다. 기존 원본 4개는 보존 commit과의 바이트·SHA-256 대조로 변경 없음을 확인했다.

이 도구의 테스트 통과는 실제 memory validation 성공이나 공식 4지표 전환 완료를 의미하지 않는다.

### 종료 처리 보강 검토 완료 / 인위적 fixture 검증 — 2026-09-22

근거: [validation runner](src/memory_validation.py), [종료 처리 테스트](tests/test_memory_validation.py), [audit 테스트](tests/test_verify_memory_validation.py).

작업 시작 시 위 세 파일에 있던 미커밋 변경을 검토하고 실행 검증했다. 추가 코드 수정이 필요한 문제는 발견하지 않았으며 기존 변경을 보존했다.

- metadata를 같은 디렉터리의 임시 파일에 완전히 쓰고 `flush`·`fsync` 후 `os.replace`한다. 직렬화·동기화·교체 실패 시 이전 metadata 바이트를 보존한다.
- 종료 시각·상태별 반복 수를 먼저 저장 시도한 뒤 소스 및 각 CSV hash를 별도로 계산한다. 정상 반복 종료 후에는 `finalizing`을 거쳐 최종 저장까지 성공해야 `completed`가 된다. 종료 처리 오류는 `finalization_errors`에 단계별로 기록하고, 정상 반복 종료 뒤 종료 처리가 실패하면 `finalization_failed`로 처리한다.
- 실행 본문에서 예외가 발생한 경우 종료 처리의 추가 오류가 원래 예외를 대체하지 않도록 예외 note에 남긴다. `RuntimeError`, `KeyboardInterrupt`, `SystemExit` 원본 예외와 hash·지속적인 저장 실패 조합을 fixture로 검증했다.
- audit는 `finalizing`, `finalization_failed`를 성공 실행으로 인정하지 않는다. 기존 schema-v1 audit의 완료 상태 검사로 이를 거부하며 해당 회귀 검증을 추가했다.
- 프로세스 강제 종료나 지속적인 저장장치 오류에서는 종료 기록을 보장할 수 없다. 마지막 저장 실패 시 디스크에는 `running` 또는 `finalizing` 등 이전 checkpoint가 남을 수 있다. 이번 보강은 과거 worker 종료의 구체적인 원인을 규명하거나 과거 실행을 복구한 것이 아니다.

실제 실행한 검증 명령과 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_validation.py -v
17 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_validation.py -v
11 tests: OK
```

샌드박스에서는 가상환경이 참조하는 사용자 Python에 접근하지 못해 사용자 권한으로 실행했다. 위 두 모듈의 총 28개 테스트만 통과했다고 기록하며 전체 suite는 실행하지 않았다. Memory worker는 mock으로 대체했으며, runner 테스트는 작은 인위적 입력의 준비용 압축·복원과 임시 파일 저장을 실행했다. fixture memory 값은 연구 측정값이 아니다. Audit 테스트에는 일반/`-O`/`-OO` CLI의 오류 거부 검증이 포함된다.

보존된 원본 네 파일은 Python으로 읽어 `708c9cb`의 바이트 및 SHA-256과 대조했고 모두 일치했다. 실제 memory 재측정·기존 결과 대상 audit·과거 입력의 복원 재검증·공식 4지표 전환은 수행하지 않았다. 기존 3지표 결과·설정·라벨·모델은 변경하지 않았다.

### 새 전체 memory 행렬 실행 완료 / 저장 기록 audit 통과 — 2026-09-22

근거: [새 결과 폴더](data/results/memory_validation_20260922/), [실행 metadata](data/results/memory_validation_20260922/memory_validation_metadata.json), [audit.json](data/results/memory_validation_20260922/audit.json).

- 실행 commit: `3e9b2673a116b045a5e225203e0d175429192c09`, 시작 시 `worktree_dirty=false`. 기존 설정과 base seed `20260915`를 유지했다. 이전 미완료 실행을 이어 쓰지 않고 새 경로에서 전체 행렬을 실행했다.
- 실행 시각(UTC): `2026-09-22T10:04:01.778566+00:00` ~ `2026-09-22T10:08:55.634330+00:00`. 종료 코드 0, `run_status=completed`, `finalization_status=completed`, `finalization_errors=[]`, `provenance_unchanged=true`이다.
- `measurement_status=validation_only`, `score_inclusion=false`이다. 공식 score는 계속 프로토콜 v2의 3지표이며 정식 4지표 실험이나 새 Pilot이 아니다.

| 저장 파일 | 실제 저장 내용 |
|---|---|
| [samples.csv](data/results/memory_validation_20260922/samples.csv) | 6종 generator × 4개 크기, sample 24개 |
| [memory_repeats.csv](data/results/memory_validation_20260922/memory_repeats.csv) | 24 sample × 4개 알고리즘 × 압축·해제 × 5회, 반복 960개 모두 `ok`·`verified=True`·`reference_roundtrip_verified=True` |
| [memory_summary.csv](data/results/memory_validation_20260922/memory_summary.csv) | sample × algorithm 집계 96개, 모두 `verified=True` |
| [memory_validation_metadata.json](data/results/memory_validation_20260922/memory_validation_metadata.json) | sample·pair·repeat 실패 수 모두 0, 종료 기록·환경·설정·소스 및 원시 CSV hash |
| [audit.json](data/results/memory_validation_20260922/audit.json) | `audit_passed=true`, 입력 재생성 hash·전체 행렬의 고유 key·worker JSON·집계 통계·metadata 수량 확인 |

실행 및 검증 명령:

```text
.venv\Scripts\python.exe -B -m src.memory_validation --output-dir data/results/memory_validation_20260922 --base-seed 20260915
.venv\Scripts\python.exe -B -m research_log.verify_memory_validation --experiment-dir data/results/memory_validation_20260922 --output data/results/memory_validation_20260922/audit.json
```

사용자 Python 접근이 가능한 권한으로 실행했으며 두 명령 모두 종료 코드 0이다. Audit는 저장값을 독립 재계산하고 원본 입력을 재생성했지만 memory 측정·압축·복원을 재실행하지 않았다. 측정 당시 부모 프로세스의 원본/복원 바이트 비교와 worker의 기대 SHA-256 대조를 수행했고, audit는 그 저장 증거의 일관성을 확인했다.

Python으로 저장된 audit 결과를 읽고 백분율로 계산한 실행 내 phase 그룹 192개의 CV 중앙값은 **0.396770%**, 최대는 **1.157033%**이다. 최대 그룹은 `memory_000017` / `mixed` / 262,144 bytes / `zstd` / `decompress`이다. 알고리즘·크기별 최대 압축/해제 CV는 `audit.json`의 `variation_by_algorithm_size`에 보존했다. 사전 합격 임계값을 정한 실험이 아니므로 이 값만으로 과학적 측정 검증 완료나 실행 간 안정성을 판정하지 않는다.

기존 2026-09-15 미완료 실행 원본 네 파일은 Python으로 `708c9cb`의 바이트·SHA-256과 대조해 변경 없음을 확인했다. 새 폴더의 `.gitattributes`는 CSV·JSON 줄바꿈 변환만 비활성화하여 측정·audit 바이트를 보존한다. 소스 코드·설정·기존 Pilot·모델은 변경하지 않았다. 이번 작업에서는 단위 테스트를 재실행하지 않았으며 실제 전체 행렬 실행과 audit로 검증했다. 이전 작업의 fixture 테스트 28개 통과 기록과 구분한다.

**미완료:** 아주 작은 파일의 runtime baseline 영향, 실행 간 반복 안정성, 공식 runner 연동·4지표 전환 및 새 기준의 후속 실험. 이번 실행 성공으로 이전 worker 종료 원인이 규명된 것은 아니다.

### 작은 파일 runtime baseline 검증 설계 완료 — 2026-09-22

근거: [별도 검증 설계](research_log/memory_runtime_baseline_design.md), 설계 ID `memory_runtime_baseline_v1`.

- 같은 worker 환경에서 `import_only`, `input_only`, `codec`을 비교하도록 대조군을 정의했다. 압축·해제의 실제 phase 입력을 사용하며 baseline 차이를 압축기 순수 메모리나 공식 score로 사용하지 않는다.
- 입력 크기·생성 규칙·seed·반복·run별 순서 무작위화·저장 schema·실패 보존·분석 범위를 측정 전에 정의했다. Python으로 예정 행렬을 계산했고, 이는 연구 측정값이 아니다.
- 범위 겹침과 run별 차이·순위 변동은 기술적 진단으로 해석한다. 공식 전환의 합격 임계값이나 순수 runtime 점유율을 주장하지 않는다.
- 코드·공식 API 근거·문서 링크·diff를 검토했다. 문서 작업이므로 실측·단위 테스트를 재실행하지 않았다. 소스·설정·기존 결과는 변경하지 않았다.
- **설계 작성 당시 미완료:** 별도 worker·runner·audit 구현 및 실제 측정. 이후 worker 검증은 다음 항목과 같으며, 기존 schema-v1 audit의 검사를 완화해 재사용하지 않는다.

### Runtime baseline worker 구현·검증 완료 — 2026-09-22

근거: [worker](src/memory_runtime_worker.py), [전용 테스트](tests/test_memory_runtime_worker.py), [CLI·응답 계약](research_log/memory_runtime_baseline_design.md).

- 설계 commit `584fc68`을 기준으로 `import_only`·`input_only`·`codec`의 공통 진입점을 구현했다. 기존 측정 모듈·설정은 그대로 사용하며 설계와 설정 일치를 검사한다.
- Controls의 `verified`는 null, 입력 대조군의 `input_verified`와 codec의 출력 검증은 서로 구분한다. `codec`은 선택한 압축 또는 해제 호출만 한 번 실행하고 출력 hash를 확인한다. 원본/복원 바이트 비교와 참조 준비는 부모 runner 책임이다.
- peak는 hash 검증 후, 응답 생성·JSON 출력 전에 조회한다. hash 불일치도 peak와 false를 남기며, 실행 오류·잘못된 peak·중단을 성공으로 바꾸지 않는다.
- 아래 전용 테스트 13개가 통과했다. 인위적 peak fixture와 임시 입력의 실제 Windows subprocess smoke test를 사용했다. 모든 arm·알고리즘·phase 성공 경로와 일반/`-O`/`-OO` hash 불일치 거부를 포함한다. smoke test는 실제 backend를 사용했으나 baseline 연구 결과로 저장·집계하지 않았다.

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_worker.py -v
13 tests: OK
```

전체 테스트 suite 및 예정 baseline 전체 실험은 실행하지 않았다. worker는 결과 파일을 쓰지 않으며 기존 연구 결과·config·3지표 라벨·모델을 변경하지 않았다. **당시 미완료:** 부모의 참조 준비·응답 검증·timeout·원시 CSV 저장·종료 metadata를 담당하는 전체 runner, 별도 audit, 전체 실측 및 공식 4지표 전환. 이후 runner 구현은 다음 항목과 같다.

### Runtime baseline runner 구현·검증 완료 — 2026-09-30

근거: [runner](src/memory_runtime_validation.py), [전용 테스트](tests/test_memory_runtime_validation.py), [저장·실행 계약](research_log/memory_runtime_baseline_design.md).

- 시작 기준 HEAD는 worker 구현 commit `018758c`이며 작업 트리는 깨끗했다. 별도 runner와 fixture 테스트를 하나의 실행 기능으로 구현했다.
- 고정된 입력 생성 명세와 run별 무작위 schedule을 먼저 저장하고 세 run을 별도 부모 subprocess에서 순차 실행한다. 부모는 전체 참조 압축물의 실제 복원 bytes와 phase 입력 파일을 검증한 후 worker를 호출한다.
- 요청·설계 식별자, 입력 크기, 타입, arm별 null/boolean 규칙, 양수 peak 및 종료 코드 조합을 검증한다. worker timeout·잘못된 응답·hash 불일치·준비 실패를 원시 CSV와 stdout·stderr로 보존한다. 실패 조건의 정상 집계는 null이다.
- run별 `references.csv`에 실제 입력·압축물 hash와 참조 복원 결과를 저장한다. 원시 반복은 즉시 flush하고 종료 metadata는 원자적으로 저장한다. 시작·종료 환경과 가용 메모리, 소스·설정·plan 변경, 산출물 hash, 원래 예외와 추가 종료 오류를 기록한다. 기존 출력 경로를 덮어쓰지 않는다.
- `completed`는 실행·저장 완료 상태이며 독립 audit 통과나 과학적 검증 완료를 의미하지 않는다. `validation_only`, `score_inclusion=false`를 유지하고 `diagnostic_summary.json`은 아직 생성하지 않는다.

실제 실행한 검증 명령과 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_validation.py -v
19 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_worker.py -v
13 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_validation.py -v
17 tests: OK
```

위 세 모듈의 테스트만 통과했으며 전체 suite는 실행하지 않았다. Runner의 측정값은 인위적 fixture이고, 임시 입력의 실제 참조 압축·복원 및 별도 부모 프로세스 CLI 저장 흐름을 검증했다. 실제 Windows worker 연결 smoke test의 peak는 연구 결과로 저장·집계하지 않았다. 샌드박스의 사용자 Python 접근 제한으로 테스트는 사용자 권한으로 실행했다.

**당시 계획/미완료:** 별도 audit, paired 대비·run 간 범위·순위 진단 구현과 fixture 검증, 전체 baseline 실측, 공식 4지표 전환. 기존 연구 결과·config·3지표 라벨·모델은 변경하지 않았다. 이후 audit 구현은 다음 항목과 같다.

### Runtime baseline 별도 audit 구현·fixture 검증 완료 — 2026-09-30

근거: [audit](research_log/verify_memory_runtime_validation.py), [전용 테스트](tests/test_verify_memory_runtime_validation.py), [감사 계약·한계](research_log/memory_runtime_baseline_design.md).

- 시작 기준 HEAD는 runner 구현 commit `9d3f120`이며 작업 트리는 깨끗했다. 새 audit와 fixture 테스트를 하나의 저장 기록 검증 기능으로 구현했다.
- runner·worker·압축 모듈을 import하지 않고 고정 입력 및 전체 schedule을 재생성한다. 원본 입력 hash, 실제 phase 참조, arm별 null/boolean, worker JSON, 원시 행의 순서·완전성·중복, 집계를 독립 확인한다.
- 최상위와 모든 run의 성공 종료 상태·수량·환경·Git·소스·설정·산출물 hash와 부모 출력을 검사한다. 미완료·실패 상태, 비유한 수·중복 JSON key·잘못된 CSV 열, 감사 도중 파일 변경을 거부한다. 일반 실행 및 `-O`·`-OO`에서도 검사를 유지한다.
- 원본 파일은 읽기 전용이며 기본 출력은 stdout이다. `--output`은 감사 통과 후 새 JSON만 만들고 기존 파일은 덮어쓰지 않는다. 실제 연구 기록에 대한 audit 성공을 주장하지 않는다.
- 저장 복원 flag와 압축물 hash는 일관성 검사의 대상이다. 압축·복원·memory 측정 재실행이나 증거 진위 인증이 아니다. 공식 score는 계속 3지표이며 memory는 `validation_only`이다.

실제 실행한 검증 명령과 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_runtime_validation.py -v
15 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_validation.py -v
11 tests: OK
```

전체 예정 행렬 크기의 임시 fixture에 인위적 peak와 테스트용 Git 정보를 사용했다. Fixture 준비는 실제 입력 생성·참조 압축·복원·저장을 수행하고 worker·부모 호출은 mock했다. Audit 실행 중 압축·복원·측정을 금지한 성공 검사와 hash를 다시 맞춘 오류 증거 거부, 입력 바이트 보존, CLI·최적화 모드·출력 독점 생성을 검증했다. 테스트는 사용자 Python 접근이 가능한 권한으로 실행했으며 위 두 모듈만 통과했다고 기록한다.

**당시 계획/미완료:** paired 대비·run 간 범위·순위 진단 구현과 fixture 검증, 전체 baseline 실측과 실제 저장 기록 audit, 공식 4지표 전환. 기존 schema-v1 audit·runner·worker·config·연구 결과·모델은 변경하지 않았다. 이후 진단 분석 구현은 다음 항목과 같다.

### Runtime baseline 진단 분석·fixture 검증 완료 — 2026-09-30

근거: [진단 분석기](research_log/analyze_memory_runtime_validation.py), [전용 테스트](tests/test_analyze_memory_runtime_validation.py), [분석 계약](research_log/memory_runtime_baseline_design.md).

- 시작 기준 HEAD는 별도 audit 구현 commit `c9bf6e6`이며 작업 트리는 깨끗했다. 분석기·fixture 테스트를 하나의 진단 기능으로 구현했다.
- 기존 audit를 직접 실행하고 감사한 바이트와 원시 입력 hash를 대조한 뒤 계산한다. 분석 종료 때 감사 증거와 관련 소스 변경을 검사하며 실패·미완료·감사 후 변경을 거부한다.
- run별 원시 peak·통계, 같은 run·round·block의 paired 차이/비율과 통계, 모든 arm 쌍 및 알고리즘 쌍의 중앙값 차이·동점·반복 범위 겹침을 저장한다. Run 간에는 각 run의 중앙값/차이와 범위·부호 일치만 요약하며 반복을 합치지 않는다.
- 음수 차이·1 초과 비율·동점을 보존한다. 비율의 부호 기준은 1이며 범위가 경계에서 맞닿아도 겹침으로 기록한다. Paired 차이의 중앙값과 중앙값끼리의 차이는 구분한다.
- 기본 출력은 stdout이며 `--output`은 새 JSON만 생성한다. 기존 원시값·metadata는 읽기 전용이다. `validation_only`, `score_inclusion=false`와 해석 한계를 보고서에 기록한다.

실제 실행한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_analyze_memory_runtime_validation.py -v
7 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_runtime_validation.py -v
15 tests: OK
```

테스트의 peak는 인위적 fixture이다. 임시 전체 행렬 fixture 준비에 실제 참조 압축·복원을 사용하고 worker·부모 호출은 mock했다. 분석 중에는 압축·복원·측정을 금지한 상태에서 실제 audit 연동을 검증했다. 원본 바이트 보존·잘못된 증거 거부·CLI 출력 덮어쓰기 거부·일반/`-O`/`-OO` 오류 거부도 확인했다. 샌드박스의 사용자 Python 접근 제한 때문에 테스트는 사용자 권한으로 실행했다. 전체 suite는 실행하지 않았다.

**당시 계획/미완료:** 전체 baseline 실측, 실제 저장 기록의 audit·진단 분석, 공식 4지표 전환. 기존 runner·worker·audit·config·연구 결과·3지표 라벨·모델은 변경하지 않았다. 이후 전체 실행은 다음 항목과 같다.

### Runtime baseline 전체 실측·audit·진단 완료 — 2026-09-30

근거: [결과 및 해석 기록](research_log/memory_runtime_baseline_results_20260930.md), [원시 증거 폴더](data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/), [audit](data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/audit.json), [진단 JSON](data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/diagnostic_summary.json).

- 실행 commit `729b97b09771ea2a50e955b22f5023d49b61733a`, 시작 `worktree_dirty=false`. 기존 결과에 이어 쓰지 않고 `attempt01`의 새 경로에서 사전 고정 전체 행렬을 실행했다.
- UTC `2026-09-30T12:01:31.276279+00:00` ~ `2026-09-30T12:23:43.063204+00:00`. 세 run의 총 5,400개 반복 모두 `ok`, 실패 0. 실행·종료 처리 `completed`, 종료 오류 없음, 소스 불변이다.
- 독립 audit와 진단 분석 명령 모두 종료 코드 0. 별도 audit와 진단에 포함된 audit의 입력 hash manifest 일치를 Python으로 확인했다. 분석은 측정·압축·복원을 재실행하지 않았다.
- Python으로 실제 진단 JSON을 집계한 결과, run별 알고리즘 쌍의 반복 범위 겹침은 121/180, 116/180, 120/180이다. 세 run에서 차이 부호가 모두 같은 조건은 113/180, 양·음 부호가 뒤집힌 조건은 64/180이다. Paired `D_codec` 중앙값이 음수인 조건은 run별 16/120, 17/120, 14/120이며 삭제·보정하지 않았다.
- 이 수치는 같은 환경의 기술적 진단이다. 모든 작은 입력에서 압축기 메모리 차이나 순위가 안정적으로 구별됐다고 주장하지 않는다. 범위 겹침은 신뢰구간이 아니고 baseline 대비 차이는 순수 메모리 할당량이 아니다.
- `validation_only`, `score_inclusion=false`를 유지했다. 기존 metadata의 분석 대기 상태는 runner 종료 시점 기록으로 보존하고 후속 완료는 별도 보고서에 남겼다. 실행 소스 hash에 포함된 사전 설계 문서도 변경하지 않아, 그 문서의 미실행 표시는 실행 전 시점의 상태이다. 최신 진행 상태는 이 문서와 실제 결과를 따른다.

실행 명령·환경·집계 재현 코드는 위 결과 기록에 있다. 사용자 Python 접근이 가능한 권한으로 실행했다. 이번에는 실제 전체 행렬·audit·진단 및 문서·Git 증거 보존을 검증했고 단위 테스트는 재실행하지 않았다. 기존 결과·소스·config·3지표 라벨·모델은 변경하지 않았다.

**미완료:** memory 지표의 과학적 채택 판단과 추가 검증 필요성 검토, 공식 4지표 전환 및 새 기준 후속 실험.

### Runtime baseline Git 증거 보존 마무리 — 2026-10-06~07

시작 HEAD는 `729b97b`이다. 실제 Git 상태를 사용자 권한으로 확인한 결과, 위 전체 실측 결과 폴더와 결과 보고서는 untracked, 이 진행 문서는 수정 상태였다. 따라서 실측·audit·진단은 완료되었으나 당시 Git 보존은 미완료였으며, 이번 작업에서 해당 증거와 문서만 함께 local commit한다. 샌드박스에서 삭제처럼 표시된 기존 Pilot 파일은 접근 제한이 원인이었고 실제 삭제가 아니었다.

- 사용자 Python의 `-B` 실행으로 `verify_memory_runtime_validation.audit()`와 `analyze_memory_runtime_validation.analyze()`를 읽기 전용으로 재실행했다. 생성 시각 필드만 제외하고 저장 audit·진단 JSON 전체 내용과 재계산 결과가 일치했다. 별도 audit와 진단 내부 audit의 입력 hash manifest도 일치했다.
- 원시 CSV를 Python으로 다시 읽어 반복 5,400개 모두 `ok`임을 확인했고, 결과 보고서의 run별 음수 paired 차이·범위 겹침·동점 및 run 간 부호 일치·양음 역전·알고리즘 쌍별 집계를 재확인했다. 두 문서의 로컬 링크 50개가 존재했다.
- 검증 전후 결과 폴더의 파일 24개 SHA-256이 모두 같았다. 폴더의 `.gitattributes`는 모든 파일의 줄바꿈 변환을 비활성화한다. Stage된 파일은 증거 24개와 문서 2개뿐이며, 모든 증거의 Git blob SHA-256이 원본과 일치했다. 기본 `git diff --cached --check`는 보존된 CRLF를 후행 공백으로 표시했으므로 원본 바이트를 유지하고 일회성 `git -c core.whitespace=cr-at-eol diff --cached --check`로 검사하여 통과했다. Git 설정은 변경하지 않았다.
- 이번 작업은 기존 저장 기록의 일관성과 Git 보존 검증이다. Memory 측정·압축·복원·단위 테스트는 재실행하지 않았다. 소스·설정·기존 연구 결과·라벨·모델을 변경하지 않았다.

**계속 미완료:** memory 지표의 과학적 채택 판단·추가 검증 필요성 검토·공식 4지표 전환. 공식 기준은 v2의 3지표, memory는 `validation_only`, `score_inclusion=false`이다. 자신의 보존 commit hash를 넣기 위한 반복 commit은 만들지 않는다.

### Memory 지표 채택·추가 검증·공식 전환 조건 검토 완료 — 2026-10-07

근거: [채택 검토 문서](research_log/memory_adoption_review_20261007.md), 실제 결과 보존 commit `3f7e91f`, runtime baseline 실행 코드 commit `729b97b`. 시작 작업 트리는 사용자 권한의 실제 Git 상태로 깨끗함을 확인했다.

- **완료:** 기존 설계·worker 코드·실제 결과를 대조하고 memory의 공식 score 채택 보류를 권고했다. 저장 일관성 검증 완료와 과학적 채택 근거를 구분했다. 이는 검토 권고이며 공식 프로토콜 변경 승인이나 추가 실측 실행이 아니다.
- **검증:** Python으로 원시 반복 상태·크기별 범위 겹침·run 간 부호 일치·양음 역전을 재집계했다. 검토 문서의 표와 재현 코드 출력이 실제 값과 일치했고 로컬 링크 14개를 확인했다. 기존 보호 대상 증거·소스·설정·설계 및 결과 문서 53개의 SHA-256이 검토 전후 같았다. Microsoft 공식 API 문서의 지표 정의도 확인했다.
- **계획/미착수:** 공식 후보 worker 경로, 최종 `max_of_phase_medians`의 실행 간 안정성, timing·memory 변동이 정답에 미치는 영향, 새 측정 전 판단 기준을 정하는 후속 검증 설계. 새로운 실측·소규모 4지표 후보 검증·공식 전환 및 새 Pilot은 별도 후속 단계이다.
- 이번 작업은 문서 근거·수치·재현 코드·링크·diff를 검증했다. 새 측정·압축·복원·audit·모델 학습·단위 테스트는 재실행하지 않았고 소스·config·기존 결과·3지표 라벨·모델은 변경하지 않았다.

공식 기준은 계속 v2의 3지표이며 memory는 `validation_only`, `score_inclusion=false`이다. 후보 weight와 추가 검증의 수치 임계값은 이번 검토에서 승인·활성화하지 않았다.

### Memory 대표값·정답 안정성 후속 검증 사전 설계 완료 — 2026-10-07

근거: [후속 검증 설계](research_log/memory_stability_validation_design.md), 설계 ID `memory_stability_v1`, 시작 HEAD `d8b329a`(채택 검토). 실제 결과 보존 commit은 `3f7e91f`, 기존 실행 코드 commit은 `729b97b`이다. 시작 실제 Git 상태는 사용자 권한으로 깨끗함을 확인했다.

- **완료:** 기존 memory worker 경로, 명시적 bytecode 옵션, 별도 timing worker의 원시 ns·bytes 검증·응답 계약, 새 입력·순서·날짜·환경·실패·저장·독립 audit 계약을 사전 정의했다. 기존 worker launcher에 `-B`가 없는 사실과 새 launcher의 옵션 전달을 구분했다.
- **계획 수량:** 핵심 입력 72개와 작은 입력 12개, 총 84개를 세 날짜·6 run에서 검증한다. 예정 memory 반복 20,160개, timing 자식 2,016개·원시 호출 20,160개이다. 모두 Python으로 계산한 예정 값이며 실측이나 성공 수가 아니다.
- **판단 기준 제안:** `delta=0.01`, `epsilon=0.005`에서 memory span의 log 한계 `0.0125`를 유도했다. Memory만의 변동·timing만의 변동·joint 시나리오를 나누고 방향 있는 run 간 regret을 계산한다. 기술적 유효성 실패·memory 조건 불만족·joint 조건 불만족·관측 조건 만족을 구분한다. 기준 만족은 공식 채택이나 미래 실행의 오차 상한을 뜻하지 않는다. 수치는 새 검증용 공학 정책 제안이며 과학적 허용값으로 입증된 것이 아니다.
- **검증:** Python으로 예정 규모·가중치 합·기존 후보 weight 일치·문서 산술 재현 코드·schedule key 고유성/재현성을 확인했다. 로컬 링크 9개와 기존 보호 대상 파일 54개의 SHA-256 일치를 확인하고 문서 근거·식·diff를 검토했다. 새 입력 생성·압축·복원·측정·audit·모델 학습·단위 테스트는 실행하지 않았다.

**당시 미착수/미완료:** 별도 timing worker·runner·새 audit·분석기 구현과 fixture 검증, 일정 준비·전체 실측·사전 판정 및 공식 전환. 당시에는 설계·진행 문서만 변경했다. 공식 v2의 3지표·config·기존 결과·라벨·모델·memory의 `validation_only`와 `score_inclusion=false`를 유지한다. 실측 전에는 사용자 확인 후 조건을 고정하며, 기존 실행의 판정에 새 기준을 소급 적용하지 않는다. 이후 timing worker 구현은 다음 항목과 같다.

### Memory 안정성 후속 검증 timing worker 구현·전용 검증 완료 — 2026-10-13

근거: [timing worker](src/memory_stability_timing_worker.py), [전용 테스트](tests/test_memory_stability_timing_worker.py), [사전 설계 계약](research_log/memory_stability_validation_design.md). 시작 HEAD는 사전 설계 commit `82550b8`이며 실제 작업 트리는 깨끗했다.

- **완료:** `python -B -m src.memory_stability_timing_worker` 진입점을 구현했다. Windows·bytecode 쓰기 비활성화·로드된 설정과 현재 설정·설계의 압축 및 timing 조건을 확인한다. 비어 있지 않은 원본·참조 압축물을 읽고 두 SHA-256을 확인한 뒤 선택한 압축기의 압축 5회→해제 5회만 실행한다.
- **완료:** codec 호출만 `time.perf_counter_ns()`로 감싸고 파일 읽기·hash·정확한 bytes 비교·JSON 직렬화는 timed 구간 밖에서 처리한다. 압축 출력 5개를 해제 반복 동안 보유하며 각 출력 hash와 원시 ns를 반환한다. 출력 bytes 불일치는 남은 반복도 수행해 종료 코드 2로, 일반 호출 오류·잘못된 시간은 완료 기록과 실패 시도만 보존해 코드 1로 반환한다. 미실행 반복은 생성하지 않고 명시적 중단은 전파한다.
- **검증:** 인위적 timer fixture로 순서·호출 횟수·timed 구간·압축 출력 보유·입력 사전 거부·bytes 비교·부분 실패 기록·양수 정수 시간·중단 처리를 확인했다. 임시 입력의 실제 Windows subprocess에서 네 압축기의 성공 응답과 원본 바이트 보존을 확인하고 일반·`-O`·`-OO`의 입력 hash 오류·출력 불일치·codec 오류 거부를 검증했다. 테스트 smoke timing은 연구 결과로 저장·집계하지 않았다.

실제 실행한 전용 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_stability_timing_worker.py -v
16 tests: OK
```

기본 실행 환경 초기화 오류로 사용자 권한에서 테스트를 실행했다. 전체 suite·새 전체 검증 실측·memory 측정·audit·분석·모델 학습은 실행하지 않았다. 부모의 실제 참조 복원 검증·응답 검증·timeout·저장 기능은 worker의 책임이 아니며 다음 runner 단계에 남아 있다.

**당시 계획/미착수:** 별도 후속 runner, 새 독립 audit·분석기와 각각의 fixture 검증, 일정 준비·전체 실측·사전 판정·공식 전환. 기존 사전 설계 문서의 미구현 표시는 작성 당시 상태로 보존한다. 당시에는 worker·전용 테스트·이 진행 문서만 변경했고 기존 소스·config·연구 결과·3지표 라벨·모델을 변경하지 않았다. 공식 v2의 3지표와 memory의 `validation_only`, `score_inclusion=false`를 유지한다. 이후 runner 구현은 다음 항목과 같다.

### Memory 안정성 후속 검증 runner 구현·전용 fixture 검증 완료 — 2026-10-13

근거: [runner](src/memory_stability_validation.py), [전용 테스트](tests/test_memory_stability_validation.py), [사전 설계](research_log/memory_stability_validation_design.md), timing worker 구현 commit `b1d0413`. 시작 실제 Git 상태는 깨끗했다.

- **완료:** 계획 생성 `init`과 다음 예정 run 실행 `run`을 분리했다. `init`은 깨끗한 Git 상태에서 구분되는 새 결과 폴더를 만들고 고정 입력 명세·sample hash/매개변수/중복 관계·전체 schedule·예정 key·후보 weight·기준의 원래 식·config·실행 commit·소스/설계 hash를 저장한다. 준비 실패 sample도 삭제하지 않는다. 계획·sample 파일을 기존 경로에 덮어쓰지 않는다.
- **완료:** 각 `run`은 배타적 claim을 잡고 다음 run만 별도 부모 subprocess로 시작한다. 자동 대기·worker retry·축소 행렬 CLI·중단 run 재실행 기능은 없다. 사전에 정한 여섯 run의 날짜별 수동 실행만 이어 가며, 미완료/중단 attempt는 재개하지 않는다. 사용자가 보고한 전원 모드·reboot·동시 활동·OS 업데이트 사건을 run마다 기록하고, 다른 연구 작업이 실행 중이라고 보고하면 codec/worker 시작 전에 중단한다.
- **완료:** 각 부모는 모든 참조 압축물의 실제 복원 bytes를 먼저 확인하고, run 간 참조 hash·불변 입력·현재 소스/설정을 대조한다. 기존 memory CLI와 별도 timing worker에 `-B`·`PYTHONDONTWRITEBYTECODE=1` 및 timeout을 명시한다. 각 worker 호출 전후와 run 종료 전 입력을 확인하며 duplicate JSON key·비유한 수·타입/요청/반복/출력 hash·종료 코드·stderr 오류를 거부한다.
- **완료:** 원시 memory/timing 반복을 별도 CSV에 즉시 flush한다. Timing 실패 전의 ns·검증 결과와 bundle 증거를 보존하고 미실행 key를 실패 행으로 남긴다. 실패 bundle·실패 pair를 정상 종합 집계에 쓰지 않는다. 종료 metadata를 원자적으로 저장하고 환경·가용 메모리·부하·일정 위반·소스/계획/산출물 hash·부모 출력·원래 예외와 추가 종료 오류를 보존한다. 부모의 전체 수량과 산출물 계약도 확인한다.
- **검증:** 전체 예정 행렬의 명세·seed·schedule/key를 독립 생성한 fixture와 대조했다. 작은 임시 행렬에서 실제 입력 생성·참조 압축/복원 및 인위적 peak/ns로 준비 선행·원시 저장·집계·여섯 run 순서·일정/환경 위반·중복·누락·입력/참조/계획/소스 변경·timeout·중단·저장 실패를 확인했다. 한 개의 실제 새 부모 CLI도 인위적 worker 측정 fixture로 검증했다. 일반·`-O`·`-OO`에서 명시적 응답/JSON 거부가 유지됐다. 임시 입력에 한해 네 압축기의 실제 memory/timing worker 연결 smoke test를 수행했으며 그 peak/ns는 연구 결과로 저장·집계하지 않았다.

실제 실행한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_stability_validation.py -v
36 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_stability_timing_worker.py -v
16 tests: OK
```

기본 실행 환경 초기화 오류로 사용자 권한에서 실행했다. 위 두 모듈만 통과했으며 전체 suite는 실행하지 않았다. 이 작업은 runner 구현 검증이다. 새 연구 attempt·여러 날짜의 전체 실측·독립 audit·정답 안정성 분석·모델 학습은 수행하지 않았다. `recording_checks_passed`는 runner의 기록 검사일 뿐 독립 audit나 과학적 판단이 아니며, `technical_validity_status`는 `pending_independent_audit`이다. 강제 프로세스 종료나 지속적인 저장 실패에서 최종 기록을 보장할 수 없고 사용자 사건 기록도 독립 인증은 아니다.

CLI 형식(아래는 사용 계약이며 이번에 연구 실행한 명령이 아니다):

```text
python -B -m src.memory_stability_validation init --attempt-id <ID> --reason <이유>
python -B -m src.memory_stability_validation run --study-dir <새 attempt 폴더> --events-file <사건 JSON>
```

사건 JSON에는 `power_mode`, `manual_reboot_since_previous_run`, `concurrent_activity`, `os_update_events`, `other_events`, `no_research_jobs_running`을 모두 넣는다. Reboot 여부와 다른 연구 작업의 부재는 boolean, 나머지는 비어 있지 않은 설명이며 사건이 없으면 `none`으로 기록한다. 정확한 CSV 열·null/검증/실패 계약은 runner의 상수와 검증 함수를 따른다.

**당시 계획/미착수:** 새 독립 audit·분석기와 전용 fixture 검증, 일정 준비·전체 실측·사전 판정·공식 전환. 사전 설계의 작성 당시 미구현 표시는 보존했다. 당시에는 새 runner·전용 테스트·이 진행 문서만 변경했으며 기존 worker·공식 config·기존 결과·3지표 라벨·모델은 변경하지 않았다. 공식 v2의 3지표와 memory의 `validation_only`, `score_inclusion=false`를 유지한다. 이후 독립 audit 구현은 다음 항목과 같다.

### Memory 안정성 후속 검증 독립 audit 구현·전용 fixture 검증 완료 — 2026-10-14

근거: [독립 audit](research_log/verify_memory_stability_validation.py), [전용 테스트](tests/test_verify_memory_stability_validation.py), [사전 설계](research_log/memory_stability_validation_design.md), runner 구현 commit `a47ba950e777df49751563105385744c2309e147`. 시작 HEAD는 이 runner commit이며 실제 작업 트리는 깨끗했다.

- **완료:** 별도 audit가 고정 입력 명세·seed·전체 schedule/예정 key·후보 weight·기준 식을 직접 재구성한다. 기록된 소스·config hash를 먼저 확인하고 순수 `src.data_generator`와 작은 입력의 고정 식으로 원본 hash·생성 매개변수·중복 관계를 재확인한다. Runner·worker·compressors·scoring은 import하지 않는다.
- **완료:** 모든 run의 참조 일관성·원시 행의 순서/완전성·argv와 임시 phase 경로·bytecode 옵션·요청/입출력 hash·worker JSON·검증 flag·종료 코드·원시 peak/ns를 검사하고 phase 중앙값·ratio·ms 변환·최종 memory 최댓값을 독립 재계산한다. Run/coordinator의 일정·환경·사건 기록·Git·수량·종료 상태·불변 파일·산출물 hash·부모 stdout/stderr도 대조한다.
- **완료:** 미완료·실패·일정/환경 위반·중복 JSON key·비유한 수·잘못된 CSV·진행 중/남은 claim을 거부한다. 입력·소스·audit 코드의 읽은 바이트를 종료 시 다시 비교한다. `python -B`를 요구하며 기본 출력은 stdout이다. `--output`은 audit 통과 후 새 JSON만 만들고 기존 파일을 덮어쓰지 않는다.
- **검증:** 전체 예정 행렬 크기의 임시 fixture를 사용했다. 입력과 참조 압축/복원은 실제 준비했지만 peak/ns·Git commit·시각·사건은 인위적 테스트 값이다. 전체 성공·원본 바이트 보존·금지된 producer/codec 호출 거부·hash를 다시 맞춘 잘못된 증거 거부·일정 경계·CLI의 금지 import 차단·출력 덮어쓰기 거부·일반/`-O`/`-OO` 오류 거부를 검증했다. 입력 재생성은 전체 성공·CLI 검증에서 실제 수행하고, 나머지 오류 사례에서는 독립 재생성해 확인한 canonical fixture 입력을 재사용했다.

실제 완료한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_stability_validation.py -v
25 tests: OK
```

기본 실행 환경의 초기화 오류로 사용자 Python 접근이 가능한 권한에서 실행했다. 초기 테스트 실행은 반복 입력 재생성 비용을 확인하고 중단했으며, fixture 입력 재사용을 적용한 위 실행은 종료 코드 0으로 완료했다. 위 전용 모듈만 통과했으며 전체 suite와 이전 테스트 모듈은 재실행하지 않았다. 새 연구 attempt·전체 실측·실제 저장 기록 audit·안정성 분석·모델 학습은 수행하지 않았다.

읽기 전용 Python으로 시작 시 tracked 파일과 대조해 진행 기록을 제외한 기존 파일 152개의 SHA-256이 모두 같음을 확인했다. 이 문서의 로컬 링크 52개가 존재했고 `git diff --check`를 통과했다. 기본 Git 줄바꿈 안내는 소스/문서의 LF→CRLF 안내이며 기존 연구 증거 파일은 변경되지 않았다.

실제 완료된 후속 attempt에 사용할 CLI 형식(이번에는 실제 연구 증거에 실행하지 않음):

```text
python -B -m research_log.verify_memory_stability_validation --experiment-dir <completed-attempt-directory>
```

`--output <new-audit-json>`은 선택 사항이다. 이 audit의 성공은 저장 증거의 일관성이다. 저장된 복원 flag와 압축물 hash는 독립 복원 재검증이 아니며, hash·사용자 사건·환경 기록은 증거의 진위나 사건을 독립 인증하지 않는다. Memory span·후보 label·regret·사전 판정 및 공식 4지표 전환은 수행하지 않았다. Runner metadata의 `pending_independent_audit`는 당시 기록으로 유지하고 후속 audit 보고서와 구분한다.

**당시 계획/미완료:** 별도 분석기 구현·fixture 검증, 일정 준비·전체 실측·실제 증거 audit·사전 판정·공식 채택 및 4지표 전환. 당시에는 독립 audit·전용 테스트·이 진행 문서만 변경했다. 기존 runner·worker·설계·공식 config·연구 결과·3지표 라벨·모델은 유지하며 memory는 `validation_only`, `score_inclusion=false`이다. 이후 분석기 검증은 다음 항목과 같다.

### Memory 안정성 후속 검증 분석기 초안 검토·전용 fixture 검증 완료 — 2026-10-16

근거: [분석기](research_log/analyze_memory_stability_validation.py), [전용 테스트](tests/test_analyze_memory_stability_validation.py), 사전 설계 commit `82550b8`와 독립 audit 구현 commit `6bea53a`. 시작 HEAD는 이 audit commit이며, 추적 파일의 변경 없이 분석기와 전용 테스트 두 파일이 untracked 상태였다. 진행 문서의 분석기 미착수 표시와 달리 초안이 존재했으므로 이를 보존해 검토·실행했다. 보완이 필요한 오류는 발견하지 않았고 두 파일의 시작 바이트를 그대로 local commit한다.

- **완료:** 분석기가 독립 audit를 직접 실행하고 감사한 바이트의 snapshot만 계산에 사용한다. 종료와 출력 저장 전후에 입력·관련 소스 hash, run 목록과 active claim을 다시 확인하며 audit 실패·미완료·증거 변경을 거부한다. 분석 중 runner·worker·compressors·공식 scoring은 import하거나 실행하지 않는다.
- **완료:** 원시 반복에서 run별 phase 중앙값·ms 변환·최종 memory 최댓값을 재계산하고, 여섯 run 대표값의 중앙값을 anchor로 사용한다. Reference·memory_only·timing_only·joint 후보 score, 정확한 동점과 차선 gap, 모든 방향 있는 run 쌍의 regret 및 anchor regret을 보존한다. 원시 반복을 run 간 합치지 않는다.
- **완료:** 핵심 층·작은 입력 층과 전체의 memory span·regret 판정, memory 산술 관계, phase/대표값의 범위·population CV, memory 알고리즘 쌍의 차이·동점·부호·범위 겹침을 보고한다. 공식 v2 비교와 후보 non-memory 비교를 구분하고 memory 선택 영향은 안정성 만족과 별도로 기록한다. 판정에는 원래 식과 반올림 전 값만 사용하며 산술 QA의 부동소수점 허용 오차는 판정에 사용하지 않는다.
- **완료:** 기본 출력은 전체 stdout JSON이다. `--output-dir`은 기존 경로를 거부하고 새 폴더에 `audit.json`, `candidate_labels.csv`, `transfer_regrets.csv`, `stability_summary.json`을 저장한다. 저장한 표의 hash·열·행 수를 summary에 연결한다. 저장 실패 시 부분 파일과 원래 예외를 보존하고 `publication_failed.json` 기록을 시도한다. 성공 반환과 실패 marker 부재를 함께 요구하며 지속적인 저장 실패에서 marker 생성을 보장하지 않는다.
- **검증:** 인위적 수치 fixture로 동점·근접 score·정확한 경계·낮은 gap의 label 변경·방향별 regret 비대칭·최댓값 phase 변경·timing/memory 영향 분리·작은 층 실패·dominant label의 span 면제 금지를 확인했다. 전체 예정 행렬 크기의 fixture에서 실제 독립 audit 연동·금지 codec 호출 차단·입력 바이트 보존·audit 전후와 계산 중 증거 변경·소스 변경·덮어쓰기 거부·저장 실패·CLI 및 일반/`-O`/`-OO` 오류 거부를 검증했다.

실제 완료한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_analyze_memory_stability_validation.py -v
21 tests: OK
```

첫 샌드박스 실행은 임시 폴더 접근 거부로 실패했으며 사용자 권한으로 재실행한 위 명령은 종료 코드 0으로 완료했다. 전체 suite와 기존 audit 전용 모듈은 재실행하지 않았다. Fixture 준비에는 실제 입력 생성·참조 압축·복원을 사용했지만 peak/ns·Git commit·시각·사건은 인위적 테스트 값이다. 전체 성공과 CLI에서는 실제 입력 재생성을 수행하고 다른 오류 검사는 독립 재생성으로 확인한 canonical fixture 입력을 재사용했다. Fixture 값과 그 판정은 연구 결과가 아니다.

읽기 전용 Python으로 진행 문서를 제외한 기존 추적 파일 154개의 SHA-256과 두 초안의 바이트가 시작 시점과 같음을 확인했다. 진행 문서의 로컬 링크와 diff도 검토했다. 샌드박스가 삭제처럼 표시한 Pilot 파일은 사용자 권한 Git 상태와 파일 hash로 확인했으며 실제 삭제가 아니었다.

실제 완료된 후속 attempt에서 사용할 CLI 형식(이번에는 실제 연구 증거에 실행하지 않음):

```text
python -B -m research_log.analyze_memory_stability_validation --experiment-dir <completed-attempt-directory> --output-dir <new-analysis-directory>
```

`--output-dir`은 선택 사항이다. 분석기는 memory/timing 측정·압축·복원·모델 학습을 재실행하지 않는다. Audit 성공은 저장 일관성이고, 후보 판정 만족은 관측한 조건에 한정된다. 독립 복원 인증·미래 오차 상한·memory 공식 채택·최종 시스템 개선을 뜻하지 않는다.

**계획/미완료:** 일정·환경 준비와 실측 전 조건 확인, 새 전체 attempt 실측·실제 증거 audit·후보 분석과 사전 판정, 공식 채택 및 4지표 전환. 이번에는 분석기·전용 테스트의 기존 초안을 검증해 보존하고 진행 문서만 갱신한다. 기존 runner·worker·audit·설계·공식 config·연구 결과·3지표 라벨·모델을 유지하며 memory는 `validation_only`, `score_inclusion=false`이다.

## 12. 아직 완료하지 않은 작업

- Memory 후속 검증의 일정·환경 준비·전체 실측·실제 증거 audit·분석·사전 판정·채택 근거 확보 및 공식 4지표 전환. 채택 검토·사전 설계·timing worker·runner·독립 audit·분석기 구현과 전용 fixture 검증은 완료했으나 공식 채택은 계속 보류 권고이다.
- 독립 `smart_decompress.py` CLI: 현재 빈 파일이다. `main.py`도 빈 파일이다.
- 사용자용 Compare/Demo Mode와 GUI.
- 실제 파일 데이터·원본 그룹 분할 설계·별도 unseen 평가.
- 특징 추출·예측 비용을 포함한 end-to-end 성능 평가.
- 약 5,000개·10,000개로의 실험 확대 및 최종 연구 정리.

## 13. 다음 단일 작업

**제안/미착수:** [후속 검증 설계](research_log/memory_stability_validation_design.md)에 따른 전체 attempt의 일정·환경·실행 조건을 준비하고 사용자 확인으로 고정한다. 연속 세 날짜·여섯 run의 실행 가능 시간과 전원 모드·동시 작업·사건 기록 방법을 확인한다. 이 준비와 실제 전체 실측은 구분하며, 사용자 확인 전 새 attempt 생성이나 실측을 시작하지 않는다. 공식 설정·가중치·라벨 전환은 이후 별도 작업이다.

이번 작업은 기존 분석기 초안 검토와 전용 fixture 검증까지 완료했다. 전체 실측·실제 증거 audit·후보 분석과 사전 판정·공식 채택 및 4지표 전환은 미완료이다.

## 14. 마지막 관련 Git commit

기존 완료 memory 실행의 구현·실험 기준 commit은 `3e9b2673a116b045a5e225203e0d175429192c09` (`Harden memory validation finalization and preserve failure evidence`)이며, 결과·audit 보존 commit은 `3ad85c9`이다. Runtime baseline 전체 실측·audit·진단의 실행 코드 commit은 `729b97b09771ea2a50e955b22f5023d49b61733a`이며, 결과·보고서 보존 commit은 `3f7e91ff36266cf2c0271a8ffc3b6a9d5edcafa4`이다. 채택 검토 commit은 `d8b329ad4305322a3bf49aa21d680585220cbb73`이다. 후속 검증 사전 설계 commit은 `82550b8`, timing worker 구현 commit은 `b1d0413`, runner 구현 commit은 `a47ba95`, 독립 audit 구현 commit은 `6bea53a`이다. 이번 분석기·전용 테스트·진행 기록은 함께 commit하며, 자신의 commit hash를 넣기 위한 반복 commit은 만들지 않는다.

기존 보존 실행이 기록한 마지막 관련 측정 구현·실행 코드 commit:

```text
c54b8f5f9b7ae114206b43ce1e23fe4b69666203
Implement persistent validation-only memory measurement matrix
```

관련 이력:

- `6bea53a`: memory 안정성 후속 검증 독립 audit 및 전용 fixture 검증. 이번 분석기 검토·검증의 시작 기준 HEAD.
- `a47ba95`: memory 안정성 후속 검증 runner 및 전용 fixture 검증. 이번 독립 audit 구현의 시작 기준 HEAD.
- `b1d0413`: memory 안정성 후속 검증 timing worker 및 전용 테스트. 이번 runner 구현의 시작 기준 HEAD.
- `82550b8`: memory 대표값·정답 안정성 후속 검증 사전 설계. 이번 timing worker 구현의 시작 기준 HEAD.
- `d8b329a`: memory 공식 채택 보류 권고·추가 검증 필요성·전환 조건 검토. 이번 후속 검증 사전 설계의 시작 기준 HEAD.
- `3f7e91f`: runtime baseline 원시 증거·audit·진단·보고서 Git 보존 및 읽기 전용 재검증. 이번 채택 검토의 시작 기준 HEAD.
- `729b97b`: runtime baseline 진단 분석 및 fixture 검증. 이번 전체 실측·audit·진단의 실행 기준 HEAD.
- `c9bf6e6`: runtime baseline 별도 audit 및 fixture 검증. 이번 진단 분석 작업의 시작 기준 HEAD.
- `9d3f120`: runtime baseline runner 및 fixture 테스트 구현. 이번 별도 audit 작업의 시작 기준 HEAD.
- `018758c`: runtime baseline worker 및 전용 테스트 구현. 이번 runner 작업의 시작 기준 HEAD.
- `584fc68`: 별도 runtime baseline 검증 설계. 새 worker 작업의 시작 기준 HEAD.
- `3ad85c9`: 2026-09-22 전체 memory 검증 행렬 및 audit 결과 보존. 현재 별도 runtime baseline 설계의 시작 기준 HEAD.
- `3e9b267`: 종료 metadata 원자적 저장·오류 기록 보강 및 관련 fixture 테스트 28개 검증. 2026-09-22 전체 행렬의 실행 코드 기준.
- `210b38d`: 완료된 memory 검증 기록의 audit 도구 및 인위적 fixture 검증 정리.
- `708c9cb`: 미완료 memory 실행 원본·보존용 Git 속성·진행 기록 보존. 이번 audit 구현·테스트는 그 후속 작업이며 문서 자신의 commit hash를 넣기 위한 반복 commit은 만들지 않는다.
- `70294a6`: 특징 기반 Smart Mode 구현. 최초 문서 작성 당시 마지막 구현 commit.
- `811385b`: 1,008 sample Pilot 실패 분석 결과 기록.
- `81adc0d`: Random Forest 평가 결과 기록.
- `c8e18b5`: Decision Tree 평가 결과 기록.
- `6b6a7bb`: baseline 평가 결과 기록.
- `572760b`: 독립 peak memory 측정 정의.
- Pilot 원시 실험 metadata의 실행 코드 commit: `4d2d637bea96a4a1ddbbedb2c077fd0474ca8c19`.

최초 문서 작성 전 `main` 작업 트리는 깨끗했다. 샌드박스의 Pilot 하위 폴더 접근 제한으로 삭제처럼 표시된 항목은 실제 권한으로 재확인했으며 삭제가 아니었다. 2026-09-16 증거 보존 작업 시작 시에는 audit 스크립트가 staged이고 memory 결과 폴더가 untracked였다. 이후 세션은 당시 상태를 그대로 가정하지 말고 `git status`와 최근 commit을 다시 확인한다.
