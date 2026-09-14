# Protocol v2 Decision Tree evaluation

## 실행 전 결정

첫 Decision Tree는 mode마다 따로 학습한다. 압축 전에 계산하는 `FEATURE_NAMES`의
12개 특징만 입력한다. sample_id, seed, generator, 압축 측정값, 종합 점수는 모델의
입력에 포함하지 않는다. ID는 행 정렬·연결에만, seed는 그룹 분할 확인에만 사용한다.

`config/experiment_config.json`에 다음 초기 설정을 기록한다. scikit-learn 기본 트리에
고정 random_state를 적용하는 첫 기준 모델이며, Pilot test 성능을 보고 튜닝하지 않는다.

```json
{
  "criterion": "gini", "splitter": "best", "max_depth": null,
  "min_samples_split": 2, "min_samples_leaf": 1, "max_features": null,
  "class_weight": null, "ccp_alpha": 0.0, "random_state": 42
}
```

깊이 제한이나 가지치기, class 가중치 조절, 재표집은 적용하지 않는다. 실제 전체
estimator 매개변수는 `get_params()`로 결과 JSON에 기록한다. 이 설정으로 과적합하거나
baseline보다 성능이 낮아져도 그대로 보존한다. 추후 튜닝은 training 내부의 그룹
교차검증 등 별도 설계가 필요하다.

## 동일 조건 비교

baseline의 기존 입력 해시, 점수 정의, Macro F1 정의, 결과 파일 해시를 확인한다.
저장된 split_assignments.csv가 현재 seed 그룹 분할과 일치할 때만 그 분할을 사용한다.
각 mode의 training 최빈값도 baseline 기록과 대조한다. 원시 입력 검증과 점수 재계산,
평가 함수는 baseline과 공유하며 원시 CSV와 기존 baseline 결과는 변경하지 않는다.

학습에는 training 특징·라벨만 전달한다. test 특징으로 예측을 끝낸 후 해당 sample의
기존 압축 측정값과 실제 종합 점수를 이용해 평가한다. 이 과정은 압축기를 호출하지 않는다.

저장 항목:

- test accuracy, 네 클래스 고정 Macro F1(`zero_division=0`), 혼동행렬
- test 예측 및 특징을 포함한 오분류, oracle 대비 score regret
- 항상 네 알고리즘 각각, training 최빈 baseline, Decision Tree, oracle의 동일 test 비교
- mode별 실제 모델 pickle, 모델에서 추출한 분기 규칙, 특징 중요도
- training accuracy/Macro F1, 실제 깊이·잎 수·클래스·매개변수
- 입력·출력·코드·설정·baseline 참조 해시, Git commit, 실행 시각과 실행 환경

저장 직후 모델을 다시 읽어 test 예측과 확률이 정확히 같은지 확인한다. pickle은 이
프로그램이 생성한 모델을 동일한 의존성 환경에서 다시 읽기 위한 형식이다.
분기 규칙 텍스트는 표시용으로 소수를 반올림하며 실제 예측은 저장된 모델을 사용한다.

특징 중요도는 학습 트리의 정규화된 불순도 감소량이다. 인과적 설명으로 해석하지 않는다.
`prediction_confidence`는 `predict_proba`의 최대값, 즉 해당 잎의 클래스 비율이다.
보정된 정답 확률이 아니며, 순수한 잎에서 1이어도 test에서 틀릴 수 있다. 학습에
등장하지 않은 클래스의 확률은 출력에서 0으로 채운다. 확률 동률은 scikit-learn의
`classes_` 순서에서 첫 최대값을 따른다.
근거: [DecisionTreeClassifier 공식 문서](https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeClassifier.html).

## 실행

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m src.train_model --model decision_tree --experiment-dir data/results/pilot_1008 --baseline-dir data/results/pilot_1008/baseline --output-dir data/results/pilot_1008/decision_tree
```

출력 경로가 이미 있으면 덮어쓰지 않고 실패한다. 테스트의 인위적 fixture는 연구
결과가 아니다. 실제 연구 수치는 위 CLI가 기존 Pilot 측정값에서 계산한 결과만 사용한다.
이 단계는 합성 Pilot의 구현·설계 검증이다. 이전 baseline에서 이미 확인한 test이므로
최종 일반화 성능은 별도 unseen 파일로 평가해야 한다. 비교표의 압축·해제 시간은
기존 측정값이며 특징 추출과 모델 예측 비용을 포함하지 않는다.
