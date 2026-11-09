# 후보 모델 전체 경로 비용 병목 진단 — 2026-11-09

직전 실험의 저장 기록을 재집계했다. 특징 계산/입력 frame 준비가 모델 압축 경로의 가장 큰 직접 계측 구간이었다. RF에서는 예측 비용도 컸다. zstd 선택률 조정만으로 전체 경로 손실이 해결된다는 근거는 없다.

[18개 조건](../data/results/usage_pipeline_bottlenecks_20261109_01/summary.csv) · [파일별 1,080개 분해](../data/results/usage_pipeline_bottlenecks_20261109_01/file_decomposition.csv) · [1,140개 시간 중앙값](../data/results/usage_pipeline_bottlenecks_20261109_01/trace_medians.csv) · [크기별](../data/results/usage_pipeline_bottlenecks_20261109_01/size_summary.csv) · [원본 그룹별](../data/results/usage_pipeline_bottlenecks_20261109_01/origin_summary.csv) · [감사](../data/results/usage_pipeline_bottlenecks_20261109_01/audit.json) · [검증](../research_log/verify_pipeline_bottlenecks_20261109.py)

## 측정 범위와 식

원본 실측 source `6a75f98`, 실측 결과 보존 `f5fcb24`, 직전 누락 분석 `eea90af`의 동일 corpus 60개·9개 가상 정책·DT/RF를 사용했다. 새 압축·특징 계산·모델 예측·학습은 실행하지 않았다. 5,700개 trial은 19개 전략(고정 zstd+18개 모델 조건)×60개×5회다. 조건별 비교는 같은 파일의 저장된 fixed_zstd를 공유한다.

`J = S·B + C·Tc + D·Tr`, `S=k_s·H`, `C=k_c`, `D=k_d·N`이다. 가상 정책점수이며 요금/에너지/메모리 비용이 아니다. 양의 delta는 모델 손실, 양의 saving은 고정 zstd 대비 이득이다. 정책마다 단위 교환비가 달라 조건들의 절대 비용을 합치지 않았다.

`feature_ns`는 `extract_features`와 pandas frame 생성·schema/유한값 검사를 포함한다. `prediction_ns`는 predict 호출과 결과 문자열 변환이다. 압축 전체 시간은 읽기/hash→특징→예측→선택한 압축기 하나→복원 byte 검증→payload/manifest 저장을 포함한다. 복원 전체 시간에는 manifest/payload 읽기·hash·해제·원본 hash 검사·복원 파일 저장이 포함된다. 일부 사후 saved-byte 확인은 timer 밖이다.

**검증·hash·읽기·쓰기의 개별 시간은 저장하지 않았다.** 이 항목들은 압축/복원 나머지 시간에 합쳐져 있다. 서로 다른 실행에서 측정한 codec 중앙값을 뺀 나머지는 음수가 될 수 있고 OS cache·순서·실행 간 변동도 포함하므로 순수 I/O 비용이나 인과 효과로 해석하지 않는다.

## 18개 조건 전부

| 조건 | 모델 | 평균 특징 ms | 평균 예측 ms | 특징/압축 전체 | 실제 비용 절감 | 특징 시간만 0 가정 | 두 시간 0 가정 |
|---|---|---:|---:|---:|---:|---:|---:|
| archive_t0p1 | decision_tree | 64.046 | 2.865 | 84.94% | -56.35% | -2.97% | 0.07% |
| archive_t0p1 | random_forest | 61.176 | 20.083 | 61.53% | -72.91% | -17.34% | 0.67% |
| archive_t1 | decision_tree | 62.058 | 2.658 | 87.74% | -309.98% | -14.88% | -1.18% |
| archive_t1 | random_forest | 58.370 | 19.128 | 69.32% | -371.39% | -90.38% | 1.69% |
| archive_t10 | decision_tree | 57.900 | 2.505 | 87.52% | -538.98% | -17.63% | 5.04% |
| archive_t10 | random_forest | 59.280 | 19.565 | 69.82% | -708.52% | -174.13% | 2.20% |
| balanced_t0p1 | decision_tree | 60.382 | 2.553 | 87.75% | -34.46% | 6.10% | 7.87% |
| balanced_t0p1 | random_forest | 61.297 | 19.661 | 70.89% | -45.58% | -4.66% | 8.63% |
| balanced_t1 | decision_tree | 59.098 | 2.556 | 86.30% | -36.23% | 5.72% | 7.56% |
| balanced_t1 | random_forest | 59.603 | 20.768 | 69.23% | -50.72% | -8.79% | 6.06% |
| balanced_t10 | decision_tree | 59.415 | 2.618 | 87.42% | -35.91% | 6.63% | 8.58% |
| balanced_t10 | random_forest | 58.411 | 19.782 | 69.45% | -47.27% | -5.54% | 8.69% |
| fast_access_t0p1 | decision_tree | 59.289 | 2.700 | 84.14% | -8.01% | 5.02% | 5.64% |
| fast_access_t0p1 | random_forest | 61.035 | 21.328 | 69.02% | -14.71% | -1.16% | 3.51% |
| fast_access_t1 | decision_tree | 66.116 | 2.715 | 84.22% | -21.20% | -6.61% | -5.98% |
| fast_access_t1 | random_forest | 57.597 | 20.755 | 68.36% | -16.49% | -3.73% | 0.83% |
| fast_access_t10 | decision_tree | 54.448 | 2.513 | 84.02% | -6.36% | 5.65% | 6.23% |
| fast_access_t10 | random_forest | 55.587 | 22.998 | 66.68% | -26.26% | -14.28% | -9.21% |

**시간 0 가정은 최적화한 프로그램의 실측값이 아니다.** 원래 trial별 압축 전체 ns에서 해당 내부 timer ns를 뺀 뒤 5회 중앙값을 다시 구했다. 선택 압축기·package bytes·복원 전체 시간은 그대로 둔, 해당 timer 제거에만 한정한 낙관적 계산이다. 전역적 성능 상한이나 새 모델의 성능을 뜻하지 않는다. 구현 후 동등성 확인과 새 계획의 실측이 필요하다.

전체 18개 조건 중 특징 시간만 0으로 두어도 가상 비용이 여전히 불리한 조건은 13개, 특징·예측을 모두 0으로 두어도 불리한 조건은 3개였다. 일부 동일 zstd 선택 조건에서도 나머지 시간 차이만으로 부호가 바뀐다. 이 변동을 압축기 선택 이득으로 해석하지 않는다.

## 비용 차이의 장부 분해

모델−고정 zstd 비용 차이를 다음 항목으로 보존했다. 파일별 합계와 조건별 합계가 원래 전체 경로 차이와 일치하는지 검사했다.

| 항목 | 정의/범위 |
|---|---|
| codec_selection_delta | 기존 Compare의 선택 압축기 비용−zstd 비용 |
| package_metadata_delta | codec payload 외 package bytes 비용의 모델−zstd 차이 |
| feature_cost / prediction_cost | 각 내부 timer 중앙값×압축 시간 비용 계수 |
| compression_remainder_delta | trial별 내부 timer를 뺀 중앙값에서 codec 시간을 제외한 양의/음의 차이 |
| median_alignment_delta | 전체 중앙값−특징 중앙값−예측 중앙값−나머지 중앙값의 보정 |
| restoration_remainder_delta | 복원 전체 중앙값에서 codec 해제 중앙값을 뺀 양의/음의 차이 |

**중앙값은 더할 수 없다.** 따라서 나머지를 trial별로 계산하고, 독립 중앙값들의 합이 전체 중앙값과 달라지는 부분을 별도 항목으로 표시했다. 실제 최적화 가정도 전체 중앙값에서 특징 중앙값을 단순히 빼지 않는다.

## codec 이득과 특징 예산

| 조건 | 모델 | 실제 codec 절감 | codec oracle 최대 절감 | 관측 특징 비용 / oracle 이득 | 모델 load 중앙값 ms |
|---|---|---:|---:|---:|---:|
| archive_t0p1 | decision_tree | 0.1406% | 1.5816% | 36.39배 | 18.644 |
| archive_t0p1 | random_forest | 0.1245% | 1.5816% | 34.76배 | 36.997 |
| archive_t1 | decision_tree | -0.0000% | 0.0000% | 이득 0 | 16.288 |
| archive_t1 | random_forest | -0.0000% | 0.0000% | 이득 0 | 27.148 |
| archive_t10 | decision_tree | -0.0000% | 0.0000% | 이득 0 | 17.160 |
| archive_t10 | random_forest | -0.0000% | 0.0000% | 이득 0 | 25.437 |
| balanced_t0p1 | decision_tree | -0.0000% | 2.4660% | 111.94배 | 18.379 |
| balanced_t0p1 | random_forest | -0.0000% | 2.4660% | 113.64배 | 30.070 |
| balanced_t1 | decision_tree | -15.5028% | 3.7606% | 113.94배 | 17.561 |
| balanced_t1 | random_forest | -0.0000% | 3.7606% | 114.91배 | 28.304 |
| balanced_t10 | decision_tree | -0.0000% | 3.9786% | 115.00배 | 17.256 |
| balanced_t10 | random_forest | -0.0000% | 3.9786% | 113.06배 | 31.130 |
| fast_access_t0p1 | decision_tree | -33.4806% | 7.3137% | 20.60배 | 19.573 |
| fast_access_t0p1 | random_forest | -0.0000% | 7.3137% | 21.20배 | 31.953 |
| fast_access_t1 | decision_tree | -33.7255% | 7.3623% | 22.97배 | 19.041 |
| fast_access_t1 | random_forest | -0.0000% | 7.3623% | 20.01배 | 33.995 |
| fast_access_t10 | decision_tree | -33.7502% | 7.3672% | 18.92배 | 19.793 |
| fast_access_t10 | random_forest | -0.0000% | 7.3672% | 19.32배 | 31.611 |

oracle 이득은 모든 codec 측정값을 아는 이상적 선택의 비용 절감이다. 특징 예산 비교는 codec 범위의 낙관적 점검이며 engine에서 이득을 보장하지 않는다. Load는 기존 warm 시간 밖의 별도 5회 read/hash/deserialization 측정이다. 파일마다 load 비용을 더한 기존 proxy는 검산했지만 실제 cold start나 batch amortization을 새로 측정하지 않았다.

## 후속 작업 판단

우선 기존 12개 특징의 의미/순서/값을 보존하는 특징 계산 최적화를 검토할 근거가 있다. 소스에는 run/bigram/block/segment 통계 계산에 여러 순회가 있으나 개별 함수 timer가 없어 어느 함수가 가장 느린지는 이번 기록으로 순위를 확정할 수 없다. 먼저 별도 계획에서 함수별 profile과 정확한 출력 동등성을 확인하는 것이 다음 단일 작업이다. RF 예측 overhead도 함께 확인하되 모델 변경/재학습은 별도 연구 결정이다.

기존 57개 zstd 누락과 반대 방향 74개 손실은 이전 보고서에 그대로 남긴다. 선택 비율 quota·사후 계수 조정으로 해결하지 않는다. 관찰된 60개는 후속 튜닝의 개발 자료이며 최종 성능 평가는 다른 원본 그룹의 holdout이 필요하다.

원본 그룹 동일 비중의 기존 주 평가량을 바꾸지 않았다. 이번 분해의 시간/비용 표는 전체 파일 합계의 기술 통계다. 크기 구간은 ≤64KiB, (64,256]KiB, >256KiB로 명시했고 빈 구간은 만들지 않았다. 저장된 원본 그룹별 분해도 보존했다. 새 평가 시나리오를 고르거나 표본을 제외하지 않았다.

## 검증과 보존

원시 5700개 trial의 고유 key·5회 완전성·verified·원본 hash·동일 출력·timer 포함 관계를 검사했다. 사전 예측과 각 trial의 압축기가 일치하고 저장 codec 측정이 정상 검증됐음을 확인했다. 기존 pipeline_metrics의 18개 조건 전체 시간/비용·load proxy를 검산했다. 파일별 1,080개와 조건별 비용 분해가 닫히고, 모든 timer 제거 가정은 trial별 계산으로 검산했다.

기존 study·57건 분석·공식 기준/config·관련 source의 실행 전후 hash를 보존했다. 별도 독립 검증기는 저장 원시 trial에서 전체/가정 비용을 다시 계산한다. 기존 공식 모델/score·memory validation_only·실제 GUI 미완료 항목을 유지했다. 연구용 상주 엔진이며 Python 시작·cold cache·fsync·대용량/스트리밍·실제 배포 성능이나 통계적 유의성을 입증하지 않는다.
