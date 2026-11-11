# 실제 60개 파일의 특징 기준선 측정 결과 — 2026-11-11

**기준선 측정·독립 감사 완료. 최적화 구현/속도 개선 실험은 아직 없다.**

[사전 계획](feature_profile_design_20261109.md) · [구현/fixture](feature_profile_implementation_20261111.md) · [원시 독립 감사](../data/results/feature_profile_baseline_20261109_01/verification.json) · [완료 기록](../data/results/feature_profile_baseline_20261109_01/complete.json) · [함수별 집계](../data/results/feature_profile_baseline_analysis_20261111_01/helper_summary.csv) · [비중복 분해 원시값](../data/results/feature_profile_baseline_analysis_20261111_01/raw_disjoint_partition.csv) · [추가 집계 감사](../data/results/feature_profile_baseline_analysis_20261111_01/analysis.json)

실행 source HEAD는 `642a733f7fecea15e95b329fe86d505e43f85324`다. 기존 원본 60개 full hash/크기를 확인하고 저장 특징 720개와 기존 모델의 단일 행 예측·확률/비보정 confidence 1,080개를 정확히 대조했다. 네 fresh worker에서 본 측정 1,200회와 warmup 240회를 수행했고 모든 slot·호출 tree·raw 기록의 독립 검증을 통과했다. 실패/중단·재시도·파일/반복 교체는 없었다.

## 비계측 시간과 계측 시간

| 모드 | 파일별 5회 중앙값의 평균 ms | 파일별 중앙값들의 중앙값 ms | p90 ms |
|---|---:|---:|---:|
| extract_and_frame | 66.066533 | 34.949400 | 139.395840 |
| extract_only | 58.727250 | 30.165200 | 133.873010 |
| frame_only | 0.720367 | 0.722800 | 0.853230 |
| instrumented_extract | 64.209005 | 34.836500 | 133.008240 |

extract_only는 통계 특징 계산, frame_only는 검증한 특징에서 pandas 입력 준비, extract_and_frame은 두 작업의 결합 범위다. 입력은 메모리의 bytes이고 읽기/hash·사전 검증·model load는 timer 밖이다. 각 모드는 별도 프로세스이므로 독립 중앙값을 더하거나 결합−특징 차이를 입력 준비의 직접 시간으로 해석하지 않는다.

계측−비계측의 파일별 중앙값 차이 평균은 5.481755ms, 범위는 -71.689400~60.513900ms였다. wrapper 비용과 고정 mode 순서·OS cache·실행 간 변동이 함께 들어 있다. 음의 차이도 삭제하지 않았다. 과거 54~66ms 결과와 이번 수치만 비교해 속도 개선/악화를 주장하지 않는다.

## 함수별 병목

| 구간 | 파일별 helper 중앙값의 평균 ms | 계측 raw root 시간의 비중 |
|---|---:|---:|
| _bigram_diversity | 24.911515 | 39.3633% |
| _run_statistics | 18.866457 | 29.7661% |
| _segment_entropy_statistics | 8.345798 | 13.3236% |
| Counter | 7.695887 | 12.3847% |
| _duplicate_block_ratio | 2.980828 | 4.8299% |
| extract_features_self | 0.153418 | 0.2575% |
| _entropy_from_counts | 0.042342 | 0.0748% |

바이트 쌍 다양성(`_bigram_diversity`)과 연속값 통계(`_run_statistics`)가 합쳐 **69.1294%**를 차지했다. 다음 최적화 후보는 이 두 구간을 우선 검토하는 것이 타당하다. 함수별 계측 시간 비중이며, 이만큼 프로그램을 빠르게 만들 수 있다는 뜻은 아니다.

비중의 분모는 warmup을 제외한 300개 계측 trial의 root inclusive ns 합이다. 분자는 root의 직접 자식 시간과 root self 시간을 trial마다 먼저 분해한 뒤 정수 ns로 합쳤다. 모든 trial에서 합계가 root와 정확히 일치했다. 구간 엔트로피 안의 Counter/entropy는 그 구간 안에 포함하므로 이 표에 다시 합산하지 않는다. 전체 histogram Counter와 전체 entropy만 root 직접 자식으로 표시했다. Self에는 wrapper/기록 overhead와 나머지 계산이 들어 있다.

표의 평균 helper 중앙값은 별도의 기술 통계다. helper의 독립 중앙값들을 더해 root 중앙값을 만들거나 그 비율을 100%로 맞추지 않았다. 모든 형식/원본 그룹과 ≤64KiB,(64,256]KiB,>256KiB 집계는 원래 summary.csv에 보존했다.

## 검증·해석과 다음 작업

사전 계획/코드·모델/runtime hash, 원본 bytes, 정확 feature/frame/prediction gate, full schedule, 호출 구간 포함/직접 자식 비중복/self 합·helper 횟수와 raw ns를 검증했다. 새 계산부는 기존 verification manifest의 모든 파일을 다시 hash 확인하고, 함수별 비중복 분해를 독립 집계했다. 기존 보호 근거와 source도 그대로다. 새 연구 숫자는 모두 저장 raw를 Python으로 읽어 계산했다.

관찰된 60개 파일은 개발 자료다. 이번 profile은 선택 정확도 개선·전체 비용 이득·실제 GUI/CLI·cold start·memory·모집단 성능을 입증하지 않는다. 사용자 동시 작업/전원 사건의 부재는 확인하지 않았으며 notes에 미제공 상태를 남겼다. 전원 설정을 바꾸지 않았다. 공식 score/라벨/모델/config·memory 보류 방침을 유지했다.

다음 단일 작업은 bigram/run 통계를 우선 대상으로 한 **기존 특징값 보존 최적화 후보와 같은 시점의 reference/candidate paired 검증 계획**이다. 정수 count와 나눗셈 정의·dtype/float.hex·전체 frame/예측을 그대로 보존하고, 새 source/계획을 고정한 뒤 새 경로에서 실측한다. 이 기준선만으로 예상 향상률이나 zstd 선택 비율을 정하지 않는다.
