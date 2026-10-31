# zstd 선택의 누락 사례 전수 분석 — 2026-10-31

후보 모델의 사전 동결 예측 1080건을 모두 대조했다. zstd 선택 995건 중 다른 압축기의 가상 정책 비용이 엄격히 낮았던 경우는 **57건**이다. 중복을 제거하면 **파일 21개·파일×시나리오 32개**다. 같은 파일을 두 모델/여러 시나리오가 반복 평가하므로 독립적인 파일 수와 구분한다.

범위는 직전 실험의 실제 파일 60개×가상 비용 시나리오 9개×DT/RF다. ‘다른 모델’은 비교 압축기 gzip/bz2/LZMA로 해석했다. 공식 v2 저장 모델의 별도 외부 평가가 아니다. 새 압축·학습·예측은 수행하지 않았다.

[전체 누락 57건](../data/results/usage_zstd_misses_20261031_01/missed_cases.csv) · [더 좋았던 대안 전부 59건](../data/results/usage_zstd_misses_20261031_01/better_alternatives.csv) · [중복 제거 파일](../data/results/usage_zstd_misses_20261031_01/unique_files.csv) · [18개 조건 요약](../data/results/usage_zstd_misses_20261031_01/scenario_model_summary.csv) · [원시 반복 범위](../data/results/usage_zstd_misses_20261031_01/timing_repeat_summary.csv) · [검증 근거](../data/results/usage_zstd_misses_20261031_01/audit.json)

## 판정과 비용

`J = k_s H B + k_c T_c + k_d N T_d`를 고정된 정책과 저장된 크기/압축 시간/복원 시간 중앙값으로 재계산했다. `모델 예측=zstd`이고 `J(대안)<J(zstd)`일 때만 누락이다. 최저 비용이 아닌 대안도 zstd보다 좋으면 전부 포함한다. 정확 동점은 누락에서 제외하며 작은 차이를 지우는 epsilon은 쓰지 않는다. 이 비율은 압축률이나 실제 요금이 아니라 가상 정책 비용 절감률이다.

Archive는 365일 보관·1회 복원, Balanced는 30일·30회, Fast Access는 1일·100회다. `t0p1/t1/t10`은 압축·복원 시간 비용의 0.1/1/10배다. 공식 가중치·memory·모델을 변경하지 않았다.

## 전체 조건

| 조건 | 모델 | zstd 선택/60 | zstd 누락/선택 | zstd 최저 비용 동점 | 잘못 바꾼 비-zstd |
|---|---|---:|---:|---:|---:|
| archive_t0p1 | decision_tree | 54 | 20 | 0 | 4 |
| archive_t0p1 | random_forest | 50 | 17 | 0 | 5 |
| archive_t1 | decision_tree | 60 | 0 | 0 | 0 |
| archive_t1 | random_forest | 60 | 0 | 0 | 0 |
| archive_t10 | decision_tree | 60 | 0 | 0 | 0 |
| archive_t10 | random_forest | 60 | 0 | 0 | 0 |
| balanced_t0p1 | decision_tree | 60 | 2 | 0 | 0 |
| balanced_t0p1 | random_forest | 60 | 2 | 0 | 0 |
| balanced_t1 | decision_tree | 36 | 1 | 0 | 23 |
| balanced_t1 | random_forest | 60 | 2 | 0 | 0 |
| balanced_t10 | decision_tree | 60 | 2 | 0 | 0 |
| balanced_t10 | random_forest | 60 | 2 | 0 | 0 |
| fast_access_t0p1 | decision_tree | 45 | 1 | 0 | 14 |
| fast_access_t0p1 | random_forest | 60 | 2 | 0 | 0 |
| fast_access_t1 | decision_tree | 45 | 1 | 0 | 14 |
| fast_access_t1 | random_forest | 60 | 2 | 0 | 0 |
| fast_access_t10 | decision_tree | 45 | 1 | 0 | 14 |
| fast_access_t10 | random_forest | 60 | 2 | 0 | 0 |

‘잘못 바꾼 비-zstd’는 모델이 다른 압축기를 선택했지만 고정 zstd보다 비용이 큰 경우다. zstd 비중을 낮추기만 하면 이 손실도 늘 수 있다. 조건별 절대 비용 합계는 서로 다른 정책끼리 더하지 않는다.

## 중복 제거 파일 전체

| 파일 ID / 이름 | 형식 | 놓친 예측 수 | 최저 비용 압축기 | 파일별 절감 범위 |
|---|---|---:|---|---:|
| cldr_01 / dateFields.json | json | 2 | gzip | 8.3284~8.3284% |
| curl_01 / CIPHERS-TLS12.md | text | 8 | gzip | 0.3614~24.9678% |
| git_01 / api-trace2.adoc | text | 2 | gzip | 0.7120~0.7120% |
| google_fonts_02 / Abel-Regular.ttf | binary | 2 | gzip | 1.5072~1.5072% |
| google_fonts_04 / Acme-Regular.ttf | binary | 2 | gzip | 0.2486~0.2486% |
| mlperf_inference_01 / mlperf_log_detail.txt | log | 2 | bz2 | 1.9253~1.9253% |
| mlperf_inference_03 / mlperf_log_detail.txt | log | 14 | gzip;bz2 | 2.6159~52.2901% |
| mlperf_inference_04 / mlperf_log_detail.txt | log | 2 | bz2 | 1.7335~1.7335% |
| mlperf_inference_05 / mlperf_log_detail.txt | log | 2 | bz2 | 0.2357~0.2357% |
| natural_earth_02 / ne_110m_geography_marine_polys.shp | binary | 2 | gzip | 2.0332~2.0332% |
| pandas_01 / config.py | python | 2 | gzip | 1.0360~1.0360% |
| pandas_02 / _typing.py | python | 2 | gzip | 1.2959~1.2959% |
| pandas_03 / extensions.py | python | 2 | gzip | 2.3203~2.3203% |
| pandas_05 / apply.py | python | 2 | gzip | 0.7361~0.7361% |
| uci_biodegradation_01 / biodeg.csv | csv | 1 | bz2 | 8.3295~8.3295% |
| uci_wine_01 / winequality-red.csv | csv | 1 | bz2 | 2.2716~2.2716% |
| uci_wine_02 / winequality-white.csv | csv | 1 | bz2 | 2.4900~2.4900% |
| vscode_01 / package.json | json | 2 | gzip | 0.0743~0.0743% |
| vscode_02 / package.json | json | 2 | gzip | 1.8771~1.8771% |
| vscode_04 / package.json | json | 2 | gzip | 0.1954~0.1954% |
| vscode_05 / package.json | json | 2 | gzip | 4.4740~4.4740% |

같은 이름의 package.json/log는 파일 ID가 다르다. CSV의 상대 경로·full SHA-256·고정 source locator로 구분한다.

## 누락 57건의 전체 목록

절감률은 해당 파일에서 `(J(zstd)−J(최저 비용))/J(zstd)×100`이다. 더 좋았던 대안은 최저 비용 순서가 아니라 고정 압축기 순서로 나열했다. 원래 float 정밀도 비용과 압축 크기/시간/성분별 차이는 CSV에 보존했다.

| 조건 | 모델 | 파일 ID | 최저 비용 | 더 좋은 대안 전부 | 절감률 |
|---|---|---|---|---|---:|
| archive_t0p1 | decision_tree | cldr_01 | gzip | gzip | 8.3284% |
| archive_t0p1 | decision_tree | git_01 | gzip | gzip | 0.7120% |
| archive_t0p1 | decision_tree | google_fonts_02 | gzip | gzip | 1.5072% |
| archive_t0p1 | decision_tree | google_fonts_04 | gzip | gzip | 0.2486% |
| archive_t0p1 | decision_tree | mlperf_inference_01 | bz2 | bz2 | 1.9253% |
| archive_t0p1 | decision_tree | mlperf_inference_03 | bz2 | bz2 | 2.6159% |
| archive_t0p1 | decision_tree | mlperf_inference_04 | bz2 | bz2 | 1.7335% |
| archive_t0p1 | decision_tree | mlperf_inference_05 | bz2 | bz2 | 0.2357% |
| archive_t0p1 | decision_tree | natural_earth_02 | gzip | gzip;lzma | 2.0332% |
| archive_t0p1 | decision_tree | pandas_01 | gzip | gzip | 1.0360% |
| archive_t0p1 | decision_tree | pandas_02 | gzip | gzip | 1.2959% |
| archive_t0p1 | decision_tree | pandas_03 | gzip | gzip | 2.3203% |
| archive_t0p1 | decision_tree | pandas_05 | gzip | gzip | 0.7361% |
| archive_t0p1 | decision_tree | uci_biodegradation_01 | bz2 | bz2 | 8.3295% |
| archive_t0p1 | decision_tree | uci_wine_01 | bz2 | bz2 | 2.2716% |
| archive_t0p1 | decision_tree | uci_wine_02 | bz2 | bz2 | 2.4900% |
| archive_t0p1 | decision_tree | vscode_01 | gzip | gzip | 0.0743% |
| archive_t0p1 | decision_tree | vscode_02 | gzip | gzip | 1.8771% |
| archive_t0p1 | decision_tree | vscode_04 | gzip | gzip | 0.1954% |
| archive_t0p1 | decision_tree | vscode_05 | gzip | gzip | 4.4740% |
| archive_t0p1 | random_forest | cldr_01 | gzip | gzip | 8.3284% |
| archive_t0p1 | random_forest | git_01 | gzip | gzip | 0.7120% |
| archive_t0p1 | random_forest | google_fonts_02 | gzip | gzip | 1.5072% |
| archive_t0p1 | random_forest | google_fonts_04 | gzip | gzip | 0.2486% |
| archive_t0p1 | random_forest | mlperf_inference_01 | bz2 | bz2 | 1.9253% |
| archive_t0p1 | random_forest | mlperf_inference_03 | bz2 | bz2 | 2.6159% |
| archive_t0p1 | random_forest | mlperf_inference_04 | bz2 | bz2 | 1.7335% |
| archive_t0p1 | random_forest | mlperf_inference_05 | bz2 | bz2 | 0.2357% |
| archive_t0p1 | random_forest | natural_earth_02 | gzip | gzip;lzma | 2.0332% |
| archive_t0p1 | random_forest | pandas_01 | gzip | gzip | 1.0360% |
| archive_t0p1 | random_forest | pandas_02 | gzip | gzip | 1.2959% |
| archive_t0p1 | random_forest | pandas_03 | gzip | gzip | 2.3203% |
| archive_t0p1 | random_forest | pandas_05 | gzip | gzip | 0.7361% |
| archive_t0p1 | random_forest | vscode_01 | gzip | gzip | 0.0743% |
| archive_t0p1 | random_forest | vscode_02 | gzip | gzip | 1.8771% |
| archive_t0p1 | random_forest | vscode_04 | gzip | gzip | 0.1954% |
| archive_t0p1 | random_forest | vscode_05 | gzip | gzip | 4.4740% |
| balanced_t0p1 | decision_tree | curl_01 | gzip | gzip | 0.3659% |
| balanced_t0p1 | decision_tree | mlperf_inference_03 | gzip | gzip | 26.4448% |
| balanced_t0p1 | random_forest | curl_01 | gzip | gzip | 0.3659% |
| balanced_t0p1 | random_forest | mlperf_inference_03 | gzip | gzip | 26.4448% |
| balanced_t1 | decision_tree | mlperf_inference_03 | gzip | gzip | 29.8375% |
| balanced_t1 | random_forest | curl_01 | gzip | gzip | 0.3619% |
| balanced_t1 | random_forest | mlperf_inference_03 | gzip | gzip | 29.8375% |
| balanced_t10 | decision_tree | curl_01 | gzip | gzip | 0.3614% |
| balanced_t10 | decision_tree | mlperf_inference_03 | gzip | gzip | 30.2426% |
| balanced_t10 | random_forest | curl_01 | gzip | gzip | 0.3614% |
| balanced_t10 | random_forest | mlperf_inference_03 | gzip | gzip | 30.2426% |
| fast_access_t0p1 | decision_tree | mlperf_inference_03 | gzip | gzip | 52.1970% |
| fast_access_t0p1 | random_forest | curl_01 | gzip | gzip | 24.9104% |
| fast_access_t0p1 | random_forest | mlperf_inference_03 | gzip | gzip | 52.1970% |
| fast_access_t1 | decision_tree | mlperf_inference_03 | gzip | gzip | 52.2817% |
| fast_access_t1 | random_forest | curl_01 | gzip | gzip | 24.9626% |
| fast_access_t1 | random_forest | mlperf_inference_03 | gzip | gzip | 52.2817% |
| fast_access_t10 | decision_tree | mlperf_inference_03 | gzip | gzip | 52.2901% |
| fast_access_t10 | random_forest | curl_01 | gzip | gzip | 24.9678% |
| fast_access_t10 | random_forest | mlperf_inference_03 | gzip | gzip | 52.2901% |

## 읽을 수 있는 패턴과 한계

Archive 시간 비용 0.1배에서 누락 37건이 발생했다. 여기서 최저 비용 압축기별 누락은 {'gzip': 26, 'bz2': 11}이다. 이는 저장 크기의 이득으로 시간 손실을 상쇄하는 경우를 포함한다. 나머지 Archive 조건에서는 더 나은 비-zstd가 없었다.

여러 조건에서 반복된 아래 두 파일은 크기만으로 설명되지 않는다. 아래 표는 측정 중앙값이며, 시간의 단위는 ms다.

| 파일 | 압축기 | 압축 bytes | 압축 ms | 복원 ms |
|---|---|---:|---:|---:|
| curl_01 | gzip | 4125 | 2.1917 | 0.1034 |
| curl_01 | bz2 | 3327 | 7.0034 | 1.3916 |
| curl_01 | lzma | 2800 | 46.1057 | 1.1216 |
| curl_01 | zstd | 4141 | 0.4319 | 0.1627 |
| mlperf_inference_03 | gzip | 65308 | 35.9256 | 1.1781 |
| mlperf_inference_03 | bz2 | 57877 | 31.7885 | 15.2259 |
| mlperf_inference_03 | lzma | 60836 | 146.9707 | 13.9061 |
| mlperf_inference_03 | zstd | 70115 | 7.9466 | 3.1429 |

특히 반복 복원이 많은 정책에서는 측정된 복원 시간 차이가 누적된다. 이 두 파일의 정확한 차이는 대안 CSV와 원시 반복 범위에서 확인할 수 있다. 저장된 5회 반복 중앙값 기준의 기술적 결과이며, 측정 순서/OS cache·작은 시간 차이의 재현성·통계적 유의성은 이 분석만으로 확정하지 않는다. 원시 반복을 삭제하거나 재선별하지 않았다.

이 목록은 모델이 놓친 **관측 사례**다. 파일 형식/통계 특징이 예측 실패의 원인이라는 인과 증명이나 모델 경로/특징 중요도 분석은 하지 않았다. Confidence는 보정되지 않은 기존 출력을 참고용으로만 연결했다. 모델을 다시 학습하거나 zstd에 벌점을 주는 근거로 자동 적용하지 않는다.

순수 codec 선택의 개선 여지이며 특징 추출/추론/검증/저장 비용까지 회복한다는 뜻은 아니다. 기존 전체 경로 평가의 모든 후보 조건에서 비용이 증가한 결과는 그대로다. 이후 이 60개를 이용해 튜닝하면 개발 자료이며 새 원본 그룹의 최종 holdout이 필요하다.

## 검증

선택 기록 4,320행 중 두 모델 1080행을 사전 동결 예측과 대조했다. 네 압축기 측정 240행을 모두 verified/status 확인했고, 2,400개 원시 시간 슬롯에서 5회 중앙값을 다시 계산했다. 540개 파일×정책의 네 비용은 기존 계산부와 별도 Fraction 계산을 대조했다. 선택/정답/비용/동점 판정과 모든 대안의 누락·중복을 검사했다. Fraction 대조의 허용 오차는 산술 검증용이며 사례 선정에는 쓰지 않았다.

기존 study 전체 파일의 실행 전후 SHA-256을 대조했다. 새 분석·시나리오 원문·공식 protocol/config·실행 환경과 Git HEAD는 audit에 남겼다. 원시 연구 파일과 기존 보고서는 덮어쓰지 않았다.
