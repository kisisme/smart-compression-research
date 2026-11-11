# 참조 특징 기준선 profile

**관찰된 개발 corpus의 새 기준선이다. 최적화 성능 결과가 아니다.**

| 모드 | 파일별 중앙값의 평균 ms | 중앙값 ms | p90 ms |
|---|---:|---:|---:|
| extract_and_frame | 66.066533 | 34.949400 | 139.395840 |
| extract_only | 58.727250 | 30.165200 | 133.873010 |
| frame_only | 0.720367 | 0.722800 | 0.853230 |
| instrumented_extract | 64.209005 | 34.836500 | 133.008240 |

함수별 inclusive/self는 call_medians.csv에 보존했다. 부모/자식 inclusive 값을 중복 합산하지 않는다. 계측 observer overhead는 별도 프로세스·고정 순서/cache 변동도 포함하므로 실제 성능 차이로 확정하지 않는다. 각 모드 중앙값을 더해 결합 시간을 만들지 않는다.

전체 raw·warmup·원본/모델 hash·정확 feature/frame/prediction gate를 보존했다. Memory/codec/실제 GUI·cold start·최종 일반화 성능은 평가하지 않았다.
