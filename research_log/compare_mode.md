# Compare Mode CLI

`compare_compress.py`는 사용자가 지정한 비어 있지 않은 파일을 네 압축기로 실제 비교한다.
공식 프로토콜 v2의 압축률·압축 시간·압축 해제 시간을 측정하고 Archive·Balanced·Fast Access
각 mode의 종합 점수와 최적 알고리즘을 계산한다. 모델 예측이나 모델 성능 평가를 수행하지 않는다.

## 실행

```powershell
.\.venv\Scripts\python.exe -B compare_compress.py README.md --output-dir data/temp/compare_readme
```

출력 폴더는 아직 존재하지 않는 경로여야 한다. 파일 전체를 메모리에 읽는 단일 파일 비교이며
압축 payload를 저장하는 기능은 아니다. 선택한 알고리즘으로 파일을 저장하려면 별도 압축 경로가 필요하다.

## 측정·점수

- gzip 9 → bz2 9 → lzma 6 → zstd 3의 고정 순서로 실행한다. 실제 설정은 `config/experiment_config.json`에서 확인한다.
- 각 알고리즘의 압축을 5회 실행하고 압축 bytes가 동일한지 확인한다. 첫 압축 bytes를 기준으로 해제를 5회 실행하며 매번 원본 bytes와 비교한다.
- 파일 읽기·해시·복원 일치 검사 밖에서 codec 호출만 `perf_counter_ns`로 측정한다. Phase별 원시 ns 5개의 중앙값을 구한 뒤 ms로 변환한다. Warmup·epsilon 보정·자동 측정 재시도는 없다.
- 기존 benchmark의 반복·중앙값·기준 payload 검증 정의를 유지하면서 원시값 보존을 별도 CLI에서 수행한다. 기존 `src/compressors.py`는 변경하지 않는다.
- 네 알고리즘이 모두 정상일 때 기존 `src.scoring.score_sample()`으로 세 mode 점수를 계산한다. 정확한 동점은 gzip, bz2, lzma, zstd 순서를 따른다. 기존 점수·가중치는 변경하지 않는다.
- 실패한 반복은 해당 알고리즘의 후속 반복을 멈추고 `not_run` 슬롯을 남긴다. 다른 알고리즘은 계속 측정한다. 일부 성공 결과만으로 정답을 계산하지 않는다.

## 출력

| 파일 | 내용 |
|---|---|
| `timing_repeats.csv` | 예정 반복 전체의 ns·상태·압축 bytes 일관성·해제 검증·출력 hash·오류. 미실행 슬롯과 실패도 보존 |
| `compression_results.csv` | 알고리즘별 크기·압축률·phase 중앙값·복원 검증·상태·오류. 실패 조합의 정상 집계값은 공란 |
| `selection_labels.csv` | 네 결과가 모두 정상일 때 세 mode의 최적 알고리즘과 네 점수. 실패/입력 무효 시 헤더만 저장 |
| `config_snapshot.json` | 실행에 사용한 설정의 원래 bytes |
| `comparison.json` | 범위·상태·입력 hash·설정·환경·실행 HEAD·소스 hash·행 수·측정 집계·계산된 선택·오류·산출물 hash |

원시 반복·집계 측정값·계산된 정답을 구분한다. Config·점수/압축 코드·입력이 바뀌면 정상 선택을
사용하지 않는다. 기존 출력은 덮어쓰지 않으며 새 폴더를 배타적으로 생성한다. 저장 중 오류나
저장 전후 입력 변경을 감지하면 가능한 부분 산출물과 `publication_failed.json`을 보존한다.

정상 점수는 `status=completed`, CLI/API 성공, `publication_failed.json` 없음의 조건을 함께
확인하고 사용한다. `completed_with_failures`는 codec·복원·점수 실패, `invalidated`는 측정 후
입력/소스 변경을 뜻한다. 이 두 경우에는 정상 선택을 비워 저장하고 CLI는 종료 코드 1을 반환한다.
저장 자체가 실패하면 일부 파일만 존재할 수 있으며 실패 표시도 저장할 수 없었다면 stderr와 실패
종료를 따른다. 기존 출력 경합으로 저장을 시작하지 못한 경우에는 그 디렉터리에 기록하지 않는다.

## 범위

Smart Mode는 압축 전 특징으로 예측한 압축기 하나를 실행한다. Compare Mode는 명시적인 비교
요청에서 네 압축기를 실제 실행한다. Compare 결과는 해당 파일·환경·실행 순서의 실측 비교이며
Smart 모델의 정확도·regret·baseline 개선이나 새 Pilot을 뜻하지 않는다. 단일 실행의 시간 순위는
환경에 따라 달라질 수 있다. Memory는 참고 지표로 보존하는 기존 방침을 유지하며 이 CLI에서는
측정하거나 점수에 넣지 않는다. 학습·특징 추출·모델 로딩도 하지 않는다.

## 검증·실제 실행 — 2026-10-23

작업 시작·실제 실행 HEAD는 `085f1ab`다. 새 CLI는 당시 commit 전 작업 트리 상태였으며
실행 보고서에 기록한 정확한 소스 hash가 최종 구현과 일치함을 확인했다.

전용 테스트 16개(2.484초), 기존 압축 회귀 7개(0.035초), 점수 회귀 9개(0.001초), 총 32개가
통과했다. 제어된 원시 시간으로 기존 benchmark와의 일치, 독립 점수 수식·exact tie,
실패·미실행 슬롯 보존·부분 집합 scoring 차단·0 시간 무보정·입력/소스 변경·저장 실패·저장 후
변경·기존 출력 경합·CLI 종료·fresh Python의 ML/특징/memory import 차단을 검증했다.
첫 독립 수식 assertion의 부동소수점 합산 차이만 수치 QA 허용 오차로 처리했으며 실제 점수와
동점 선택 정책은 변경하지 않았다. 제어 fixture 수치는 연구 데이터가 아니며 전체 저장소 suite는 실행하지 않았다.

README 파일로 실제 비교를 한 번 실행했고 네 알고리즘 모두 복원 검증을 통과했다.
원시 반복 40개·집계 4개·mode 정답 3개를 저장하고 원시 중앙값·공식 점수·hash·stdout/보고서·
빈 stderr와 보호 대상 기존 파일 8개 불변을 Python으로 재검증했다. 이 한 번의 세 mode 선택은
모두 zstd였으며 다른 파일·환경의 우수성이나 모델 성능으로 일반화하지 않는다.

근거:

- [실제 비교 보고서](../data/results/compare_mode_validation_20261023T120641453081Z/comparison.json)
- [원시 반복](../data/results/compare_mode_validation_20261023T120641453081Z/timing_repeats.csv)
- [집계 측정](../data/results/compare_mode_validation_20261023T120641453081Z/compression_results.csv)
- [mode 정답](../data/results/compare_mode_validation_20261023T120641453081Z/selection_labels.csv)
- [실제 호출 기록](../data/results/compare_mode_validation_20261023T120641453081Z/invocation.json)
- [재검증·테스트 기록](../data/results/compare_mode_validation_20261023T120641453081Z/verification.json)
