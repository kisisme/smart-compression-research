# 후보 모델 학습·실제 파일 검증 결과 — 2026-10-31

**범위: 고정된 가상 총비용 정책의 후보 실험. 공식 점수·모델 전환이 아니다. 모든 결과를 보존한다.**

[실행 전 기준](usage_model_study_design_20261031.md) · [계획](usage_model_study_plan_20261031.json) · [코드](run_usage_model_study_20261031.py) · [원시/저장 검증](../data/results/usage_candidate_study_20261031_01/audit.json)

## 완료 범위

후보 모델 18개, 실제 파일 60개, 사전 예측 1080개를 보존했다. 기존 train 부분만 학습하고 원래 test는 개발 진단으로 구분했다. 원본/권리·notice·기존 재생성 hash 겹침 근거를 동결한 자료 전체를 사용했다. Generic manifest의 evaluation_ready=false와 독립성/익명성 미인증·과거 합성 원본 hash 미저장 한계를 유지한다.

실제 파일의 특징/모델 예측을 네 압축기 benchmark 전에 동결했다. Codec 반복 2,400개와 검증용 package 엔진 trial 5,700개 모두 원시 기록/저장 복원 검증을 확인했다. 기존 보호 파일 268개는 그대로다. Memory는 측정/점수 편입하지 않았다.

## 순수 codec 측정값에서 후보 모델 비교

| 가상 시나리오 | 모델 | Accuracy | Macro F1 | zstd 대비 총비용 절감 | 그룹 평균 차이 vs train-majority ↓ |
|---|---|---:|---:|---:|---:|
| archive_t0p1 | decision_tree | 0.6000 | 0.2617 | 0.1406% | -0.12064548 |
| archive_t0p1 | random_forest | 0.6333 | 0.3264 | 0.1245% | -0.04707239 |
| archive_t1 | decision_tree | 1.0000 | 0.2500 | 0.0000% | 0.00000000 |
| archive_t1 | random_forest | 1.0000 | 0.2500 | 0.0000% | 0.00000000 |
| archive_t10 | decision_tree | 1.0000 | 0.2500 | 0.0000% | 0.00000000 |
| archive_t10 | random_forest | 1.0000 | 0.2500 | 0.0000% | 0.00000000 |
| balanced_t0p1 | decision_tree | 0.9667 | 0.2458 | 0.0000% | 0.00000000 |
| balanced_t0p1 | random_forest | 0.9667 | 0.2458 | 0.0000% | 0.00000000 |
| balanced_t1 | decision_tree | 0.6000 | 0.2054 | -15.5028% | 1.67688623 |
| balanced_t1 | random_forest | 0.9667 | 0.2458 | 0.0000% | 0.00000000 |
| balanced_t10 | decision_tree | 0.9667 | 0.2458 | 0.0000% | 0.00000000 |
| balanced_t10 | random_forest | 0.9667 | 0.2458 | 0.0000% | 0.00000000 |
| fast_access_t0p1 | decision_tree | 0.7500 | 0.2430 | -33.4806% | 2.05836514 |
| fast_access_t0p1 | random_forest | 0.9667 | 0.2458 | 0.0000% | 0.00000000 |
| fast_access_t1 | decision_tree | 0.7500 | 0.2430 | -33.7255% | 20.59349814 |
| fast_access_t1 | random_forest | 0.9667 | 0.2458 | 0.0000% | 0.00000000 |
| fast_access_t10 | decision_tree | 0.7500 | 0.2430 | -33.7502% | 205.94482814 |
| fast_access_t10 | random_forest | 0.9667 | 0.2458 | 0.0000% | 0.00000000 |

양의 그룹 평균 차이는 train-majority보다 손실이 큼을 뜻한다. 음수 절감률은 zstd보다 정책 비용이 증가한 것이다. 모든 고정 압축기·train-majority·모델·oracle의 혼동행렬/선택 수·크기·시간·비용/평균·최대 regret는 [전체 지표](../data/results/usage_candidate_study_20261031_01/evaluation/codec_metrics.json)와 [파일별 선택](../data/results/usage_candidate_study_20261031_01/evaluation/strategy_choices.csv)에 있다. 네 클래스 고정 Macro F1이며 미등장 클래스도 제외하지 않는다. 확률 출력은 보정된 정답 확률이 아니다.

## 특징·예측·검증·저장을 포함한 검증용 엔진

| 가상 시나리오 | 모델 | 상주 모델 총비용 절감 vs 고정 zstd | 평균 특징 ms | 평균 예측 ms | 모델 load 중앙값 ms |
|---|---|---:|---:|---:|---:|
| archive_t0p1 | decision_tree | -56.3545% | 64.0463 | 2.8645 | 18.6439 |
| archive_t0p1 | random_forest | -72.9124% | 61.1765 | 20.0829 | 36.9970 |
| archive_t1 | decision_tree | -309.9769% | 62.0577 | 2.6579 | 16.2879 |
| archive_t1 | random_forest | -371.3896% | 58.3699 | 19.1283 | 27.1480 |
| archive_t10 | decision_tree | -538.9779% | 57.8998 | 2.5050 | 17.1605 |
| archive_t10 | random_forest | -708.5165% | 59.2798 | 19.5652 | 25.4368 |
| balanced_t0p1 | decision_tree | -34.4592% | 60.3821 | 2.5533 | 18.3790 |
| balanced_t0p1 | random_forest | -45.5792% | 61.2967 | 19.6612 | 30.0697 |
| balanced_t1 | decision_tree | -36.2271% | 59.0985 | 2.5562 | 17.5607 |
| balanced_t1 | random_forest | -50.7164% | 59.6025 | 20.7680 | 28.3037 |
| balanced_t10 | decision_tree | -35.9084% | 59.4149 | 2.6182 | 17.2562 |
| balanced_t10 | random_forest | -47.2745% | 58.4114 | 19.7820 | 31.1302 |
| fast_access_t0p1 | decision_tree | -8.0092% | 59.2893 | 2.6995 | 19.5725 |
| fast_access_t0p1 | random_forest | -14.7075% | 61.0352 | 21.3280 | 31.9533 |
| fast_access_t1 | decision_tree | -21.1995% | 66.1165 | 2.7154 | 19.0407 |
| fast_access_t1 | random_forest | -16.4930% | 57.5965 | 20.7550 | 33.9954 |
| fast_access_t10 | decision_tree | -6.3635% | 54.4484 | 2.5129 | 19.7926 |
| fast_access_t10 | random_forest | -26.2600% | 55.5869 | 22.9980 | 31.6113 |

파일 읽기→hash→특징→예측→선택한 압축기 하나→복원/byte 검증→research payload/manifest 저장과, 다시 읽기→해제→크기/hash 검증→원래 이름으로 복원 저장을 각각 실측했다. Package bytes와 각 phase 중앙값을 정책 비용에 넣었다. 음수 절감은 이 범위에서 전체 경로가 고정 zstd보다 불리하다는 결과다. 모델 로딩은 별도 실측이며 상주 모델 경로 밖이다. 로딩을 추가한 비용 proxy도 [전체 경로 지표](../data/results/usage_candidate_study_20261031_01/evaluation/pipeline_metrics.csv)에 구분했다. Python 시작/cold cache·fsync·실제 GUI/CLI 배포·모델 배포 공간·네트워크·CPU/전력/메모리 비용은 검증하지 않았다.

## 해석 한계와 보존

시나리오의 보관 기간·복원 횟수·정책점수 교환비는 사전 선언한 가정이며 실제 사용량/요금이 아니다. 고정 알고리즘/phase 순서와 OS cache가 있으며, 저장 중앙값을 꼬리/실시간 지연 보장으로 해석하지 않는다. 비확률 형식 quota·알려진 원본 관계가 있는 단일 외부 corpus의 기술적 비교로 제한한다. 통계적 유의성이나 전체 실제 파일 모집단의 개선을 주장하지 않고, 유리한 시나리오/모델만 선택하지 않는다.

기존 공식 score·라벨·모델/config와 memory 참고 방침을 유지했다. 새 자료를 학습/튜닝·class balancing·calibration에 쓰지 않았다. GUI 수동 Compare 저장 검증/전체 시각 QA는 이 연구용 엔진 검증과 별개의 미완료 항목이다.
