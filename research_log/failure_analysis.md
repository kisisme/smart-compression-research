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
