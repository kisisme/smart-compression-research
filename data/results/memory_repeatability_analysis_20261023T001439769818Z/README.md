# 동일 환경 반복 검증·Run 2 교체 후보 분석

독립 저장 감사를 다시 실행한 뒤 고정된 후보 계산을 수행했다. 새 압축 측정·복원·모델 학습은 수행하지 않았다.

- 실행 HEAD: `3927a35c06e6c00fbae0eaaf2bd53d4cbd65e4da`; 분석 코드·테스트는 당시 commit 전 추가 파일이며 정확한 hash를 invocation과 summary에 보존했다.
- 실행: `2026-10-23T00:14:39.769818+00:00` ~ `2026-10-23T00:14:59.364291+00:00` (UTC). CLI 종료 0, stderr 0바이트.
- 최초 측정 HEAD: `a8c3e47edc4f9d231605434c464b036240b7b2ed`; Run 2 재측정 HEAD: `9a261e46d01f61e986d98eedc11f634eda19c863`.
- 실제 활성 순서: 1 → 3 → 4 → 5 → 6 → 2. 논리 Run 2 번호를 유지하되 시각을 소급하지 않았다.
- 활성 실패 반복 0건과 원본 실패 반복 3건을 구분한다. 원본·교체 session·기존 manifest는 수정하지 않았다.

## 사전 고정 계산

기존 3일 분석기는 변경하지 않았다. 순수 수치 계산부만 재사용하고 새 독립 감사·계획과 수치 규칙 일치를 검사했다. Anchor는 여섯 run 대표값의 중앙값이며 raw 반복을 합쳐 계산하지 않는다. Memory는 phase별 중앙값의 최댓값이다. 정확한 동점 순서는 gzip, bz2, lzma, zstd이며 근사 동점·사후 weight 조정·sample 제외는 없다.

각 sample·mode·시나리오에 자기 자신을 포함한 방향 있는 run 쌍 전체를 계산했다. 후보 weight, 원래 3지표 공식 비교와 후보의 memory weight만 0으로 둔 비교를 구분한다. Regret는 후보 score 차이이며 모델 평가가 아니다.

| Mode | size | compress | decompress | memory |
|---|---:|---:|---:|---:|
| archive | 0.65 | 0.1 | 0.1 | 0.15 |
| balanced | 0.4 | 0.2 | 0.2 | 0.2 |
| fast_access | 0.2 | 0.2 | 0.45 | 0.15 |

## 실제 결과

- 판정: `memory_stability_not_satisfied`. Memory 안정성 False, joint 안정성 False.
- Sample 84개, 대표값 2016개, 후보 정답 4788행, 방향별 regret 27216행.
- Memory span은 336개 조건 중 96개가 한계를 넘었다. 원래 식 epsilon/(2*w_memory_max)의 Python 값은 `0.012499999999999999`이며 판정에 반올림을 사용하지 않았다.

| 층 | span 조건 | 미충족 | 최대 log span | 최대 memory_only regret | 최대 joint regret |
|---|---:|---:|---:|---:|---:|
| core | 288 | 89 | 0.026396253608327876 | 0.0 | 1.7749495552044472 |
| tiny | 48 | 7 | 0.02710013828754913 | 0.0 | 0.0 |

| 층 | 시나리오 | 방향별 쌍 | 선택 일치율 | 최대 regret | 평균 regret |
|---|---|---:|---:|---:|---:|
| core | memory_only | 7776 | 1.0 | 0.0 | 0.0 |
| core | timing_only | 7776 | 0.9765946502057613 | 1.7752505920281887 | 0.00581390716797561 |
| core | joint | 7776 | 0.9765946502057613 | 1.7749495552044472 | 0.005815750273839201 |
| tiny | memory_only | 1296 | 1.0 | 0.0 | 0.0 |
| tiny | timing_only | 1296 | 1.0 | 0.0 | 0.0 |
| tiny | joint | 1296 | 1.0 | 0.0 | 0.0 |

- 모든 run에서 memory 이득이 delta를 초과한 sample·mode 조건: 0/252.
- Candidate joint와 후보 memory=0의 선택 차이: 0/1512; 기존 공식 3지표와의 선택 차이: 6/1512. 후자는 memory 단독 효과를 뜻하지 않는다.

Memory-only 선택이 같고 regret가 0이어도 사전 memory span 기준을 면제하지 않는다. 두 층 모두 span 조건을 충족하지 못했으며 core의 timing_only/joint는 regret budget도 초과했다. 이 관측은 시간 변동이 함께 영향을 주었음을 보여주지만 환경 기록만으로 특정 원인을 확정하지 않는다.

공식 memory 채택·4지표 전환 근거는 충족하지 못했다. Memory는 계속 `validation_only`, `score_inclusion=false`이며 공식 3지표 가중치·과거 Pilot·모델은 그대로 유지한다. 관측 환경 범위의 결과이며 날짜 간 안정성이나 미래 오차 한계로 일반화하지 않는다.

## 검증 및 파일

새 연결부 fixture 테스트 11개와 기존 계산부 회귀 테스트 13개가 통과했다. Fresh Python의 producer import 차단, 일반/-O/-OO의 잘못된 증거 거부, 두 입력 root·소스 변경 감지, CSV round-trip·전체 방향 행렬·해시·기존 출력 보존, 저장 실패 및 저장 후 변경 감지를 확인했다. 인위적 fixture는 연구 실측이 아니며 전체 저장소 suite는 실행하지 않았다.

- [stability_summary.json](stability_summary.json): 가중치·기준·판정·대표값·phase 진단·anchor·span·선택 비교·완전한 provenance.
- [candidate_labels.csv](candidate_labels.csv), [transfer_regrets.csv](transfer_regrets.csv): 전체 후보 정답과 방향별 regret.
- [audit.json](audit.json): 원본 실패 보관·교체·활성 전체 저장 기록 독립 감사.
- [derived_findings.json](derived_findings.json), [additional_findings.json](additional_findings.json): 전체 결과에서 Python으로 집계한 관측.
- [invocation.json](invocation.json), [stdout.json](stdout.json), [stderr.txt](stderr.txt): 실제 호출·HEAD·소스 hash·테스트·출력 기록.
- [verification.json](verification.json): 저장 출력과 두 증거 root의 최종 재검증.

재실행은 invocation의 명령에서 새 output-dir를 지정한다. 기존 출력이나 입력 아래 저장은 거부한다. 저장 실패 표시가 있거나 CLI/API가 실패한 출력은 성공한 분석으로 사용하지 않는다.
