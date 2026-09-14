# Protocol v2 majority baseline

이 단계는 합성 Pilot으로 baseline 구현을 검증한다. Decision Tree, Random Forest,
실제 unseen 파일 평가 및 GUI는 포함하지 않는다. 기존 측정값과 라벨은 수정하지 않는다.

## 실행 전 고정한 규칙

- `config/experiment_config.json`의 `baseline` 설정을 사용한다:
  `test_size=0.20`, `random_state=42`, `group_column=seed`.
- sample_id로 정렬하고 GroupShuffleSplit을 한 번 실행한다. 라벨을 분할에 사용하지
  않으며, 모든 mode에서 같은 분할을 사용한다. 20%는 sample 수가 아닌 고유 seed
  그룹 수의 비율이다(올림). 실제 sample 수와 그룹 수는 결과에 기록한다.
- mode마다 training set의 종합 점수 정답 중 최빈 알고리즘만 선택한다.
  동률이면 기존 알고리즘 순서 `gzip, bz2, lzma, zstd`를 사용한다.
- Macro F1은 네 알고리즘을 고정하여 평균하고 `zero_division=0`으로 계산한다.
  test에 등장하지 않고 예측도 없는 클래스의 F1도 0으로 포함한다. 따라서 단일
  클래스 test를 모두 맞혀도 이 정의의 Macro F1은 1이 아닐 수 있다.
- 혼동행렬은 실제 라벨이 행, 예측 라벨이 열이며 항상 네 클래스 전체를 기록한다.
- baseline은 특징을 사용하지 않으므로 feature importance는 해당 없음(null)으로
  기록한다. 학습 라벨 빈도는 예측 confidence로 해석하지 않는다.
- test의 항상 gzip/bz2/lzma/zstd, baseline, oracle 성능과 score regret을 비교한다.
  파일을 새로 압축하지 않고 기존 측정값을 조회한다. 이는 feature 추출·예측 비용을
  포함하는 end-to-end 실행 시간 평가가 아니다.

근거: [GroupShuffleSplit 공식 문서](https://sklearn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html),
[F1 공식 문서](https://scikit-learn.org/1.7/modules/generated/sklearn.metrics.f1_score.html).

## 입력 검증 및 재현

samples/compression_results의 SHA-256을 실험 metadata와 대조하고 압축 설정,
시간 설정 및 특징 설정이 현재 config와 일치하는지 검사한다. CSV schema, 중복 ID,
비유한 값, 비양수 크기·시간, 복원 실패를 검사한다. 원시 네 측정값으로 v2 점수를
재계산하여 selection_labels의 모든 score와 best_algorithm을 검증한다.

출력 디렉터리가 이미 존재하면 실패하며 덮어쓰지 않는다. 분할 목록, training 라벨
빈도와 상수 모델, accuracy/Macro F1, 혼동행렬, 모든 test 예측, 특징을 포함한 오분류
목록, 전략 비교표를 저장한다. 요약 JSON에는 입력·출력·코드·config 해시, Git 상태,
Python/package/OS, 실행 시각, 원래 측정 metadata를 보존한다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_train_model.py" -v
.\.venv\Scripts\python.exe -m src.train_model --experiment-dir data/results/pilot_1008 --output-dir data/results/pilot_1008/baseline
```

현재 seed 그룹은 동일 seed가 양쪽으로 나뉘는 것을 방지한다. 서로 다른 seed에서
우연히 생성된 유사 데이터를 탐지하는 것은 아니며, 실제 파일에는 원본 식별자를
이용한 별도의 그룹 정책이 필요하다. 이 Pilot의 test 결과를 향후 모델 선택에
사용하면 최종 일반화 성능은 별도로 보존한 unseen 데이터에서 평가해야 한다.

`tests/test_train_model.py`의 인위적 측정 fixture는 오류 검출용 단위 테스트이며,
연구 결과로 저장하거나 해석하지 않는다. 연구 결과는 CLI가 기존 Pilot의 실제
측정 CSV를 검증한 후 계산한 출력만 사용한다.
