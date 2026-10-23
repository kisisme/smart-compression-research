# 데이터의 통계적 특성을 이용한 무손실 압축 알고리즘 자동 선택 시스템 연구

과학고등학교 창의개인연구를 위한 초기 프로젝트입니다.

## Compression Algorithms

- gzip
- bz2
- LZMA
- zstd

## Research Goal

파일을 네 알고리즘으로 모두 압축한 뒤 선택하는 대신, 압축 전에 파일의 통계적 특징을 추출하고 그 특징만으로 적합한 압축 알고리즘을 예측하는 시스템을 구현합니다.

최적 알고리즘은 압축률만으로 결정하지 않으며, 압축률과 압축 시간, 압축 해제 시간을 함께 고려합니다.

## Usage Modes

- **Archive**: 파일 크기 감소를 가장 중요하게 고려합니다.
- **Balanced**: 파일 크기와 처리 속도의 균형을 고려합니다.
- **Fast Access**: 빠른 압축 해제와 사용 속도를 중요하게 고려합니다.

## Research Process

1. 압축 성능 측정
2. 데이터 특징 추출
3. 합성 및 실제 데이터 실험
4. 통계 분석
5. 머신러닝 모델 학습
6. 자동 압축 알고리즘 선택
7. 최종 Smart/Compare 프로그램 구현

## CLI 사용

프로젝트 루트의 가상환경 Python으로 실행합니다. 각 출력 폴더는 아직 존재하지 않는 새 경로여야 합니다.

```powershell
.\.venv\Scripts\python.exe -B main.py --help
.\.venv\Scripts\python.exe -B main.py smart README.md --mode archive --model decision_tree --output-dir data/temp/smart_example
.\.venv\Scripts\python.exe -B main.py decompress data/temp/smart_example --output-dir data/temp/restored_example
.\.venv\Scripts\python.exe -B main.py compare README.md --output-dir data/temp/compare_example
```

- `smart`: 압축 전 특징으로 선택한 압축기 하나를 실행하고 복원 일치를 검증해 payload·manifest를 저장합니다. `--model`은 `decision_tree` 또는 `random_forest`로 명시합니다. 기본 모델은 저장된 Pilot 모델이며, 직접 생성한 신뢰할 수 있는 모델만 사용합니다.
- `decompress`: 압축 결과 폴더의 manifest·payload를 읽어 새 폴더에 원래 파일명으로 복원하고 크기·SHA-256을 검사합니다. 모델이나 원본 파일은 필요하지 않습니다.
- `compare`: 네 압축기를 실제 실행하여 원시 반복 시간·중앙값·복원 검증·세 mode의 공식 점수를 저장합니다. 비교 보고서를 생성하며 압축 package는 저장하지 않습니다.

각 명령에 `--help`를 붙이면 해당 기능의 옵션을 확인할 수 있습니다. 기존 `smart_compress.py`, `smart_decompress.py`, `compare_compress.py`도 계속 사용할 수 있습니다.

공식 평가는 압축률·압축 시간·압축 해제 시간의 3지표입니다. Memory는 참고 지표로 보존하며 추가 구현은 보류합니다. 저장 모델의 confidence는 보정된 정답 확률이 아니고, 기존 Pilot에서는 최빈 baseline 대비 개선이 확인되지 않았습니다. 파일 처리 성공과 모델의 일반화 성능을 구분합니다.

상세 사용·검증 기록: [Smart 압축·복원](research_log/smart_mode.md), [실제 비교](research_log/compare_mode.md), [연구 진행 상태](research_progress.md).
