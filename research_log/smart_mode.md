# 최소 Smart Mode 구현

## 범위와 선택 방식

`smart_compress.py`는 파일을 메모리로 읽고 프로토콜의 12개 특징을 계산하여,
지정한 mode의 저장 모델로 알고리즘을 예측한다. 그 알고리즘으로만 한 번 압축하고
한 번 압축 해제하여 `restored == original`을 검사한 뒤 결과를 저장한다.
선택 과정에서 benchmark, 다른 압축기 시험, 점수 계산, 재학습을 수행하지 않는다.

Decision Tree 또는 Random Forest를 `--model`로 명시한다. Pilot test 결과를 보고
더 유리한 모델을 자동 채택하거나 설정을 바꾸지 않는다. 기존 Pilot에서 두 학습
모델의 training 최빈 baseline 개선이 확인되지 않았다는 제한을 유지한다.

## 실행 방법

프로젝트 루트에서 실행한다. `--output-dir`은 아직 존재하지 않는 경로여야 한다.

```powershell
.\.venv\Scripts\python.exe -B smart_compress.py README.md --mode archive --model random_forest --output-dir data/temp/smart_archive
```

mode: `archive`, `balanced`, `fast_access`.
model: `decision_tree`, `random_forest`.
기본 모델 경로는 `data/results/pilot_1008/<model>/`이며 `--model-dir`로 명시할 수도 있다.
각 디렉터리에는 기존 학습 코드가 만든 `<model>_summary.json`과 선택한 mode의
`<model>_<mode>.pkl`이 필요하다. 원시 실험 CSV는 추론 입력으로 읽지 않는다.

모델은 이 프로젝트에서 직접 생성한 신뢰할 수 있는 파일만 사용한다. pickle을 읽기
전에 summary에 기록된 SHA-256을 대조하지만, 해시는 외부 pickle의 실행 안전성을
보증하지 않는다. 학습 시점의 Python 및 추론에 필요한 기록된 패키지 버전,
특징 순서·계산 코드, 압축 코드·설정, 점수 코드·가중치, 모델 설정이 다르면 중단한다.

## 출력과 복원

새 출력 디렉터리에 다음 두 파일을 함께 저장한다.

- `payload.gz`, `payload.bz2`, `payload.xz`, `payload.zst` 중 선택된 하나: 표준 압축 바이트
- `manifest.json`: 원본 이름·크기·해시, 압축 크기·해시·비율, 실제 특징, mode,
  알고리즘, 예측 확률, confidence, 복원 검증, 모델·설정·코드·환경·Git 기록

기존 원본과 출력은 덮어쓰지 않는다. 빈 입력은 특징 정의 및 0 크기 처리 원칙에 따라
거부한다. 복원 불일치나 잘못된 모델 확률이 있으면 정상 출력 디렉터리를 게시하지
않고 오류를 표시한다. 압축 파일을 임시 위치에 저장한 후 검증된 바이트와 같은지도
확인한다. `manifest.json`에는 원본 파일의 절대 경로가 포함된다.

payload는 별도 컨테이너가 아닌 기존 `src.compressors.decompress_data`와 호환되는
표준 형식이다. 독립적인 `smart_decompress.py` CLI 구현은 이후 단계로 남겨 둔다.

## 수치 해석

`prediction_confidence`는 실제 `predict_proba`의 최댓값이며 보정된 정답 확률이 아니다.
모델 학습에 없던 알고리즘의 확률은 0으로 표시한다. 알고리즘 선택은 모델의 `predict`
출력이며, 확률의 첫 최댓값과 일치하는지 검사한다. 임의의 선택 이유를 생성하지 않는다.

이 단계는 실제 파일 처리 동작 검증이다. 알고리즘을 한 번만 실행하므로 5회 중앙값
benchmark와 혼동되는 압축·해제 시간 필드를 만들지 않는다. oracle 점수나 정확도를
계산하지 않으며, 실제 파일에 대한 일반화 성능은 별도의 unseen 평가로 남긴다.

## 검증 방법

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_smart_compress.py -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

테스트는 사람이 지정한 정답으로 만든 제어용 모델을 사용하며 연구 결과가 아니다.
두 모델·세 mode·네 압축기 경로에서 예측이 압축 전에 실행되는지, 12개 특징만
전달하는지, 압축·해제가 각각 한 번인지, 저장 파일이 실제 복원되는지 확인한다.
모델·원본 보존, 메타데이터 불일치, 손상 모델, 잘못된 확률, 복원 실패, 빈 입력,
기존 출력 보호 및 CLI 성공·실패도 검사한다.

## 실제 실행 기록 — 2026-09-15

Smart Mode 테스트 5개와 기존 테스트를 포함한 전체 72개 테스트가 통과했다.
저장된 Pilot Decision Tree 및 Random Forest 각각의 세 mode로 현재 `README.md`를
실제로 처리했다. 여섯 CLI 실행 모두 성공했고, 예측은 모두 zstd였으며
`verified=True`였다. 이는 이 파일에 대한 동작 확인이며 최적 선택이나 정확도 평가가 아니다.

출력은 `data/temp/smart_mode_validation_20260915/<model>_<mode>/`에 보존했다.
각 manifest는 실제 특징과 확률, 해시 및 수정 중인 작업 트리 상태를 기록한다.
이 경로는 기존 `.gitignore`에 따라 Git에서 제외되는 구현 검증용 출력이다.
실험 원시 CSV, 기존 모델, 정답 및 설정은 변경하지 않았다.
