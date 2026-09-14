# Protocol v2 Random Forest evaluation

## 실행 전 결정

Archive, Balanced, Fast Access별로 별도 Random Forest를 학습한다. 입력은
압축 전에 계산한 `FEATURE_NAMES`의 12개 특징뿐이다. sample_id, seed, generator,
압축 측정값, 점수는 모델 입력에 포함하지 않는다.

첫 모델은 `config/experiment_config.json`의 `random_forest`에 기록한 설정을
사용한다. 트리 100개, gini, 깊이 제한 없음, min_samples_split=2,
min_samples_leaf=1, max_features=sqrt, bootstrap=True, max_samples=None,
class_weight=None, ccp_alpha=0, random_state=42, n_jobs=1이다. 나머지 매개변수도
config에 명시하며 설치된 scikit-learn 1.9.0의 기본값을 사용한다. n_jobs=1은
동일 환경에서 확률 집계 순서와 재현성을 유지하기 위한 선택이다.

결과를 보고 튜닝하거나 클래스 비율을 맞추지 않는다. Bootstrap은 training 내부의
표준 Random Forest 학습 절차이며, 원시 sample 삭제나 test 재표집을 의미하지 않는다.
실제 전체 매개변수는 get_params()로 결과 JSON에 기록한다.

## 동일 조건 비교 및 검증

기존 baseline의 입력 및 출력 해시, 점수 정의, Macro F1 정의를 확인하고 저장된
seed 그룹 분할을 재사용한다. Decision Tree도 같은 baseline 분할을 사용했다.
원시 측정값으로 v2 점수를 재계산한 후 학습하며, training 특징·라벨만 fit에 전달한다.
예측 이후 기존 압축 측정값으로 평가한다. 이 단계는 압축기를 호출하지 않는다.

baseline 및 Decision Tree와 공통 입력 검증·평가 코드를 사용한다. 네 알고리즘 고정
Macro F1(`zero_division=0`), accuracy, 혼동행렬, 특징 중요도, 오분류, 예측 확률,
oracle 대비 regret을 저장한다. 전략 비교표는 항상 gzip/bz2/lzma/zstd,
training 최빈 baseline, Random Forest, oracle을 같은 test에서 비교한다.
Decision Tree의 기존 별도 비교표와도 동일 sample·지표로 비교할 수 있다.

mode별 pickle, training 성능, 트리별 깊이·잎 수, 입력·출력·코드·설정·baseline
참조 해시, Git commit, 실행 시각과 환경을 기록한다. 방금 저장한 모델을 다시 읽어
test 예측과 확률이 정확히 동일한지 확인한다. 기존 출력 경로는 덮어쓰지 않는다.

prediction_confidence는 각 트리의 잎 클래스 확률을 평균한 predict_proba의 최대값이다.
보정된 정답 확률이나 단순 다수결 투표 비율로 해석하지 않는다. 학습에 없는 클래스는
출력 확률을 0으로 채우며 확률 동률은 classes_ 순서의 첫 최대값을 따른다.
특징 중요도는 숲의 불순도 감소 기반 중요도이며 인과적 설명이 아니다.
근거: [RandomForestClassifier 공식 문서](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html).

## 실행

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m src.train_model --model random_forest --experiment-dir data/results/pilot_1008 --baseline-dir data/results/pilot_1008/baseline --output-dir data/results/pilot_1008/random_forest
```

테스트의 인위적 fixture는 연구 결과가 아니다. 연구 수치는 Python CLI가 기존 Pilot의
실제 측정 CSV에서 계산한 출력만 사용한다. 합성 Pilot에서 이미 사용한 test이므로
최종 일반화 성능은 별도 unseen 파일에서 평가해야 한다. 저장된 압축·해제 시간은
특징 추출과 모델 예측 비용을 포함하지 않는다. 다른 seed의 유사 데이터까지
탐지하는 그룹 분할은 아니므로 이 한계도 유지한다.

## 실제 Pilot 실행 기록

구현 커밋 `01259749bb0bd517765d884f3bbb31b1ed648163`의 깨끗한 작업 트리에서
위 CLI를 실행했다. 실행 전 전체 64개 테스트가 통과했다. 실제 학습 sample은 806개,
test sample은 202개이며, 결과는 `data/results/pilot_1008/random_forest/`에 저장했다.
아래 값은 Python이 생성한 CSV를 Python으로 읽어 소수점 6자리로 표시한 값이다.

| Mode | Accuracy | Macro F1 | Mean regret |
|---|---:|---:|---:|
| Archive | 0.990099 | 0.248756 | 0.001788 |
| Balanced | 0.995050 | 0.249380 | 0.000326 |
| Fast Access | 0.985149 | 0.248130 | 0.004662 |

Archive와 Fast Access에서는 Random Forest의 accuracy와 Macro F1이 Decision Tree보다
높고 mean regret이 낮았지만, training 최빈 baseline보다 좋지는 않았다. Balanced는
세 방법의 이 지표들이 같았다. 따라서 이번 Pilot에서는 Random Forest가 항상 최빈
알고리즘을 선택하는 방법을 개선했다는 근거를 얻지 못했다. 설정과 데이터는 유지한다.

Random Forest는 Archive·Fast Access에서 각각 gzip 1개, zstd 201개를 예측했고,
Balanced에서는 zstd 202개를 예측했다. 오분류 CSV는 sample × mode 기준 6행이다.
네 클래스 고정 Macro F1에는 실제 또는 예측에 없는 클래스의 F1도 0으로 포함하므로,
높은 accuracy와 약 0.25의 Macro F1을 함께 해석해야 한다.

사후 검증에서 summary에 기록된 출력 11개 파일의 SHA-256을 대조했다. baseline,
Decision Tree, Random Forest의 split_assignments.csv는 바이트 단위로 일치했다.
원시 측정 CSV와 기존 평가 결과는 변경하지 않았다. 최종 일반화 결론은 별도의
unseen 평가로 남기며, 상세 실패 사례 분석은 다음 연구 단계에서 수행한다.
