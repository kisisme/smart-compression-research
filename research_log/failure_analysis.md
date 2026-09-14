# Protocol v2 실패 사례 분석

기존 baseline, Decision Tree, Random Forest의 동일 test 분할을 분석한다.
재학습이나 압축 재측정은 수행하지 않는다. 원시 측정값, 가중치, 정답, 예측은 유지한다.

`src.failure_analysis`는 입력 및 평가 산출물 해시, 분할 일치, CSV 구조, 복원 검증값,
측정값의 유효성, v2 점수 재계산을 검사한다. 저장 예측의 정답·정오답·점수·regret·특징과
확률 범위·합·confidence도 대조한다. 모델 pickle은 해시만 확인하며 실행하지 않는다.

분석 출력은 다음을 포함한다.

- model/mode별 오류 수, accuracy, 네 클래스 고정 Macro F1, regret, baseline 대비 복구·추가 오류 수
- 전체 train/test 라벨 분포 및 generator·크기별 test sample 수와 오류율
- 모든 오분류의 실제 특징·생성 매개변수·confidence·oracle margin
- 압축률·압축 시간·해제 시간의 signed regret 기여와 해당 sample의 네 압축기 측정값
- 정오답별 confidence 통계, 오류 특징의 training 범위 및 누적 비율
- Python이 자동 생성한 Markdown 보고서와 재현성 metadata

오류율 분모는 오류 sample 수가 아니라 해당 그룹의 전체 test 수다. oracle margin은
최저와 두 번째 점수의 차이며 라벨 불확실성을 확정하는 기준이 아니다. 측정 반복의
원시 분포가 없는 기존 중앙값만으로 시간 노이즈나 통계적 유의성을 판단하지 않는다.
특징 범위와 confidence는 관찰이며 모델 판단의 인과적 설명으로 제시하지 않는다.
baseline confidence의 빈칸은 해당 없음이며 NaN 오류나 측정된 0을 뜻하지 않는다.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m src.failure_analysis --experiment-dir data/results/pilot_1008 --output-dir data/results/pilot_1008/failure_analysis
```

이미 존재하는 출력은 덮어쓰지 않는다. 테스트 fixture는 연구 결과가 아니며 실제 수치는
위 CLI가 만든 CSV와 `report.md`를 사용한다. 이 분석은 기존 Pilot의 사후 진단이다.
새 변경의 최종 성능은 별도 unseen 데이터로 검증해야 한다.

## 실제 실행과 관찰

구현 커밋 `c63874d062939b846b50d124ebb6c94456423449`의 깨끗한 작업 트리에서
CLI를 실행했다. 실행 전 전체 67개 테스트가 통과했다. 입력 1,008 sample 중 기존
test 202개를 분석했다. 모든 입력·출력 해시를 Python으로 사후 대조했다.

생성 보고서: [전체 표와 손실 분해](../data/results/pilot_1008/failure_analysis/report.md).
아래 수치는 해당 Python 출력에서 옮긴 실제 집계다. 오류 수는 sample × mode 기준이다.

| 모델 | Archive 오류 | Balanced 오류 | Fast Access 오류 |
|---|---:|---:|---:|
| baseline | 1 | 1 | 2 |
| Decision Tree | 4 | 1 | 6 |
| Random Forest | 2 | 1 | 3 |

세 방법을 합친 오분류는 model × sample × mode 기준 21행이며 고유 sample은 7개다.
Decision Tree와 Random Forest 모두 baseline의 오류를 바로잡은 사례가 0건이었다.
Decision Tree는 Archive에서 3건, Fast Access에서 4건의 추가 오류를 만들었고,
Random Forest는 Archive와 Fast Access에서 각각 1건의 추가 오류를 만들었다.
Balanced에서는 추가 오류가 없다.

Decision Tree 오류 11건 중 structured는 10건, small_alphabet은 1건이었다.
Random Forest 오류 6건 중 structured는 5건, small_alphabet은 1건이었다.
그룹별 표에는 전체 test 수를 분모로 한 오류율도 별도로 보존했다.

Decision Tree의 오류 11건 모두 confidence가 1이었고, Random Forest도 오류 6건 중
4건의 confidence가 1이었다. 따라서 confidence가 낮을 때만 적용하는 fallback으로는
이번의 confidence=1 오류를 탐지할 수 없다. 이는 관찰한 예측값에서 따르는 제한이며
fallback을 이번 단계에서 구현하거나 임계값을 조정한 것은 아니다.

Random Forest의 최대 regret 사례는 `sample_000922 / fast_access`였다. 실제 정답은
zstd지만 gzip을 예측했다. signed regret 기여는 압축률 -0.052216, 압축 시간 0.475545,
해제 시간 0.128180이며 총 regret은 0.551509였다(각각 소수점 6자리 표시).
이 sample에서 gzip은 크기 측면의 이점이 있었지만 처리 시간 손실이 이를 넘었다.
이 분해는 잘못된 선택의 성능상 이유이며, 모델이 왜 gzip을 예측했는지의 인과적
설명을 의미하지 않는다.

`sample_000916`은 세 mode 모두 실제 정답이 gzip인데 세 방법이 모두 zstd를 선택했다.
`sample_000841`은 Fast Access에서 같은 형태의 오류를 보였다. 학습 라벨의 gzip 수는
Archive 7개, Balanced 4개, Fast Access 10개로 적었다. 희소한 정답을 학습하는 데
한계가 있었을 가능성은 있으나, 현재 관찰만으로 오류 원인을 확정하지 않는다.

오류 sample의 12개 특징 중 training의 개별 특징 최솟값·최댓값 범위를 벗어난 값은
없었다. 이는 개별 특징 범위에 대한 결과이며, 특징 조합의 분포 차이나 데이터 유사성,
측정 변동을 배제하는 결과가 아니다. 설정·데이터·라벨·모델은 그대로 보존했다.

이번 Pilot에서는 두 학습 모델의 baseline 개선을 확인하지 못했다. Smart Mode는
특징 기반 선택 흐름을 구현하는 다음 단계로 남기되, 성능 개선이나 confidence의
신뢰성을 이미 입증한 것처럼 표현하지 않는다.
