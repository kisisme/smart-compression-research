# Pilot 실패 사례 분석

이 문서의 모든 표와 개수는 Python이 저장된 측정·예측 CSV에서 계산했다.

오분류는 model × sample × mode 기준 21행, 고유 sample은 7개이다.

## 모델별 시험 결과

| model | mode | test_count | error_count | accuracy | macro_f1 | mean_regret | recovered_from_baseline | harmed_vs_baseline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | archive | 202 | 1 | 0.995050 | 0.249380 | 0.000435 | 0 | 0 |
| baseline | balanced | 202 | 1 | 0.995050 | 0.249380 | 0.000326 | 0 | 0 |
| baseline | fast_access | 202 | 2 | 0.990099 | 0.248756 | 0.001932 | 0 | 0 |
| decision_tree | archive | 202 | 4 | 0.980198 | 0.247500 | 0.002999 | 0 | 3 |
| decision_tree | balanced | 202 | 1 | 0.995050 | 0.249380 | 0.000326 | 0 | 0 |
| decision_tree | fast_access | 202 | 6 | 0.970297 | 0.246231 | 0.009081 | 0 | 4 |
| random_forest | archive | 202 | 2 | 0.990099 | 0.248756 | 0.001788 | 0 | 1 |
| random_forest | balanced | 202 | 1 | 0.995050 | 0.249380 | 0.000326 | 0 | 0 |
| random_forest | fast_access | 202 | 3 | 0.985149 | 0.248130 | 0.004662 | 0 | 1 |

## 학습·시험 정답 분포

| mode | split | algorithm | count | sample_count |
| --- | --- | --- | --- | --- |
| archive | train | gzip | 7 | 806 |
| archive | train | bz2 | 0 | 806 |
| archive | train | lzma | 0 | 806 |
| archive | train | zstd | 799 | 806 |
| archive | test | gzip | 1 | 202 |
| archive | test | bz2 | 0 | 202 |
| archive | test | lzma | 0 | 202 |
| archive | test | zstd | 201 | 202 |
| balanced | train | gzip | 4 | 806 |
| balanced | train | bz2 | 0 | 806 |
| balanced | train | lzma | 0 | 806 |
| balanced | train | zstd | 802 | 806 |
| balanced | test | gzip | 1 | 202 |
| balanced | test | bz2 | 0 | 202 |
| balanced | test | lzma | 0 | 202 |
| balanced | test | zstd | 201 | 202 |
| fast_access | train | gzip | 10 | 806 |
| fast_access | train | bz2 | 0 | 806 |
| fast_access | train | lzma | 0 | 806 |
| fast_access | train | zstd | 796 | 806 |
| fast_access | test | gzip | 2 | 202 |
| fast_access | test | bz2 | 0 | 202 |
| fast_access | test | lzma | 0 | 202 |
| fast_access | test | zstd | 200 | 202 |

## 모든 오분류

| model | sample_id | mode | generator | size | true_algorithm | predicted_algorithm | prediction_confidence | regret | oracle_margin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | sample_000916 | archive | structured | 16384 | gzip | zstd |  | 0.087834 | 0.087834 |
| baseline | sample_000916 | balanced | structured | 16384 | gzip | zstd |  | 0.065889 | 0.065889 |
| baseline | sample_000916 | fast_access | structured | 16384 | gzip | zstd |  | 0.303277 | 0.303277 |
| baseline | sample_000841 | fast_access | small_alphabet | 16384 | gzip | zstd |  | 0.086910 | 0.086910 |
| decision_tree | sample_000922 | archive | structured | 65536 | zstd | gzip | 1.000000 | 0.273275 | 0.273275 |
| decision_tree | sample_000664 | archive | structured | 262144 | zstd | gzip | 1.000000 | 0.123282 | 0.123282 |
| decision_tree | sample_000286 | archive | structured | 1048576 | zstd | gzip | 1.000000 | 0.121345 | 0.121345 |
| decision_tree | sample_000916 | archive | structured | 16384 | gzip | zstd | 1.000000 | 0.087834 | 0.087834 |
| decision_tree | sample_000916 | balanced | structured | 16384 | gzip | zstd | 1.000000 | 0.065889 | 0.065889 |
| decision_tree | sample_000922 | fast_access | structured | 65536 | zstd | gzip | 1.000000 | 0.551509 | 0.551509 |
| decision_tree | sample_000604 | fast_access | structured | 16384 | zstd | gzip | 1.000000 | 0.486300 | 0.486300 |
| decision_tree | sample_000916 | fast_access | structured | 16384 | gzip | zstd | 1.000000 | 0.303277 | 0.303277 |
| decision_tree | sample_000664 | fast_access | structured | 262144 | zstd | gzip | 1.000000 | 0.279632 | 0.279632 |
| decision_tree | sample_000256 | fast_access | structured | 262144 | zstd | gzip | 1.000000 | 0.126813 | 0.126813 |
| decision_tree | sample_000841 | fast_access | small_alphabet | 16384 | gzip | zstd | 1.000000 | 0.086910 | 0.086910 |
| random_forest | sample_000922 | archive | structured | 65536 | zstd | gzip | 0.540000 | 0.273275 | 0.273275 |
| random_forest | sample_000916 | archive | structured | 16384 | gzip | zstd | 1.000000 | 0.087834 | 0.087834 |
| random_forest | sample_000916 | balanced | structured | 16384 | gzip | zstd | 1.000000 | 0.065889 | 0.065889 |
| random_forest | sample_000922 | fast_access | structured | 65536 | zstd | gzip | 0.540000 | 0.551509 | 0.551509 |
| random_forest | sample_000916 | fast_access | structured | 16384 | gzip | zstd | 1.000000 | 0.303277 | 0.303277 |
| random_forest | sample_000841 | fast_access | small_alphabet | 16384 | gzip | zstd | 1.000000 | 0.086910 | 0.086910 |

## 오류가 발생한 generator·크기 그룹

오류율의 분모는 해당 그룹의 전체 test sample 수이다. 오류가 없는 그룹도 CSV에는 보존한다.

| model | mode | dimension | value | test_count | error_count | error_rate |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | archive | generator | structured | 31 | 1 | 0.032258 |
| baseline | archive | size | 16384 | 48 | 1 | 0.020833 |
| baseline | balanced | generator | structured | 31 | 1 | 0.032258 |
| baseline | balanced | size | 16384 | 48 | 1 | 0.020833 |
| baseline | fast_access | generator | small_alphabet | 34 | 1 | 0.029412 |
| baseline | fast_access | generator | structured | 31 | 1 | 0.032258 |
| baseline | fast_access | size | 16384 | 48 | 2 | 0.041667 |
| decision_tree | archive | generator | structured | 31 | 4 | 0.129032 |
| decision_tree | archive | size | 16384 | 48 | 1 | 0.020833 |
| decision_tree | archive | size | 65536 | 44 | 1 | 0.022727 |
| decision_tree | archive | size | 262144 | 51 | 1 | 0.019608 |
| decision_tree | archive | size | 1048576 | 59 | 1 | 0.016949 |
| decision_tree | balanced | generator | structured | 31 | 1 | 0.032258 |
| decision_tree | balanced | size | 16384 | 48 | 1 | 0.020833 |
| decision_tree | fast_access | generator | small_alphabet | 34 | 1 | 0.029412 |
| decision_tree | fast_access | generator | structured | 31 | 5 | 0.161290 |
| decision_tree | fast_access | size | 16384 | 48 | 3 | 0.062500 |
| decision_tree | fast_access | size | 65536 | 44 | 1 | 0.022727 |
| decision_tree | fast_access | size | 262144 | 51 | 2 | 0.039216 |
| random_forest | archive | generator | structured | 31 | 2 | 0.064516 |
| random_forest | archive | size | 16384 | 48 | 1 | 0.020833 |
| random_forest | archive | size | 65536 | 44 | 1 | 0.022727 |
| random_forest | balanced | generator | structured | 31 | 1 | 0.032258 |
| random_forest | balanced | size | 16384 | 48 | 1 | 0.020833 |
| random_forest | fast_access | generator | small_alphabet | 34 | 1 | 0.029412 |
| random_forest | fast_access | generator | structured | 31 | 2 | 0.064516 |
| random_forest | fast_access | size | 16384 | 48 | 2 | 0.041667 |
| random_forest | fast_access | size | 65536 | 44 | 1 | 0.022727 |

## Confidence와 정오답

| model | mode | correct | count | confidence_min | confidence_mean | confidence_max | confidence_equal_one_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| decision_tree | archive | False | 4 | 1.000000 | 1.000000 | 1.000000 | 4 |
| decision_tree | archive | True | 198 | 1.000000 | 1.000000 | 1.000000 | 198 |
| decision_tree | balanced | False | 1 | 1.000000 | 1.000000 | 1.000000 | 1 |
| decision_tree | balanced | True | 201 | 1.000000 | 1.000000 | 1.000000 | 201 |
| decision_tree | fast_access | False | 6 | 1.000000 | 1.000000 | 1.000000 | 6 |
| decision_tree | fast_access | True | 196 | 1.000000 | 1.000000 | 1.000000 | 196 |
| random_forest | archive | False | 2 | 0.540000 | 0.770000 | 1.000000 | 1 |
| random_forest | archive | True | 200 | 0.590000 | 0.992700 | 1.000000 | 188 |
| random_forest | balanced | False | 1 | 1.000000 | 1.000000 | 1.000000 | 1 |
| random_forest | balanced | True | 201 | 0.560000 | 0.991592 | 1.000000 | 186 |
| random_forest | fast_access | False | 3 | 0.540000 | 0.846667 | 1.000000 | 2 |
| random_forest | fast_access | True | 199 | 0.590000 | 0.988442 | 1.000000 | 170 |

## 오분류 손실의 지표별 기여

각 항은 w × (예측 알고리즘의 로그 상대 손실 − oracle의 로그 상대 손실)이다. 음수는 그 지표에서 예측 알고리즘이 더 좋았다는 뜻이며, 세 항의 합은 regret이다.

| model | sample_id | mode | size_regret | compression_regret | decompression_regret | regret |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | sample_000916 | archive | 0.084526 | -0.128012 | 0.131320 | 0.087834 |
| baseline | sample_000916 | balanced | 0.060376 | -0.213354 | 0.218867 | 0.065889 |
| baseline | sample_000916 | fast_access | 0.036225 | -0.170683 | 0.437734 | 0.303277 |
| baseline | sample_000841 | fast_access | 0.022519 | -0.452165 | 0.516556 | 0.086910 |
| decision_tree | sample_000922 | archive | -0.121838 | 0.356659 | 0.038454 | 0.273275 |
| decision_tree | sample_000664 | archive | -0.145818 | 0.277437 | -0.008337 | 0.123282 |
| decision_tree | sample_000286 | archive | -0.146133 | 0.301928 | -0.034451 | 0.121345 |
| decision_tree | sample_000916 | archive | 0.084526 | -0.128012 | 0.131320 | 0.087834 |
| decision_tree | sample_000916 | balanced | 0.060376 | -0.213354 | 0.218867 | 0.065889 |
| decision_tree | sample_000922 | fast_access | -0.052216 | 0.475545 | 0.128180 | 0.551509 |
| decision_tree | sample_000604 | fast_access | -0.029397 | 0.367411 | 0.148286 | 0.486300 |
| decision_tree | sample_000916 | fast_access | 0.036225 | -0.170683 | 0.437734 | 0.303277 |
| decision_tree | sample_000664 | fast_access | -0.062493 | 0.369917 | -0.027791 | 0.279632 |
| decision_tree | sample_000256 | fast_access | -0.062794 | 0.357583 | -0.167976 | 0.126813 |
| decision_tree | sample_000841 | fast_access | 0.022519 | -0.452165 | 0.516556 | 0.086910 |
| random_forest | sample_000922 | archive | -0.121838 | 0.356659 | 0.038454 | 0.273275 |
| random_forest | sample_000916 | archive | 0.084526 | -0.128012 | 0.131320 | 0.087834 |
| random_forest | sample_000916 | balanced | 0.060376 | -0.213354 | 0.218867 | 0.065889 |
| random_forest | sample_000922 | fast_access | -0.052216 | 0.475545 | 0.128180 | 0.551509 |
| random_forest | sample_000916 | fast_access | 0.036225 | -0.170683 | 0.437734 | 0.303277 |
| random_forest | sample_000841 | fast_access | 0.022519 | -0.452165 | 0.516556 | 0.086910 |

## 특징과 해석 범위

error_details.csv에는 실제 특징과 생성 매개변수를, error_feature_context.csv에는 오류 sample의 특징별 training 범위와 누적 비율을 기록했다. train_fraction_le_value는 training 값이 해당 값 이하인 비율이다. 범위 밖 여부나 누적 비율은 관찰이며 모델 판단의 인과적 설명이 아니다.

oracle_margin은 실제 최저 점수와 두 번째 점수의 차이다. 현재 저장된 중앙값만으로 측정 변동, 통계적 유의성 또는 라벨 안정성을 판정할 수 없다. 낮은 margin을 이유로 sample을 제거하거나 정답을 바꾸지 않는다.

Confidence는 보정되지 않은 모델 출력이다. baseline의 빈칸은 해당 없음이다. confidence=1인 오분류도 그대로 보존한다. Macro F1은 네 클래스를 고정하고 없는 클래스의 F1을 0으로 포함한다.

이는 이미 사용한 합성 Pilot test의 사후 진단이다. 재학습·튜닝·압축 재측정을 수행하지 않았으며, 이 분석을 바탕으로 변경한 모델의 최종 성능은 별도 unseen 데이터에서 평가해야 한다. 기존 알고리즘 시간에는 특징 추출·예측 비용이 포함되지 않는다.
