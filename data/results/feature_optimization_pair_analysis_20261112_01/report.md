# 정확 특징 NumPy 후보의 paired 측정 결과 — 2026-11-12

실제 개발 corpus의 저장 기록을 Python으로 독립 검증·집계했다. 공식 특징 추출기·모델·score는 변경하지 않았다.

실측 실행 HEAD: `b2957bc50ad41611ed1ca7435d584923661e1ca3`. 보호 근거 533개 파일은 불변이다.

## 전체 결과

| 후보 | 범위 | 참조 평균 ms | 후보 평균 ms | 그룹 동일 비중 paired 차이 ms | 중앙값 합 비율 | 절감률 % | 개선/악화/동점 파일 |
|---|---|---:|---:|---:|---:|---:|---:|
| bigram_numpy | extract_only | 67.762237 | 42.428099 | -31.184255 | 1.597108 | 37.3868 | 60/0/0 |
| bigram_numpy | extract_and_frame | 65.025368 | 41.557512 | -31.012659 | 1.564708 | 36.0903 | 60/0/0 |
| run_numpy | extract_only | 72.681122 | 52.165078 | -26.492402 | 1.393291 | 28.2275 | 60/0/0 |
| run_numpy | extract_and_frame | 72.702777 | 52.788771 | -25.798579 | 1.377239 | 27.3910 | 60/0/0 |
| both_numpy | extract_only | 71.232623 | 24.982401 | -61.327183 | 2.851312 | 64.9284 | 60/0/0 |
| both_numpy | extract_and_frame | 69.596911 | 25.146623 | -57.902357 | 2.767644 | 63.8682 | 60/0/0 |

참조/후보 평균은 각각 파일별 6회 중앙값의 평균이다. 주 지표는 인접 pair 차이의 파일별 중앙값 → 원본 그룹 내 평균 → 그룹 동일 비중 평균이다. 두 독립 중앙값의 차이로 대체하지 않았다.

사전 주 비교 both_numpy/extract_and_frame의 다음 단계 조건 충족: **True**. 이 판정은 별도 전체 경로 검증을 진행할 근거이며 공식 채택·통계적 유의성·최종 일반화 성능을 뜻하지 않는다.

## 검증과 범위

60개 원본의 hash/특징/frame 및 네 버전 각각 1080개 기존 모델 예측·확률·비보정 confidence를 대조했다. 본 호출 4320회와 warmup 720회가 고정 일정·순서·timer·worker 종료 검증을 통과했다. 매 파일 본 pair는 참조 먼저 3회/후보 먼저 3회다. 실패/재시도·이상치 삭제·파일 교체는 없다.

[파일별 전체 결과](files.csv) · [모든 pair와 warmup](pairs.csv) · [형식·원본 그룹·고정 크기 구간](breakdowns.csv) · [순서별 진단](order.csv) · [독립 감사 manifest](analysis.json)

악화·동점도 전체 표에 포함했다. 기존 기준선과 다른 시점의 시간을 빼서 개선으로 해석하지 않고, 이번 paired 비교만 사용한다. 메모리 상주 bytes에서 특징과 배열/frame 할당을 측정했고 읽기/hash·모델 loading/예측·기록은 timer 밖이다.

실행 중 외부 사건에 관한 기록: Concurrent activity/power events not reported; absence is not inferred.

공식 src/feature_extractor.py, config/모델/라벨 및 기존 측정은 유지했다. Memory는 validation_only 보류 상태다. 이번 파일은 이미 사용한 개발 corpus이며 cold-start/실제 Smart 전체 경로/GUI/새 원본 그룹 holdout을 검증한 결과가 아니다.

다음 단일 작업은 조건 충족 시 전체 경로의 추론·압축·복원·검증·저장을 포함하는 별도 비교 계획을 먼저 고정하는 것이다. 주 후보를 사후 보조 후보로 바꾸지 않는다.
