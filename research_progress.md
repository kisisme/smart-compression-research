# 연구 진행 상태

최초 전체 확인일: 2026-09-15. Memory 검증 증거 보존·audit 도구 갱신: 2026-09-16. 종료 처리 보강 검토·fixture 검증 및 새 전체 memory 행렬 실행·audit: 2026-09-22. Runtime baseline 구현·fixture 검증·전체 실측·audit·진단 분석: 2026-09-30. Git 증거 보존·memory 채택 검토·후속 검증 사전 설계: 2026-10-07. 후속 검증 timing worker·runner 구현 및 전용 검증: 2026-10-13. 후속 검증 독립 audit 구현·전용 fixture 검증: 2026-10-14. 후속 검증 분석기 초안 검토·전용 fixture 검증 완료: 2026-10-16. 후속 실측 준비 점검·일정안 작성 및 조건 확인 대기: 2026-10-16~17.

공식 기준: [research_protocol_v2.md](research_protocol_v2.md)

최신 memory 실제 측정 확인: 2026-10-22. 독립 감사 실행 확인: 2026-10-23(KST). 별도 동일 환경 반복 검증 attempt02의 최초 수집은 Run 2 timeout 3건을 포함한 `completed_with_failures`로 마감·보존했다. 이후 사용자 지시에 따라 Run 2 전체를 새로 측정하고 검증 후 기존 활성 경로에 교체했다. 새 Run 2는 실패 0건·336개 pair 검증 통과이며 활성 여섯 슬롯은 실패 0건이다. 현재 상태는 `completed_after_run_replacement`이고 실제 활성 실행 순서는 1→3→4→5→6→replacement 2다. 이번에는 이 변경을 포함한 저장 기록 일관성 독립 감사를 통과했다. 원래 수집의 실패와 기존 3일 attempt01의 미완료 증거는 그대로 보존한다.

최신 진행: 커밋된 NumPy 후보의 실제 60개 개발 파일 전체 paired 측정·독립 감사를 완료했다(2026-11-12). [결과 보고서](data/results/feature_optimization_pair_analysis_20261112_01/report.md)·[실측 완료](data/results/feature_optimization_pair_20261112_01/complete.json)·[독립 집계/감사](data/results/feature_optimization_pair_analysis_20261112_01/analysis.json)·[전용/회귀 테스트](research_log/feature_pair_analysis_validation_20261112.json)에 근거를 보존했다. 본 호출 4320회·warmup 720회가 실패/재시도 없이 완료됐고, 네 버전 각각 기존 예측/확률 1,080개와 정확 특징/frame을 대조했다. 주 후보 both_numpy의 특징+입력 준비는 파일별 중앙값 평균 69.5969→25.1466ms, 중앙값 합 기준 63.8682% 단축, 원본 그룹 동일 비중 paired 차이 -57.9024ms였다. 모든 여섯 비교에서 파일 60개 모두 paired 중앙값이 개선됐다. 기존 보호/source 533개는 불변이며 전용/회귀 테스트 10개가 실패/오류 0개로 통과했다. 실행 HEAD는 `b2957bc50ad41611ed1ca7435d584923661e1ca3`이다. 사전 다음 단계 조건은 충족했지만 공식 시스템 채택이나 전체 비용/최종 일반화 검증은 아니다. 다음 단일 작업은 주 후보를 유지해 전체 경로 추론·압축·복원·검증·저장 비용 비교 계획을 별도로 동결하는 것이다. 공식 코드/모델/config/score와 memory 보류 방침은 유지했다.

직전 구현: 격리 NumPy 후보 세 개와 균형 paired 실행부·저장 기록 검사를 구현했다(2026-11-11). [후보 코드](research_log/feature_pair_candidates_20261111.py)·[실행부](research_log/run_feature_pairs_20261111.py)·[검증 lock](data/results/feature_pair_implementation_20261111_01/implementation.json)에 근거를 보존했다. 전용 테스트 7개가 실패/오류 0개로 통과했고 정상 입력 133개·오류 입력 5개에서 정확 특징/frame/예외를 확인했다. 두 순서·모드·세 후보의 pair 기록과 변조/부분 실패 보존을 검사했다. 원본 corpus 읽기와 저장 모델 로딩을 막은 검증이며 기존 근거 529개 파일은 불변이다. 실제 개발 corpus 동등성·예측 gate·4,320회 본 호출과 속도 비교는 아직 실행하지 않았다. 다음은 커밋한 source/lock으로 전체 paired 실행과 결과 검증이다.

직전 후보 계획: Bigram/run의 정확 특징값 보존 최적화 후보와 새 paired 비교 계획을 고정했다(2026-11-11). [후보 설계](research_log/feature_optimization_pair_design_20261111.md)·[JSON 계획](research_log/feature_optimization_pair_plan_20261111.json)·[동결](data/results/feature_optimization_pair_plan_20261111_01/freeze.json)·[독립 일정 검증](data/results/feature_optimization_pair_plan_20261111_01/verification.json)을 보존했다. NumPy 정수 pair histogram과 run 경계 계산을 후보로 정하고, 두 함수 결합을 주 후보·단독 변경 둘을 보조로 사전 구분했다. 세 후보×두 모드에서 파일당 6-pair 본 측정·1-pair warmup 순서를 정해 매 파일 참조 먼저 3회/후보 먼저 3회가 되도록 확인했다. 예정 본 호출 4,320회·warmup 720회이며 실제 실행 결과가 아니다. 정확 builtin type/float.hex/frame/예측·subclass fallback과 주 판정식을 고정했고 기존 근거 523개 파일을 보존했다. 후보 코드·fixture 테스트·새 특징/예측·paired 속도 측정은 아직 없다. 다음은 격리 후보/paired 실행부·독립 감사 구현과 인위적 동등성 검증이다.

직전 기준선 실측: 실제 60개 파일의 특징 기준선 profile·독립 감사·병목 집계를 완료했다(2026-11-11). [결과 보고서](research_log/feature_profile_baseline_results_20261111.md)·[완료 기록](data/results/feature_profile_baseline_20261109_01/complete.json)·[독립 감사](data/results/feature_profile_baseline_20261109_01/verification.json)·[추가 집계](data/results/feature_profile_baseline_analysis_20261111_01/analysis.json)를 보존했다. 원본 bytes/hash·저장 특징 720개·예측/확률 1,080개가 정확히 일치했고 본 측정 1,200회·warmup 240회가 실패/재시도 없이 완료됐다. 파일별 중앙값 평균은 특징만 58.7273ms·입력 준비만 0.7204ms·결합 66.0665ms·계측 특징 64.2090ms였다. 계측 raw root의 비중복 분해에서 bigram 39.3633%·run 통계 29.7661%, 합 69.1294%로 우선 병목이었다. 비중은 계측 시간이며 예상 속도 향상률이 아니다. 기존 근거/구현 source는 불변이었다. 당시 다음은 특징값 보존 최적화 후보와 paired 검증 계획이었다. 실제 최적화·새 모델/score 전환·memory는 진행하지 않았다.

직전 실행부 구현: 고정 계획의 특징 profile 실행부·정확 동등성/저장 감사 도구를 구현하고 인위적 입력으로 검증했다(2026-11-11). [구현 설명](research_log/feature_profile_implementation_20261111.md)·[source lock/검증 결과](data/results/feature_profile_implementation_20261111_01/implementation.json)·[테스트 로그](data/results/feature_profile_implementation_20261111_01/tests.log)를 보존했다. 전용 테스트 17개가 실패/오류/skip 0개로 통과했고 정상 fixture 131개·오류 입력 5개의 정확한 특징/frame/예외·nested call tree를 확인했다. 네 모드의 기록/실패 보존·자식 프로세스 smoke·중단/반환 코드 처리, 미commit 구현/lock의 corpus 실행 차단을 구현했다. 원본 corpus 읽기·저장 모델 역직렬화/예측을 금지한 검증이며 기존 근거 481개 파일은 불변이다. 실제 60개 입력의 새 특징/예측 gate·실측·최적화는 당시 실행하지 않았다. 다음 단계는 구현/lock commit 후 기준선 profile과 독립 저장 감사였다.

직전 계획 동결: 특징 계산 profiling·정확 동등성 검증의 사전 계획과 참조 자료 동결을 완료했다(2026-11-09). [설계](research_log/feature_profile_design_20261109.md)·[계획](research_log/feature_profile_plan_20261109.json)·[동결](data/results/feature_profile_plan_20261109_01/freeze.json)·[독립 구조/저장 검증](data/results/feature_profile_plan_20261109_01/verification.json)을 보존했다. 기존 실제 파일 60개·저장 특징 720개·모델 18개·예측 1,080개를 연결했고, 비계측 특징/입력 frame/결합과 함수별 계측의 네 모드에 측정 1,200회·warmup 240회 순서를 미리 고정했다. 이름/순서/builtin type·정수값/float.hex·모델 출력의 정확 보존과 nested timer/self-time 규칙을 명시했다. 인위적 정상 131개·오류 5개 입력은 계획만 수립했다. Python/패키지·모델 bytes·기존 근거 467개 파일과 참조 코드 사본/계획 링크를 확인했다. 원본 bytes 재검증·특징 재계산·모델 로딩/예측·실측·최적화·fixture 테스트는 당시 수행하지 않았다. 다음 작업은 이 계획의 실행부/검증기 구현과 인위적 fixture 검증이었다.

직전 비용 진단: 저장된 후보 모델 전체 경로의 비용 병목 진단을 완료했다(2026-11-09). [보고서](research_log/pipeline_bottlenecks_20261109.md)와 [독립 검증](data/results/usage_pipeline_bottlenecks_20261109_01/verification.json)을 보존했다. 5,700개 원시 trial을 1,140개 파일×전략 중앙값으로 재집계하고, 모델 파일별 1,080개 비용 차이를 분해했다. 특징 계산/입력 frame 준비는 파일당 조건별 평균 54.45~66.12ms, 압축 전체 시간에서 DT 84.02~87.75%·RF 61.53~70.89%였고, 평균 예측은 DT 2.50~2.86ms·RF 19.13~23.00ms였다. 특징 시간을 0으로 두는 가정에서도 18개 중 13개 조건의 가상 비용은 고정 zstd보다 불리했다. 이는 원시 trial에서 시간을 제거한 진단이며 최적화 실측이 아니다. 검증/hash/읽기/쓰기의 개별 계측은 없어 나머지 시간으로 구분했다. 기존 근거 460개 파일은 불변이고 전용 fixture 6개·독립 저장 검산을 통과했다. 당시 다음은 기존 특징값을 보존하는 함수별 profiling의 사전 계획이었다. 공식 score/모델과 memory 방침은 유지했다.

직전 zstd 진단: 사용자 요청에 따라 직전 후보 모델 실제 파일 평가의 zstd 선택 누락을 전수 분석했다. [57건 전체 목록·보고서](research_log/zstd_misses_20261031.md)와 [독립 저장 검증](data/results/usage_zstd_misses_20261031_01/verification.json)을 보존했다. 사전 예측 1,080건 중 zstd 선택 995건에서 다른 압축기의 가상 정책 비용이 엄격히 낮았던 선택은 57건(5.7286%), 중복 제거 파일은 21개·파일×시나리오는 32개다. 최저 비용은 gzip 46건·bz2 11건이며 최저가 아니어도 나은 LZMA 2건까지 대안 59건을 보존했다. 정확 동점은 0건이다. Archive 시간 비용 0.1배에 37건이 있고, 반대 방향으로 비-zstd 선택이 고정 zstd보다 나빴던 경우도 74건이다. 기존 측정/예측을 다시 읽은 개발 진단이며 재측정·재학습·계수/모델 변경은 하지 않았다. 당시 다음 작업은 특징/추론/저장 비용 병목의 별도 분해였으며 공식 score/모델과 memory 참고 지표 방침은 유지했다.

직전 전체 실험: 사용자 요청의 기준 확정→별도 모델 학습→실제 파일 검증을 모두 완료했다. [결과 보고서](research_log/usage_model_study_results_20261031.md)와 [원시 저장 감사](data/results/usage_candidate_study_20261031_01/audit.json)·[독립 지표 검증](data/results/usage_candidate_study_20261031_01/metrics_verification.json)을 보존했다. 모델 18개·실제 파일 60개·사전 예측 1080개, codec 반복 2,400개와 전체 경로 trial 5,700개를 검증했다. 순수 codec 비용에서만 Archive 0.1배 시간 비용의 작은 개선(DT 0.1406%, RF 0.1245%)이 있었고, 특징/예측/검증/저장 포함 상주 모델 비용은 모든 조건에서 zstd보다 6.36~708.52% 높았다. 이번 corpus/가상 정책에서 자동 선택의 실용적 비용 이득을 확인하지 못했다. 공식 모델/score와 memory 방침은 유지했다. GUI 수동 Compare 저장 검증/전체 시각 QA와 기존 공식 v2 모델의 별도 외부 평가/공식 채택은 미완료다.

직전 예측 동결: 동결한 실제 corpus 60개에서 사전 통계 특징과 후보 모델 예측 1080개를 [predictions checkpoint](data/results/usage_candidate_study_20261031_01/predictions.json)에 고정했다. 원본 full hash·모델 hash/설정/runtime·특징 순서를 확인했으며 confidence는 보정되지 않은 모델 출력이다. 이 파일들의 codec benchmark/전체 경로 실측은 아직 수행하지 않았다. 이 예측을 commit한 뒤 측정하고 사후 모델/시나리오 재선택을 하지 않는다.

직전 후보 모델 학습: 후보 모델 학습을 완료하고 [저장 검증](data/results/usage_candidate_study_20261031_01/training_verification.json)을 통과했다. 기존 train 806개만 사용해 고정 시나리오 전체의 두 모델 18개와 별도 후보 정답 9072행을 저장했다. 기존 test 202개는 개발 진단으로만 사용했고 실제 corpus는 학습에 쓰지 않았다. 모든 모델의 저장 hash·실제 class/설정·특징 순서/패키지·재로딩 예측과 train-only majority를 대조했다. 다음은 동결된 실제 60개 입력의 특징·모델 예측을 benchmark 전에 고정한 뒤 raw codec/전체 경로 평가를 실행하는 단계다.

직전 실행부 구현: 후보 모델의 별도 학습·사전 예측 동결·Compare 연결·overhead 포함 검증용 엔진·저장 감사 실행부를 구현했다. 학습 전 전용 인위적 fixture 11개가 통과했고 source/hash·테스트 출력을 [implementation lock](data/results/usage_candidate_study_20261031_01/implementation_lock.json)에 고정했다. 초기 모델 reload 검사에서 명시적 config와 estimator 기본값의 차이를 정상 모델 오류로 본 문제를 수정하고 전체 저장 매개변수·명시적 config·runtime version을 검증했다. 실제 학습·corpus 예측/측정은 아직 없으며 이 코드를 commit한 뒤 기존 train 부분으로 별도 후보 모델을 학습한다.

직전 기준/입력 동결: 사용자 요청의 기준 확정→후보 모델 학습→실제 파일 평가 순서 중 기준/입력 동결을 완료했다. [평가 기준](research_log/usage_model_study_design_20261031.md)·[계획](research_log/usage_model_study_plan_20261031.json)에 모든 고정 총비용 시나리오/두 모델·기존 train-only 분할·전체 실패 보존·원본 그룹 동일 비중 평가와 overhead 포함 검증용 엔진 범위를 명시했다. 검토 후보 60개 전체·notice 참조 72개와 겹침 근거를 새 corpus에 연결했고 보호 파일 268개는 불변이다. 이 단계에서는 특징/예측/학습/압축을 실행하지 않았다. 다음은 별도 후보 모델과 평가 엔진 구현·fixture 검증·학습이다. 공식 score/config·기존 모델·memory 방침을 유지한다.

직전 시나리오 탐색: 실행 전 고정/commit한 가상 사용 조건으로 [Pilot 시나리오별 탐색](research_log/usage_scenarios_20261031.md)을 완료했다. 원래 1,008개 전체에서 총비용/시간 제한 각 9개 시나리오를 계산하고, 각 9,072행의 선택/비용/제약과 그룹 집계를 독립 검증했다. 기본 시간 비용의 비-zstd 선택 비율은 archive 0.30%, balanced 2.88%, fast_access 7.44%다. 시간 비용 0.1배 Archive는 28.97% 선택·2.50% 가상 총비용 절감이었다. 보호 파일 84개는 불변이다. 이는 모든 실측을 알고 있는 oracle의 가상 정책 결과이며 모델/Smart의 성능 개선이 아니다. 공식 score·모델·memory 방침을 유지했다. 다음은 실제 적용 목적·계수 근거와 후속 평가 정의를 정리하는 후보 검토 기록이다. GUI 수동 Compare 저장 검증/전체 QA·실제 corpus 선정/동결·독립 평가·새 모델은 미완료다.

직전 시나리오 고정: [가상 사용 시나리오 사전 계획](research_log/usage_scenarios_plan_20261031.json)과 [실행 전 고정 근거](research_log/usage_scenarios_frozen_20261031.json)를 보존했다. 총비용 9개와 시간 제한 9개를 고정하고 집계 fixture 테스트 7개를 통과했다. 정책점수의 교환비·세 profile의 가상 보관/복원 사용량·시간 비용 배수·절대 deadline 전체 조합과 분모/실패 규칙을 명시했다. 이 단계에서는 실제 Pilot 후보 함수 분석을 아직 실행하지 않았다. 다음은 이 계획/실행 코드를 commit한 HEAD에서 지정 freeze hash로 새 출력에 분석·독립 검증하는 작업이다. 공식 score·모델/config·memory 방침과 실제 unseen 자료는 유지한다.

직전 후보 계산부: [후보 목적 함수의 순수 계산부](research_log/usage_objectives.md)를 별도 `src/usage_objectives.py`로 구현했다. `LifetimePolicy`의 명시적 매개변수로 생애 총비용을 계산하고, 시간 제한 아래 정수 압축 크기를 최소화한다. 누락 측정은 measurement_required, 빈 시간 제약 집합은 constraint_unsatisfied로 구분하고 검증 실패/잘못된 값·overflow/0 underflow는 거부한다. 전용 인위적 테스트 25개(0.181초), 설계의 가상 비용 6개·제약 4개 대조, 기존 보호 파일 79개 불변을 확인한 [실행 근거](research_log/usage_objectives_validation_20261031.json)를 보존했다. 공식 score·모델/CLI/GUI에는 연결하지 않았고 연구 압축·학습·memory 측정을 하지 않았다. 다음 단일 작업은 가상 사용 scenario를 먼저 고정한 뒤 별도 출력에서 기존 Pilot을 탐색하는 것이다. 운영 계수·공식 전환·독립 평가와 GUI 저장 검증/전체 QA·corpus 동결은 미완료다.

직전 후보 수학 설계: 사용자에게 사용 상황 선택을 위임받아 [사용 조건 기반 후보 목적 함수 v1](research_log/usage_objective_design_v1.md)을 설계했다. 기존 세 모드를 유지하고 주후보는 `J=k_s H B+k_c T_c+k_d N T_d`의 생애 총비용, 비교 대안은 시간 제한을 만족한 후보 중 크기 최소화로 정했다. 보관 기간/복원 횟수·정책 계수의 단위·유효 범위·순위 전환 경계·동점/빈 제약 집합·후속 별도 모델/평가 계약을 기록했다. 익명 가상 비용 예제 6개·제약 예제 4개와 불변성 검산, 로컬 링크 9개·보호 파일 75개 불변을 확인했다. 운영 profile 값은 근거 미확정으로 null이며 공식 점수/모델 전환이나 새 실측을 하지 않았다. 다음 단일 작업은 별도 순수 계산부 구현과 인위적 fixture 검증이다. Memory 참고 지표 유지, GUI 저장 검증·전체 시각 QA와 corpus 동결/평가 미완료 상태를 유지한다.

직전 Pilot 탐색: 사용자 요청에 따라 [기존 Pilot 우세 조건·점수 민감도 분석](research_log/pilot_tradeoffs_20261029.md)을 완료했다. 압축 크기에서는 다른 압축기가 548/1008개에서 zstd보다 좋았다. 지표/Pareto·generator/size·공식 regret와 사전에 정한 가중치 격자를 별도 탐색 결과로 보존했다. 시간 비중을 조금 줄인 경로에서는 선택 변화가 작았고, 동일 시간 비중의 0.01 격자에서 0.88/0.06/0.06부터 비-zstd 엄격 개선 비율이 10%를 넘었다. 전용 테스트 8개·독립 저장 검증을 통과했고 보호 파일 59개는 불변이다. 공식 가중치·정답·모델은 유지하며 memory 추가/추정·새 압축·실제 unseen 평가를 하지 않았다. 다음 연구 결정은 사용 목적을 명시한 별도 후보 함수 설계이며, 수동 Compare 정식 저장 검증·GUI 전체 시각 QA와 corpus 동결/평가는 별도 미완료다.

직전 수동 GUI 진행: [사용자 수동 GUI 복원·저장 검증](research_log/gui_manual_restore_20261028.md)을 완료했다. 원래 이름의 4,433 bytes 파일이 원본 bytes와 SHA-256 모두 일치했고 GUI 표시 6개·성공 로그·package/manifest/payload·source snapshot을 대조했다. 직전 Smart 산출물/모델/config와 보호 파일 250개는 그대로다. 이번에 assistant는 복원을 재실행하지 않았고 별도 픽셀 QA·테스트 suite도 수행하지 않았다. 다음은 사용자가 같은 입력으로 수동 Compare를 실행한 뒤 원시 반복/점수/Demo/로그를 검증하는 작업이다. 창 가림/입력 guard·전체 시각 QA와 corpus 동결/연구 평가는 미완료다.

직전 합성 감사: [기존 합성 입력 재생성·후보 hash 겹침 감사](research_log/unseen_overlap_audit_20261027.md)를 완료했다. 초기 검증/Pilot의 clean 실행 commit·CPython 버전·당시 source/config·sample 계획과 매개변수를 대조해 1,080개 전체를 재생성했으며 검토 후보 60개와의 정확 full hash 중복은 0건이다. 과거 input bytes/hash·stdlib hash는 저장하지 않았으므로 기록 조건에 대한 재생성 감사이며 당시 bytes의 독립 증명은 아니다. [독립 저장 검증](data/results/real_unseen/synthetic_overlap_20261027_01/verification.json)에서 비교/index·source·보호 파일 246개 불변을 확인했고 전용 인위적 테스트 10개가 통과했다. 선정 0개·동결/특징/예측/benchmark/연구 평가는 미수행이다. 다음은 필수 notice/citation과 검토·감사 근거를 연결하는 명시적 선정/실제 corpus 동결이다.

직전 후보 검토: [후보 60개의 파일별 권리·개인정보 맥락·원본 관계 검토](research_log/unseen_candidate_review_20261026.md)를 마치고 새 검토 inventory/draft에 반영했다. 원본/notice/citation을 보존하는 무수정 로컬 연구 입력 범위에서 60개를 승인했으며, 공개 저자·예시·telemetry metadata가 있으므로 익명 자료라는 판정은 아니다. NumPy 한 파일의 CPython 유래를 확인해 PSF notice·적응 내용과 license 근거를 보완했고, 관련 지도/원래 자료/반복 run 관계를 기록했다. [독립 검증](data/results/real_unseen/real_candidate_review_20261026_01/verification.json)에서 원본 60개·기존 보호 파일 221개 및 추가 근거 포함 226개 불변, 판정/notice/draft 연결을 확인했다. 선정 0개·`evaluation_ready=false`, 합성 겹침 감사·동결·연구 평가는 미수행이다. 다음은 기존 합성 입력 재생성 근거 확인과 hash 겹침 감사다.

직전 추가 수집: [추가 원본 30개 수집·통합 draft](research_log/unseen_additional_collection_20261026.md)를 완료했다. CSV/log 각 10개·JSON/binary 각 5개를 새 경로에 확보하고, 기존 30개를 보존한 채 총 60개·여섯 형식 각 10개·잠정 원본 그룹 18개를 구성했다. [독립 검증](data/results/real_unseen/real_candidates_20261026_02/verification.json)에서 Git/전체 hash·archive member bytes/CRC·형식·정확 중복 0개·quota·그룹 상한과 기존 보호 파일 114개 불변을 확인했다. 당시 후보는 권리/개인정보 검토 `pending`, 선정 0개였고 해당 수집본은 그대로 보존했다. 이후 위 최신 검토본을 별도로 만들었으며 합성 겹침 감사·동결·연구 평가는 미수행이다.

직전 보고서: 사용자 요청에 따라 [1차 수집 보고서](research_log/unseen_collection_20261026.md)를 보강했다. 저장 inventory·계획·검증 JSON을 Python으로 읽어 원본 그룹별 실제 수량/bytes와 파일 30개의 경로·크기·hash 목록을 정리했다. 보고서 정리 다음에 부족한 30개 후보를 수집하는 순서를 명시했다. 당시 CSV/log 각 10개·JSON/binary 각 5개와 최소 6개 새 원본 그룹이 필요했으며, 기존 후보에서 검토 제외가 발생하면 대체 수집량이 더 늘 수 있다고 기록했다. 해당 보고서 작업에서는 추가 다운로드·후보 승인·압축/모델 평가를 하지 않았다. [보고서 검증 근거](research_log/unseen_collection_report_checks_20261026.json)를 보존한다.

직전 수집: [실제 파일 후보 1차 출처 검토·초안 수집](research_log/unseen_collection_20261026.md)을 마쳤다. 고정 upstream commit에서 text 10·Python 10·JSON 5·binary 5, 총 30개와 라이선스 원문 6개를 새 Git 제외 경로에 보존했다. 원본 그룹은 6개이며 각 5개다. [독립 검증](data/results/real_unseen/real_candidates_20261026_01/verification.json)에서 bytes/크기/full SHA-256/Git blob hash·정확 중복 0개·draft 연결·기존 보호 파일 총 59개 불변을 확인했다. 목표 60개/최소 12개 그룹은 미충족이고 모든 후보의 권리·개인정보 검토는 `pending`, 선정은 0개다. `evaluation_ready=false`, 합성 겹침 확인·실제 corpus 동결·압축/모델 평가는 미수행이다. 공식 3지표·memory 참고 지표 방침을 유지하며 GUI OS QA/현재 Node 시작 오류는 별도 미완료다.

직전 manifest 구현: [실제 파일 후보 도구](research_log/unseen_manifest.md)의 초안·명시적 선정·동결·기대 hash 감사·경로/수량/검토/중복/변경·실패 보존을 구현하고 전용 테스트 23개와 실제 CLI 9건의 인위적 검증을 완료했다. [최종 근거](research_log/unseen_manifest_validation_20261026_final.json)는 test fixture 전용이다. 이때는 실제 파일 수집·동결·연구 평가를 수행하지 않았고, 위 최신 진행에서 실제 원본의 미선정 draft 수집을 시작했다.

직전 환경 복구: 누락된 커널 임시 폴더를 빈 폴더로 복원해 원래 `kernel assets` 단계는 통과했으나 Node 시작 오류가 남아 있다. 구 CLI 경로 누락·현재 디스크 설정과 살아 있는 프로세스의 차이 및 독립 재현을 [진단 기록](research_log/node_repl_recovery_20261026.md)과 [근거 JSON](research_log/node_repl_recovery_20261026.json)에 보존했다. 공식 reload 연결 초기화가 timeout돼 사용자에게 MCP Restart를 요청했다. 현재 연결·화면 자동화의 전체 복구 완료는 확인하지 않았다.

직전 unseen 준비: [실제 파일 unseen 평가 사전 설계 v1](research_log/unseen_evaluation_design_v1.md)을 완료했다. 60개 파일·여섯 형식·원본 그룹/중복/출처 확인·저장 모델/baseline 고정·3지표 점수·실패 보존·평가 범위를 정했다. 60개는 수집 목표이며 설계 당시 실제 후보·예측·측정·평가는 없었다. 기존 산출물 32개 hash·Pilot 학습 라벨의 최빈 baseline·모델/설정 계약과 보호 파일 55개 불변을 확인한 [읽기 전용 근거](research_log/unseen_evaluation_design_v1_checks.json)를 보존한다. 이후 manifest 도구의 구현/인위적 검증과 실제 후보 30개의 미선정 초안을 마련했으며 연구 평가는 미완료다.

직전 GUI 진행: `gui_app.py`에 Smart 압축·복원·실제 비교 탭과 명시적 Demo 대조를 연결했다. 실제 Tk 창을 생성해 callback/queue·이벤트 응답·중복/닫기 차단·결과/오류 표시를 검증했다. 전용 15개와 계층 회귀 18개, 총 33개 테스트가 통과했다. 저장 모델 두 종류×세 mode의 압축/복원 12개 및 Compare 1개 정상, 손상 복사본 복원 1개 실패 판정과 기존 출력의 사전 차단을 확인했다. 원시 반복·공식 점수·로그/queue·보호 hash를 Python으로 재검증했다. [GUI 안내](research_log/gui_app.md)·[완료 근거](research_log/gui_validation_20261026.json)·[중단된 최초 시도](research_log/gui_validation_interrupted_20261024.json)를 보존한다. OS 클릭·선택창·스크린샷/DPI QA는 미완료다.

현재 memory 방침: 2026-10-23 사용자가 memory를 참고 지표로 보존하고, 추가 구현은 여건이 마련됐을 때 진행하기로 선택했다. [결정 기록](research_log/memory_reference_indicator_decision_20261023.md)에 기존 검토·최신 독립 감사·후보 분석 근거를 연결했다. 공식 기준은 계속 압축률·압축 시간·압축 해제 시간의 3지표이며 memory는 `validation_only`, `score_inclusion=false`를 유지한다. Memory 추가 구현·측정·4지표 전환은 재개 일정이 없는 보류 과제다. 당장의 작업 우선순위는 기존 3지표 시스템 완성이다.

최신 후보 분석은 구현·전용 fixture 11개·기존 계산부 회귀 13개·실제 분석·저장 재검증을 완료한 상태다. 고정 기준 판정은 `memory_stability_not_satisfied`이며 memory span 336개 조건 중 96개가 한계를 넘었다. Memory-only 선택은 유지됐고 core의 joint regret는 한계를 넘었다. 이 미충족 결과와 원래 실패 기록을 그대로 보존한다.

실제 설정: [config/experiment_config.json](config/experiment_config.json)

이 문서는 저장소의 코드·테스트·실험 결과·연구 로그·Git 이력을 조사한 상태 기록이다. 결과 CSV의 행 수와 평가 수치를 Python으로 읽고, 원시 결과 및 모델 평가 summary에 기록된 산출물 SHA-256을 대조했다. 최초 문서 작성과 증거 보존 단계에서는 압축 실험·학습·테스트를 재실행하지 않았다. 이후 audit 도구 정리에서는 아래에 명시한 인위적 fixture 테스트만 실행했다.

## 1. 연구 목표

「데이터의 통계적 특성을 이용한 무손실 압축 알고리즘 자동 선택 시스템 연구」

파일을 모든 압축 알고리즘으로 시험하기 전에 통계적 특징을 계산하고, 그 특징만으로 사용 목적에 적합한 압축 알고리즘을 예측한다. 항상 하나의 알고리즘을 사용하는 기준 방법보다 실제 종합 성능을 개선하는지 검증한다. 단순 압축률 비교가 목표는 아니다.

## 2. 현재 완료된 구현

| 기능 | 근거 파일 및 상태 |
|---|---|
| 압축·해제·시간 측정·무손실 검증 | `src/compressors.py` |
| 통계적 특징 추출 | `src/feature_extractor.py` |
| seed 기반 6종 합성 데이터 생성 | `src/data_generator.py` |
| 실험 실행, 원시 CSV와 재현성 metadata 저장 | `src/experiment_runner.py` |
| 3지표 종합 점수와 mode별 정답 생성 | `src/scoring.py`, `src/selection_labels.py` |
| 통계 요약, Pearson/Spearman 상관관계, 선택 비율, Pareto 분석 | `src/analysis.py` |
| 최빈 baseline, Decision Tree, Random Forest 학습·평가 | `src/train_model.py` |
| 저장 예측의 오류·confidence·regret 기여 분석 | `src/failure_analysis.py` |
| 최소 Smart Mode CLI | `smart_compress.py`: 특징 기반 예측 후 선택한 압축기 하나를 한 번 실행하고, 한 번 해제하여 검증 후 저장 |
| 독립 압축 해제 CLI | `smart_decompress.py`: 기존 version-1 manifest·payload 검증 후 저장된 해제기 하나로 복원·원본 크기/SHA-256 대조·새 출력 게시. 전용 테스트 13개와 기존 압축 회귀 5개, 기존 package 여섯 건 실제 복원 완료. 모델·특징·benchmark·memory 측정 불필요 |
| 독립 Compare Mode CLI | `compare_compress.py`: 네 알고리즘의 실제 5회 압축/해제·원시 ns·중앙값·복원 검증·기존 공식 3지표 점수를 새 출력에 저장. 실패·미실행·입력 변경·부분 저장을 구분한다. 전용 16개/회귀 16개와 README 실제 비교·재검증 완료. 모델 평가·새 Pilot과 구분 |
| 통합 CLI 진입점 | `main.py`: Smart 압축·해제·Compare 명령을 선택적으로 연결한다. 기존 파서·검증·종료 코드를 유지하고 Python 3.14 모듈 문맥의 도움말을 선택적 `prog`로 전달한다. 전용 12개/회귀 34개 및 최종 실제 호출 22건 검증 완료 |
| GUI 작업 실행 계층 | `src/gui_jobs.py`: Tk와 분리된 frozen 요청·기존 CLI 프로세스·입력/모델/source 및 산출물 검증·단일 worker/queue·실행 기록. 전용 테스트 18개와 실제 요청 14건 검증 완료 |
| Tkinter GUI·명시적 Demo | `gui_app.py`: Smart/복원/실제 비교 입력·새 출력·단일 작업·상태/결과/로그·조건 일치 시 예측/실측 대조. 전용 15개+계층 18개 통과 및 실제 Tk callback/이벤트/CLI 14개 검증. OS 클릭·파일 선택창·스크린샷/DPI QA는 미완료 |
| 실제 파일 후보 manifest | `src/unseen_manifest.py`: metadata 초안·명시적 선정·고정 정책 검증·새 manifest 동결·기대 hash 기반 감사. 전용 23개·인위적 파일 CLI 9건 검증 완료. 실제 후보 수집/겹침 확인/연구 평가 준비 완료와 구분 |
| 후보 사용 조건 모델·실제 파일 평가 엔진 | `src/usage_objectives.py`와 `research_log/run_usage_model_study_20261031.py`: 별도 후보 정답/모델·train-only 학습·성능 전 예측 동결·실제 Compare 및 특징/예측/검증/저장 경로·저장 감사 완료. 공식 Smart/GUI 모델과 분리 |
| 독립 memory 측정 | `src/memory_benchmark.py`: 참고·검증용으로 보존. 2026-10-23 사용자 결정에 따라 공식 점수 편입·추가 구현은 여건이 마련될 때까지 보류 |
| Memory 검증 기록 저장 | `src/memory_validation.py`: 반복 원시값·pair 집계·실패·환경 metadata 저장 및 종료 처리 보강 (`3e9b267`). 2026-09-15 실행은 미완료 보존, 2026-09-22 새 전체 행렬은 완료·audit 통과 |
| 완료 실행의 저장 기록 감사 | `research_log/verify_memory_validation.py`: 완료된 schema-v1 검증 기록의 일관성 확인. 미완료 실행 거부, 공식 검증 완료 판정과 구분 |
| Runtime baseline 진단 worker | `src/memory_runtime_worker.py`: 세 arm의 별도 CLI 및 fixture·Windows subprocess 검증 완료 |
| Runtime baseline 별도 runner | `src/memory_runtime_validation.py`: 구현·fixture 검증 및 2026-09-30 고정 전체 실측 완료 |
| Runtime baseline 저장 기록 감사 | `research_log/verify_memory_runtime_validation.py`: 구현·fixture 검증 및 2026-09-30 실제 저장 기록 audit 통과 |
| Runtime baseline 진단 분석 | `research_log/analyze_memory_runtime_validation.py`: 구현·fixture 검증 및 2026-09-30 실제 저장 기록 분석 완료. 과학적 memory 검증 완료·공식 score 편입과 구분 |
| Memory 안정성 후속 검증 timing worker | `src/memory_stability_timing_worker.py`: 원시 ns·출력 bytes 검증·응답·오류 처리 구현 및 전용 fixture·임시 Windows subprocess 검증 완료. 전체 실측은 미완료 |
| Memory 안정성 후속 검증 runner | `src/memory_stability_validation.py`: 고정 계획·별도 부모 실행·worker 응답 검증·원시 CSV·종료 metadata 구현 및 전용 fixture 검증 완료. 실제 attempt 분석·전체 실측은 미완료 |
| Memory 안정성 후속 검증 저장 기록 감사 | `research_log/verify_memory_stability_validation.py`: 독립 audit 구현·전용 fixture 검증 완료. 실제 후속 검증 attempt 대상 audit·분석·전체 실측은 미완료 |
| Memory 안정성 후속 검증 분석기 | `research_log/analyze_memory_stability_validation.py`: 기존 초안 검토·전용 fixture 검증 완료. 독립 audit와 결합한 후보 score·regret·사전 판정·진단 및 새 출력 저장 구현. 실제 attempt 분석·전체 실측은 미완료 |
| 동일 환경 memory·timing 반복 검증 runner | `src/memory_repeatability_validation.py`: 별도 study ID·시각 제한 없는 설계. Collector revision 2의 metadata I/O 보완과 전용 테스트 47개는 2026-10-19 완료했다. Attempt02 최초 수집 실패를 보존한 뒤 사용자 지시로 Run 2 전체를 재측정·교체했다. 활성 원시 기록은 정상 행렬이며 실제 순서 변경을 포함하는 별도 독립 감사와 후보 분석을 완료했다. 후보 안정성 기준은 미충족 |
| 동일 환경·Run 2 교체 저장 기록 독립 감사 | `research_log/verify_memory_repeatability_validation.py`: 전용 fixture 24개 및 실제 활성/원본/교체 session의 저장 일관성 감사 통과. 원래 실패·phase 검증·집계·보관·실제 순서·실행 HEAD·보고서 저장 시 입력 불변을 대조한다. 과학적 memory 채택과 구분 |
| 동일 환경·Run 2 교체 후보 분석 | `research_log/analyze_memory_repeatability_validation.py`: 기존 순수 수치 계산부를 새 독립 감사와 연결했다. 전용 fixture 11개·기존 계산부 회귀 13개 및 실제 분석·출력 재검증 완료. 고정 weight·anchor·exact tie·세 시나리오·전체 방향별 regret를 계산했으며 결과는 `memory_stability_not_satisfied`. 공식 memory 채택과 구분 |

Smart Mode는 Decision Tree 또는 Random Forest를 명시적으로 지정한다. 모델·설정·소스·환경의 일치와 모델 해시를 검사하며, 기존 출력 경로를 덮어쓰지 않는다. 선택 전에 benchmark나 네 압축기 비교를 실행하지 않는다.

2026-09-15 최초 상태 조사에서는 테스트 소스 파일 12개와 `test_` 메서드 72개를 기록했다. 이후 `c54b8f5`에서 `tests/test_memory_validation.py`가 추가되었으므로 이전 개수를 현재 전체 개수로 취급하지 않는다. [Smart Mode 연구 로그](research_log/smart_mode.md)에 전체 72개 테스트 통과 및 두 모델 × 세 mode의 README 처리 성공 기록이 있다. 이는 과거 실행 기록이며 이번 증거 보존 작업에서는 테스트를 재실행하지 않았다. README 처리 성공은 일반화 성능 평가가 아니다.

## 3. 현재 실험 규모

| 구분 | 경로 | Sample | 압축 결과 행 | 정답 행 | verified=False |
|---|---|---:|---:|---:|---:|
| 초기 3지표 검증 | `data/results/` | 72 | 288 | 216 | 0 |
| 기존 3지표 Pilot | `data/results/pilot_1008/` | 1,008 | 4,032 | 3,024 | 0 |
| 외부 실제 파일 codec 측정·후보 연구 | `data/results/usage_candidate_study_20261031_01/` | 60 | 240 | 180 (v2 참조) | 0 |

- 두 실험 모두 `samples.csv`, `compression_results.csv`, `selection_labels.csv`, `experiment_metadata.json`을 보존한다.
- generator: `random`, `small_alphabet`, `repeated_pattern`, `long_runs`, `structured`, `mixed`.
- Pilot은 generator별 168개, 파일 크기별 252개이다.
- 파일 크기: 16,384 / 65,536 / 262,144 / 1,048,576 bytes.
- 초기 검증 base seed는 `20260911`, Pilot base seed는 `20260983`이다. sample별 seed는 base seed + sample index이다.
- 기존 공식 Pilot은 합성 데이터이며 그대로다. 별도 후보 함수 연구에서 실제 60개 파일의 codec/모델 및 전체 경로 평가를 추가했다. 새 후보 정답 조건은 540개이며 공식 참조 라벨과 구분한다. 기존 공식 v2 저장 모델의 별도 외부 비교를 완료한 것은 아니다.
- **기존 72개와 1,008개 결과에는 memory 열·측정값이 없다. 이 결과는 계속 3지표 결과로 보존한다.**

## 4. 현재 사용 중인 특징

ML 입력은 `FEATURE_NAMES`의 다음 12개뿐이다.

```text
file_size
entropy
unique_byte_count
most_common_byte_ratio
zero_byte_ratio
adjacent_repeat_ratio
average_run_length
max_run_length
duplicate_block_ratio
bigram_diversity
segment_entropy_mean
segment_entropy_std
```

중복 block 크기는 16 bytes, entropy segment 크기는 4,096 bytes이다. segment entropy 표준편차는 population standard deviation이다. sample_id·seed·generator·압축 측정값·score는 모델 입력이 아니다.

## 5. 현재 압축 알고리즘과 측정 설정

| 알고리즘 | 설정 |
|---|---|
| gzip | level 9 |
| bz2 | level 9 |
| LZMA (`lzma`) | preset 6 |
| zstd | level 3 |

압축 시간과 해제 시간은 메모리의 `bytes`에 대해 `time.perf_counter_ns`로 각각 5회 측정하고 중앙값을 사용한다. 파일 입출력·특징 추출·모델 예측 시간은 이 측정값에 포함되지 않는다.

## 6. 현재 공식 score 정의

**공식 score는 압축률·압축 시간·압축 해제 시간의 3지표이다. Memory는 정식 score에 포함되지 않는다.** 프로토콜 v2, config의 `selection_modes`, `src/scoring.py`, 결과 CSV가 이 정의를 사용한다.

```text
C_a  = compressed_size / original_size
Tc_a = compression_time_ms
Td_a = decompression_time_ms

C_best  = min_a C_a
Tc_best = min_a Tc_a
Td_best = min_a Td_a

Score_m(a) = w_size       * ln(C_a / C_best)
           + w_compress   * ln(Tc_a / Tc_best)
           + w_decompress * ln(Td_a / Td_best)
```

최솟값은 같은 sample의 네 압축기 사이에서 구한다. mode별 최저 score 알고리즘이 정답이며, 완전 동점은 `gzip, bz2, lzma, zstd` 순서로 결정한다. 현재 epsilon은 사용하지 않으며 양수가 아닌 시간·비유한 값·복원 실패 등은 score 계산에서 거부한다.

`regret = predicted score - oracle best score`이며 작을수록 좋다.

## 7. 현재 mode별 weight

| Mode | 압축률 | 압축 시간 | 해제 시간 |
|---|---:|---:|---:|
| Archive | 0.70 | 0.15 | 0.15 |
| Balanced | 0.50 | 0.25 | 0.25 |
| Fast Access | 0.30 | 0.20 | 0.50 |

이 표는 현재 활성 설정이다. 아래 memory 후보 weight와 구분한다.

## 8. 현재 모델과 분할

- **Baseline:** mode별 training 정답의 최빈 알고리즘. 현재 세 mode 모두 zstd이다.
- **Decision Tree:** mode별 별도 모델. gini, splitter=best, max_depth=None, min_samples_split=2, min_samples_leaf=1, class_weight=None, ccp_alpha=0, random_state=42.
- **Random Forest:** mode별 별도 모델. n_estimators=100, gini, max_depth=None, max_features=sqrt, bootstrap=True, class_weight=None, random_state=42, n_jobs=1. 전체 매개변수는 config 및 평가 summary에 기록되어 있다.
- **공통 분할:** seed 그룹 기준 `GroupShuffleSplit`, test_size=0.20, random_state=42. 학습 806개 / 시험 202개이며 baseline의 저장 분할을 두 학습 모델도 사용한다.
- 루트 `models/`는 비어 있다. 저장 모델은 `data/results/pilot_1008/decision_tree/decision_tree_<mode>.pkl`과 `data/results/pilot_1008/random_forest/random_forest_<mode>.pkl`에 있다. 각 디렉터리에 평가 summary가 함께 있다.
- Smart Mode의 기본 모델 디렉터리도 위 Pilot 경로이다. 단일 최종 모델을 자동 채택한 상태는 아니다.

별도 후보 연구의 모델 18개는 `data/results/usage_candidate_study_20261031_01/training/`에 보존했다. 기존 train 806개만 학습했고 원래 test 202개는 개발 진단으로 구분했다. 공식 Smart/GUI 기본 경로는 바꾸지 않았다.

## 9. 현재 평가 결과 요약

근거: [model_summary.csv](data/results/pilot_1008/failure_analysis/model_summary.csv), 각 모델의 `metrics.csv`와 `strategy_comparison.csv`. 아래는 저장된 Python 계산 결과를 소수점 6자리로 표시한 것이다.

| 모델 | Mode | Accuracy | Macro F1 | 평균 regret |
|---|---|---:|---:|---:|
| Baseline | Archive | 0.995050 | 0.249380 | 0.000435 |
| Baseline | Balanced | 0.995050 | 0.249380 | 0.000326 |
| Baseline | Fast Access | 0.990099 | 0.248756 | 0.001932 |
| Decision Tree | Archive | 0.980198 | 0.247500 | 0.002999 |
| Decision Tree | Balanced | 0.995050 | 0.249380 | 0.000326 |
| Decision Tree | Fast Access | 0.970297 | 0.246231 | 0.009081 |
| Random Forest | Archive | 0.990099 | 0.248756 | 0.001788 |
| Random Forest | Balanced | 0.995050 | 0.249380 | 0.000326 |
| Random Forest | Fast Access | 0.985149 | 0.248130 | 0.004662 |

이번 Pilot에서 두 학습 모델의 baseline 대비 개선은 확인되지 않았다. Balanced에서는 세 방법이 같고, Archive·Fast Access에서는 baseline이 더 좋다.

Macro F1은 네 알고리즘을 고정하고 `zero_division=0`으로 계산한다. 실제·예측에 없는 클래스도 F1=0으로 포함한다. 높은 accuracy와 약 0.25의 Macro F1을 함께 해석해야 한다.

### 별도 후보 함수의 외부 실제 파일 평가 — 2026-10-31

고정된 가상 총비용 시나리오×두 모델 18개 조건에서 순수 codec 비용의 양의 개선은 2개 조건뿐이었다. Archive 0.1배 시간 비용에서 DT 0.1406%, RF 0.1245%로 작았다. 특징·예측·검증·저장을 포함한 상주 모델 경로의 가상 비용은 모든 조건에서 고정 zstd보다 6.36~708.52% 높았다. 모델 load는 별도 실측/비용 proxy로 구분하고 process startup/cold cache·실제 GUI/CLI 배포는 측정하지 않았다. 일부 accuracy=1은 zstd 고정과 같은 선택이며 개선을 뜻하지 않는다. 모든 조건·baseline·oracle·오류/혼동행렬/그룹 집계를 [보고서](research_log/usage_model_study_results_20261031.md)와 결과 파일에 보존했다. 단일 quota corpus·가상 정책의 기술적 비교로 제한한다.

## 10. 현재 알려진 문제와 한계

- 정답이 zstd에 집중된다. Pilot의 zstd 정답 수는 Archive 1,000개, Balanced 1,003개, Fast Access 996개이다. 나머지는 gzip이며 bz2·LZMA 정답은 없다. 분포를 맞추기 위한 데이터 삭제나 점수 조정은 하지 않는다.
- 실패 분석은 model × sample × mode 기준 21개 오류 행, 고유 sample 7개를 기록했다. 두 학습 모델이 baseline의 오류를 바로잡은 사례는 없다.
- Decision Tree 오류 11건 모두 confidence=1이며 Random Forest 오류 6건 중 4건도 confidence=1이다. confidence는 보정된 정답 확률이 아니다.
- seed 그룹 분할은 서로 다른 seed에서 생성된 유사 데이터까지 탐지하지 않는다. 실제 파일에는 원본 단위 분할 정책이 필요하다.
- 기존 결과에는 시간 반복별 원시 분포가 없다. 중앙값만으로 시간 변동·통계적 유의성·정답 안정성을 판정할 수 없다.
- 기존 공식 Pilot 전략 비교에는 특징/예측 비용이 없다. 별도 후보 연구의 실제 파일·상주 모델 package 경로는 새로 검증했으나 기존 공식 저장 모델·실제 GUI/CLI 배포·cold start 및 모집단 일반화는 미검증이다. 새 후보도 모든 조건에서 전체 경로의 비용 이득을 확인하지 못했다.
- baseline의 작은 소수 압축률 파싱 오류는 `6898bc8`에서 수정되었다. 현재 미해결 오류로 취급하지 않으며 실패 기록은 `research_log/baseline_evaluation.md`에 남아 있다.
- 프로토콜 v2의 32절은 초기 구현 현황이며 실제 진행 상태보다 오래되었다. 연구 기준은 v2를 따르되 현재 완료 상태는 이 문서와 실제 저장소를 대조한다.

## 11. Memory 관련 구현 상태와 계획/미완료

근거: [측정 설계](research_log/peak_memory_measurement_design.md), `src/memory_benchmark.py`, `src/memory_validation.py`, `tests/test_memory_benchmark.py`, `tests/test_memory_validation.py`, config의 `memory`.

### 구현된 부분 — validation_only

- Windows `GetProcessMemoryInfo.PeakWorkingSetSize`를 사용하여 bytes 단위 전체 프로세스 peak working set을 측정한다.
- sample × algorithm × compress/decompress × repeat마다 새 subprocess를 시작한다.
- 압축·해제 각각 5회 값을 반환하고 각각의 중앙값을 계산한다. `peak_memory_bytes`는 두 중앙값의 최댓값이다.
- worker 출력의 SHA-256을 기대값과 대조하고 반복 검증 결과를 집계한다.
- backend의 양수 반환, gzip 반복 측정, 잘못된 입력 거부 테스트가 구현되어 있다.
- 이 값에는 Python runtime·입력·출력·네이티브 라이브러리가 포함된다. 압축 라이브러리만의 순수 할당량이 아니다.
- `c54b8f5`에서 별도 validation runner의 long-form 원시 CSV, pair 집계, worker 실패 기록, 설정·환경·소스 hash metadata 저장을 구현했다. 구현 완료와 실제 검증 실행 완료는 구분한다.

### 증거 보존 완료 — 2026-09-15 실행은 incomplete / validation_only

보존 경로: [memory_validation_20260915](data/results/memory_validation_20260915/). 성공한 공식 연구 결과나 4지표 실험이 아니다. 2026-09-16에 기존 파일을 읽기 전용 Python으로 집계했으며, 측정·복원·audit 스크립트를 재실행하지 않았다.

| 원본 파일 | 크기(bytes) | 저장 내용 |
|---|---:|---|
| [samples.csv](data/results/memory_validation_20260915/samples.csv) | 6,581 | 생성 정보·입력 hash 22행. 원본 sample bytes는 없음 |
| [memory_repeats.csv](data/results/memory_validation_20260915/memory_repeats.csv) | 276,583 | 원시 반복 기록 855행: `ok` 854행, `worker_failed` 1행 |
| [memory_summary.csv](data/results/memory_validation_20260915/memory_summary.csv) | 16,949 | 저장된 pair 집계 85행, 모두 `verified=True` |
| [memory_validation_metadata.json](data/results/memory_validation_20260915/memory_validation_metadata.json) | 8,133 | 실행 계획·설정·환경·Git·소스 hash 및 마지막 진행 checkpoint |

원본 4개 합계는 308,246 bytes이다. 보존용 `.gitattributes`는 원본 실행 산출물이 아니며 이 합계에 포함하지 않는다. 해당 파일은 이 폴더의 CSV·JSON에만 줄바꿈 변환을 비활성화하여 원본 바이트를 보존한다.

- 계획은 sample 24개 / pair 96개 / repeat 960개였으나 저장된 기록은 각각 22개 / 85개 / 855개이다. 계획된 repeat key 105개가 없으며 저장된 key의 중복·계획 외 key는 없다. `memory_000022`, `memory_000023`의 sample 기록도 없다.
- 마지막 기록은 `memory_000021`, `long_runs`, 1,048,576 bytes, seed `20260936`, `bz2`, `compress`, repeat 5의 실패이다. `return_code=4294967295`, `error="Worker exited with code 4294967295"`이며 메모리 값·`verified`·stdout·stderr는 비어 있다. 성공한 무손실 측정값으로 사용하지 않는다. 이 기록만으로 worker 종료나 전체 중단의 구체적인 원인을 확정할 수 없다.
- metadata는 `run_status="running"`, `repeat_count=850`, `failed_repeat_count=0`으로 남아 있다. 실제 원시 CSV와 다른 미완료 checkpoint이며 실패 없음 또는 현재 프로세스 실행 중이라는 근거가 아니다. runner는 pair 완료 후 metadata를 저장하므로 마지막 부분 pair의 원시 기록이 metadata보다 앞서 저장될 수 있다.
- 종료 필드 `finished_at_utc`, `repeat_status_counts`, `source_sha256_at_end`, `provenance_unchanged`, `artifact_sha256`가 없다. 종료 처리가 완료되었다고 판단할 수 없다. 원본 metadata를 사후 수정하거나 누락 행을 보충하지 않았다.
- summary의 `verified=True`는 저장된 pair에 한정된다. 전체 실행의 성공, runtime baseline 검증, 공식 memory score 편입을 의미하지 않는다.
- metadata는 시작 시각 `2026-09-15T11:02:20.343691+00:00`, 실행 commit `c54b8f5f9b7ae114206b43ce1e23fe4b69666203`, 당시 `worktree_dirty=false`를 기록한다. 2026-09-16 보존 점검 당시 파일과 기록된 소스·설정 hash의 일치는 읽기 전용으로 확인했지만 실행 종료 시 소스 불변성을 소급 증명하지는 않는다. 이후 종료 처리 보강으로 현재 runner 소스는 당시 기록과 다르다.
- metadata의 `environment.python_executable`에는 로컬 계정명과 절대 경로가 있다. 원본 증거로 로컬 Git에 보존하며 이번 작업에서는 push하지 않는다. 외부 공개 전 해당 정보의 공개 여부를 검토해야 한다.

다음 SHA-256은 **2026-09-16 보존 점검 시 원본 바이트에서 계산한 값**이며, 누락된 실행 종료 hash를 대신한 당시 기록이 아니다.

| 원본 파일 | 보존 점검 SHA-256 |
|---|---|
| samples.csv | `5c3fb733f55b9134d2aeb12cdc3ef578c0ca0cf390eabdd9689f0f35cdd3d4c6` |
| memory_repeats.csv | `b1f2719175b06a4511e76ba9e9dad737775a974e3e2932abd91bdc72d41b3173` |
| memory_summary.csv | `7673b5cd0884192b5fb7d8c555f3f001eba1122d3d1c0bba2bd30b912c647f0a` |
| memory_validation_metadata.json | `1698a3b46b2cde14864a9073588e45880aedbc38640217a66361f5082d536c45` |

### 계획/미완료

- 네 압축기·네 크기 전체 행렬 실행과 실행 내 반복 변동의 집계는 아래 2026-09-22 결과로 완료했다. 작은 파일의 runtime baseline 영향과 실행 간 안정성 검증은 미완료이다. 위 2026-09-15 미완료 증거는 별도로 보존한다.
- 공식 experiment runner 연동 및 공식 결과 schema 확장. 별도 validation runner의 원시값·집계·실패 저장은 구현되었으나 공식 파이프라인 편입은 미완료이다.
- 새 기준의 50~100개 검증 실험 후 공식 4지표 score 활성화 및 새 Pilot 실행.
- `research_protocol_v3.md` 작성 및 공식 전환 기록. 현재 해당 파일은 없다.

측정 설계 문서에는 다음 **후보 weight**가 있다. 현재 config의 활성 weight가 아니며, 검증·공식 전환을 마친 값도 아니다.

| Mode | 압축률 | 압축 시간 | 해제 시간 | Memory |
|---|---:|---:|---:|---:|
| Archive | 0.65 | 0.10 | 0.10 | 0.15 |
| Balanced | 0.40 | 0.20 | 0.20 | 0.20 |
| Fast Access | 0.20 | 0.20 | 0.45 | 0.15 |

후보 추가 항은 `w_memory * ln(peak_memory_bytes / 같은 sample의 최소 peak_memory_bytes)`이다.

**기존 1,008 sample Pilot에는 memory 측정값이 없으므로 4지표 결과로 바꾸지 않는다. 과거 CSV·라벨·모델은 보존하고, 향후 4지표 실험은 별도 버전과 경로로 기록한다.**

### Audit 도구 정리 완료 / 인위적 fixture 검증 — 2026-09-16

근거: [audit 스크립트](research_log/verify_memory_validation.py), [전용 테스트](tests/test_verify_memory_validation.py).

- 기존 staged 스크립트의 `assert`를 명시적 `AuditError` 검사로 교체했다. `-O`·`-OO`에서도 실패 검사를 유지한다.
- 지원 범위는 `run_status=completed`, `validation_only`, `score_inclusion=false`인 schema-v1 전체 검증 행렬이다. 네 압축기·두 phase·각 5회 및 기존 generator·설정 크기·seed 계획을 확인하고, 누락된 hash manifest나 불완전한 행렬을 거부한다. `running`, `interrupted`, `aborted`, `completed_with_failures` 등은 성공 보고서를 만들지 않는다.
- 입력을 메모리에서 재생성하여 hash를 확인하고 저장 원시값으로 집계 통계를 재계산한다. 압축·해제·memory 측정은 실행하지 않는다. worker의 `verified`는 저장된 증거 확인이며 독립 복원 검증이 아니다. 압축 digest는 형식·반복 간 일관성을 확인할 뿐 재압축해 검증하지 않는다.
- 실행 당시 소스·설정 바이트와 현재 checkout이 일치해야 한다. 과거 결과의 소스 hash 불일치는 기록된 소스·설정을 갖춘 checkout에서 확인해야 하며 검사 생략으로 우회하지 않는다.
- 기본 출력은 stdout JSON이다. `--output`은 감사 통과 후 새 JSON만 생성하고 기존 경로는 덮어쓰지 않는다. 오류 시 CLI는 비정상 종료하며 성공 JSON을 출력하지 않는다. 아래 `-B`는 import에 따른 bytecode 파일 쓰기를 방지한다.

저장소 루트에서 사용하는 명령 형식(성공적으로 완료된 실행 경로에만 적용):

```text
python -B -m research_log.verify_memory_validation --experiment-dir <completed-run-directory>
```

검증 명령과 실제 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_validation.py -v
11 tests: OK
```

임시 폴더의 인위적 memory 값으로 성공 집계, 실패·미완료 거부, hash 불일치, 축소·중복 행렬, 비유한 집계값, worker 응답 형식, 일반/`-O`/`-OO` 오류 거부, 출력 생성·덮어쓰기 거부 및 입력 바이트 보존을 검증했다. fixture 값은 연구 결과가 아니다. 기존 실제 결과 대상 audit·메모리 재측정·복원 재검증은 실행하지 않았으며 전체 테스트 suite를 통과했다고 주장하지 않는다. 기존 원본 4개는 보존 commit과의 바이트·SHA-256 대조로 변경 없음을 확인했다.

이 도구의 테스트 통과는 실제 memory validation 성공이나 공식 4지표 전환 완료를 의미하지 않는다.

### 종료 처리 보강 검토 완료 / 인위적 fixture 검증 — 2026-09-22

근거: [validation runner](src/memory_validation.py), [종료 처리 테스트](tests/test_memory_validation.py), [audit 테스트](tests/test_verify_memory_validation.py).

작업 시작 시 위 세 파일에 있던 미커밋 변경을 검토하고 실행 검증했다. 추가 코드 수정이 필요한 문제는 발견하지 않았으며 기존 변경을 보존했다.

- metadata를 같은 디렉터리의 임시 파일에 완전히 쓰고 `flush`·`fsync` 후 `os.replace`한다. 직렬화·동기화·교체 실패 시 이전 metadata 바이트를 보존한다.
- 종료 시각·상태별 반복 수를 먼저 저장 시도한 뒤 소스 및 각 CSV hash를 별도로 계산한다. 정상 반복 종료 후에는 `finalizing`을 거쳐 최종 저장까지 성공해야 `completed`가 된다. 종료 처리 오류는 `finalization_errors`에 단계별로 기록하고, 정상 반복 종료 뒤 종료 처리가 실패하면 `finalization_failed`로 처리한다.
- 실행 본문에서 예외가 발생한 경우 종료 처리의 추가 오류가 원래 예외를 대체하지 않도록 예외 note에 남긴다. `RuntimeError`, `KeyboardInterrupt`, `SystemExit` 원본 예외와 hash·지속적인 저장 실패 조합을 fixture로 검증했다.
- audit는 `finalizing`, `finalization_failed`를 성공 실행으로 인정하지 않는다. 기존 schema-v1 audit의 완료 상태 검사로 이를 거부하며 해당 회귀 검증을 추가했다.
- 프로세스 강제 종료나 지속적인 저장장치 오류에서는 종료 기록을 보장할 수 없다. 마지막 저장 실패 시 디스크에는 `running` 또는 `finalizing` 등 이전 checkpoint가 남을 수 있다. 이번 보강은 과거 worker 종료의 구체적인 원인을 규명하거나 과거 실행을 복구한 것이 아니다.

실제 실행한 검증 명령과 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_validation.py -v
17 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_validation.py -v
11 tests: OK
```

샌드박스에서는 가상환경이 참조하는 사용자 Python에 접근하지 못해 사용자 권한으로 실행했다. 위 두 모듈의 총 28개 테스트만 통과했다고 기록하며 전체 suite는 실행하지 않았다. Memory worker는 mock으로 대체했으며, runner 테스트는 작은 인위적 입력의 준비용 압축·복원과 임시 파일 저장을 실행했다. fixture memory 값은 연구 측정값이 아니다. Audit 테스트에는 일반/`-O`/`-OO` CLI의 오류 거부 검증이 포함된다.

보존된 원본 네 파일은 Python으로 읽어 `708c9cb`의 바이트 및 SHA-256과 대조했고 모두 일치했다. 실제 memory 재측정·기존 결과 대상 audit·과거 입력의 복원 재검증·공식 4지표 전환은 수행하지 않았다. 기존 3지표 결과·설정·라벨·모델은 변경하지 않았다.

### 새 전체 memory 행렬 실행 완료 / 저장 기록 audit 통과 — 2026-09-22

근거: [새 결과 폴더](data/results/memory_validation_20260922/), [실행 metadata](data/results/memory_validation_20260922/memory_validation_metadata.json), [audit.json](data/results/memory_validation_20260922/audit.json).

- 실행 commit: `3e9b2673a116b045a5e225203e0d175429192c09`, 시작 시 `worktree_dirty=false`. 기존 설정과 base seed `20260915`를 유지했다. 이전 미완료 실행을 이어 쓰지 않고 새 경로에서 전체 행렬을 실행했다.
- 실행 시각(UTC): `2026-09-22T10:04:01.778566+00:00` ~ `2026-09-22T10:08:55.634330+00:00`. 종료 코드 0, `run_status=completed`, `finalization_status=completed`, `finalization_errors=[]`, `provenance_unchanged=true`이다.
- `measurement_status=validation_only`, `score_inclusion=false`이다. 공식 score는 계속 프로토콜 v2의 3지표이며 정식 4지표 실험이나 새 Pilot이 아니다.

| 저장 파일 | 실제 저장 내용 |
|---|---|
| [samples.csv](data/results/memory_validation_20260922/samples.csv) | 6종 generator × 4개 크기, sample 24개 |
| [memory_repeats.csv](data/results/memory_validation_20260922/memory_repeats.csv) | 24 sample × 4개 알고리즘 × 압축·해제 × 5회, 반복 960개 모두 `ok`·`verified=True`·`reference_roundtrip_verified=True` |
| [memory_summary.csv](data/results/memory_validation_20260922/memory_summary.csv) | sample × algorithm 집계 96개, 모두 `verified=True` |
| [memory_validation_metadata.json](data/results/memory_validation_20260922/memory_validation_metadata.json) | sample·pair·repeat 실패 수 모두 0, 종료 기록·환경·설정·소스 및 원시 CSV hash |
| [audit.json](data/results/memory_validation_20260922/audit.json) | `audit_passed=true`, 입력 재생성 hash·전체 행렬의 고유 key·worker JSON·집계 통계·metadata 수량 확인 |

실행 및 검증 명령:

```text
.venv\Scripts\python.exe -B -m src.memory_validation --output-dir data/results/memory_validation_20260922 --base-seed 20260915
.venv\Scripts\python.exe -B -m research_log.verify_memory_validation --experiment-dir data/results/memory_validation_20260922 --output data/results/memory_validation_20260922/audit.json
```

사용자 Python 접근이 가능한 권한으로 실행했으며 두 명령 모두 종료 코드 0이다. Audit는 저장값을 독립 재계산하고 원본 입력을 재생성했지만 memory 측정·압축·복원을 재실행하지 않았다. 측정 당시 부모 프로세스의 원본/복원 바이트 비교와 worker의 기대 SHA-256 대조를 수행했고, audit는 그 저장 증거의 일관성을 확인했다.

Python으로 저장된 audit 결과를 읽고 백분율로 계산한 실행 내 phase 그룹 192개의 CV 중앙값은 **0.396770%**, 최대는 **1.157033%**이다. 최대 그룹은 `memory_000017` / `mixed` / 262,144 bytes / `zstd` / `decompress`이다. 알고리즘·크기별 최대 압축/해제 CV는 `audit.json`의 `variation_by_algorithm_size`에 보존했다. 사전 합격 임계값을 정한 실험이 아니므로 이 값만으로 과학적 측정 검증 완료나 실행 간 안정성을 판정하지 않는다.

기존 2026-09-15 미완료 실행 원본 네 파일은 Python으로 `708c9cb`의 바이트·SHA-256과 대조해 변경 없음을 확인했다. 새 폴더의 `.gitattributes`는 CSV·JSON 줄바꿈 변환만 비활성화하여 측정·audit 바이트를 보존한다. 소스 코드·설정·기존 Pilot·모델은 변경하지 않았다. 이번 작업에서는 단위 테스트를 재실행하지 않았으며 실제 전체 행렬 실행과 audit로 검증했다. 이전 작업의 fixture 테스트 28개 통과 기록과 구분한다.

**미완료:** 아주 작은 파일의 runtime baseline 영향, 실행 간 반복 안정성, 공식 runner 연동·4지표 전환 및 새 기준의 후속 실험. 이번 실행 성공으로 이전 worker 종료 원인이 규명된 것은 아니다.

### 작은 파일 runtime baseline 검증 설계 완료 — 2026-09-22

근거: [별도 검증 설계](research_log/memory_runtime_baseline_design.md), 설계 ID `memory_runtime_baseline_v1`.

- 같은 worker 환경에서 `import_only`, `input_only`, `codec`을 비교하도록 대조군을 정의했다. 압축·해제의 실제 phase 입력을 사용하며 baseline 차이를 압축기 순수 메모리나 공식 score로 사용하지 않는다.
- 입력 크기·생성 규칙·seed·반복·run별 순서 무작위화·저장 schema·실패 보존·분석 범위를 측정 전에 정의했다. Python으로 예정 행렬을 계산했고, 이는 연구 측정값이 아니다.
- 범위 겹침과 run별 차이·순위 변동은 기술적 진단으로 해석한다. 공식 전환의 합격 임계값이나 순수 runtime 점유율을 주장하지 않는다.
- 코드·공식 API 근거·문서 링크·diff를 검토했다. 문서 작업이므로 실측·단위 테스트를 재실행하지 않았다. 소스·설정·기존 결과는 변경하지 않았다.
- **설계 작성 당시 미완료:** 별도 worker·runner·audit 구현 및 실제 측정. 이후 worker 검증은 다음 항목과 같으며, 기존 schema-v1 audit의 검사를 완화해 재사용하지 않는다.

### Runtime baseline worker 구현·검증 완료 — 2026-09-22

근거: [worker](src/memory_runtime_worker.py), [전용 테스트](tests/test_memory_runtime_worker.py), [CLI·응답 계약](research_log/memory_runtime_baseline_design.md).

- 설계 commit `584fc68`을 기준으로 `import_only`·`input_only`·`codec`의 공통 진입점을 구현했다. 기존 측정 모듈·설정은 그대로 사용하며 설계와 설정 일치를 검사한다.
- Controls의 `verified`는 null, 입력 대조군의 `input_verified`와 codec의 출력 검증은 서로 구분한다. `codec`은 선택한 압축 또는 해제 호출만 한 번 실행하고 출력 hash를 확인한다. 원본/복원 바이트 비교와 참조 준비는 부모 runner 책임이다.
- peak는 hash 검증 후, 응답 생성·JSON 출력 전에 조회한다. hash 불일치도 peak와 false를 남기며, 실행 오류·잘못된 peak·중단을 성공으로 바꾸지 않는다.
- 아래 전용 테스트 13개가 통과했다. 인위적 peak fixture와 임시 입력의 실제 Windows subprocess smoke test를 사용했다. 모든 arm·알고리즘·phase 성공 경로와 일반/`-O`/`-OO` hash 불일치 거부를 포함한다. smoke test는 실제 backend를 사용했으나 baseline 연구 결과로 저장·집계하지 않았다.

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_worker.py -v
13 tests: OK
```

전체 테스트 suite 및 예정 baseline 전체 실험은 실행하지 않았다. worker는 결과 파일을 쓰지 않으며 기존 연구 결과·config·3지표 라벨·모델을 변경하지 않았다. **당시 미완료:** 부모의 참조 준비·응답 검증·timeout·원시 CSV 저장·종료 metadata를 담당하는 전체 runner, 별도 audit, 전체 실측 및 공식 4지표 전환. 이후 runner 구현은 다음 항목과 같다.

### Runtime baseline runner 구현·검증 완료 — 2026-09-30

근거: [runner](src/memory_runtime_validation.py), [전용 테스트](tests/test_memory_runtime_validation.py), [저장·실행 계약](research_log/memory_runtime_baseline_design.md).

- 시작 기준 HEAD는 worker 구현 commit `018758c`이며 작업 트리는 깨끗했다. 별도 runner와 fixture 테스트를 하나의 실행 기능으로 구현했다.
- 고정된 입력 생성 명세와 run별 무작위 schedule을 먼저 저장하고 세 run을 별도 부모 subprocess에서 순차 실행한다. 부모는 전체 참조 압축물의 실제 복원 bytes와 phase 입력 파일을 검증한 후 worker를 호출한다.
- 요청·설계 식별자, 입력 크기, 타입, arm별 null/boolean 규칙, 양수 peak 및 종료 코드 조합을 검증한다. worker timeout·잘못된 응답·hash 불일치·준비 실패를 원시 CSV와 stdout·stderr로 보존한다. 실패 조건의 정상 집계는 null이다.
- run별 `references.csv`에 실제 입력·압축물 hash와 참조 복원 결과를 저장한다. 원시 반복은 즉시 flush하고 종료 metadata는 원자적으로 저장한다. 시작·종료 환경과 가용 메모리, 소스·설정·plan 변경, 산출물 hash, 원래 예외와 추가 종료 오류를 기록한다. 기존 출력 경로를 덮어쓰지 않는다.
- `completed`는 실행·저장 완료 상태이며 독립 audit 통과나 과학적 검증 완료를 의미하지 않는다. `validation_only`, `score_inclusion=false`를 유지하고 `diagnostic_summary.json`은 아직 생성하지 않는다.

실제 실행한 검증 명령과 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_validation.py -v
19 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_runtime_worker.py -v
13 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_validation.py -v
17 tests: OK
```

위 세 모듈의 테스트만 통과했으며 전체 suite는 실행하지 않았다. Runner의 측정값은 인위적 fixture이고, 임시 입력의 실제 참조 압축·복원 및 별도 부모 프로세스 CLI 저장 흐름을 검증했다. 실제 Windows worker 연결 smoke test의 peak는 연구 결과로 저장·집계하지 않았다. 샌드박스의 사용자 Python 접근 제한으로 테스트는 사용자 권한으로 실행했다.

**당시 계획/미완료:** 별도 audit, paired 대비·run 간 범위·순위 진단 구현과 fixture 검증, 전체 baseline 실측, 공식 4지표 전환. 기존 연구 결과·config·3지표 라벨·모델은 변경하지 않았다. 이후 audit 구현은 다음 항목과 같다.

### Runtime baseline 별도 audit 구현·fixture 검증 완료 — 2026-09-30

근거: [audit](research_log/verify_memory_runtime_validation.py), [전용 테스트](tests/test_verify_memory_runtime_validation.py), [감사 계약·한계](research_log/memory_runtime_baseline_design.md).

- 시작 기준 HEAD는 runner 구현 commit `9d3f120`이며 작업 트리는 깨끗했다. 새 audit와 fixture 테스트를 하나의 저장 기록 검증 기능으로 구현했다.
- runner·worker·압축 모듈을 import하지 않고 고정 입력 및 전체 schedule을 재생성한다. 원본 입력 hash, 실제 phase 참조, arm별 null/boolean, worker JSON, 원시 행의 순서·완전성·중복, 집계를 독립 확인한다.
- 최상위와 모든 run의 성공 종료 상태·수량·환경·Git·소스·설정·산출물 hash와 부모 출력을 검사한다. 미완료·실패 상태, 비유한 수·중복 JSON key·잘못된 CSV 열, 감사 도중 파일 변경을 거부한다. 일반 실행 및 `-O`·`-OO`에서도 검사를 유지한다.
- 원본 파일은 읽기 전용이며 기본 출력은 stdout이다. `--output`은 감사 통과 후 새 JSON만 만들고 기존 파일은 덮어쓰지 않는다. 실제 연구 기록에 대한 audit 성공을 주장하지 않는다.
- 저장 복원 flag와 압축물 hash는 일관성 검사의 대상이다. 압축·복원·memory 측정 재실행이나 증거 진위 인증이 아니다. 공식 score는 계속 3지표이며 memory는 `validation_only`이다.

실제 실행한 검증 명령과 결과:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_runtime_validation.py -v
15 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_validation.py -v
11 tests: OK
```

전체 예정 행렬 크기의 임시 fixture에 인위적 peak와 테스트용 Git 정보를 사용했다. Fixture 준비는 실제 입력 생성·참조 압축·복원·저장을 수행하고 worker·부모 호출은 mock했다. Audit 실행 중 압축·복원·측정을 금지한 성공 검사와 hash를 다시 맞춘 오류 증거 거부, 입력 바이트 보존, CLI·최적화 모드·출력 독점 생성을 검증했다. 테스트는 사용자 Python 접근이 가능한 권한으로 실행했으며 위 두 모듈만 통과했다고 기록한다.

**당시 계획/미완료:** paired 대비·run 간 범위·순위 진단 구현과 fixture 검증, 전체 baseline 실측과 실제 저장 기록 audit, 공식 4지표 전환. 기존 schema-v1 audit·runner·worker·config·연구 결과·모델은 변경하지 않았다. 이후 진단 분석 구현은 다음 항목과 같다.

### Runtime baseline 진단 분석·fixture 검증 완료 — 2026-09-30

근거: [진단 분석기](research_log/analyze_memory_runtime_validation.py), [전용 테스트](tests/test_analyze_memory_runtime_validation.py), [분석 계약](research_log/memory_runtime_baseline_design.md).

- 시작 기준 HEAD는 별도 audit 구현 commit `c9bf6e6`이며 작업 트리는 깨끗했다. 분석기·fixture 테스트를 하나의 진단 기능으로 구현했다.
- 기존 audit를 직접 실행하고 감사한 바이트와 원시 입력 hash를 대조한 뒤 계산한다. 분석 종료 때 감사 증거와 관련 소스 변경을 검사하며 실패·미완료·감사 후 변경을 거부한다.
- run별 원시 peak·통계, 같은 run·round·block의 paired 차이/비율과 통계, 모든 arm 쌍 및 알고리즘 쌍의 중앙값 차이·동점·반복 범위 겹침을 저장한다. Run 간에는 각 run의 중앙값/차이와 범위·부호 일치만 요약하며 반복을 합치지 않는다.
- 음수 차이·1 초과 비율·동점을 보존한다. 비율의 부호 기준은 1이며 범위가 경계에서 맞닿아도 겹침으로 기록한다. Paired 차이의 중앙값과 중앙값끼리의 차이는 구분한다.
- 기본 출력은 stdout이며 `--output`은 새 JSON만 생성한다. 기존 원시값·metadata는 읽기 전용이다. `validation_only`, `score_inclusion=false`와 해석 한계를 보고서에 기록한다.

실제 실행한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_analyze_memory_runtime_validation.py -v
7 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_runtime_validation.py -v
15 tests: OK
```

테스트의 peak는 인위적 fixture이다. 임시 전체 행렬 fixture 준비에 실제 참조 압축·복원을 사용하고 worker·부모 호출은 mock했다. 분석 중에는 압축·복원·측정을 금지한 상태에서 실제 audit 연동을 검증했다. 원본 바이트 보존·잘못된 증거 거부·CLI 출력 덮어쓰기 거부·일반/`-O`/`-OO` 오류 거부도 확인했다. 샌드박스의 사용자 Python 접근 제한 때문에 테스트는 사용자 권한으로 실행했다. 전체 suite는 실행하지 않았다.

**당시 계획/미완료:** 전체 baseline 실측, 실제 저장 기록의 audit·진단 분석, 공식 4지표 전환. 기존 runner·worker·audit·config·연구 결과·3지표 라벨·모델은 변경하지 않았다. 이후 전체 실행은 다음 항목과 같다.

### Runtime baseline 전체 실측·audit·진단 완료 — 2026-09-30

근거: [결과 및 해석 기록](research_log/memory_runtime_baseline_results_20260930.md), [원시 증거 폴더](data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/), [audit](data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/audit.json), [진단 JSON](data/results/memory_runtime_baseline_v1_20260930T120130Z_attempt01/diagnostic_summary.json).

- 실행 commit `729b97b09771ea2a50e955b22f5023d49b61733a`, 시작 `worktree_dirty=false`. 기존 결과에 이어 쓰지 않고 `attempt01`의 새 경로에서 사전 고정 전체 행렬을 실행했다.
- UTC `2026-09-30T12:01:31.276279+00:00` ~ `2026-09-30T12:23:43.063204+00:00`. 세 run의 총 5,400개 반복 모두 `ok`, 실패 0. 실행·종료 처리 `completed`, 종료 오류 없음, 소스 불변이다.
- 독립 audit와 진단 분석 명령 모두 종료 코드 0. 별도 audit와 진단에 포함된 audit의 입력 hash manifest 일치를 Python으로 확인했다. 분석은 측정·압축·복원을 재실행하지 않았다.
- Python으로 실제 진단 JSON을 집계한 결과, run별 알고리즘 쌍의 반복 범위 겹침은 121/180, 116/180, 120/180이다. 세 run에서 차이 부호가 모두 같은 조건은 113/180, 양·음 부호가 뒤집힌 조건은 64/180이다. Paired `D_codec` 중앙값이 음수인 조건은 run별 16/120, 17/120, 14/120이며 삭제·보정하지 않았다.
- 이 수치는 같은 환경의 기술적 진단이다. 모든 작은 입력에서 압축기 메모리 차이나 순위가 안정적으로 구별됐다고 주장하지 않는다. 범위 겹침은 신뢰구간이 아니고 baseline 대비 차이는 순수 메모리 할당량이 아니다.
- `validation_only`, `score_inclusion=false`를 유지했다. 기존 metadata의 분석 대기 상태는 runner 종료 시점 기록으로 보존하고 후속 완료는 별도 보고서에 남겼다. 실행 소스 hash에 포함된 사전 설계 문서도 변경하지 않아, 그 문서의 미실행 표시는 실행 전 시점의 상태이다. 최신 진행 상태는 이 문서와 실제 결과를 따른다.

실행 명령·환경·집계 재현 코드는 위 결과 기록에 있다. 사용자 Python 접근이 가능한 권한으로 실행했다. 이번에는 실제 전체 행렬·audit·진단 및 문서·Git 증거 보존을 검증했고 단위 테스트는 재실행하지 않았다. 기존 결과·소스·config·3지표 라벨·모델은 변경하지 않았다.

**미완료:** memory 지표의 과학적 채택 판단과 추가 검증 필요성 검토, 공식 4지표 전환 및 새 기준 후속 실험.

### Runtime baseline Git 증거 보존 마무리 — 2026-10-06~07

시작 HEAD는 `729b97b`이다. 실제 Git 상태를 사용자 권한으로 확인한 결과, 위 전체 실측 결과 폴더와 결과 보고서는 untracked, 이 진행 문서는 수정 상태였다. 따라서 실측·audit·진단은 완료되었으나 당시 Git 보존은 미완료였으며, 이번 작업에서 해당 증거와 문서만 함께 local commit한다. 샌드박스에서 삭제처럼 표시된 기존 Pilot 파일은 접근 제한이 원인이었고 실제 삭제가 아니었다.

- 사용자 Python의 `-B` 실행으로 `verify_memory_runtime_validation.audit()`와 `analyze_memory_runtime_validation.analyze()`를 읽기 전용으로 재실행했다. 생성 시각 필드만 제외하고 저장 audit·진단 JSON 전체 내용과 재계산 결과가 일치했다. 별도 audit와 진단 내부 audit의 입력 hash manifest도 일치했다.
- 원시 CSV를 Python으로 다시 읽어 반복 5,400개 모두 `ok`임을 확인했고, 결과 보고서의 run별 음수 paired 차이·범위 겹침·동점 및 run 간 부호 일치·양음 역전·알고리즘 쌍별 집계를 재확인했다. 두 문서의 로컬 링크 50개가 존재했다.
- 검증 전후 결과 폴더의 파일 24개 SHA-256이 모두 같았다. 폴더의 `.gitattributes`는 모든 파일의 줄바꿈 변환을 비활성화한다. Stage된 파일은 증거 24개와 문서 2개뿐이며, 모든 증거의 Git blob SHA-256이 원본과 일치했다. 기본 `git diff --cached --check`는 보존된 CRLF를 후행 공백으로 표시했으므로 원본 바이트를 유지하고 일회성 `git -c core.whitespace=cr-at-eol diff --cached --check`로 검사하여 통과했다. Git 설정은 변경하지 않았다.
- 이번 작업은 기존 저장 기록의 일관성과 Git 보존 검증이다. Memory 측정·압축·복원·단위 테스트는 재실행하지 않았다. 소스·설정·기존 연구 결과·라벨·모델을 변경하지 않았다.

**계속 미완료:** memory 지표의 과학적 채택 판단·추가 검증 필요성 검토·공식 4지표 전환. 공식 기준은 v2의 3지표, memory는 `validation_only`, `score_inclusion=false`이다. 자신의 보존 commit hash를 넣기 위한 반복 commit은 만들지 않는다.

### Memory 지표 채택·추가 검증·공식 전환 조건 검토 완료 — 2026-10-07

근거: [채택 검토 문서](research_log/memory_adoption_review_20261007.md), 실제 결과 보존 commit `3f7e91f`, runtime baseline 실행 코드 commit `729b97b`. 시작 작업 트리는 사용자 권한의 실제 Git 상태로 깨끗함을 확인했다.

- **완료:** 기존 설계·worker 코드·실제 결과를 대조하고 memory의 공식 score 채택 보류를 권고했다. 저장 일관성 검증 완료와 과학적 채택 근거를 구분했다. 이는 검토 권고이며 공식 프로토콜 변경 승인이나 추가 실측 실행이 아니다.
- **검증:** Python으로 원시 반복 상태·크기별 범위 겹침·run 간 부호 일치·양음 역전을 재집계했다. 검토 문서의 표와 재현 코드 출력이 실제 값과 일치했고 로컬 링크 14개를 확인했다. 기존 보호 대상 증거·소스·설정·설계 및 결과 문서 53개의 SHA-256이 검토 전후 같았다. Microsoft 공식 API 문서의 지표 정의도 확인했다.
- **계획/미착수:** 공식 후보 worker 경로, 최종 `max_of_phase_medians`의 실행 간 안정성, timing·memory 변동이 정답에 미치는 영향, 새 측정 전 판단 기준을 정하는 후속 검증 설계. 새로운 실측·소규모 4지표 후보 검증·공식 전환 및 새 Pilot은 별도 후속 단계이다.
- 이번 작업은 문서 근거·수치·재현 코드·링크·diff를 검증했다. 새 측정·압축·복원·audit·모델 학습·단위 테스트는 재실행하지 않았고 소스·config·기존 결과·3지표 라벨·모델은 변경하지 않았다.

공식 기준은 계속 v2의 3지표이며 memory는 `validation_only`, `score_inclusion=false`이다. 후보 weight와 추가 검증의 수치 임계값은 이번 검토에서 승인·활성화하지 않았다.

### Memory 대표값·정답 안정성 후속 검증 사전 설계 완료 — 2026-10-07

근거: [후속 검증 설계](research_log/memory_stability_validation_design.md), 설계 ID `memory_stability_v1`, 시작 HEAD `d8b329a`(채택 검토). 실제 결과 보존 commit은 `3f7e91f`, 기존 실행 코드 commit은 `729b97b`이다. 시작 실제 Git 상태는 사용자 권한으로 깨끗함을 확인했다.

- **완료:** 기존 memory worker 경로, 명시적 bytecode 옵션, 별도 timing worker의 원시 ns·bytes 검증·응답 계약, 새 입력·순서·날짜·환경·실패·저장·독립 audit 계약을 사전 정의했다. 기존 worker launcher에 `-B`가 없는 사실과 새 launcher의 옵션 전달을 구분했다.
- **계획 수량:** 핵심 입력 72개와 작은 입력 12개, 총 84개를 세 날짜·6 run에서 검증한다. 예정 memory 반복 20,160개, timing 자식 2,016개·원시 호출 20,160개이다. 모두 Python으로 계산한 예정 값이며 실측이나 성공 수가 아니다.
- **판단 기준 제안:** `delta=0.01`, `epsilon=0.005`에서 memory span의 log 한계 `0.0125`를 유도했다. Memory만의 변동·timing만의 변동·joint 시나리오를 나누고 방향 있는 run 간 regret을 계산한다. 기술적 유효성 실패·memory 조건 불만족·joint 조건 불만족·관측 조건 만족을 구분한다. 기준 만족은 공식 채택이나 미래 실행의 오차 상한을 뜻하지 않는다. 수치는 새 검증용 공학 정책 제안이며 과학적 허용값으로 입증된 것이 아니다.
- **검증:** Python으로 예정 규모·가중치 합·기존 후보 weight 일치·문서 산술 재현 코드·schedule key 고유성/재현성을 확인했다. 로컬 링크 9개와 기존 보호 대상 파일 54개의 SHA-256 일치를 확인하고 문서 근거·식·diff를 검토했다. 새 입력 생성·압축·복원·측정·audit·모델 학습·단위 테스트는 실행하지 않았다.

**당시 미착수/미완료:** 별도 timing worker·runner·새 audit·분석기 구현과 fixture 검증, 일정 준비·전체 실측·사전 판정 및 공식 전환. 당시에는 설계·진행 문서만 변경했다. 공식 v2의 3지표·config·기존 결과·라벨·모델·memory의 `validation_only`와 `score_inclusion=false`를 유지한다. 실측 전에는 사용자 확인 후 조건을 고정하며, 기존 실행의 판정에 새 기준을 소급 적용하지 않는다. 이후 timing worker 구현은 다음 항목과 같다.

### Memory 안정성 후속 검증 timing worker 구현·전용 검증 완료 — 2026-10-13

근거: [timing worker](src/memory_stability_timing_worker.py), [전용 테스트](tests/test_memory_stability_timing_worker.py), [사전 설계 계약](research_log/memory_stability_validation_design.md). 시작 HEAD는 사전 설계 commit `82550b8`이며 실제 작업 트리는 깨끗했다.

- **완료:** `python -B -m src.memory_stability_timing_worker` 진입점을 구현했다. Windows·bytecode 쓰기 비활성화·로드된 설정과 현재 설정·설계의 압축 및 timing 조건을 확인한다. 비어 있지 않은 원본·참조 압축물을 읽고 두 SHA-256을 확인한 뒤 선택한 압축기의 압축 5회→해제 5회만 실행한다.
- **완료:** codec 호출만 `time.perf_counter_ns()`로 감싸고 파일 읽기·hash·정확한 bytes 비교·JSON 직렬화는 timed 구간 밖에서 처리한다. 압축 출력 5개를 해제 반복 동안 보유하며 각 출력 hash와 원시 ns를 반환한다. 출력 bytes 불일치는 남은 반복도 수행해 종료 코드 2로, 일반 호출 오류·잘못된 시간은 완료 기록과 실패 시도만 보존해 코드 1로 반환한다. 미실행 반복은 생성하지 않고 명시적 중단은 전파한다.
- **검증:** 인위적 timer fixture로 순서·호출 횟수·timed 구간·압축 출력 보유·입력 사전 거부·bytes 비교·부분 실패 기록·양수 정수 시간·중단 처리를 확인했다. 임시 입력의 실제 Windows subprocess에서 네 압축기의 성공 응답과 원본 바이트 보존을 확인하고 일반·`-O`·`-OO`의 입력 hash 오류·출력 불일치·codec 오류 거부를 검증했다. 테스트 smoke timing은 연구 결과로 저장·집계하지 않았다.

실제 실행한 전용 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_stability_timing_worker.py -v
16 tests: OK
```

기본 실행 환경 초기화 오류로 사용자 권한에서 테스트를 실행했다. 전체 suite·새 전체 검증 실측·memory 측정·audit·분석·모델 학습은 실행하지 않았다. 부모의 실제 참조 복원 검증·응답 검증·timeout·저장 기능은 worker의 책임이 아니며 다음 runner 단계에 남아 있다.

**당시 계획/미착수:** 별도 후속 runner, 새 독립 audit·분석기와 각각의 fixture 검증, 일정 준비·전체 실측·사전 판정·공식 전환. 기존 사전 설계 문서의 미구현 표시는 작성 당시 상태로 보존한다. 당시에는 worker·전용 테스트·이 진행 문서만 변경했고 기존 소스·config·연구 결과·3지표 라벨·모델을 변경하지 않았다. 공식 v2의 3지표와 memory의 `validation_only`, `score_inclusion=false`를 유지한다. 이후 runner 구현은 다음 항목과 같다.

### Memory 안정성 후속 검증 runner 구현·전용 fixture 검증 완료 — 2026-10-13

근거: [runner](src/memory_stability_validation.py), [전용 테스트](tests/test_memory_stability_validation.py), [사전 설계](research_log/memory_stability_validation_design.md), timing worker 구현 commit `b1d0413`. 시작 실제 Git 상태는 깨끗했다.

- **완료:** 계획 생성 `init`과 다음 예정 run 실행 `run`을 분리했다. `init`은 깨끗한 Git 상태에서 구분되는 새 결과 폴더를 만들고 고정 입력 명세·sample hash/매개변수/중복 관계·전체 schedule·예정 key·후보 weight·기준의 원래 식·config·실행 commit·소스/설계 hash를 저장한다. 준비 실패 sample도 삭제하지 않는다. 계획·sample 파일을 기존 경로에 덮어쓰지 않는다.
- **완료:** 각 `run`은 배타적 claim을 잡고 다음 run만 별도 부모 subprocess로 시작한다. 자동 대기·worker retry·축소 행렬 CLI·중단 run 재실행 기능은 없다. 사전에 정한 여섯 run의 날짜별 수동 실행만 이어 가며, 미완료/중단 attempt는 재개하지 않는다. 사용자가 보고한 전원 모드·reboot·동시 활동·OS 업데이트 사건을 run마다 기록하고, 다른 연구 작업이 실행 중이라고 보고하면 codec/worker 시작 전에 중단한다.
- **완료:** 각 부모는 모든 참조 압축물의 실제 복원 bytes를 먼저 확인하고, run 간 참조 hash·불변 입력·현재 소스/설정을 대조한다. 기존 memory CLI와 별도 timing worker에 `-B`·`PYTHONDONTWRITEBYTECODE=1` 및 timeout을 명시한다. 각 worker 호출 전후와 run 종료 전 입력을 확인하며 duplicate JSON key·비유한 수·타입/요청/반복/출력 hash·종료 코드·stderr 오류를 거부한다.
- **완료:** 원시 memory/timing 반복을 별도 CSV에 즉시 flush한다. Timing 실패 전의 ns·검증 결과와 bundle 증거를 보존하고 미실행 key를 실패 행으로 남긴다. 실패 bundle·실패 pair를 정상 종합 집계에 쓰지 않는다. 종료 metadata를 원자적으로 저장하고 환경·가용 메모리·부하·일정 위반·소스/계획/산출물 hash·부모 출력·원래 예외와 추가 종료 오류를 보존한다. 부모의 전체 수량과 산출물 계약도 확인한다.
- **검증:** 전체 예정 행렬의 명세·seed·schedule/key를 독립 생성한 fixture와 대조했다. 작은 임시 행렬에서 실제 입력 생성·참조 압축/복원 및 인위적 peak/ns로 준비 선행·원시 저장·집계·여섯 run 순서·일정/환경 위반·중복·누락·입력/참조/계획/소스 변경·timeout·중단·저장 실패를 확인했다. 한 개의 실제 새 부모 CLI도 인위적 worker 측정 fixture로 검증했다. 일반·`-O`·`-OO`에서 명시적 응답/JSON 거부가 유지됐다. 임시 입력에 한해 네 압축기의 실제 memory/timing worker 연결 smoke test를 수행했으며 그 peak/ns는 연구 결과로 저장·집계하지 않았다.

실제 실행한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_stability_validation.py -v
36 tests: OK
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_stability_timing_worker.py -v
16 tests: OK
```

기본 실행 환경 초기화 오류로 사용자 권한에서 실행했다. 위 두 모듈만 통과했으며 전체 suite는 실행하지 않았다. 이 작업은 runner 구현 검증이다. 새 연구 attempt·여러 날짜의 전체 실측·독립 audit·정답 안정성 분석·모델 학습은 수행하지 않았다. `recording_checks_passed`는 runner의 기록 검사일 뿐 독립 audit나 과학적 판단이 아니며, `technical_validity_status`는 `pending_independent_audit`이다. 강제 프로세스 종료나 지속적인 저장 실패에서 최종 기록을 보장할 수 없고 사용자 사건 기록도 독립 인증은 아니다.

CLI 형식(아래는 사용 계약이며 이번에 연구 실행한 명령이 아니다):

```text
python -B -m src.memory_stability_validation init --attempt-id <ID> --reason <이유>
python -B -m src.memory_stability_validation run --study-dir <새 attempt 폴더> --events-file <사건 JSON>
```

사건 JSON에는 `power_mode`, `manual_reboot_since_previous_run`, `concurrent_activity`, `os_update_events`, `other_events`, `no_research_jobs_running`을 모두 넣는다. Reboot 여부와 다른 연구 작업의 부재는 boolean, 나머지는 비어 있지 않은 설명이며 사건이 없으면 `none`으로 기록한다. 정확한 CSV 열·null/검증/실패 계약은 runner의 상수와 검증 함수를 따른다.

**당시 계획/미착수:** 새 독립 audit·분석기와 전용 fixture 검증, 일정 준비·전체 실측·사전 판정·공식 전환. 사전 설계의 작성 당시 미구현 표시는 보존했다. 당시에는 새 runner·전용 테스트·이 진행 문서만 변경했으며 기존 worker·공식 config·기존 결과·3지표 라벨·모델은 변경하지 않았다. 공식 v2의 3지표와 memory의 `validation_only`, `score_inclusion=false`를 유지한다. 이후 독립 audit 구현은 다음 항목과 같다.

### Memory 안정성 후속 검증 독립 audit 구현·전용 fixture 검증 완료 — 2026-10-14

근거: [독립 audit](research_log/verify_memory_stability_validation.py), [전용 테스트](tests/test_verify_memory_stability_validation.py), [사전 설계](research_log/memory_stability_validation_design.md), runner 구현 commit `a47ba950e777df49751563105385744c2309e147`. 시작 HEAD는 이 runner commit이며 실제 작업 트리는 깨끗했다.

- **완료:** 별도 audit가 고정 입력 명세·seed·전체 schedule/예정 key·후보 weight·기준 식을 직접 재구성한다. 기록된 소스·config hash를 먼저 확인하고 순수 `src.data_generator`와 작은 입력의 고정 식으로 원본 hash·생성 매개변수·중복 관계를 재확인한다. Runner·worker·compressors·scoring은 import하지 않는다.
- **완료:** 모든 run의 참조 일관성·원시 행의 순서/완전성·argv와 임시 phase 경로·bytecode 옵션·요청/입출력 hash·worker JSON·검증 flag·종료 코드·원시 peak/ns를 검사하고 phase 중앙값·ratio·ms 변환·최종 memory 최댓값을 독립 재계산한다. Run/coordinator의 일정·환경·사건 기록·Git·수량·종료 상태·불변 파일·산출물 hash·부모 stdout/stderr도 대조한다.
- **완료:** 미완료·실패·일정/환경 위반·중복 JSON key·비유한 수·잘못된 CSV·진행 중/남은 claim을 거부한다. 입력·소스·audit 코드의 읽은 바이트를 종료 시 다시 비교한다. `python -B`를 요구하며 기본 출력은 stdout이다. `--output`은 audit 통과 후 새 JSON만 만들고 기존 파일을 덮어쓰지 않는다.
- **검증:** 전체 예정 행렬 크기의 임시 fixture를 사용했다. 입력과 참조 압축/복원은 실제 준비했지만 peak/ns·Git commit·시각·사건은 인위적 테스트 값이다. 전체 성공·원본 바이트 보존·금지된 producer/codec 호출 거부·hash를 다시 맞춘 잘못된 증거 거부·일정 경계·CLI의 금지 import 차단·출력 덮어쓰기 거부·일반/`-O`/`-OO` 오류 거부를 검증했다. 입력 재생성은 전체 성공·CLI 검증에서 실제 수행하고, 나머지 오류 사례에서는 독립 재생성해 확인한 canonical fixture 입력을 재사용했다.

실제 완료한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verify_memory_stability_validation.py -v
25 tests: OK
```

기본 실행 환경의 초기화 오류로 사용자 Python 접근이 가능한 권한에서 실행했다. 초기 테스트 실행은 반복 입력 재생성 비용을 확인하고 중단했으며, fixture 입력 재사용을 적용한 위 실행은 종료 코드 0으로 완료했다. 위 전용 모듈만 통과했으며 전체 suite와 이전 테스트 모듈은 재실행하지 않았다. 새 연구 attempt·전체 실측·실제 저장 기록 audit·안정성 분석·모델 학습은 수행하지 않았다.

읽기 전용 Python으로 시작 시 tracked 파일과 대조해 진행 기록을 제외한 기존 파일 152개의 SHA-256이 모두 같음을 확인했다. 이 문서의 로컬 링크 52개가 존재했고 `git diff --check`를 통과했다. 기본 Git 줄바꿈 안내는 소스/문서의 LF→CRLF 안내이며 기존 연구 증거 파일은 변경되지 않았다.

실제 완료된 후속 attempt에 사용할 CLI 형식(이번에는 실제 연구 증거에 실행하지 않음):

```text
python -B -m research_log.verify_memory_stability_validation --experiment-dir <completed-attempt-directory>
```

`--output <new-audit-json>`은 선택 사항이다. 이 audit의 성공은 저장 증거의 일관성이다. 저장된 복원 flag와 압축물 hash는 독립 복원 재검증이 아니며, hash·사용자 사건·환경 기록은 증거의 진위나 사건을 독립 인증하지 않는다. Memory span·후보 label·regret·사전 판정 및 공식 4지표 전환은 수행하지 않았다. Runner metadata의 `pending_independent_audit`는 당시 기록으로 유지하고 후속 audit 보고서와 구분한다.

**당시 계획/미완료:** 별도 분석기 구현·fixture 검증, 일정 준비·전체 실측·실제 증거 audit·사전 판정·공식 채택 및 4지표 전환. 당시에는 독립 audit·전용 테스트·이 진행 문서만 변경했다. 기존 runner·worker·설계·공식 config·연구 결과·3지표 라벨·모델은 유지하며 memory는 `validation_only`, `score_inclusion=false`이다. 이후 분석기 검증은 다음 항목과 같다.

### Memory 안정성 후속 검증 분석기 초안 검토·전용 fixture 검증 완료 — 2026-10-16

근거: [분석기](research_log/analyze_memory_stability_validation.py), [전용 테스트](tests/test_analyze_memory_stability_validation.py), 사전 설계 commit `82550b8`와 독립 audit 구현 commit `6bea53a`. 시작 HEAD는 이 audit commit이며, 추적 파일의 변경 없이 분석기와 전용 테스트 두 파일이 untracked 상태였다. 진행 문서의 분석기 미착수 표시와 달리 초안이 존재했으므로 이를 보존해 검토·실행했다. 보완이 필요한 오류는 발견하지 않았고 두 파일의 시작 바이트를 그대로 local commit한다.

- **완료:** 분석기가 독립 audit를 직접 실행하고 감사한 바이트의 snapshot만 계산에 사용한다. 종료와 출력 저장 전후에 입력·관련 소스 hash, run 목록과 active claim을 다시 확인하며 audit 실패·미완료·증거 변경을 거부한다. 분석 중 runner·worker·compressors·공식 scoring은 import하거나 실행하지 않는다.
- **완료:** 원시 반복에서 run별 phase 중앙값·ms 변환·최종 memory 최댓값을 재계산하고, 여섯 run 대표값의 중앙값을 anchor로 사용한다. Reference·memory_only·timing_only·joint 후보 score, 정확한 동점과 차선 gap, 모든 방향 있는 run 쌍의 regret 및 anchor regret을 보존한다. 원시 반복을 run 간 합치지 않는다.
- **완료:** 핵심 층·작은 입력 층과 전체의 memory span·regret 판정, memory 산술 관계, phase/대표값의 범위·population CV, memory 알고리즘 쌍의 차이·동점·부호·범위 겹침을 보고한다. 공식 v2 비교와 후보 non-memory 비교를 구분하고 memory 선택 영향은 안정성 만족과 별도로 기록한다. 판정에는 원래 식과 반올림 전 값만 사용하며 산술 QA의 부동소수점 허용 오차는 판정에 사용하지 않는다.
- **완료:** 기본 출력은 전체 stdout JSON이다. `--output-dir`은 기존 경로를 거부하고 새 폴더에 `audit.json`, `candidate_labels.csv`, `transfer_regrets.csv`, `stability_summary.json`을 저장한다. 저장한 표의 hash·열·행 수를 summary에 연결한다. 저장 실패 시 부분 파일과 원래 예외를 보존하고 `publication_failed.json` 기록을 시도한다. 성공 반환과 실패 marker 부재를 함께 요구하며 지속적인 저장 실패에서 marker 생성을 보장하지 않는다.
- **검증:** 인위적 수치 fixture로 동점·근접 score·정확한 경계·낮은 gap의 label 변경·방향별 regret 비대칭·최댓값 phase 변경·timing/memory 영향 분리·작은 층 실패·dominant label의 span 면제 금지를 확인했다. 전체 예정 행렬 크기의 fixture에서 실제 독립 audit 연동·금지 codec 호출 차단·입력 바이트 보존·audit 전후와 계산 중 증거 변경·소스 변경·덮어쓰기 거부·저장 실패·CLI 및 일반/`-O`/`-OO` 오류 거부를 검증했다.

실제 완료한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_analyze_memory_stability_validation.py -v
21 tests: OK
```

첫 샌드박스 실행은 임시 폴더 접근 거부로 실패했으며 사용자 권한으로 재실행한 위 명령은 종료 코드 0으로 완료했다. 전체 suite와 기존 audit 전용 모듈은 재실행하지 않았다. Fixture 준비에는 실제 입력 생성·참조 압축·복원을 사용했지만 peak/ns·Git commit·시각·사건은 인위적 테스트 값이다. 전체 성공과 CLI에서는 실제 입력 재생성을 수행하고 다른 오류 검사는 독립 재생성으로 확인한 canonical fixture 입력을 재사용했다. Fixture 값과 그 판정은 연구 결과가 아니다.

읽기 전용 Python으로 진행 문서를 제외한 기존 추적 파일 154개의 SHA-256과 두 초안의 바이트가 시작 시점과 같음을 확인했다. 진행 문서의 로컬 링크와 diff도 검토했다. 샌드박스가 삭제처럼 표시한 Pilot 파일은 사용자 권한 Git 상태와 파일 hash로 확인했으며 실제 삭제가 아니었다.

실제 완료된 후속 attempt에서 사용할 CLI 형식(이번에는 실제 연구 증거에 실행하지 않음):

```text
python -B -m research_log.analyze_memory_stability_validation --experiment-dir <completed-attempt-directory> --output-dir <new-analysis-directory>
```

`--output-dir`은 선택 사항이다. 분석기는 memory/timing 측정·압축·복원·모델 학습을 재실행하지 않는다. Audit 성공은 저장 일관성이고, 후보 판정 만족은 관측한 조건에 한정된다. 독립 복원 인증·미래 오차 상한·memory 공식 채택·최종 시스템 개선을 뜻하지 않는다.

**계획/미완료:** 일정·환경 준비와 실측 전 조건 확인, 새 전체 attempt 실측·실제 증거 audit·후보 분석과 사전 판정, 공식 채택 및 4지표 전환. 이번에는 분석기·전용 테스트의 기존 초안을 검증해 보존하고 진행 문서만 갱신한다. 기존 runner·worker·audit·설계·공식 config·연구 결과·3지표 라벨·모델을 유지하며 memory는 `validation_only`, `score_inclusion=false`이다.

### Memory 안정성 후속 실측 준비 점검·일정안 작성 완료 / 조건 확인 대기 — 2026-10-16~17

근거: [실측 준비안](research_log/memory_stability_execution_preparation_20261016.md), [환경·계획 점검 snapshot](research_log/memory_stability_preflight_20261016.json), 마지막 구현·검증 commit `a51907fe8d8c220b95502977a627cef51c21bfa7`. 사용자 권한으로 확인한 시작 작업 트리는 깨끗했으며 새 후속 attempt 폴더는 없었다.

- **완료:** 실제 runner 계약을 기준으로 실행 순서·동일 HEAD 유지·사건 파일 위치·중단 보존·독립 audit·후보 분석의 명령을 정리했다. Init 후 attempt 밖의 문서 변경이나 commit도 runner의 Git 검사에 걸린다는 점과, 일정 위반을 기록한 채 측정이 진행될 수 있으므로 호출 전에 시간 창을 확인해야 한다는 점을 명시했다.
- **검증:** Python 3.14.4와 직접 의존성 버전이 requirements와 맞고 `pip check`가 통과했다. Runner config 검사와 메모리상 예정 계획의 독립 audit 계획 대조가 통과했다. 입력 생성·참조 준비·init·worker·codec은 호출을 차단한 채 계획만 확인했다. 예정 수량과 일정 창을 Python으로 확인하고 사건 JSON의 필드·미확인 null 거부 및 CLI 도움말을 대조했다. 일정 검사의 인위적 10분 소요 시간은 실측값이나 소요 시간 추정이 아니다.
- **환경 관측:** 10월 16일과 날짜 변경 후 17일의 환경을 snapshot에 구분했다. 고정 환경·config·전원 구성표·절전 설정은 일치했다. 17일 11:09경 KST에도 AC 미연결·배터리 23%였고, 배터리 자동 절전 설정은 180초이다. 전원 구성표는 균형 조정이며 Windows 설정의 실제 전원 모드는 별도 확인 대기이다. Python 프로세스 목록은 비어 있었으나 다른 종류의 작업이나 미래의 부재를 인증하지 않는다. 시스템 설정 변경·프로세스 종료는 하지 않았다.
- **제안/미확정:** 2026-10-17~19 매일 19:00 첫 run, 종료 60분 후 둘째 run의 일정안을 준비했다. 실제 허용 창은 run 1 실제 시작 시각을 기준으로 계산하고 둘째 run은 같은 날짜의 종료 후 30~90분 조건을 따른다. 사용자에게 실행 가능 날짜·시각과 동일 전원 조건·다른 연구 작업 중지 가능 여부를 요청했으나 아직 답변을 받지 않았다. 이 제안은 확정 일정이나 실행 승인이 아니다.

진행 문서를 제외한 기존 추적 파일 156개의 SHA-256을 준비 snapshot의 시작 기준과 대조했다. 준비 문서·진행 문서의 로컬 링크와 diff를 확인했다. 샌드박스의 Pilot 접근 경고는 사용자 권한 Git 상태와 읽기 전용 hash 확인으로 재확인했으며 삭제가 아니었다. 문서·준비 점검 작업으로 단위 테스트와 전체 suite는 재실행하지 않았고 테스트 통과를 새로 주장하지 않는다.

**미완료:** 사용자 일정·전원·동시 연구 작업 조건 확인과 확정 기록, 새 attempt 생성·전체 실측·실제 증거 audit·후보 분석·사전 판정·공식 채택 및 4지표 전환. 새 입력 생성·압축·복원·memory/timing 실측·실제 증거 audit·모델 학습은 수행하지 않았다. 이번에는 준비 문서·snapshot·진행 기록만 보존하며 공식 v2의 3지표와 memory `validation_only`, `score_inclusion=false`를 유지한다.

### Memory 안정성 후속 검증 즉시 착수 요청·init 준비 — 2026-10-19

근거: [착수 기록](research_log/memory_stability_execution_start_20261019.md), 준비 commit `103d1cb`. 사용자가 “지금 작업 시작해줘”라고 지시했다. 실제 현재 시각은 10월 19일 10:20경 KST였으며, 과거 18시 제안 대신 지금 착수한다. 실제 측정 `t0`는 아직 없고 run 1 metadata에서 정한다.

- **점검 완료:** 실제 Git 상태는 깨끗했고 기존 후속 attempt 폴더는 없었다. Python·패키지·config 검사와 `pip check`가 통과했다. AC 연결·균형 조정 전원 구성표·실제 AC 모드 Best Power Efficiency를 읽기 전용으로 확인했다. 실행 중인 Python 프로세스는 관측되지 않았다. 전원 설정이나 측정 소스는 변경하지 않았다.
- **다음 실행:** 이 착수 기록·진행 문서를 commit한 깨끗한 HEAD에서 새 `attempt01`을 init한다. Init 결과·경로·성공 여부는 실제 새 metadata와 반환값으로 확인하며, 이 사전 문서에서 완료를 주장하지 않는다. 이후 HEAD를 유지하므로 중간 진행은 attempt 안에 기록한다.
- **사용자 사건 답변 대기:** 다른 연구 작업 실행 여부·일반 동시 작업·업데이트·기타 사건과 AC 유지 가능 여부를 요청했다. 관측한 빈 Python 목록을 사용자 확인으로 바꾸지 않으며 답변 전 정상 사건 값이나 측정 결과를 생성하지 않는다. 실제 memory/timing run·전체 실측·독립 audit·분석·공식 전환은 아직 미실행이다.

### Memory 안정성 attempt01 Run 1 완료·제한된 저장 검증 / Run 2 시작 창 경과 — 2026-10-19

근거: [보존 attempt](data/results/memory_stability_v1_20261019T012359281616Z_attempt01/), [실행 상태 기록](data/results/memory_stability_v1_20261019T012359281616Z_attempt01/execution_status_20261019.md), [제한된 저장 기록 검증](data/results/memory_stability_v1_20261019T012359281616Z_attempt01/run_01_saved_record_review.json). 실제 측정 commit은 `f66f5c0b7e1a41ffb1af66f42d961451e5bf8ac7`이다.

- **완료:** 같은 HEAD에서 새 attempt를 init하고 sample 84개(핵심 72·작은 입력 12), sample 상태 모두 `ok`, 준비 실패·중복 입력 0개, 계획·원본 hash·종료 기록을 확인했다. 기존 Pilot이나 memory 실행에 이어 쓰지 않았다.
- **완료:** 사용자 보고를 반영한 사건 파일로 Run 1을 실행했다. 다른 연구 작업·업데이트는 없고 Steam 게임은 실행될 수 있으며, 일시적 인터넷 단절 가능성과 배터리를 꺼지지 않을 정도로 유지할 계획을 기록했다. 게임 미실행이나 지속적인 AC 연결을 확인된 사실로 만들지 않았다. 일반 ChatGPT 대화는 가능하나 로컬 고부하 작업은 변동을 키울 수 있다고 안내했다.
- **실제 실행:** KST 10:29:03.899448~10:54:05.908610, 경과 1,502.009162초. Run 1의 job 3,696개, memory 원시 반복 3,360개·timing 원시 호출 3,360개 모두 `ok`, 실패 반복 0개, 참조·pair 집계 각각 336개이다. 부모 종료 코드 0, run `completed`, coordinator `awaiting_next_run`, 종료 처리 완료·오류 없음·소스 불변이다.
- **제한된 검증:** Python으로 원시 key 전체 집합·고유성·수량·저장 검증 flag·양수 값과 phase 중앙값·ms 변환·최종 memory 최댓값·산출물 hash를 확인했다. 이는 Run 1의 저장 기록 검사이며 전체 attempt 독립 audit 통과나 새 독립 복원 인증을 뜻하지 않는다. 전체 여섯 run audit·후보 label·regret·안정성 판정·모델 학습·단위 테스트는 실행하지 않았다.
- **미완료/일정 경과:** 실제 종료에서 Run 2 시작 창을 계산하면 KST 11:24:05.908610~12:24:05.908610이다. 사용자가 작업 재개를 요청한 뒤 15:01 확인 시 Run 2는 실행되지 않았고 창이 지났다. 늦은 Run 2를 정상 일정으로 실행하거나 허용 간격을 사후 완화하지 않았다. 미실행의 구체적 원인을 인터넷 단절 등으로 단정하지 않는다. 활성 claim은 없다.

최상위 metadata의 `awaiting_next_run`, `recording_checks_passed=true`, `pending_independent_audit`는 당시 runner 저장 상태로 보존한다. 현재 일정 적격성·전체 성공·과학적 안정성 판정을 뜻하지 않는다. 기존 실행 증거 13개의 SHA-256을 기록하고 원본 bytes를 보존했다. 제한된 검증 JSON과 실행 상태 문서는 후속 기록으로 구분한다. 새 측정값·실패 행·누락 행·score·label을 보충하지 않았다.

현재 attempt는 고정 일정대로 이어갈 수 없으므로 이번 단계는 기존 증거·후속 판단·진행 기록의 Git 보존으로 마무리한다. 전체 검증 재시도는 이유와 사용자 확인을 남긴 별도 새 attempt에서 여섯 run 전체로 진행하며, 새 실측에 기존 Run 1을 재사용하지 않는다. 이번 보존 작업에서 새 attempt는 생성하지 않았다. 공식 v2의 3지표와 memory `validation_only`, `score_inclusion=false`를 유지한다.

### 동일 환경 반복 검증으로 사용자 승인 변경·별도 runner 검증 완료 / 새 Run 1 실행 준비 — 2026-10-19

근거: [새 설계](research_log/memory_repeatability_validation_design.md), [새 runner](src/memory_repeatability_validation.py), [전용 테스트](tests/test_memory_repeatability_validation.py). 시작 HEAD는 증거 보존 commit `82041e85c528e6b6edf3142d0d9861f057263118`이며 실제 작업 트리는 깨끗했다. 사용자가 고정 시각 대신 이전처럼 진행할 수 있는지 물었고, 동일 환경 반복 검증의 범위 차이를 설명한 뒤 “지금으로 진행. run 1 진행하자”라고 승인했다.

- **완료:** 별도 `memory_repeatability_v1` 설계를 새 실측 전에 추가했다. 연속 세 날짜·±60분·30~90분·같은 날짜 조건을 제거하고 실제 날짜·시각·간격을 보존한다. 관측 환경의 반복 검증으로 해석하며 날짜 간 안정성으로 일반화하지 않는다. 기존 미완료 `memory_stability_v1` attempt01은 당시 설계의 기록으로 보존한다.
- **완료:** 검증된 기존 수집 구현을 별도 runner 파일로 고정해 파생했다. 입력·seed·전체 행렬·압축기 설정·memory/timing worker·원시값·복원 검증·오류 처리·환경·소스/HEAD/hash 보존 계약은 유지한다. 새 study ID와 기존 timing worker wire protocol ID를 별도로 명시·검증한다. 새 plan과 결과 경로를 사용하고 예전 측정값을 복사하지 않는다.
- **완료:** 시간 간격만으로 실패시키지 않되 run 1~6 순서·비겹침·배타적 claim을 유지한다. 겹침은 worker 시작 전에 거부하고 종료 실패 기록을 남긴다. Job 자동 재시도·중단 run 재개·입력 축소 CLI는 추가하지 않았다. `run` CLI 한 번은 다음 run 한 개만 실행한다. 이번 사용자 요청 범위는 Run 1 한 번이다.
- **검증:** 전용 모듈에서 기존 수집 계약 fixture를 새 runner에 테스트 범위 안에서 연결하고 종료 후 원래 연결을 복구했다. 전체 계획·순서·새 ID/worker ID 구분·즉시/장시간/날짜 변경 후 이어가기·겹침 거부·일반/`-O`/`-OO` 오류 거부·원시 저장·부분 실패·중단·입력/소스/계획 변경·이전 증거 변경·저장 실패·새 부모 CLI를 검증했다. 임시 입력으로 네 압축기의 실제 worker 연결 smoke test도 수행했으나 연구 결과로 저장·집계하지 않았다.

실제 완료한 검증:

```text
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_memory_repeatability_validation.py -v
41 tests: OK
```

처음 실행에서는 겹침 거부를 다른 환경 위반에도 잘못 적용한 분기 때문에 fixture 오류 2개가 발생했다. 겹침 flag에만 해당 분기를 적용하도록 수정한 뒤 위 모듈 전체가 종료 코드 0으로 완료했다. Fixture의 peak/ns/Git/시각은 인위적 테스트 값이며 연구 결과가 아니다. 전체 suite와 기존 전용 모듈은 재실행하지 않았다. 기존 추적 파일은 진행 문서를 제외하고 SHA-256으로 보존을 확인한다.

**실행 계획/미완료:** 새 설계·runner·테스트·진행 문서를 함께 commit한 깨끗한 HEAD에서 새 attempt를 init하고 Run 1을 실행한다. 실제 생성 경로·성공 여부·실측 수량은 새 metadata와 원시 파일을 확인하며 이 사전 기록에서 완료를 주장하지 않는다. Init 후 여섯 run이 끝날 때까지 같은 HEAD를 유지하고 중간 실행 상태는 attempt 안에 기록한다. 새 프로토콜 전용 독립 audit·분석 연결과 전체 후보 판정은 미구현이다. 기존 audit를 완화해 새 결과를 통과시키지 않는다. 공식 v2의 3지표와 memory `validation_only`, `score_inclusion=false`는 유지한다.

### 동일 환경 반복 검증 attempt01 Run 1 중단·원본 보존 — 2026-10-19

근거: [새 설계 attempt01](data/results/memory_repeatability_v1_20261019T122219435170Z_attempt01/), [실패 보고서](data/results/memory_repeatability_v1_20261019T122219435170Z_attempt01/failure_report.json), 실행 commit `7a0ea69abbae7931389993b701380324cded3b42`.

- **실제 실행/미완료:** UTC 12:23:41.237151~12:29:07.291151. Job 469개 뒤 `aborted`로 종료했다. Memory 원시값 426행·timing 430행, 총 856행은 모두 저장 상태 `ok`·`verified=True`였으나 전체 예정 행렬을 완료하지 못했다. `measurements.csv`는 생성되지 않았고 정상 pair 집계·독립 audit·후보 분석은 수행하지 않았다. 실패 반복 수 0을 run 성공으로 해석하지 않는다.
- **확인한 원인:** 원래 부모 예외는 metadata 임시 파일을 `metadata.json`으로 `os.replace`하는 단계의 `PermissionError: WinError 5`이다. Coordinator의 `Parent did not finish`는 그 후속 오류다. 종료 기록은 완료했고 소스 불변을 확인했으며 활성 claim은 없다. 압축 검증 실패·게임·네트워크 단절이 원인이라고 단정하지 않는다. 특정 잠금 보유 프로세스는 확인하지 못했다.
- **보존/후속 수정:** 원시값·metadata·계획·사건·stderr를 원본 hash와 함께 별도 실패 증거로 보존한다. 중단 run을 이어 쓰거나 누락을 보충하지 않는다. 새 runner의 파일 조회에 삭제/이름 변경 공유를 허용하고 metadata 저장에만 한정한 bounded I/O 재시도를 fixture로 검증할 계획이다. 압축기나 측정 job을 재시도하는 변경은 아니다. 수정 후 새 attempt에서 전체 Run 1을 실행한다.

### 동일 환경 반복 검증 metadata I/O 수정·검증 — 2026-10-19

근거: [새 runner](src/memory_repeatability_validation.py), [설계의 collector revision 2](research_log/memory_repeatability_validation_design.md), [전용 테스트](tests/test_memory_repeatability_validation.py). 실패 attempt01 보존 commit: `b249d53`.

- **구현 완료:** 새 runner에만 collector revision 2와 metadata I/O 정책을 추가했다. Windows 읽기 핸들을 JSON 해석 전에 닫으며 read/write/delete 공유를 허용한다. 실제 Windows에서는 삭제 공유가 있어도 열린 대상에 대한 교체가 실패할 수 있음을 fixture와 설계에 반영했다. Metadata 저장만 WinError 5·32·33에 최대 5번, 합계 최대 0.50초 backoff를 적용하고 첫 예외·재시도 사건을 보존한다. Worker·압축기·측정 job 재시도는 없다. 기존 공용 writer·기존 3일 runner·과거 결과는 수정하지 않았다.
- **검증 완료:** `.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_memory_repeatability_validation.py -v`에서 실제 잠금·해제·영구 잠금·공유 조회와 기존 수집 계약을 포함한 47개 테스트가 통과했다(26.226초). 최초 수정 테스트에서는 삭제 공유만으로 교체 성공을 가정한 한 항목이 실패했고, 실제 OS 동작에 맞춰 구현 설명과 fixture를 수정한 뒤 전체를 다시 통과했다. 테스트용 원시값은 연구 실측이 아니다. 전체 저장소 테스트·새 연구 Run 1 성공·독립 audit·후보 분석 완료를 주장하지 않는다.
- **다음 실행/미완료:** 이 수정과 사전 기록을 commit하고 깨끗한 HEAD에서 새 attempt02를 init해 전체 Run 1을 실행한다. 첫 실패 attempt 원시값은 재사용하지 않는다. 성공 후에는 여섯 run 동안 HEAD를 유지하기 위해 중간 완료·제한 검사 기록을 attempt 안에 남긴다.

### 동일 환경 반복 검증 attempt02 여섯 run 수집 마감 — 2026-10-22

근거: [수집 마감 기록](data/results/memory_repeatability_v1_20261019T124938284221Z_attempt02/collection_completion.md), [Python 마감 집계](data/results/memory_repeatability_v1_20261019T124938284221Z_attempt02/collection_summary.json), [Run 6 완료 기록](data/results/memory_repeatability_v1_20261019T124938284221Z_attempt02/run_06_completion.md). 모든 run의 측정 commit은 `a8c3e47edc4f9d231605434c464b036240b7b2ed`이다.

- **실행 완료:** 고정 시각·날짜·간격 제한이 없는 별도 설계에서 동일 입력 84개로 여섯 run을 같은 HEAD에서 수집했다. Run 6은 KST 2026-10-22T16:00:45.777913+09:00~2026-10-22T16:27:29.070826+09:00, 부모 wall 1603.292913초이며 새 실패는 0건이다. 전체 최종 상태는 `completed_with_failures`이다.
- **실제 수량:** 전체 job 22176개, memory 20160행·timing 20160행으로 원시 40320행이다. Pair 기록 2016개 중 정상 flag 2013개·실패 3개다. 새로운 독립 학습 sample을 늘린 결과가 아니다.

| Run | 상태 | Job | Memory 원시 행 | Timing 원시 행 | 실패 반복 | 검증 통과 pair / 전체 |
|---|---|---:|---:|---:|---:|---:|
| 1 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |
| 2 | completed_with_failures | 3696 | 3360 | 3360 | 3 | 333 / 336 |
| 3 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |
| 4 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |
| 5 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |
| 6 | completed | 3696 | 3360 | 3360 | 0 | 336 / 336 |

- **실패 보존:** Run 2의 memory decompress timeout 3건과 해당 pair 공란을 유지했다. Windows 절전/재개 관련 로그도 해당 attempt에 보존했다. 부분 재시도·누락 보충·다른 run 값으로 대체·실패 sample 삭제를 하지 않았다. 나머지 run 성공이 Run 2 실패를 해소하지 않는다. 최종 coordinator의 `recording_checks_passed=false`와 마감 집계의 `all_repeats_successful=false`를 정상 성공으로 바꾸지 않았다.
- **제한 검사 완료:** 각 run 원시 key·검증 flag·양수 값·원시 중앙값·ns→ms·phase memory 최댓값·ratio와 소스/산출물 hash를 저장 검사로 대조했다. 마감 점검에서 전체 수량·실패·공란 pair·시각 순서/비겹침·참조 동일성과 과거 결합 파일 불변을 확인했다. 과거 보고서의 최상위 coordinator metadata hash는 당시 checkpoint이며 이후 정상 갱신되는 현재 값과 구분한다. 독립 프로토콜 audit나 후보 분석 완료를 뜻하지 않는다.
- **점검 코드 오류 수정:** 최초 마감 점검에서 이미 존재하는 `run_id`를 중복 전달한 TypeError가 결과 파일 생성 전에 발생했다. 첫 코드·오류를 보존하고 별도 `check_collection_closure_v2.py`에서 합치기를 고친 뒤 저장 무결성 점검을 통과했다. 실측 원본·이전 검사 보고서·측정 job은 변경하거나 재실행하지 않았다.
- **환경·범위:** Run 6 사전 관측은 외부 전원 미연결·배터리 62%였고 전원 로그에는 공급원 변경 이벤트가 있었다. 사용자 보고와 관측을 구분했으며 연속 AC나 게임 미실행을 인증하지 않았다. 전원·절전·덮개 설정은 바꾸지 않았다. 이번 작업에서 단위 테스트·학습·새 후보 score 계산은 수행하지 않았다.
- **Git 보존/미완료:** 여섯 run이 종료됐으므로 측정 HEAD 고정을 마감하고 진행 문서와 실제 원본 증거를 로컬 commit으로 보존한다. 공식 3지표 정의와 memory `validation_only`·`score_inclusion=false`는 유지한다. 새 설계 전용 독립 audit·분석·채택 판단과 공식 4지표 전환은 미완료다. 문서 자신의 commit hash를 넣기 위한 반복 commit은 만들지 않는다.

### Run 2 전체 재측정·활성 결과 교체 준비 — 2026-10-22

근거: [사전 변경 기록](research_log/memory_run02_replacement_amendment.md), [교체 도구](research_log/replace_memory_repeatability_run02.py), [전용 테스트](tests/test_replace_memory_repeatability_run02.py). 시작 HEAD: `d0f801d`.

- **사용자 지시:** “전체 재측정으로 다시 하고, 덮어씌우는걸로 가자.” 대상은 논의 중인 Run 2 전체이며 나머지 다섯 run은 유지한다. 이전 설계의 재측정·덮어쓰기 제한에 대한 이번 명시적 변경이며 공식 3지표 정의는 변경하지 않는다.
- **구현 완료:** 원본 attempt 전체 hash snapshot, 같은 입력·job 순서·memory/timing 전체 측정, 새 출력 staging, 독립 계산에 의한 저장 중앙값·ratio·검증·행렬 검사, 검증 후 활성 경로 교체, 실패 시 비삭제 rollback, 현재 summary/coordinator/manifest 갱신을 구현했다. 실제 Run 2 재측정은 Run 6 이후이며 시각을 소급하지 않는다. 원래 수집 실패와 교체 후 활성 결과를 구분한다. 측정 함수·worker·config·원래 설계 소스는 변경하지 않았다.
- **검증 완료:** 전용 인위적 fixture 13개 테스트가 통과했다(1.995초). 임시 폴더 접근 거부 때문에 샌드박스 실행은 실패했고 사용자 권한 실행으로 검증했다. 보관·설치·오류 rollback·절전 요청 해제·변조/잘못된 중앙값/중복 key/요청 ID 탐지·실패 pair 공란·실제 시각 순서·활성 manifest 및 coordinator 갱신을 확인했다. 전체 저장소 테스트는 실행하지 않았다.
- **실제 사전 관측:** Python으로 원래 여섯 run의 저장 무결성 검사를 통과하고 Run 2 실패 반복 3건을 확인했다. 측정 소스 hash와 고정 환경이 원래 plan과 같았다. 실제 전원 관측 UTC 2026-10-22T10:29:26.165024+00:00은 AC 연결·배터리 80%, OS 부팅 시각 UTC 2026-10-22T08:18:28.5000000Z였다. 현재 Python 검사와 그 launcher 외 다른 Python 프로세스는 관측되지 않았다. 게임/업데이트 미실행을 인증하지 않는다. 임시 thread 절전 억제·복원 API를 실제 호출해 성공했다. 영구 전원 설정은 바꾸지 않았다.
- **계획/미완료:** 사전 기록과 도구를 commit한 깨끗한 HEAD에서 한 번의 전체 Run 2 재측정을 실행한다. 다시 실패하거나 절전이 관측되면 새 원시값을 보존하고 교체하지 않는다. 성공 시 원본 보존·다른 run 불변을 대조하고 교체·검증 결과를 별도 기록한다. 변경 설계 전용 독립 audit·후보 분석·memory 채택은 이번 작업 범위가 아니다.

### Run 2 전체 재측정·활성 결과 교체 완료 — 2026-10-22

근거: [활성 Run 2 완료 기록](data/results/memory_repeatability_v1_20261019T124938284221Z_attempt02/run_02_completion.md), [활성 집계](data/results/memory_repeatability_v1_20261019T124938284221Z_attempt02/collection_summary.json), [교체 실행 기록](data/results/memory_run02_replacement_20261022T103143486097Z/replacement.json), [교체 후 Python 검증](data/results/memory_run02_replacement_20261022T103143486097Z/post_replacement_verification.json), [원본 전체 snapshot](data/results/memory_run02_replacement_20261022T103143486097Z/original_snapshot/collection_summary.json). 실제 실행 HEAD는 `9a261e46d01f61e986d98eedc11f634eda19c863`이며 재사용한 측정 코드의 원래 기준은 `a8c3e47`이다.

- **실제 실행 완료:** KST 2026-10-22T19:31:44.587980+09:00~2026-10-22T20:11:16.086534+09:00, 부모 wall 2371.498554초. Run 2 전체 3696개 job에서 memory 원시 3360행·timing 원시 3360행을 새로 측정했다. 전부 `ok`·`verified=True`, 실패 반복 0건·정상 pair 336개다. 기존 실패 세 job만 보충하지 않았고 자동 측정 재시도는 하지 않았다.
- **교체 완료:** 사용자가 지정한 기존 `run_02/` 경로의 memory/timing 원시 CSV·집계·metadata를 새 결과로 교체하고 현재 coordinator·summary·관련 기록·증거 manifest를 갱신했다. `references.csv`는 새로 준비·검증한 결과가 기존과 byte 동일하다. 논리 슬롯은 2이며 실제 새 시각을 그대로 기록했다. 활성 상태는 `completed_after_run_replacement`, 실행 순서는 1→3→4→5→6→replacement 2다. 원래 1~6 순서 계약을 충족했다고 소급 주장하지 않고 `recording_checks_passed=false`와 변경 설계 독립 감사 대기를 구분해 둔다.
- **원본 보존·검증 완료:** 원본 전체 104개 파일의 snapshot과 SHA-256 manifest, 설치 때 이동한 기존 파일을 보존했다. 최초 Run 2 timeout 3건과 실패 pair 공란도 그대로다. 다른 다섯 run의 원시 파일·metadata 25개는 hash 불변이다. 교체 후 Python으로 활성 여섯 슬롯의 전체 key·검증 flag·원시 중앙값·단위 변환·phase memory 최댓값·ratio, coordinator 산출물 hash와 활성 전체 manifest를 재대조했다. 현재 활성 원시는 memory 20160행·timing 20160행, 총 40320행이며 정상 pair 2016개·실패 반복 0건이다. 이 수치는 원본에 있었던 실패 기록을 삭제했다는 뜻이 아니다.
- **파생 기록 마감:** 최초 설치가 포함한 `validated_ready_to_install` checkpoint도 별도로 보존한 뒤, 활성 교체 기록과 그 사본을 실제 `installed_and_verified` 결과로 마감하고 현재 manifest를 다시 계산했다. 이 마감은 측정 CSV·plan·sample·run metadata를 바꾸거나 측정을 재실행하지 않았다. 검사 코드는 session의 `finalize_and_verify_replacement.py`에 보존했다.
- **환경 관측·한계:** 실행 전후 모두 AC 연결·배터리 80%를 관측했다. 해당 측정 시간 범위의 System 전원 사건 조회 결과는 빈 목록이고, 임시 idle 절전 억제 요청은 실제 성공·복원됐다. 연속 AC나 모든 OS 활동을 인증하지 않는다. 진행 중 상태 조회에서 Defender·PyCharm 등의 CPU 활동이 관측됐으나 지연 원인을 확정하지 않았고 전원 설정·프로세스·측정 정의를 바꾸지 않았다. 이 부모 wall은 준비·프로세스·저장 비용을 포함하며 codec 시간으로 해석하지 않는다.
- **Git 검증:** staged 전체 공백 검사에서는 원본 보관 파일의 기존 EOF 빈 줄 경고가 있었다. 보관 바이트를 수정하지 않았으며 원본 snapshot·이동 보관 경로를 제외한 새 변경의 staged 공백 검사는 통과했다. Python으로 stage된 경로가 이번 작업 범위인지 확인하고 모든 staged blob과 실제 파일 바이트의 일치를 확인했다.
- **검증 범위·미완료:** 사전 전용 fixture 테스트 13개를 통과한 도구로 실제 측정·교체·저장 재검증을 완료했다. 새 소스 변경이나 전체 suite 추가 실행은 없었다. 저장 무결성 검사는 변경 설계 전용 독립 프로토콜 audit가 아니다. 후보 score·변동·regret 분석·memory 공식 채택·4지표 전환은 미완료다. 현재 결과·원본 보관·진행 문서를 관련 파일만 stage하여 로컬 commit으로 보존하며 문서 자신의 commit hash를 넣기 위한 반복 commit은 만들지 않는다.

### 동일 환경·Run 2 교체 전용 독립 감사 완료 — 2026-10-23

근거: [독립 감사](research_log/verify_memory_repeatability_validation.py), [전용 테스트](tests/test_verify_memory_repeatability_validation.py), [실제 감사 보고서](data/results/memory_repeatability_audit_20261022T172740466801Z/audit.json), [실행·테스트 기록](data/results/memory_repeatability_audit_20261022T172740466801Z/invocation.json), [보고서 안내](data/results/memory_repeatability_audit_20261022T172740466801Z/README.md). 작업 시작 및 실제 감사 호출 당시 HEAD는 `f4dc8c7`이다. 호출 시 새 감사 코드·테스트는 아직 commit 전 추가 파일이었으며 정확한 코드/의존성 SHA-256과 테스트 소스 hash를 보고서·실행 기록에 남기고 이번 기능의 commit에 함께 보존한다.

- **구현 완료:** 새 `memory_repeatability_v1`과 사전 Run 2 교체 변경 전용 읽기 전용 감사다. 기존 3일 감사 모듈의 순수 계획·파싱·스키마·입력 재생성 helper만 재사용하며 기존 `audit()`·수집기·교체 도구 검사·worker·codec·scoring을 호출하거나 import하지 않는다. 기존 3일 감사·runner·설계·교체 adapter·공식 config는 변경하지 않았다. 새 감사는 원래 1~6 순서와 실패 이력을 보존한 뒤 변경에 따른 1→3→4→5→6→replacement 2의 활성 순서를 별도로 대조한다.
- **대조 범위:** 고정 입력·seed·job 순서·후보 weight·기준, 재생성한 입력 hash·매개변수·중복 보존, 원시 key·worker 명령·응답 JSON·종료 코드·검증 flag·양수 값·순서/비겹침, ns→ms·원시 중앙값·phase memory 최댓값·ratio를 독립 계산으로 확인한다. 원본 timeout의 부분 stdout은 진단으로만 보존하고 정상 peak로 편입하지 않는다. 원본 manifest·사전 이력·이동 보관본·새 staging·활성 산출물·설치 transaction·설치 전 checkpoint·마감 보고서를 대조한다. 전체 입력과 source를 snapshot으로 읽고 종료 및 보고서 저장 전후에 파일 목록·디렉터리·claim·바이트 불변을 확인한다. 기존 보고서 덮어쓰기와 입력 내부 보고서 저장을 거부한다.
- **fixture 검증 완료:** `.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_verify_memory_repeatability_validation.py -v`가 전용 24개 테스트를 303.075초에 통과했다. 전체 행렬의 인위적 peaks/ns·Git·사건 fixture이며 연구 실측이 아니다. 정상 기준 fixture를 먼저 통과시킨 뒤 rehash된 변조·실패 pair 공란·partial stdout·raw/worker 불일치·중앙값·순서·원본 manifest·metadata 재시도 이력·사전 기록·보고서 저장 실패/입력 변경·기존 출력 보존을 확인했다. fresh Python에서 금지 producer import를 차단했고 일반/`-O`/`-OO`의 잘못된 증거 거부와 기존 3일 감사기의 새 프로토콜 거부를 확인했다. 전체 저장소 suite는 실행하지 않았다.
- **개발 중 수정:** 샌드박스 임시 폴더 접근 거부로 시작하지 못한 테스트는 사용자 권한에서 실행했다. 독립 byte 비교 처리와 Windows 보고서 경로 표기, fixture의 원래 설치 대상 파일 누락 및 실제 탐지 지점에 대한 테스트 기대를 보완한 뒤 최종 전체 전용 테스트를 통과했다. 이 과정에서 연구 원시값이나 과거 실패 기록을 고치지 않았다.
- **실제 감사 완료:** UTC 2026-10-22T17:27:49.085096+00:00, CLI 종료 코드 0·stderr 0바이트이며 stdout JSON과 저장 보고서가 일치했다. 활성 105개 파일·교체 session 140개 파일과 감사/측정/adapter 관련 소스 13개의 hash를 남겼다. 활성 memory 20160행·timing 20160행, 총 40320행·2016 pair는 실패 0건이다. 원본의 동일 원시 행렬에는 실패 반복 3건·정상 pair 2013개·실패 pair 3개가 그대로 남아 있다. 원본 전체 104개 파일과 다른 다섯 run의 측정 파일·metadata 불변을 확인했다. 새 Run 2의 metadata 저장 재시도 사건 6개는 고정된 metadata-only 정책과 일치하며 측정 job 재시도와 구분했다.
- **Git 검증:** 이번 기능의 staged 파일 9개만 확인하고 실제 파일과 staged blob의 바이트 일치를 Python으로 대조했다. 전체 공백 검사의 실행 기록/실제 stdout CRLF 및 EOF 경고는 원본 출력 형식으로 보존했다. `cr-at-eol`을 허용하고 실제 stdout만 제외한 코드·문서·나머지 보고서의 staged 공백 검사는 통과했다.
- **보존·판정 한계:** 기존 활성/원본/session 파일과 manifest를 수정하지 않았고 새 압축 측정·실제 복원·후보 score·regret 계산·모델 학습은 실행하지 않았다. 입력 metadata에 남은 `pending` 또는 `independent_protocol_audit_performed=false`는 작성 당시 checkpoint로 유지하며 현재 감사 판정은 새 보고서를 참조한다. 이 감사는 저장 증거 일관성 확인이며 실행·연속 환경·절전 인과관계를 독립 인증하거나 날짜 간 안정성·과학적 memory 채택을 입증하지 않는다. 후보 분석·공식 4지표 전환은 미완료다. 이번 기능 코드·테스트·새 보고서·진행 문서만 로컬 commit으로 보존하며 문서 자신의 commit hash를 넣는 반복 commit은 만들지 않는다.

### 동일 환경·Run 2 교체 후보 분석 완료 — 2026-10-23

근거: [새 후보 분석기](research_log/analyze_memory_repeatability_validation.py), [전용 테스트](tests/test_analyze_memory_repeatability_validation.py), [실제 결과 안내](data/results/memory_repeatability_analysis_20261023T001439769818Z/README.md), [전체 진단·판정](data/results/memory_repeatability_analysis_20261023T001439769818Z/stability_summary.json), [실행 기록](data/results/memory_repeatability_analysis_20261023T001439769818Z/invocation.json), [저장 재검증](data/results/memory_repeatability_analysis_20261023T001439769818Z/verification.json). 작업 시작·실제 호출 HEAD는 독립 감사 보존 commit `3927a35c06e6c00fbae0eaaf2bd53d4cbd65e4da`다. 새 분석기·테스트는 호출 당시 commit 전 추가 파일이었으며 정확한 source/test SHA-256을 실행 기록과 함께 보존했다.

- **구현 완료:** 기존 3일 분석기를 변경하지 않고 순수 수치·CSV 함수만 재사용한다. 기존 `audit()`·`analyze()`·날짜 승인 규칙·publisher는 호출하지 않는다. 새 독립 감사로 두 입력 root를 다시 검증하고 audit manifest와 같은 active snapshot만 계산에 사용한다. 고정 plan·후보 weight·수치 기준·tie order와 계산부의 일치를 확인하며 원본 archive·교체 session·소스 전체를 계산 전후와 저장 전후에 재대조한다. 입력 아래 저장·기존 출력 덮어쓰기를 거부하고 저장 실패나 저장 후 입력 변경은 부분 출력과 `inconclusive` 표시를 남긴다.
- **fixture 검증 완료:** 새 전용 `.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_analyze_memory_repeatability_validation.py -v`는 11개를 471.879초에, 기존 계산부의 `-p test_analyze_memory_stability_validation.py -k CalculationTests -v`는 13개를 0.357초에 통과했다. Fresh Python producer import 차단, 일반/`-O`/`-OO`의 잘못된 증거 거부, 불리한 결과 보존·정확한 동점·경계값·anchor·방향 비대칭·두 root와 소스 변경·전체 CSV round-trip·저장 실패/후속 변경·기존 출력 보존을 확인했다. 첫 sandbox 실행은 임시 fixture 폴더 WinError 5로 차단돼 같은 테스트를 실제 권한으로 재실행했다. 인위적 fixture 수치는 연구 실측이 아니며 전체 저장소 suite는 실행하지 않았다.
- **실제 분석 완료:** 새 출력 `data/results/memory_repeatability_analysis_20261023T001439769818Z/`에 CLI 종료 0·stderr 0바이트로 저장했다. Sample 84개·대표값 2016개·phase 진단 8064개·후보 정답 4788행·방향별 regret 27216행·anchor regret 4536개·공식/후보 비교 1512개다. Anchor는 여섯 run 대표값 중앙값, memory는 phase 중앙값의 최댓값이며 정확한 tie order와 모든 36개 방향 쌍을 적용했다. 실제 순서는 1→3→4→5→6→replacement 2이며 논리 ID·실제 시각·별도 실행 HEAD를 유지했다.
- **사전 판정:** 결과는 `memory_stability_not_satisfied`, memory 안정성 false·joint 안정성 false다. Memory span은 총 336조건 중 96조건 미충족(core 89/288, tiny 7/48)이며 최대 log span은 core `0.026396253608327876`, tiny `0.02710013828754913`이다. 원래 한계식 `epsilon/(2*w_memory_max)`의 Python 값 `0.012499999999999999`를 반올림 없이 적용했다. 두 층의 memory_only regret는 모두 0이고 선택은 일치했지만 span 기준을 면제하지 않았다. Core 최대 timing_only regret는 `1.7752505920281887`, joint regret는 `1.7749495552044472`로 budget `0.01`을 넘었다. Tiny의 timing_only/joint regret는 0이다. 이는 관측한 시간 변동의 영향을 포함하며 환경 로그만으로 특정 원인을 단정하지 않는다.
- **효과와 한계:** Candidate joint와 후보 memory=0 선택 차이는 0/1512이며 모든 여섯 run에서 memory 이득이 delta를 초과한 sample·mode 조건은 0/252다. 기존 공식 3지표와의 선택 차이 6/1512는 다른 비-memory weight도 포함하므로 memory 단독 효과로 해석하지 않는다. 실제 수치는 모두 Python으로 저장 결과에서 집계했다. 원하는 결과를 위한 weight 변경·sample 제외·실패값 추정은 하지 않았다. 공식 memory 채택·4지표 전환 근거는 충족하지 못했으며 계속 `validation_only`, `score_inclusion=false`다.
- **보존·재검증 완료:** CSV 정답의 score·exact tie·gap, regret 차이·0 diagonal·전체 방향 행렬, 저장 artifact hash·행 수·stdout/summary 일치·빈 stderr와 두 증거 root·분석 소스 불변을 재확인했다. 원본 실패 3건과 활성 실패 0건은 구분해 유지했다. 기존 manifest·metadata의 당시 pending/분석 미수행 checkpoint는 수정하지 않았으며 현재 판정은 새 보고서를 참조한다. 새 압축 측정·복원·모델 학습·공식 라벨 생성은 수행하지 않았다. 이번 기능의 코드·테스트·별도 결과·진행 문서만 로컬 commit으로 보존한다.

### Memory 참고 지표 보존·추가 구현 보류 결정 — 2026-10-23

근거: [사용자 결정 기록](research_log/memory_reference_indicator_decision_20261023.md), [기존 채택 검토](research_log/memory_adoption_review_20261007.md), [최신 실제 후보 분석](data/results/memory_repeatability_analysis_20261023T001439769818Z/README.md). 이번 결정 기록 작업의 시작 HEAD와 마지막 관련 분석 보존 commit은 `0761b098142433476ef29f9bcc4e70454ef7562b`다.

- **확정 완료:** 사용자가 memory를 참고 지표로 보존하고 여건이 마련되면 추가 구현을 검토하기로 선택했다. 공식 평가는 프로토콜 v2의 3지표를 유지한다. 현재 설정의 `memory.status=validation_only`와 보존 결과의 `score_inclusion=false`가 이미 이 방침과 일치하므로 설정·scoring·모델을 변경하지 않는다.
- **기록 완료:** 최신 독립 감사와 후보 분석의 사전 안정성 미충족·memory_only 선택 유지·관측 선택 이득 미확인을 새 결정 문서에 연결했다. 실제 수치는 Python으로 저장 JSON을 다시 읽어 집계했다. 기존 검토 문서와 원시값·실패·교체 이력·후보 산출물·코드는 당시 기록으로 보존한다.
- **보류/계획:** 추가 memory 구현·재측정·공식 4지표 전환은 즉시 진행할 작업에서 보류 과제로 이동한다. 재개 일정·자동 실행은 설정하지 않는다. 향후 재개 시 사용 목적·측정 대상·환경·입력 범위·허용 오차·선택 효용을 사전 설계하고 새 근거로 공식 채택을 검토한다.
- **문서 검증 완료:** 결정 문서와 진행 기록만 갱신했다. Python으로 로컬 링크 6개·근거 집계·공식 설정·보호 대상 262개 파일의 SHA-256 불변·다음 작업 일치를 확인했다. 새 압축 측정·복원·모델 학습·단위 테스트·감사·후보 분석 전체 재실행은 하지 않았다. 다음 단일 작업은 기존 3지표 Smart Mode의 독립 압축 해제 CLI로 정리했다. 이번 문서 두 개만 stage하고 diff를 확인하여 로컬 commit으로 보존한다.

### 독립 압축 해제 CLI 구현·검증 완료 — 2026-10-23

근거: [구현](smart_decompress.py), [전용 테스트](tests/test_smart_decompress.py), [사용 안내·검증 범위](research_log/smart_mode.md), [실제 CLI·출력·테스트 기록](research_log/smart_decompression_validation_20261023.json). 작업 시작·실제 실행 HEAD는 memory 참고 지표 보존 결정 commit `409c9fd`다. 실제 CLI 실행 당시 새 구현은 commit 전 작업 트리 상태였으며 소스 SHA-256을 기록하고 최종 구현과의 일치를 확인했다.

- **구현 완료:** 압축 결과 폴더와 `--output-dir`을 입력받는다. Version-1·성공 검증 flag·알고리즘/payload 이름·원본 파일명·양수 크기·해시·비율을 확인하고 압축 payload 크기·SHA-256 대조 후 해제기 하나를 한 번 호출한다. 복원 결과의 원본 크기·SHA-256 일치, 저장 bytes 및 입력 불변을 확인한 뒤 Windows의 새 출력 디렉터리로 게시한다. 원본 경로·학습 모델을 열지 않고 특징·예측·scoring·benchmark·memory를 실행하지 않는다. 출력에는 복원 파일 하나가 있고 JSON 검증 기록은 stdout으로 반환한다.
- **오류 처리 완료:** 중복 JSON key·비유한 수치·잘못된 schema·알고리즘·flag·크기·해시·비율·경로·예약 파일명, payload 손상·누락/링크 파일·복원 불일치·입력 변경을 거부한다. 기존 출력과 입력 폴더 아래의 출력은 거부하며 임시 저장·저장 bytes 대조·게시 전 기존 출력 재확인을 사용한다. 작업 오류는 stderr와 종료 코드 1을 반환하고, 실패한 복원·저장을 정상 출력으로 게시하지 않는다. 해시 일치는 저장 metadata의 무결성 확인이며 진위 인증이나 악성 대용량 입력에 대한 자원 제한을 뜻하지 않는다.
- **실제 실행 완료:** 기존 `data/temp/smart_mode_validation_20260915/`의 Decision Tree/Random Forest × 세 mode 결과 여섯 건을 새 CLI로 복원했다. 모두 원본 README와 bytes·크기·SHA-256이 일치했고 종료 코드 0·빈 stderr였다. 기존 여섯 payload는 zstd였으며 네 형식 전체의 동작은 제어 fixture와 실제 producer 호환 테스트에서 별도로 확인했다. 기존 package·모델·config·압축 코드·원본 등 보호 파일 43개의 SHA-256 불변과 저장 복원 bytes를 재확인했다. 원래 실행 기록과 파일은 Git 제외 경로 `data/temp/smart_decompression_validation_20261023T114847091056Z/`에 보존하고 실행·검증 기록 JSON을 별도로 Git 보존한다.
- **테스트 완료:** `.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_smart_*.py -v`의 기존 압축 5개·새 복원 13개, 총 18개가 11.170초에 통과했다. 잘못된 입력이 해제기 호출 전에 차단되는 assertion을 강화한 뒤 `-p test_smart_decompress.py -v`의 최종 13개가 3.872초에 다시 통과했다. 두 모델·세 mode·네 알고리즘 producer 출력 호환, Unicode 이름·한 번 해제·크기/해시·손상 stream·기존 출력 보호·입력 변경·저장/게시 실패를 확인했다. Fresh Python에서 ML·특징·scoring·memory 모듈 import를 차단한 채 CLI 성공을 확인했다. 제어용 모델·인위적 fixture는 연구 측정·모델 평가가 아니며 전체 저장소 suite는 실행하지 않았다.
- **유지/미완료:** 공식 3지표·기존 점수/모델·memory 참고 지표 방침을 유지했다. 파일 전체를 메모리에 읽는 구현이며 스트리밍 대용량 복원·Compare Mode·GUI·새 unseen 평가·성능 개선 검증은 미완료다. 이번에는 새 압축 연구 행렬·학습·memory 실험을 실행하지 않았다.

### 독립 Compare Mode CLI 구현·검증 완료 — 2026-10-23

근거: [구현](compare_compress.py), [전용 테스트](tests/test_compare_compress.py), [사용·실행 기록](research_log/compare_mode.md), [실제 비교](data/results/compare_mode_validation_20261023T120641453081Z/comparison.json), [원시 ns](data/results/compare_mode_validation_20261023T120641453081Z/timing_repeats.csv), [실제 호출](data/results/compare_mode_validation_20261023T120641453081Z/invocation.json), [저장 재검증·테스트](data/results/compare_mode_validation_20261023T120641453081Z/verification.json). 작업 시작·실제 실행 HEAD는 독립 압축 해제 commit `085f1ab`다. 실제 비교 당시 새 CLI는 commit 전 작업 트리 상태였고 정확한 소스 hash를 기록해 최종 구현과의 일치를 확인했다.

- **구현 완료:** 비어 있지 않은 실제 파일을 입력받아 gzip·bz2·lzma·zstd 고정 순서로 각 압축 5회·기준 payload 해제 5회를 실행한다. Codec 호출만 `perf_counter_ns`로 측정하며 매 압축 bytes 일관성·해제 원본 일치를 검사한다. Phase별 원시 ns와 그 중앙값/1000000의 ms 집계를 보존하고, 네 결과가 모두 정상일 때 기존 `src.scoring.score_sample()`으로 세 mode의 점수·최적 알고리즘을 계산한다. 공식 가중치·exact tie 순서·기존 압축 코드·Smart 경로는 변경하지 않았다.
- **실패 보존 완료:** 실패 반복은 해당 알고리즘을 중단하고 예정 `not_run` 슬롯을 남기며 다른 알고리즘은 계속 실행한다. 일부 성공 결과만으로 정답을 계산하지 않는다. 크기·시간·검증 집계와 오류를 CSV에 남기고 실패 조합의 정상 집계값은 공란으로 둔다. 0 시간의 epsilon 대체·측정 재시도·불리한 결과 제외를 하지 않는다. 입력/소스가 바뀌면 `invalidated`, codec/점수 실패는 `completed_with_failures`로 정상 선택을 비워 저장하고 CLI 종료 1을 반환한다. 배타적 새 폴더에 저장하며 게시 중 실패는 가능한 부분 원시 산출물과 `publication_failed.json`을 보존한다. 기존 출력 경합 시 그 폴더에 실패 표시도 쓰지 않는다.
- **실제 실행·재검증 완료:** 새 `data/results/compare_mode_validation_20261023T120641453081Z/`에서 README 한 파일의 비교를 실행했다. 원시 반복 40개·알고리즘 집계 4개·mode 정답 3개 모두 정상이며 네 알고리즘의 복원이 일치했다. 세 mode의 이번 선택은 모두 zstd다. Python으로 원시 key·유한 양수 시간·phase 중앙값·공식 점수·산출물 hash·stdout/보고서·빈 stderr·보호 대상 기존 파일 8개 불변을 확인했다. Config 원래 bytes·입력 hash·설정·환경·실행 HEAD·소스 hash를 보존했다. 이 결과는 해당 파일의 단일 실행 동작 검증이며 일반화·모델 성능·새 Pilot이 아니다.
- **테스트 완료:** `.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_compare_compress.py -v` 16개(2.484초), `-p test_compressors.py -v` 7개(0.035초), `-p test_scoring.py -v` 9개(0.001초), 총 32개가 통과했다. 기존 benchmark와 제어 ns/중앙값 일치, 독립 점수 수식·exact tie, 실패·미실행·부분 점수 차단·입력/소스 변경·저장 실패·저장 후 변경·출력 경합·CLI/import 차단을 확인했다. 최초 독립 수식 검증의 부동소수점 합산 차이를 수치 QA 허용 오차로만 보완했고 실제 점수·동점 정책은 바꾸지 않았다. 인위적 fixture는 연구 측정이 아니며 전체 저장소 suite는 실행하지 않았다.
- **범위·미완료:** Compare CLI는 보고서만 만들고 압축 package·모델 예측·특징·학습·memory 측정을 실행하지 않는다. Memory 참고 지표 보존·추가 구현 보류를 유지했다. 통합 `main.py`·GUI/Demo·스트리밍 처리·새 unseen 평가·성능 개선 검증은 미완료다. 정상 점수 사용에는 `status=completed`, 성공 반환, 실패 표시 없음이 모두 필요하다.

### 통합 CLI 진입점 구현·검증 완료 — 2026-10-23

근거: [진입점](main.py), [전용 테스트](tests/test_main_cli.py), [사용 안내](README.md), [통합 실행 기록](research_log/unified_cli.md), [실제 호출·비교 산출물·검증 JSON](research_log/unified_cli_validation_20261023.json). 작업 시작·실제 실행 HEAD는 Compare CLI 보존 commit `c0394a0`이다. 새 진입점과 선택적 도움말 인자 변경은 당시 commit 전 작업 트리 상태였으며 정확한 소스·테스트 hash를 기록했다.

- **구현 완료:** 명시적인 `smart`, `decompress`, `compare` 명령을 받은 뒤 대응 모듈 하나를 import하고 나머지 인자를 기존 `main()`에 전달한다. 각 기능의 필수 옵션·입력/출력·모델·무결성·실패/기존 출력 검사를 유지한다. 정상 0·작업 실패 1·파서 오류 2를 전달하며 잘못된 최상위 명령과 최상위 도움말은 기능 모듈을 불러오지 않는다. 독립 CLI도 계속 사용할 수 있다.
- **도움말 보완 완료:** 기존 세 CLI의 `main(arguments=None, *, prog=None)`에 선택적인 도움말 이름만 추가했다. 측정·특징·점수·압축 설정·모델·복원 함수의 정의는 변경하지 않았다. 최초 직접 CLI 검증은 통과했으나 Python 3.14의 모듈 실행 문맥에서 기본 도움말 이름이 달라지는 점을 테스트로 확인했다. 전역 `sys.argv`를 바꾸는 방식을 제거하고 `prog`를 명시해 파일/`python -m main` 실행 모두 명령 이름을 유지하도록 보완했다.
- **테스트 완료:** `.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_main_cli.py -v` 최종 12개(5.936초), `-p test_smart_*.py -v` 18개(10.390초), `-p test_compare_compress.py -v` 16개(2.048초), 총 46개가 통과했다. 인자 전달·종료/예외·전역 인자 불변·모듈 실행 도움말·필수 옵션·기존 출력 보존·부분 비교 실패를 확인했다. Fresh Python에서 최상위 도움말의 기능 import 없음과 해제/Compare의 모델·불필요한 모듈 import 차단을 확인했다. Smart 경로는 한 번 압축·복원 검증을 유지하고 Compare/benchmark를 호출하지 않았다. 제어 fixture는 연구 데이터가 아니며 전체 저장소 suite는 실행하지 않았다.
- **실제 실행·재검증 완료:** 최종 코드로 도움말·정상 처리·기존 출력 거부·잘못된 명령/필수 옵션 등 22개 CLI 호출의 기대 종료 코드를 확인했다. 실제 저장 모델 두 종류 × 세 mode의 README 압축→복원 여섯 건이 원본 bytes·크기·SHA-256과 일치했다. Compare 한 건의 원시 반복 40개·집계 4개·mode 정답 3개를 중앙값·공식 점수·산출물 hash로 재검증했다. 입력·모델·설정·구현 등 보호 파일 38개의 SHA-256 불변을 확인했다. 측정/학습 정의·모델을 변경하지 않았으며 이는 해당 파일의 동작 검증이지 일반화·모델 우수성·새 Pilot이 아니다.
- **결과 보존:** 최초 직접 실행은 `data/temp/unified_cli_validation_20261023T122426688067Z/`, 최종 코드 재검증은 `data/temp/unified_cli_validation_20261023T124503907295Z/`에 각각 보존했다. 중단된 서버 재시작 뒤 최종 재검증 호출이 시작되지 않았음을 확인하고 이어 실행했다. 최종 실행의 전체 명령·stdout/stderr·원시 비교 산출물 원문·보호 hash·테스트 기록은 별도 JSON으로 Git 보존한다. README에 세 명령과 상세 안내를 추가했다. Memory 추가 구현·GUI·새 모델·성능 개선 평가·스트리밍은 수행하지 않았다.

### GUI/Demo 최소 화면·실행 흐름 설계 완료 — 2026-10-23

근거: [설계](research_log/gui_demo_design_v1.md), [환경·backend 계약 확인](research_log/gui_demo_design_v1_checks.json), [공식 프로토콜 26~27절](research_protocol_v2.md), [기존 통합 CLI](research_log/unified_cli.md). 작업 시작 및 마지막 관련 구현 보존 commit은 `f1d8388`이다.

- **설계 완료:** 로컬 Tkinter/ttk 창의 Smart 압축·복원·실제 비교 탭, 파일/package·새 출력 선택, Smart 사용 목적/모델 명시 선택, 원본 정보·실제 특징·예측 출력·복원 검증·네 알고리즘 결과 표를 정의했다. 기존 `main.py`를 별도 프로세스로 명시 실행하고 widget 없는 작업 계층과 Tk 화면을 분리하는 계획이다. Backend의 측정·점수·모델·복원 정의를 재구현하지 않는다.
- **실행·오류 계약 정리:** 단일 작업 snapshot·입력/중복 실행 잠금·worker/queue/after 역할·UTF-8 응답 수집·정상/부분/무효/저장 실패 판정·기존 출력 및 실패 근거 보존을 정했다. 현재 backend에는 실시간 진행 이벤트가 없으므로 전체 작업 상태와 indeterminate 표시만 사용하고 알고리즘별 상태는 결과에서 확인한다. 가짜 완료율·남은 시간·codec 진행을 표시하지 않는다. 중간 취소는 후속 과제이며 정상적인 창 닫기에서 작업을 조용히 중단하지 않는다.
- **Demo 범위·미완료 명시:** 프로토콜의 예측 대조는 현재 Compare CLI 단독 기능에 없다. 사용자가 Smart와 Compare를 각각 요청한 뒤 입력/config hash·압축 설정·사용 목적이 일치하는 정상 결과만 나란히 표시하는 계획이다. 다른 파일·모델·mode·설정 또는 실패 후에는 이전 예측 대조를 해제하고 자동 모델 실행·자동 Compare를 하지 않는다. 단일 파일의 점수 차이를 모델 accuracy나 baseline 개선으로 표현하지 않는다.
- **읽기 전용·문서 확인 완료:** 창을 만들지 않는 tkinter import/Tcl 초기화에서 Tcl 8.6.15/Tk 8.6을 확인했다. Python AST로 기존 공개 함수 인자를 읽고 보존된 실제 통합 CLI JSON에서 성공 응답 필드를 확인했다. 코드·config·프로토콜·기존 근거·관련 테스트 15개의 SHA-256 불변과 설계 로컬 링크 6개 유효·다음 작업 일치를 확인했다. GUI 실행·화면 렌더링·단위 테스트·모델 로딩·새 압축/복원·새 Compare·새 연구 실험은 수행하지 않았으며 GUI가 동작한다고 기록하지 않는다.
- **다음 구현 계획:** 먼저 `src/gui_jobs.py`의 작업 요청·명령 구성·프로세스/응답 처리·단일 worker·로그 계층을 구현·검증한다. 그 다음 Tk 화면·상태/결과 연결·명시적 Demo 대조와 실제 Windows 창 검증을 진행한다. Memory는 참고 지표로 유지하며 새 UI 지표·score·측정을 추가하지 않는다.

### GUI 작업 실행 계층 구현·검증 완료 — 2026-10-24

근거: [구현](src/gui_jobs.py), [전용 테스트](tests/test_gui_jobs.py), [API·판정·실행 기록](research_log/gui_jobs.md), [실제 worker 결과·명령·로그·원시 비교·테스트](research_log/gui_jobs_validation_20261024.json). 작업 시작·실제 실행 HEAD는 설계 보존 commit `8a8d3c8`이다. 새 계층은 당시 commit 전 작업 트리 상태였으며 정확한 소스 hash를 기록해 최종 구현과의 일치를 확인했다.

- **구현 완료:** Frozen `JobRequest`, `build_command`, 동기 worker용 `run_job`, 비동기 `JobRunner.submit/poll/busy`를 추가했다. 별도 Python의 기존 `main.py`에 인자 목록·`-B`·프로젝트 cwd·UTF-8을 전달하며 Windows 콘솔을 숨긴다. Tk·ML 역직렬화·특징·codec·scoring을 부모 계층에서 import/실행하지 않는다. Source·config·입력 및 선택한 model/summary의 hash snapshot을 확인하고 무거운 읽기/대기는 worker에서 수행한다. 정상적인 runtime 호출은 재시도하지 않는다.
- **판정·보존 완료:** 종료 코드만으로 정상 처리하지 않고 Smart manifest/payload·복원 파일·Compare stdout/보고서/hash·정상 검증·입력/모델/config/source 일치를 대조한다. `succeeded`, `partial`, `invalidated`, `failed`, `inconclusive`를 구분하고 정상 표시용 데이터는 유효한 결과만 반환한다. 비교 실패의 정상 선택은 비어 있어야 한다. 로그는 별도 새 session에 원문 bytes/base64·요청·명령·시각·상태·근거를 보존한다. 입력 package/출력 아래 로그와 기존 로그 덮어쓰기는 거부한다. Backend 성공 후 로그만 실패하면 성공 파일을 유지하고 log_error로 별도 보고한다.
- **단일 작업 제어 완료:** 하나의 non-daemon thread만 실행하고 busy일 때 중복 요청을 거부한다. Widget callback 대신 ID가 있는 terminal 결과를 queue로 반환하며 예외 후에도 busy를 해제한다. GUI는 `poll()`을 사용하고 `wait()`는 테스트/비-GUI 호출자용이다. 취소·백분율·실시간 codec 진행·Tk 화면은 이 계층에 추가하지 않았다.
- **실제 실행·재검증 완료:** 새 `data/temp/gui_jobs_validation_20261024T034613427419Z/`에서 JobRunner 요청 14건을 확인했다. 저장된 두 Pilot 모델 × 세 mode의 Smart→복원 여섯 건과 Compare 한 건, 총 자식 작업 13개가 정상이고 기존 출력 요청 한 건은 자식 프로세스 시작 전에 차단됐다. 모든 복원 bytes가 원본과 일치했고 각 queue 결과와 저장 로그가 일치했다. Python으로 Compare 원시 반복 40개·집계 4개·mode 정답 3개의 중앙값·공식 점수와 입력·모델·설정·구현 등 보호 파일 38개의 SHA-256 불변을 확인했다. 이 동작 검증은 모델 성능·일반화·새 Pilot이 아니다.
- **테스트 완료:** `.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_gui_jobs.py -v`의 최종 18개가 3.128초에 통과했다. Frozen 요청·명령/환경·단일 worker·busy/queue·사전 차단·비정상 JSON/검증/산출물·입력/모델/source 변경·비교 상태·로그 저장/동기화/ID 충돌·원문 bytes 보존·부모 의존성 import 차단을 확인했다. 인위적인 payload·모델·CSV fixture는 GUI 계약 검사용이며 연구 데이터나 실제 codec 결과가 아니다. 실제 codec 동작은 별도 CLI 연결로 확인했고 전체 저장소 suite는 실행하지 않았다.
- **범위·미완료:** 기존 CLI·측정·점수·특징·모델·config는 변경하지 않았다. 실제 파일과 원래 로그는 Git 제외 경로에, 실행 결과와 원시 비교 산출물 원문·보호 hash·최종 테스트는 별도 JSON으로 Git 보존한다. Tk 창·UI 응답성·화면 Demo 대조·취소·스트리밍·새 학습·memory 측정은 미완료다. GUI가 실행됐다고 기록하지 않는다.

### Tkinter GUI 연결·자동 검증 완료 / OS 입력·시각 QA 미완료 — 2026-10-24~26

- **근거:** `gui_app.py`, `tests/test_gui_app.py`, `tests/validate_gui_app.py`, [GUI 안내](research_log/gui_app.md), [최종 실제 창·테스트 기록](research_log/gui_validation_20261026.json), [최초 중단 근거](research_log/gui_validation_interrupted_20261024.json). 시작 HEAD는 `ea3892d`다.
- **구현 완료:** 세 탭의 파일/package·출력 부모·새 이름·사용 목적/모델 선택, 실측/manifest 결과 표·오류·실행 기록을 기존 JobRunner에 연결했다. `after()`/queue로 완료를 받고 Tk에서 모델·codec·프로세스 대기를 실행하지 않는다. 단일 작업 중 입력·중복·다른 탭·닫기를 잠그고 완료 후 복구한다. 폴더 재사용·예약 이름·빈 입력·필수 선택 누락을 차단한다. 복원/비교 연결 버튼은 입력만 준비하고 실행은 각 탭에서 명시 요청한다.
- **Demo 구현·검증 완료:** 정상 Smart/Compare의 입력 hash·config·압축 설정·해당 mode 가중치가 일치할 때만 예측/실측 best·이 파일의 점수 차이를 표시한다. 모델/입력/mode 변경과 실패 뒤 이전 대조를 해제한다. 부분/무효/실패에는 정상 점수·best를 표시하지 않는다. 보정되지 않은 모델 출력과 baseline 개선 미확인 한계를 안내한다.
- **최종 테스트 완료:** `python -B -m unittest discover -s tests -p 'test_gui*.py' -v`로 전용 Tk 15개+계층 회귀 18개, 총 33개가 9.402초에 통과했다. 실제 Tk 생성·최소 창 크기의 주요 위젯 좌표/상태·입력/출력 보호·중복/닫기·queue ID·Demo 및 실패/로그 경고·제어 복구를 확인했다. 인위적인 응답/측정 fixture는 연구 데이터가 아니다. 전체 저장소 suite는 실행하지 않았다.
- **실제 창·기존 모델 흐름 완료:** 새 `data/temp/gui_app_validation_20261025T234658401068Z/`에서 한국어/공백/기호/emoji 입력의 실제 Tk callback을 호출하고 이벤트를 처리했다. 두 Pilot 모델×세 mode의 압축/복원 12개와 Compare 1개가 정상이며 별도 손상 복사본 복원 1개는 오류로 거부됐다. 기존 출력 요청은 자식 시작 전 차단했다. 각 작업 동안 heartbeat·중복/닫기 차단·완료 후 입력 복구·로그/queue 일치를 확인했다. Python으로 비교 40개 원시 반복·4개 집계·3개 정답의 중앙값/공식 점수와 입력·소스·모델·새 정상 package 등 보호 파일 35개 SHA-256 불변을 재검증했다. 파일 동작 검증이며 새 연구 행렬·모델 성능 평가가 아니다.
- **중단 근거 보존:** 최초 10월 24일 시도는 첫 작업에서 120초 harness deadline 오류로 중단됐고 화면 완료는 기록되지 않았다. 뒤늦은 backend 로그는 성공이며 원래 package와 partial 로그를 보존했다. 시각 공백의 원인을 절전이라고 확정하지 않는다. 새 경로에서 최종 검증을 완료했고 실패 이력을 지우지 않았다.
- **미완료·범위:** Windows 화면 자동화 도구는 reset/재시도에도 `kernel assets` 경로 오류(`os error 3`)로 초기화되지 않았다. OS 마우스/키보드·파일 선택 대화상자·스크린샷/글꼴/잘림/DPI QA는 미완료다. 실제 Tk 위젯/이벤트 검증과 구분한다. CLI·점수·모델·config·기존 연구 결과는 변경하지 않았다. 취소·스트리밍·새 학습·unseen 평가·memory 추가 구현은 수행하지 않았다.

### 실제 파일 unseen 평가 사전 설계 완료 / corpus·평가는 미완료 — 2026-10-26

- **근거:** [사전 설계 v1](research_log/unseen_evaluation_design_v1.md), [읽기 전용 계약·hash·검증 프로그램 원문](research_log/unseen_evaluation_design_v1_checks.json). 시작 HEAD는 `e1e9d41`(Tk GUI 구현·자동 검증 보존)이다.
- **GUI 재시도·범위 변경:** 초기화와 kernel reset 후 재초기화 모두 `failed to write kernel assets` / `os error 3`로 실패했다. OS 입력·선택창·스크린샷 검증은 실행하지 않았고 완료로 바꾸지 않았다. 화면 도구와 독립적인 다음 연구 준비인 unseen 사전 설계만 진행했다.
- **설계 완료:** 실제 원본 60개·여섯 형식 각 10개, 최소 12개 원본 그룹·그룹당 최대 5개·형식마다 최소 2개 원본, 원래 16 KiB~1 MiB 파일의 수집 목표를 정했다. 실제 확보 수가 아니며 개별 출처·라이선스·원본 그룹 목록은 미정이다. 선정 metadata와 제외/중복 사유·full 입력 hash를 예측/측정 전에 동결하며 원본 파일을 변형하지 않는다.
- **누수 방지·평가 계약 완료:** 실제 파일을 기존 seed 기반 재학습 경로에 넣지 않는다. 두 저장 모델×세 mode와 기존 Pilot 학습 최빈 baseline을 고정하고 외부 holdout 전체를 별도 평가한다. 기존 12개 특징·공식 3지표/5회 중앙값·네 클래스 고정 Macro F1·oracle regret를 사용한다. 파일/그룹 동일 비중과 형식/크기/coverage를 구분하고 원본 그룹 mean regret의 baseline 대비 차이를 1차 비교량으로 정했다. 실패·미실행·baseline 미개선·모델 오답을 보존하며 조건부 집계를 전체 결과로 부르지 않는다.
- **읽기 전용 검증 완료:** Python 표준 라이브러리로 기존 baseline/두 모델의 산출물 32개 hash·저장 Pilot 입력 hash·학습 분할 라벨에서 재계산한 baseline과 summary 일치·특징/설정/소스/런타임 계약·55개 보호 파일 전후 SHA-256 불변을 확인했다. 모델 pickle은 bytes/hash만 읽었으며 역직렬화·추론·학습을 하지 않았다. 이 숫자는 설계 계약 확인이며 새 연구 성능 결과가 아니다.
- **미완료:** 출처/권리 확인·실제 후보 수집·후보 manifest/선정·기존 합성 bytes와의 겹침 검사·corpus 동결·별도 평가 runner·연구 실측·독립 저장 감사·실제 unseen 성능 평가. 이번에는 단위 테스트·특징 추출·합성 재생성·모델 로딩/예측·압축·GUI 입력·새 memory 측정을 실행하지 않았다. 문서/JSON 내용·링크·현재 소스/hash·diff를 검증해 보존한다.

### node_repl 환경 오류 진단·부분 복구 / 현재 연결 재검증 대기 — 2026-10-26

- **근거:** [진단 기록](research_log/node_repl_recovery_20261026.md), [원래 응답·진단 프로그램·보호 hash](research_log/node_repl_recovery_20261026.json). 시작 HEAD는 `d474f54`다. 사용자 지시로 이 복구를 다음 연구 구현보다 우선했다.
- **원인 분리·재현 완료:** 최소 JavaScript도 kernel assets 단계에서 실패했다. 같은 설정의 새 MCP 프로세스는 기본/새 TEMP와 구/현 runtime에서 정상이다. 실패 요청을 처리하는 프로세스를 식별하고 그 프로세스가 보유한 `.tmpqycGtw` 경로가 없는 것을 확인했다. 별도로 만든 빈 테스트 임시 폴더만 제거하면 같은 오류가 나고, 다시 생성하면 같은 테스트 프로세스에서 정상 JavaScript를 실행했다.
- **부분 복구 완료:** 실제 누락된 임시 폴더를 빈 폴더로 생성했다. 현재 연결이 kernel assets를 생성했으며 원래 오류 단계는 통과했다. 그다음 `failed to start Node runtime: ... (os error 3)`가 남아 있다. 프로세스 환경의 구 CLI 실행 경로가 없고 현재 설정의 새 경로는 존재한다. 누가 언제 경로를 제거했는지는 확인하지 않았다.
- **미확정·한계:** 없는 CLI 경로만 적용한 단순 독립 MCP는 정상이라, 그 테스트를 현재 세션 sandbox 실행과 같다고 보거나 CLI 경로를 다음 오류의 유일한 원인이라고 단정하지 않는다. 현재 설정으로 연결을 재시작해 검증해야 한다. 공식 app-server proxy의 initialize가 timeout돼 config reload는 전송되지 않았다. 사용자에게 Codex 설정의 `node_repl` Restart를 요청했으며 현재 연결 정상·Sky 초기화·Windows 창 조회·GUI QA는 미완료다.
- **보존·범위:** 연구 코드·저장 모델·프로젝트 config·기존 결과 55개 SHA-256 불변을 확인했다. 사용자 MCP 설정은 변경하지 않았고 바이너리 위장/교체·process memory 쓰기·권한/sandbox 변경·앱/daemon 강제 종료를 하지 않았다. 진단에서 해당 프로세스의 임시/실행 경로만 출력했으며 전체 메모리 덤프나 인증 값은 보존하지 않았다. 연구 실행·학습·단위 테스트·GUI 입력은 수행하지 않았다.

### 실제 파일 후보 manifest 도구 구현·인위적 검증 완료 — 2026-10-26

- **근거:** `src/unseen_manifest.py`, `tests/test_unseen_manifest.py`, `tests/validate_unseen_manifest.py`, [도구 안내](research_log/unseen_manifest.md), [최종 CLI/테스트 기록](research_log/unseen_manifest_validation_20261026_final.json), [선정 상태 보강 전 CLI 기록](research_log/unseen_manifest_validation_20261026.json). 시작 HEAD는 `c0efb44`다.
- **구현 완료:** 표준 라이브러리의 `draft`, `freeze`, `audit` CLI를 추가했다. 원래 metadata bytes·full 입력 hash·명시적 선정 ID·후보 상태/제외 사유·동결 정책·실행 Git/source와 artifact hash를 새 경로에 보존한다. 60개·여섯 형식 각 10개·원본 그룹/상한·크기·검토/근거·중복/파생 관계를 확인하고 자동 후보 보충/교체를 하지 않는다. `audit`는 별도로 기록한 기대 hash가 필수다.
- **보호·실패 검증 완료:** 경로 탈출·예약 이름·symlink/junction/reparse point·대소문자/같은 파일 alias·메타데이터/원본/source 변경·기존 출력·손상/위조·부분 저장을 검사한다. Windows 열린 handle 경로도 확인한다. 실패 표시가 있으면 manifest 파일이 있어도 거부한다. 처음 테스트에서 path stat/handle fstat의 ctime 차이로 정상 파일을 변경으로 오판한 문제를 발견해, Windows birth time·파일 ID·크기·수정 시각 비교와 hash/게시 fence로 수정하고 회귀 fixture를 추가했다.
- **최종 테스트 완료:** `python -B -m unittest discover -s tests -p test_unseen_manifest.py -v`의 23개가 48.910초에 통과했다. 연구/ML/codec/GUI 모듈을 차단한 fresh Python import/help도 확인했다. 인위적 파일·권리/그룹 선언은 계약 검사용 fixture이며 실제 자료·라이선스 검증 결과가 아니다. 전체 저장소 suite는 실행하지 않았다.
- **실제 CLI 연결 완료 — fixture 전용:** 새 `data/temp/unseen_manifest_validation_20261026T014612253392Z/`에서 help·draft·freeze·audit와 거부 사례 총 9건을 확인했다. 기존 출력·잘못된 기대 hash·검토 대기 freeze·손상 복사본 audit가 종료 1로 차단되고 기존 파일은 유지됐다. Python으로 raw metadata와 정책/선정/full hash·원본 fixture bytes·기존 연구 파일 55개 및 최종 구현/테스트 source hash 불변을 대조했다. 최종 source는 commit 전 작업 트리 상태였으며 정확한 hash와 stdout/stderr·원래 산출물을 보존했다. 초기 CLI 검증의 새 경로와 근거도 유지했다.
- **미완료·범위:** `data_kind=test_fixture`와 `research_candidate`를 구분한다. `frozen`은 입력 목록 고정이고 항상 `evaluation_ready=false`, `unseen_overlap_audit=not_performed`다. 실제 출처/권리/원본 관계 검토·후보 수집·기존 합성 bytes와의 겹침 검사·실제 corpus 동결·평가 runner·연구 실측·모델 평가는 미완료다. 기존 학습/압축/점수/특징/config/모델 코드는 변경하지 않았다. Memory 추가 구현·재학습을 하지 않았다. 현재 연결의 Node 시작 오류와 GUI OS QA도 미완료다.

### 실제 파일 후보 1차 출처 검토·초안 수집 완료 — 2026-10-26

- **근거/실행 기준:** [수집 보고서](research_log/unseen_collection_20261026.md), 고정 [계획](research_log/unseen_collection_plan_20261026.json)·[출처 검토](research_log/unseen_source_review_20261026.json), `data/results/real_unseen/real_candidates_20261026_01/`의 inventory/draft·획득·검증·중단 기록. 시작 HEAD이자 마지막 manifest 구현 commit은 `173bb47`이다. 획득/검증 source hash와 실제 명령·UTC를 보존했다.
- **수집 완료 범위:** 원본 30개(text/Python 각 10, JSON/binary 각 5), 고정 버전 라이선스 6개. 원본 그룹은 NumPy·pandas·Git·curl·CLDR·Natural Earth 각 5개다. 전체 저장소를 한 그룹으로 묶고 테스트/fixture·vendored source·인공 좌표 격자/기준선 파일은 넣지 않았다. 권리/개인정보가 해결되지 않은 로그는 metadata 확인/미수집으로 남겼다.
- **실제 실행·검증 완료:** HTTP 원본 bytes를 새 경로에 보존하고 Git tree 크기/blob hash를 대조했다. draft CLI 종료 0이며 별도 Python 검증에서 snapshot/artifact/full hash·형식·정확 중복 0개·원본 Git 제외 36개와 보호 파일 총 59개 불변을 확인했다. 후보 합계 1,730,855 bytes, 개별 16,836~339,268 bytes로 사전 범위 안이다. 기존 보호 55개와 도구/테스트/기준 문서의 집합을 대조했으며 중복 경로를 이중 집계하지 않았다. 제한 환경의 Pilot 읽기 실패 및 검증 스크립트의 상태명 기대 오류/수정도 기록했다. 원본과 draft를 오류에 맞춰 고치지 않았다.
- **미완료:** 목표까지 CSV/log 각 10개와 별도 원본 그룹의 JSON/binary 각 5개, 전체 최소 6개 원본 그룹이 더 필요하다. 모든 후보의 권리/개인정보 검토는 `pending`, 선정은 0개이며 출처 간 파생/복제 관계도 승인하지 않았다. 간단한 내용 패턴/형식 검사는 개인정보 승인으로 사용하지 않는다. 합성 bytes 겹침 감사·실제 corpus 동결·연구 평가는 미수행이다.
- **범위:** 연구 특징·압축·예측·pickle 로딩·학습·memory 추가 측정을 실행하지 않았다. 이번 수집 검증 때문에 기존 단위 테스트/전체 suite를 재실행하지 않았다. `evaluation_ready=false`, `unseen_overlap_audit=not_performed`를 유지한다. 정확한 byte hash가 Git 개행 변환으로 달라지지 않도록 이번 package/source에 한정한 속성을 추가했다.

### 1차 수집 보고서 정리 완료 — 2026-10-26

- **근거/기준 commit:** [보고서](research_log/unseen_collection_20261026.md), [문서 검증 근거](research_log/unseen_collection_report_checks_20261026.json). 기존 수집/검증 보존 commit이자 이번 작업 시작 HEAD는 `65deab0`이다.
- **완료:** 저장 inventory·획득·계획·검증 파일을 Python으로 읽어 기존 30개/6개 그룹의 수량·그룹별 bytes·원래 경로·크기·hash 목록을 보고서에 보강했다. 나머지 형식별 수집 목표와 최소 새 그룹 수, 보고서→추가 수집→검토/선정→겹침 확인/동결 순서를 명시했다. 검토 제외 시 대체 후보가 더 필요할 수 있음을 기록했다.
- **검증/범위:** 보고서의 표·기존 근거 파일과 로컬 링크·Git diff를 확인했다. 기존 수집 package/source와의 byte 일치도 문서 근거에 기록했다. 추가 다운로드·원본 변경·후보 승인·연구 실험·학습·단위 테스트 재실행을 하지 않았다. 후보 30개는 계속 `pending`이며 실제 corpus 동결/연구 평가는 미완료다.

### 추가 실제 원본 30개 수집·통합 draft 검증 완료 — 2026-10-26

- **근거/실행 기준:** [보고서](research_log/unseen_additional_collection_20261026.md), [고정 계획](research_log/unseen_additional_collection_plan_20261026.json), `data/results/real_unseen/real_candidates_20261026_02/`의 통합/추가 inventory·draft·획득/attribution·실제 CLI·독립 검증·보존·최초 중단 기록. 실행 HEAD는 `edf2dcf`이고 당시 commit 전 수집/검증 script hash를 별도로 기록했다.
- **수집 완료:** UCI의 원래 관측 collection 8개에서 CSV 10개, VS Code의 배포 설정 JSON 5개, Google Fonts의 글꼴 binary 5개, MLPerf Training/Inference 실행 로그 각 5개를 확보했다. 새 원본 그룹은 12개, 기존을 합쳐 잠정 18개다. 전체 형식별 각 10개·그룹당 최대 5개·형식별 최소 2개 그룹을 충족했다. 같은 저장소의 폴더/버전·같은 자료의 red/white 또는 train/test를 별도 그룹으로 세지 않았다.
- **출처/보존:** Git commit·blob hash/크기와 root/family notice, UCI DOI·source page·전체 archive/member·citation·CC BY legalcode를 보존했다. 후보 전체 파일을 그대로 읽었으며 자르기·재인코딩·개행/값/확장자 변환을 하지 않았다. 기존 30개/notice/metadata는 유지하고 새 raw 경로에 독립적인 바이트 사본을 만들었다. 상충하는 이용 조건의 Air Quality, 크기 범위 밖/형식이 다른 자료, 개인정보 불확실 로그의 미수집 이유를 남겼다.
- **실제 실행·독립 검증 완료:** 획득 오류 0개, draft CLI와 독립 검증 종료 0. 통합 후보 60개의 정확 중복 0개·원본/notice Git blob hash·UCI archive/member bytes/CRC·JSON/CSV/로그/TrueType 형식을 확인했다. 기존 연구/1차 자료 포함 보호 파일 114개 불변, 새 raw 경로 파일 92개 Git 제외를 확인했다. 추가 후보 3,553,944 bytes, 통합 5,284,799 bytes, 개별 16,836~604,166 bytes다. 초기 제한 실행의 Pilot 읽기 거부도 보존했다.
- **검토/미완료:** 모든 후보의 권리/개인정보 상태는 `pending`, 선정 0개다. root license·파싱·패턴 검사로 안전/독립성을 승인하지 않았다. MLCommons 조직/동일 제출 업체와 각 UCI 원래 collection의 공통 호스트/출처도 기록했다. 실제 내용·추가 notice·embedded 정보·개인정보·파생 관계 검토와 필요한 대체 수집, 합성 겹침 확인·실제 corpus 동결·평가 runner/평가는 남아 있다.
- **범위:** 연구 특징·압축 benchmark·모델 로딩/예측/학습·memory 추가 측정·기존 단위 테스트/전체 suite를 실행하지 않았다. ZIP member 추출은 원본 획득으로 구분한다. `evaluation_ready=false`, `unseen_overlap_audit=not_performed`를 유지한다. 기존 1차 보고서/결과를 소급 수정하지 않았다.

### 후보 60개 파일별 검토·새 검토 draft 반영 완료 — 2026-10-26

- **근거/기준 commit:** [검토 보고서](research_log/unseen_candidate_review_20261026.md), [명시적 판정/정책](research_log/unseen_candidate_decisions_20261026.json), [추가 source 계획](research_log/unseen_review_evidence_plan_20261026.json), `data/results/real_unseen/real_candidate_review_20261026_01/`의 후보별 근거·관계·사용 조건·새 inventory/draft·검증. 시작/실행 HEAD는 `4610aa3`이며 commit 전 검사/판정 반영/검증 source hash를 보존했다.
- **내용/권리 검토 완료:** 모든 셀/JSON/MLLOG/지도 record/글꼴 name table 파싱과 전체 문자열/주석 스캔을 실제 source·notice 및 표시된 맥락 검토와 결합했다. 사람이 모든 source line을 수동 정독했다고 기록하지 않는다. 60개 모두 무수정 로컬 연구 입력 범위에서 권리·개인정보 맥락 검토를 승인했다. 공개 저자/문의처/인용·문서 예시·배포 telemetry 설정은 실제 비공개 사용자 기록/credential과 구분해 분류했으며, 개인정보가 전혀 없는 익명 자료로 선언하지 않았다.
- **보완/관계:** `numpy_04`의 CPython 3.2 reprlib 유래를 대조하고 전체 Python license/PSF notice·NumPy의 적응 내용을 보존했다. 새 license metadata는 `BSD-3-Clause AND PSF-2.0`다. 글꼴 Actor의 오래된 URL은 명시적 OFL 문구/동일 family notice로 판정하고 원본은 수정하지 않았다. 동일 지도 경계·Wine/Wilt collection·Training 반복·Inference 구성·공통 제출자/외부 upstream·dependency 등 9개 관계 기록을 남겼다. 알려지지 않은 파생 방향이나 통계적 독립성을 주장하지 않는다.
- **실행/보존 검증 완료:** 새 draft CLI와 독립 검증 종료 0. 원본 60개 bytes/hash, 기존 수집본과 보호 파일 221개, 추가 고정 license/source 근거를 포함한 226개 불변을 확인했다. 과거 `pending` 수집본은 보존하고 새 검토본에서 상태/시각과 NumPy 한 파일의 license 근거만 보완했다. 정확 중복 0개·여섯 형식 각 10개·18개 그룹을 유지했다. 제한 환경의 추가 source 다운로드 실패와 새 경로의 승인 재시도, 접근 불가 Python docs/논문 page의 대체 근거도 기록했다.
- **사용 조건/미완료:** 후보별 notice/citation/hash와 추가 PSF 적응 요약을 후속 동결·배포에 함께 보존해야 한다. 새 후보도 선정 0개이며 `evaluation_ready=false`, `unseen_overlap_audit=not_performed`다. 일반 manifest 도구의 `provenance_review=declared_metadata_only`와 별도 assistant 파일별 판단을 구분한다. 합성 72개/1,008개 입력 재생성 근거·겹침 감사·명시적 선정/실제 corpus 동결·평가 runner/평가는 남아 있다.
- **범위:** source/입력/metadata를 실행하지 않고 읽어 검토했다. 연구 특징·압축 benchmark·pickle/모델 예측/학습·memory 추가 측정·기존 단위 테스트/전체 suite를 실행하지 않았다. 상세 맥락값은 Git 제외 로컬 검사 기록에 두고 게시한 판단에는 원본 hash·분류·위치만 연결했다.

### 기존 Pilot 우세 조건·가중치 민감도 탐색 완료 — 2026-10-29

- **근거/실행 기준:** [보고서](research_log/pilot_tradeoffs_20261029.md), [분석 전 고정 계획](research_log/pilot_tradeoff_plan_20261029.json), [결과/재현 근거](data/results/pilot_tradeoff_20261029_01/summary.json), [독립 검증](data/results/pilot_tradeoff_20261029_01/verification.json), [문서·그래프 hash](data/results/pilot_tradeoff_20261029_01/publication.json). 시작/실행 HEAD는 `699801e`, 원래 Pilot 측정 commit은 `4d2d637bea96a4a1ddbbedb2c077fd0474ca8c19`다. Commit 전 분석 source의 정확한 hash를 보존했다.
- **완료:** 원래 1,008개 전체의 hash·설정·검증·완전한 측정 조합과 모든 공식 점수/라벨을 재계산했다. 압축률 단독 최소는 bz2 226·LZMA 322·zstd 460개다. 지표별 minima/동점·zstd 대비 절감 bytes/%/ms·Pareto·generator×size·공식 score regret를 새 CSV/JSON에 저장했다. 전체 0.05 단체 격자 231개와 동일 시간 비중의 0.01 경로 101개 전체를 보존하고, 선택 비율과 엄격 개선·동점만의 선택을 분리했다. 10%는 해석용 참고선이며 가중치를 채택하거나 클래스 비율을 강제하지 않았다.
- **검증 완료:** 전용 인위적 수학 fixture 테스트 8개 통과(0.034초). 최초 제한 실행에서는 임시 폴더 접근 오류 2개가 있었고 승인 재실행에서 통과했다. 별도 검증기가 원래 측정값에서 pairwise 4,032행·가중치 조건 332개 전체의 선택/엄격 개선/평균 regret 및 파일별 지표/Pareto·그룹 선택 수를 대조했다. 보호 파일 59개와 분석 source/output hash 불변을 확인했다. 보고서 로컬 링크와 그래프 렌더링을 확인했으며 기존 전체 suite는 재실행하지 않았다.
- **한계/미완료:** 기존 train/test를 포함한 전체 Pilot의 탐색 재분석이며 일반화 성능 검증이 아니다. 기존 중앙값만 사용해 작은 시간 차이의 통계적 유의성을 입증하지 않는다. 공식 점수·라벨·모델/config를 수정하지 않았고 memory 보충·4지표 점수·새 압축/학습·실제 후보 성능 평가를 하지 않았다. 사용 목적에 근거한 새 함수 채택과 독립 평가, 수동 Compare 저장 검증·GUI 전체 QA, corpus 동결/평가는 남아 있다.

### 사용 조건 기반 후보 목적 함수 v1 설계 완료 — 2026-10-30

- **근거/기준:** [설계 문서](research_log/usage_objective_design_v1.md), [명세](research_log/usage_objective_spec_v1.json), [문서·수학 검산](research_log/usage_objective_design_checks_20261030.json), [검산기](research_log/verify_usage_objective_design_20261030.py). 시작/검산 HEAD는 `210e13eb4df6d58f15b6afe8881ff349799fe09d`(Pilot 탐색 분석 보존)이며 새 source의 정확한 hash를 근거에 보존했다.
- **완료:** 사용자가 상황 선택을 위임해 기존 세 모드 유지·생애 총비용 주후보와 시간 제한 아래 크기 최소화 비교 대안을 정했다. 보관 기간·기대 복원 횟수는 사용 조건이고 새 측정 지표와 구분한다. 공통 비용 단위·가정·값 누락/비유한 값 거부 계약, 순위 전환/영 분모·동점·빈 제약 집합·Smart의 사전 예측과 실제 제한 위반 구분·별도 profile/model/평가 계획을 기록했다. 10% 선택 비율에 맞춰 공식 계수를 변경하지 않았다.
- **검증 완료:** Decimal로 익명 인위적 A/B 비용 사례 6개와 제약 사례 4개, 계수 스케일·bytes/KiB 변환·음수 보관 경계·복원 횟수 경계를 검산했다. 로컬 링크 9개와 새 명세/문서/source hash, 기존 Pilot/모델/config·직전 분석 등 보호 파일 75개 불변을 대조했다. 이번은 문서/수학 설계 검증이며 연구 실험·기존 분석 전체·unit test suite를 재실행하지 않았다.
- **미완료:** 실제 사용량·비용 교환비·deadline 근거가 없어 운영 profile 값은 null로 남긴다. 명시적 가상 매개변수로 계산부 구현은 진행 가능하다. 실제 scenario 고정·새 계산부/fixture·새 정의의 정답/모델·독립 평가는 아직 없다. 기존 공식 score·정답·모델과 memory validation_only를 유지한다. GUI 수동 Compare 저장 검증/전체 QA·실제 corpus 선정/동결/평가는 별도 미완료다.

### 후보 목적 함수 순수 계산부·fixture 검증 완료 — 2026-10-31

- **근거/실행 기준:** [계산부 안내](research_log/usage_objectives.md), [모듈](src/usage_objectives.py), [전용 테스트](tests/test_usage_objectives.py), [실행/설계 대조 근거](research_log/usage_objectives_validation_20261031.json), [검증 프로그램](research_log/validate_usage_objectives_20261031.py). 시작/검증 HEAD는 `2dfa7a41201b83dd9e74612c9b5577c58c9db31f`(후보 수학 설계 보존)이며 commit 전 새 source의 정확한 hash를 기록했다.
- **구현 완료:** 명시적 `LifetimePolicy`와 별도 offline 후보 선택 함수를 추가했다. 생애 총비용의 저장/압축/복원 항을 분리하고 시간 제한은 경계 포함·빈 집합/위반 이유·정확 정수 bytes를 처리한다. 누락을 0으로 보충하거나 나머지 후보만으로 고르지 않는다. 같은 sample/원본 크기·복원 검증·측정 status·숫자/매개변수와 정확 동점 순서를 검증한다. Binary64 곱/합과 0 underflow를 거부하며 숫자 문자열 변환 단계의 작은 양수가 0이 되는 경우도 거부하도록 보강했다. 기본 저장 profile과 명시적 time_only profile을 구분한다.
- **검증 완료:** 최종 전용 인위적 테스트 25개 통과(0.181초), stdout/stderr 원문 보존. 독립 Fraction 비용 대조·순위 반전/동점·유효/실패/누락·시간 경계·정수 정밀도·모든 입력 순서·원본 불변·overflow/underflow·fresh import 격리를 확인했다. 기존 설계의 익명 가상 비용 6개와 제약 4개를 새 함수로 계산해 대조하고, 보호 파일 79개·source hash 불변과 안내 링크 7개를 검증했다. 전체 저장소 테스트 suite는 실행하지 않았다.
- **범위/미완료:** 모든 codec 이름의 새 입력은 인위적 fixture이고 실제 압축 연구 결과가 아니다. 공식 scoring/config·기존 라벨/모델을 수정하지 않았으며 함수를 CLI/GUI/Smart에 연결하거나 새 압축·특징·모델 로딩/학습/평가·memory 측정을 하지 않았다. 운영 profile 값은 여전히 null이다. 다음은 실제 사용 사실과 구분한 가상 scenario 집합의 사전 고정·Pilot 별도 탐색이며, 목적 함수 공식 채택/새 모델/독립 평가와 GUI 수동 Compare 저장 검증/전체 QA·실제 corpus 선정/동결은 별도 미완료다.

### 가상 사용 시나리오·탐색 계약 실행 전 고정 — 2026-10-31

- **근거:** [사전 계획](research_log/usage_scenarios_plan_20261031.json), [고정 파일](research_log/usage_scenarios_frozen_20261031.json), [탐색/검증 코드](research_log/analyze_usage_scenarios_20261031.py), [fixture](tests/test_usage_scenarios.py). 준비 시작 HEAD는 `623872f`다. Freeze SHA-256은 `92b7c97e98abb6bcb74c148f1bb403c0e07e32d67dd42a8a52b5f160e1331be5`이며 source/plan hash와 테스트 출력 원문을 보존했다.
- **고정 완료:** 총비용 9개·시간 제한 9개 전체. 1 MiB·day 보관과 1 ms 지연을 같은 기본 정책 비용으로 가정하고 시간 비용 0.1/1/10배를 탐색한다. Archive 365일/복원 1회·Balanced 30일/30회·Fast Access 1일/100회는 가상 상황이며 실제 운영값/요금이 아니다. 마지막 10% 선택 비율에 맞춰 계수를 고르거나 결과 후 시나리오를 교체하지 않는다.
- **검증 완료/미실행:** 집계 전용 인위적 테스트 7개 통과. 총비용 합 비율/파일별 비율, 제약 미충족을 남긴 분모와 누락 거부/전체 조합을 확인했다. 이번 고정 단계에서는 실제 Pilot의 새 후보 결과를 계산하지 않았다. 원래 Pilot은 전부 탐색 자료로 쓰며 공식 점수·모델·실제 unseen 자료를 수정하지 않는다. 이 계획/코드를 commit한 후 새 경로에서 분석과 독립 검증을 수행한다.

### 고정 가상 사용 시나리오의 기존 Pilot 탐색 완료 — 2026-10-31

- **근거/실행 기준:** [보고서](research_log/usage_scenarios_20261031.md), [사전 계획](research_log/usage_scenarios_plan_20261031.json), [실행 전 고정 파일](research_log/usage_scenarios_frozen_20261031.json), [분석/검증 코드](research_log/analyze_usage_scenarios_20261031.py), `data/results/usage_scenarios_20261031_01/`의 파생 CSV·summary·verification·publication. 실제 분석 HEAD는 `73ce6df1104904ca4d3d3c47379a53e9faaba6a0`이며 고정된 source/plan hash와 외부 기대 freeze SHA-256을 확인했다.
- **완료:** 1,008개 전체에 총비용 9개·시간 제한 9개를 계산했다. 선택/정확 동점·총비용 합과 파일별 비율·크기/시간 증감·미충족 및 zstd도 같은 제한을 만족한 비교 분모·feasibility 회복을 보존했다. 가상 조건 전체와 generator/size/교차 집계를 남겼으며 선택 비율을 보고 시나리오/파일/계수를 바꾸지 않았다.
- **관측:** 기본 시간 비용에서 비-zstd 선택은 archive 0.30%, balanced 2.88%, fast_access 7.44%. 0.1배 시간 비용의 Archive는 28.97% 선택과 2.50% 총비용 절감을 보였다. 선택 빈도와 비용 절감은 서로 다른 지표이며 실제 사용 조건의 적합성이나 달성한 모델 성능으로 해석하지 않는다.
- **검증 완료:** 실행 전 집계 fixture 7개 통과 후 `73ce6df`로 계획/코드를 commit하고 깨끗한 HEAD에서 실행했다. 원래 metadata/hash·설정·공식 점수/라벨 검증 뒤 독립 Fraction 비용 및 binary64 순위·동점 대조, 총비용 9,072행·시간 제한 9,072행 전체의 coverage/선택·제약·집계/그룹을 확인했다. 보호 파일 84개와 source/input/output hash 불변·보고서 링크를 대조했다. 새 codec 실행·복원·특징·모델/학습·memory·실제 파일 평가·기존 전체 suite를 실행하지 않았다.
- **범위/미완료:** 사전 가정한 정책점수·사용량·절대 시간 제한의 탐색 결과이며 운영 profile 채택이나 공식 3지표 정답/모델 전환이 아니다. 저장 중앙값은 꼬리/실시간 지연 보장이 아니고 전체 Pilot은 개발 자료다. 실제 적용 목적·계수 근거/후속 평가 정의, GUI 수동 Compare 저장 검증/전체 QA·실제 corpus 선정/동결·독립 평가·새 모델은 남아 있다.

### 후보 모델 학습·실제 파일 평가 기준/입력 동결 완료 — 2026-10-31

- **근거:** [기준](research_log/usage_model_study_design_20261031.md), [계획](research_log/usage_model_study_plan_20261031.json), [동결 도구](research_log/prepare_usage_model_study_20261031.py), [study lock](data/results/usage_candidate_study_20261031_01/study_lock.json), 새 corpus manifest/audit·selection·notice index. 시작 HEAD `8fcc29b`.
- **완료/검증:** 후보 60개 전부를 명시 선정하고 기존 manifest freeze/audit로 hash·quota·group·검토 metadata를 확인했다. 필수 notice 72개 참조의 실제 bytes/hash 사본, source/citation/PSF 적응 요약·알려진 관계·합성 재생성 겹침 근거를 연결했다. 보호 파일 268개는 그대로다. 일반 manifest의 evaluation_ready=false/declared_metadata_only는 유지하며 이번 연구별 실행 자격·과거 합성 원본 hash 미저장·독립성/익명성 미인증 한계를 별도로 기록했다.
- **미실행/다음:** 모델 선택·특징·예측·학습·benchmark는 아직 없다. 기존 고정 총비용 시나리오 전체×두 모델을 기존 train IDs로 학습하고 실제 자료 예측을 benchmark 전에 고정한다. Overhead 포함 검증 엔진과 모델 load 시간을 별도 측정한다. 공식 변경은 하지 않는다.

### 후보 모델 별도 학습·재로딩 검증 완료 — 2026-10-31

- **근거:** [학습 checkpoint](data/results/usage_candidate_study_20261031_01/training.json), [저장 검증](data/results/usage_candidate_study_20261031_01/training_verification.json), training/의 후보 라벨·원래 분할·개발 예측·새 모델. 실행 코드 commit `4ab7c73`, 기준/corpus commit `419c484`.
- **완료/검증:** 원래 train 806개만 학습하고 고정 시나리오×두 모델 18개를 저장했다. 기존 test 202개는 Pilot 전체 탐색에 따른 개발 진단이며 독립 시험 성능이 아니다. 후보 정답 9072행은 공식 라벨과 분리했다. 전체 모델을 다시 읽어 hash·class·명시 config/전체 저장 매개변수·feature_names·runtime version과 개발 예측 일치, train-only majority를 확인했다.
- **미실행/다음:** 실제 corpus의 특징/예측/압축과 전체 경로 실측은 아직 없다. 사전 예측 동결 후 같은 파일·조건으로 평가한다. 공식 기준·과거 모델/config·memory 방침을 유지한다.

### 후보 모델의 실제 파일·전체 경로 평가 및 독립 검증 완료 — 2026-10-31

- **근거/실행 기준:** [보고서](research_log/usage_model_study_results_20261031.md), [기준](research_log/usage_model_study_design_20261031.md), [사전 계획](research_log/usage_model_study_plan_20261031.json), [원시 저장 감사](data/results/usage_candidate_study_20261031_01/audit.json), [독립 지표 검증](data/results/usage_candidate_study_20261031_01/metrics_verification.json), 각 단계 checkpoint/CSV·원래 Compare 보고서. 기준/corpus `419c484`, 실행부 `4ab7c73`, train-only 모델 `0cc7df1`, 성능 전 사전 예측 `6a75f98`로 순서대로 commit했다. 실제 codec/전체 경로 측정·집계 HEAD도 `6a75f98`이며 source/hash를 고정했다.
- **완료:** 원본 60개, 모델 18개, 예측 1080개, codec 반복 2,400개, 전체 경로 trial 5,700개·별도 모델 load 반복 90개, 전략 선택 4,320행. 동결한 자료 전체와 모든 시나리오/모델·고정 codec·train-majority·oracle을 보존했다. 부적합 repeat 제거/자동 재시도·실제 자료 학습/튜닝은 하지 않았다.
- **검증 완료:** 실행 전 전용 인위적 fixture 11개 통과. 초기 모델 reload 검사의 config 기본값 비교 오류를 실제 학습 전에 수정/재검증했다. 각 단계 artifact/source/input/model hash·복원 bytes·원시 ns/중앙값·사전 예측 순서를 감사했다. 별도 산술로 Fraction 비용·수동 네 클래스 accuracy/Macro F1/혼동행렬·원본 그룹 동일 비중 비교 등 codec 72개/전체 경로 18개 조건을 검산했다. 기존 보호 파일 268개는 그대로다. 전체 저장소 테스트 suite는 재실행하지 않았다.
- **결과:** 순수 codec에서 Archive 시간 비용 0.1배의 DT/RF만 각각 0.1406%/0.1245% 비용 개선이었다. 전체 경로 비용은 모든 후보 조건에서 6.36~708.52% 증가했다. 고정 corpus/가상 정책에서 실용적 비용 개선 미확인으로 기록하고 불리한 결과를 유지한다.
- **한계/후속:** 상주 모델 연구용 package 엔진이며 실제 배포 GUI/CLI·process startup·cold cache/fsync·모델 배포 공간·CPU/전력/메모리·모집단 효과는 검증하지 않았다. Generic corpus manifest의 evaluation_ready=false와 과거 합성 원본 bytes/hash 미저장·권리/익명성/독립성 범위를 유지한다. 이 외부 자료는 이후 튜닝에 활용하면 개발 자료이며 새 최종 일반화 평가는 다른 원본 그룹의 holdout이 필요하다. 공식 score/라벨/모델/config와 memory 방침은 유지하며 GUI 수동 Compare 저장 검증/전체 시각 QA는 별도 미완료다.

### zstd 선택 누락의 전수 개발 진단 완료 — 2026-10-31

- **근거:** [분석 코드](research_log/analyze_zstd_misses_20261031.py), [57건 보고서](research_log/zstd_misses_20261031.md), [모든 더 나은 대안 59건](data/results/usage_zstd_misses_20261031_01/better_alternatives.csv), 파일·조건별 CSV, [독립 검증기](research_log/verify_zstd_misses_20261031.py)·[검증 기록](data/results/usage_zstd_misses_20261031_01/verification.json). 원본 실측 source commit `6a75f98`, 원본 결과 보존 commit/이번 분석 시작 HEAD `f5fcb24`.
- **완료/결과:** 실제 파일 60개×9개 정책×DT/RF 전체 1,080개 사전 예측을 대조했다. zstd 995개 선택 중 엄격한 누락 57개, 파일 21개·파일×시나리오 32개, 모든 나은 대안 59개(중복 제거 파일×시나리오×대안 33개)를 보존했다. gzip 최선 46건·bz2 최선 11건이며 LZMA도 더 나은 2건이 있지만 최선은 아니다. Archive 시간 비용 0.1배의 DT 20건·RF 17건에 집중된다. `mlperf_inference_03`은 Fast Access에서 gzip의 짧은 복원 시간 때문에 파일별 정책 비용 절감 여지가 약 52.3%였지만 두 모델이 zstd를 선택했다. 비-zstd로 잘못 바꿔 비용이 높아진 74건도 조건별 요약에 함께 보존했다.
- **검증:** 인위적 fixture 7개 통과(명령: `.venv/Scripts/python.exe -m unittest discover -s tests -p test_zstd_misses.py -v`). 전체 4,320개 선택 key·240개 정상 복원 측정·2,400개 원시 슬롯/5회 중앙값과 540개 파일×정책의 네 비용/성분을 대조했다. 별도 Fraction 산술 및 기존 계산부, 사전 예측·full hash/출처, 모든 누락/대안/동점 set과 보고서 57행을 검증했다. 기존 study 전체와 기준 source/config 등 451개 파일의 실행 전후 SHA-256이 일치했다. 초기 분석기의 압축 전용 반복 필드를 복원 슬롯에도 요구한 검사 오류는 산출물 생성 전에 중단됐고 phase별 검증으로 수정·회귀 fixture를 추가했다. 원본 연구 측정 실패가 아니다.
- **범위/미완료:** 저장된 codec 중앙값을 이용한 가상 정책 기술 분석이며 작은 시간 차이의 유의성·파일 형식/특징의 인과·실제 배포 성능을 입증하지 않는다. 원시 반복/계수/라벨/모델을 수정하거나 새 압축·추론·학습·memory 측정을 하지 않았다. 관찰된 실제 60개는 후속 튜닝의 개발 자료이며 새 최종 원본 그룹 holdout이 필요하다. 특징/추론/검증/저장 비용 병목의 추가 분해와 공식 모델 외부 평가/GUI 관련 미완료는 별도다.

### 후보 모델 전체 경로 비용 병목의 개발 진단 완료 — 2026-11-09

- **근거:** [분석 코드](research_log/analyze_pipeline_bottlenecks_20261109.py), [보고서](research_log/pipeline_bottlenecks_20261109.md), [18개 조건 요약](data/results/usage_pipeline_bottlenecks_20261109_01/summary.csv), 파일별 비용 분해·5회 중앙값·크기/원본 그룹별 CSV, [독립 검증기](research_log/verify_pipeline_bottlenecks_20261109.py)·[검증 결과](data/results/usage_pipeline_bottlenecks_20261109_01/verification.json). 분석 시작 HEAD `eea90af`; 원본 실측 source `6a75f98`, 실측 결과 보존 `f5fcb24`.
- **완료/방법:** 원시 5,700개 trial(60파일×19전략×5회)·90개 load 반복과 기존 codec 측정을 읽었다. 1,140개 시간 중앙값과 두 모델의 파일×시나리오 1,080개 비용 차이를 보존했다. codec 선택·package metadata·특징·예측·압축 나머지·중앙값 정렬 차이·복원 나머지로 장부 분해하고 전체 비용 차이와 대조했다. 중앙값 합의 비가산성을 별도 항목으로 남겼으며 시간 제거 가정은 원시 trial별로 먼저 뺀 뒤 중앙값을 다시 구했다.
- **결과:** 특징 계산과 frame 준비 평균은 조건별 54.45~66.12ms, 평균 예측은 DT 2.50~2.86ms·RF 19.13~23.00ms다. 특징 구간의 압축 전체 대비 비중은 DT 84.02~87.75%·RF 61.53~70.89%였다. 특징 구간을 0으로 보는 가정에서도 18개 중 13개 조건, 특징/예측을 모두 0으로 보아도 3개 조건이 가상 정책 비용에서 불리했다. 나머지 시간의 양/음 차이는 다른 실행의 codec 중앙값·OS cache·고정 순서 변동을 포함한다. 동일 codec 선택 조건의 부호 변동을 선택 이득으로 해석하지 않았다.
- **검증:** 전용 인위적 fixture 6개 통과(명령: `.venv/Scripts/python.exe -m unittest discover -s tests -p test_pipeline_bottlenecks.py -v`). 중복/누락 슬롯·복원 hash/verified·압축기 사전 예측·내부 timer 포함 관계, 기존 18개 pipeline 비용/평균 timer/load proxy를 검사했다. 별도 검증기는 분석기를 import하지 않고 정렬 중앙 원소로 원시 중앙값·세 시간 제거 가정·1,080개 분해·조건/크기/원본 그룹 집계를 다시 검산했다. 기존 study/누락 분석/기준 config·source 등 460개 파일의 해시와 파일 집합이 일치했고 보고서 링크를 확인했다.
- **한계/미완료:** 검증/hash/읽기/쓰기의 개별 timer가 없으므로 순수 비용을 따로 확정하지 않는다. 기록된 특징 구간은 통계 함수와 pandas 입력 준비를 합친 값이다. 어느 함수가 가장 느린지는 실제 함수별 profile이 필요하다. 시간 제거는 낙관적 계산이며 구현/새 실측·실제 cold start/배포 성능을 뜻하지 않는다. 새 연구 압축·특징 계산·모델 예측/학습·memory 측정을 하지 않았다. 관찰한 60개는 개발 자료이며 향후 최종 평가는 새 원본 그룹 holdout이 필요하다. 다음은 기존 12개 특징의 의미/순서/값을 보존하는 profiling/동등성 검증 계획이다.

### 특징 profiling·정확 동등성의 사전 계획/참조 동결 완료 — 2026-11-09

- **근거:** [설계](research_log/feature_profile_design_20261109.md), [JSON 계획](research_log/feature_profile_plan_20261109.json), [준비 코드](research_log/prepare_feature_profile_20261109.py), [동결 기록](data/results/feature_profile_plan_20261109_01/freeze.json), [독립 계획 검증기](research_log/verify_feature_profile_plan_20261109.py)·[검증 기록](data/results/feature_profile_plan_20261109_01/verification.json). 시작 HEAD는 직전 비용 진단 `fdf6f66`이다.
- **완료:** 원래 특징 source/config/테스트/study runner를 byte 그대로 복사했고, 기존 frame 함수의 AST가 같은 사본을 만들었다. 실제 60개 파일 metadata와 저장 특징 720개를 타입별 정수/float.hex로 연결했다. 기존 18개 모델 hash/클래스와 1,080개 예측 파일을 보존했으며 새 단일 행 예측·확률·confidence 정확 보존 기준을 정했다. 네 모드×파일당 5회 측정(1,200회)·1회 warmup(240회)의 고정 seed 전체 순서를 저장했다. 정상 경계 입력 131개·오류 입력 5개는 인위적 fixture 계획이다.
- **검증:** 기존 감사 chain·467개 관련 파일 hash, feature AST/설정/모델 기록과 현재 Python·패키지 일치, 원본 파일 metadata/모델 bytes·저장 특징·예측 key, 각 모드/round의 전체 입력 포함과 deterministic shuffle, source 사본 bytes/frame AST와 문서 링크를 확인했다. 별도 검증기는 준비 코드를 import하지 않고 저장 자료/구조/해시/순서를 재검사했다. 계획 준비·검증 명령은 각각 `.venv/Scripts/python.exe research_log/prepare_feature_profile_20261109.py`, `.venv/Scripts/python.exe research_log/verify_feature_profile_plan_20261109.py`다. 문서/설정 동결 단계이므로 fixture 테스트·연구 실험을 실행하거나 통과했다고 기록하지 않았다.
- **계획/미실행:** 이후 worker에서 원본 bytes/hash 확인→참조 특징의 기존 저장값 일치→계측/향후 후보의 정확 특징·frame/예측 일치를 먼저 확인한다. 비계측 특징·frame·결합 시간과 nested 함수별 계측을 구분하고 inclusive/self 중복 합산·독립 중앙값 가산을 금지한다. 계측 observer overhead와 fixed mode order/cache 한계를 표시한다. 이번에는 원본 bytes 재검증·특징 실행·모델 역직렬화/예측·시간 측정·최적화를 하지 않았다. 후속 실행부/인위적 검증과 commit 후 새 경로에서 기준선 profile하며, 최적화의 실제 비교는 별도의 균형 paired 계획으로 진행한다. 공식 score/모델·memory 보류·GUI 미완료는 유지한다.

### 특징 profile 실행부·정확 동등성/저장 감사 구현 및 fixture 검증 완료 — 2026-11-11

- **근거:** [구현 설명](research_log/feature_profile_implementation_20261111.md), [격리 실행/검사](research_log/feature_profile_runtime_20261111.py), [controller/worker](research_log/run_feature_profile_20261111.py), [저장 감사](research_log/verify_feature_profile_run_20261111.py), [검증 실행기](research_log/validate_feature_profile_implementation_20261111.py), [전용 테스트](tests/test_feature_profile.py), [source lock](data/results/feature_profile_implementation_20261111_01/implementation.json)·tests.log·fixture_results.json. 시작 HEAD는 계획 동결 `c680183`이며, 구현/lock을 commit하기 전 실제 corpus 실행을 거부한다.
- **완료:** 고정 plan/source/runtime/model bytes·전체 schedule 확인, 별도 참조 namespace/frame, builtin type/float.hex/frame/단일 행 예측/확률 gate, 네 fresh worker와 raw slot/call tree flush를 구현했다. Inclusive/self·호출 parent/depth·전체/segment helper 횟수를 독립 검사하며, 파일/함수별 중앙값과 형식/그룹/크기 집계·observer 차이를 보존한다. 기존 출력/실패 slot 재사용을 거부하고 실패/중단과 worker log/반환 코드를 보존하며 자신이 만든 child만 종료한다. 공식 feature/score/model·config/GUI 코드는 수정하지 않았다.
- **검증:** 최종 명령 `.venv/Scripts/python.exe research_log/validate_feature_profile_implementation_20261111.py`에서 전용 테스트 17개가 실패 0·오류 0·skip 0으로 통과했다. 정상 fixture 131개·오류 입력 5개의 정확 특징/frame/예외와 call tree를 확인했다. 음의 0/한 float 단계·잘못된 타입/열/확률·partial/duplicate/hash/timer/tree 변조·wrapper 복구·실패 덮어쓰기 방지·실제 child smoke·중단/비정상 종료를 검증했다. 최종 검증은 real corpus 읽기·저장 모델 실행/pickle load를 차단했고 481개 기존 파일과 구현 source hash가 불변이었다. 전체 프로젝트 suite나 GUI 검증은 실행하지 않았다.
- **개발 중 제한/처리:** 첫 샌드박스 테스트는 새 TemporaryDirectory의 ACL 접근 거부로 6개 파일 검사가 중단됐다. 권한을 허용한 동일 테스트에서 통과했고 추가한 child 종료 검사까지 최종 통과했다. 권한을 코드로 바꾸거나 이전 실패 임시 폴더를 삭제하지 않았다. 서버 재시작 때 저장된 runtime 파일/Git 상태를 먼저 대조한 뒤 이어서 작성했다. 원본 연구 측정의 실패/재시도나 corpus 결과가 아니다.
- **미실행/다음:** 실제 원본 60개 bytes 재검증·새 특징/기존 1,080개 예측 gate·고정된 1,200회 본 측정/240회 warmup·독립 실측 감사/보고는 아직 없다. source/lock commit 후 새 기본 경로에서 전체 profile하고, 실패 시 기존 경로를 보존하며 새 attempt에서 전체 일정으로 실행한다. 이후 실제 병목에 근거한 특징값 보존 최적화/새 paired 계획을 검토한다. Memory·공식 채택·GUI 관련 기존 미완료는 유지한다.

### 실제 60개 파일의 기준선 특징 profile·독립 감사·병목 집계 완료 — 2026-11-11

- **근거/실행 기준:** [보고서](research_log/feature_profile_baseline_results_20261111.md), [실행 완료](data/results/feature_profile_baseline_20261109_01/complete.json), [독립 검증](data/results/feature_profile_baseline_20261109_01/verification.json), 각 mode raw/started/complete·process/log·사전 정확 예측 JSONL·파일/함수/형식/그룹/크기 집계, [병목 집계 코드](research_log/analyze_feature_profile_baseline_20261111.py)·[비중복 분해 감사](data/results/feature_profile_baseline_analysis_20261111_01/analysis.json). 실행 HEAD는 구현 commit `642a733`; 계획/참조 동결 `c680183`을 따랐다.
- **실행/검증:** 깨끗한 HEAD와 commit된 source/lock·원본 60개 크기/full SHA-256을 먼저 확인했다. 기존 특징 720개와 18개 모델의 단일 행 예측·확률/비보정 confidence 1,080개가 정확히 일치했다. 네 새 worker에서 본 측정 1,200회와 warmup 240회·파일별 중앙값 240개를 보존했다. 고정 일정·raw timer·호출 tree 포함/직접 자식 비중복/self 합/helper 횟수·원본/모델/코드 hash를 독립 검증했다. 네 worker 반환 코드 0이며 실패/중단·재시도·표본/반복 교체는 없었다. 기존 근거 481개와 구현 source 6개의 hash를 다시 확인했다. 코드/fixture 테스트를 수정하거나 재실행하지 않았으며 이번 실제 실행/독립 감사를 수행했다.
- **결과:** 파일별 5회 중앙값의 평균은 extract_only 58.727250ms, frame_only 0.720367ms, extract_and_frame 66.066533ms, instrumented_extract 64.209005ms다. Warmup 제외 계측 trial 300개를 root 직접 자식/self로 정수 ns 분해한 결과 bigram 39.3633%·run 29.7661%·segment entropy 13.3236%·전체 Counter 12.3847%·duplicate block 4.8299% 순이었다. Bigram/run 합 69.1294%는 계측 raw 시간 비중이며 독립 helper 중앙값을 더해 만든 비율이 아니다. 원시 2,100개 분해 항목의 합이 root와 정확히 일치했다.
- **한계/다음:** 계측−비계측 파일 중앙값 차이 평균은 5.481755ms이고 -71.6894~60.5139ms 범위의 음/양 변동을 모두 보존했다. Observer 비용과 고정 mode 순서/cache·다른 실행 영향이 섞여 있으므로 과거 시간과 비교한 속도 개선이나 69.1% 향상을 주장하지 않는다. 사용자 동시 작업/전원 사건 상태는 미제공으로 남겼고 전원 설정을 바꾸지 않았다. 다음은 bigram/run의 정확 count·나눗셈/타입/float.hex·frame/예측을 보존하는 별도 최적화 후보와 동시점 paired 계획이다. 실제 최적화/전체 비용/GUI·cold start·모집단/최종 holdout·memory·공식 전환은 별도 미완료다.

### Bigram/run 최적화 후보 설계·균형 paired 계획 동결 완료 — 2026-11-11

- **근거:** [설계](research_log/feature_optimization_pair_design_20261111.md), [JSON 계획](research_log/feature_optimization_pair_plan_20261111.json), [준비 코드](research_log/prepare_feature_optimization_pair_20261111.py), [독립 검증기](research_log/verify_feature_optimization_pair_plan_20261111.py), [동결](data/results/feature_optimization_pair_plan_20261111_01/freeze.json)·[검증](data/results/feature_optimization_pair_plan_20261111_01/verification.json)·pair_schedule.csv·input_inventory.csv·numpy_api.json. 시작 HEAD는 실제 기준선 보존 `3ca5f2a`다.
- **완료/후보:** uint16 승격 후 인접 byte code를 histogram으로 세는 bigram 후보와 intp 경계 차이로 run 길이/count를 계산하는 후보를 설계했다. 원래 정수 나눗셈/builtin 출력·entropy/Counter 순서/기타 통계는 보존한다. 짧은 입력·bytes subclass는 원래 helper로 fallback해 기존 override/예외를 유지한다. 두 변경 결합이 주 후보이고 단독 둘은 보조 비교다. 기존 NumPy 2.5.2 설치 문서·dtype metadata만 확인했으며 새 의존성이나 후보 연산을 실행하지 않았다.
- **계획/순서:** 같은 worker·입력에서 참조/후보를 인접 실행하고 파일별 6개 본 pair에서 3회씩 선행하도록 2,520개 pair 행을 동결했다. 예정 본 pair 2,160개(호출 4,320개)·warmup pair 360개(호출 720개)다. 전체 실제 개발 파일 60개·18개 원본 그룹, 네 버전·두 모드를 포함하며 예상 특징 확인 2,880개·단일 행 예측 확인 4,320개는 계획 수량이다. 정상 공개 fixture 133개·오류 5개·두 helper의 빈/단일 byte 직접 확인 4개를 계획했다. 주 지표는 결합 후보의 결합 모드에서 파일별 paired delta 중앙값을 그룹 동일 비중으로 평균한 값이며, 음수와 pooled 중앙값 합 비율 >1·모든 정확 gate 통과를 전체 경로 검증 진입 조건으로 고정했다.
- **검증:** 준비/독립 검증 도구로 기존 감사 chain·523개 보호 파일/기준선 source·참조 hash·원본 metadata 목록·후보 allowlist·각 파일/round의 전체 포함과 seed 순서·매 round 30/30 선행 및 파일별 3/3 선행·실행하지 않았다는 상태/문서 링크를 확인했다. 첫 검증은 아직 만들기 전인 자신의 verification.json 링크를 존재 검사해 출력 전에 중단됐고, 다른 링크를 먼저 확인하고 자신의 링크는 생성 후 확인하도록 수정했다. 후보/계획/일정은 바꾸지 않았으며 그 경위를 검증 기록에 남겼다. 단위/fixture 테스트나 연구 실험을 통과했다고 기록하지 않았다.
- **미실행/다음:** 격리 후보·paired runner/저장 감사·133개 fixture/오류/전체 corpus 동등성·새 속도 측정은 아직 없다. source/fixture를 구현·검증·commit한 뒤 `data/results/feature_optimization_pair_20261111_01`의 새 전체 일정으로 실측한다. 과거 시간만으로 향상을 확정하거나 보조 후보를 사후 주 후보로 교체하지 않는다. 공식 source/모델/score·memory 보류·GUI 미완료와 새 최종 원본 그룹 holdout 필요성을 유지한다.

### 격리 후보·paired 실행부 구현 및 인위적 검증 완료 — 2026-11-11

- **완료:** 고정 계획의 bigram_numpy/run_numpy/both_numpy를 별도 참조 namespace에 구현했다. uint16 승격/정수 histogram·intp run 경계와 subclass/짧은 입력 fallback을 유지한다. 공식 feature/config/모델은 수정하지 않았다. 고정 일정의 인접 실행·raw flush·오류 보존, 새 worker별 실행 및 정확 특징/예측 gate, 저장 pair의 순서/시간/값 검증과 그룹 동일 비중 paired delta·pooled ratio 집계를 연결했다.
- **검증:** `.venv/Scripts/python.exe research_log/validate_feature_pairs_20261111.py`의 전용 테스트 7개가 실패/오류 0개로 통과했다. 정상 입력 133개에서 세 후보의 특징/frame이 정확히 같고 오류 입력 5개·private helper 경계·subclass override를 보존했다. 두 실행 순서/두 모드, 부분/중복/출력/hash/timer 변조·실패 flush·미commit lock의 실행 차단을 확인했다. 실제 corpus 읽기와 저장 모델 pickle 로딩을 금지했고 기존 529개 근거 파일 hash가 일치했다. 전체 프로젝트 suite나 실제 paired 성능 검증으로 해석하지 않는다.
- **근거:** [후보/실행 코어](research_log/feature_pair_candidates_20261111.py), [controller/worker와 집계](research_log/run_feature_pairs_20261111.py), [전용 테스트](tests/test_feature_pair_candidates.py), [검증 실행기](research_log/validate_feature_pairs_20261111.py), [source lock](data/results/feature_pair_implementation_20261111_01/implementation.json)·tests.log·fixtures.json. 시작 HEAD는 후보 계획 commit `554009b`다.
- **미실행:** 실제 60개 파일의 네 버전 동등성·4,320개 모델 출력 확인·4,320회 본 호출/720회 warmup·실제 worker 전체 일정·저장 감사는 다음 단계다. 속도 향상/공식 채택을 주장하지 않으며 memory 보류와 기존 GUI 미완료는 유지한다.

## 12. 아직 완료하지 않은 작업

- **사용자 선택에 따른 보류:** Memory 추가 구현·측정 검증·공식 4지표 전환. 참고 지표와 기존 미충족/실패 증거를 보존하며 자동 재개하지 않는다.
- GUI 화면 도구의 창 가림/입력 guard 원인·전체 시각/선택창/DPI QA. 수동 Smart/복원 저장 검증과 일부 실제 scroll/click은 완료했으나 전체 도구 복구로 취급하지 않는다.
- 사용자 수동 Compare의 화면상 성공 이후 원시 반복/점수/Demo/로그의 정식 저장 검증. 이번 연구 엔진 감사와 별개다.
- 기존 공식 v2 저장 모델의 별도 실제 파일 비교 및 운영 모델/목적 함수 공식 채택. 후보 모델 연구의 corpus 동결·별도 학습·실제 파일/상주 engine 평가는 완료했으나 실용적 비용 개선은 미확인이다.
- 실제 사용량/비용 교환비 근거, 배포 GUI/CLI·cold start·대용량/스트리밍·새 환경 평가. 이후 모델/특징 튜닝에는 관찰된 실제 자료를 개발 자료로 구분하고 새 최종 holdout을 마련한다.
- 약 5,000개·10,000개 실험 확대 여부 판단 및 최종 연구 정리.

## 13. 다음 단일 작업

**전체 개발 corpus의 정확 동등성·균형 paired 실행:** commit된 후보/source lock을 확인한 뒤 `research_log/run_feature_pairs_20261111.py`로 새 경로 `data/results/feature_optimization_pair_20261111_01`에서 실행한다. 원본 hash/특징/frame·네 버전의 저장 모델 예측 확인을 먼저 통과해야 한다. 모든 본 호출 4,320회·warmup 720회·실패/악화 결과를 보존하고 주 후보/고정 그룹 지표를 평가한다. 과거 기준선과 새 후보 시간만 비교하지 않는다. 실패 시 같은 경로/slot을 덮어쓰지 않는다. 전체 Smart 경로 비용 검증·공식 채택·최종 holdout은 별도다.

## 14. 마지막 관련 Git commit

격리 후보/paired 실행부의 인위적 구현 검증은 계획 commit `554009b`에서 수행했다. 새 실제 파일 성능 실험 commit이 아니며 source/테스트 결과와 보호 hash는 implementation lock에 기록했다.

Bigram/run 최적화 후보·paired 사전 계획은 실제 기준선 보존 commit `3ca5f2a`에서 준비했다. 후보 구현/새 특징/예측/속도 실측 commit이 아니며 계획·일정·환경·관련 source/입력 hash를 freeze/verification에 보존했다.

실제 특징 기준선 profile은 실행부/fixture commit `642a733`의 고정 source/lock에서 실행했다. 사전 계획/참조 commit은 `c680183`이며, 실측 raw·모델/특징/예측·함수별 분해 근거를 새 출력에 보존했다. 최적화 구현/실험 commit은 아니다.

특징 profile 실행부/fixture 검증은 계획 동결 commit `c680183`에서 구현했다. 실제 corpus를 실행한 commit이 아니며 새 source/검증 log·fixture 값/보호 hash는 implementation lock에 기록했다. 실제 측정은 이 source/lock을 commit한 이후에만 진행한다.

특징 profiling 사전 계획/참조 동결은 직전 비용 병목 진단 commit `fdf6f66`에서 준비했다. 이번 단계는 저장 특징/예측/모델과 source를 읽어 계획·metadata/hash를 고정했으며 실제 profiling/모델 실행 commit이 아니다. source/사본/산출물 hash와 실행 환경은 freeze/verification에 남겼다.

후보 모델 전체 경로 비용 병목의 읽기 전용 분석은 직전 누락 분석 commit `eea90af`에서 수행했다. 기존 실측은 `6a75f98` source/`f5fcb24` 결과를 그대로 읽었으며 새 최적화/연구 실측 commit이 아니다. 분석/검증 코드와 산출물 hash·실행 환경은 별도 audit/verification에 보존했다.

zstd 선택 누락의 읽기 전용 분석은 원본 결과 보존 commit `f5fcb24`에서 수행했다. 모든 파일별 사전 예측/원시 실측은 기존 `6a75f98` source에서 실행된 결과를 읽었다. 새 모델/codec 실험 commit이 아니며 분석 source/output hash는 별도 audit·verification에 기록했다.

이번 후보 실험의 기준/corpus 동결 `419c484`, 구현/fixture `4ab7c73`, train-only 학습/재로딩 검증 `0cc7df1`, 성능 확인 전 예측 동결 `6a75f98`을 보존했다. 원시 codec/전체 경로 측정·평가/감사는 `6a75f98`의 고정 source에서 실행했다. 결과 보고서 자신의 hash를 넣기 위한 반복 commit은 만들지 않는다.

이번 가상 사용 시나리오 탐색의 마지막 관련 구현/실행 commit은 `73ce6df`(시나리오·실행 코드/fixture의 분석 전 고정)다. 외부 기대 freeze SHA-256과 source hash를 검증하고 깨끗한 HEAD에서 새 파생 결과를 만들었다. 새 codec 측정이나 공식 점수·모델 전환 commit이 아니다.

이번 후보 목적 함수 순수 계산부 구현·fixture 검증의 시작/검증 HEAD는 `2dfa7a4`(후보 수학 설계·검산 보존)다. 새 계산부/전용 테스트/source hash·기존 설계 예제 대조와 보호 hash를 기록했으며 공식 점수 전환이나 연구 실측 commit이 아니다.

이번 사용 조건 기반 후보 목적 함수 설계/검산의 시작 HEAD는 `210e13e`(기존 Pilot 우세 조건·가중치 민감도 탐색 보존)다. 가상 수학 예제와 실제 연구 측정값을 구분하고 source/hash·공식 기준 불변을 기록했다. 새 score의 공식 채택 commit이 아니다.

이번 Pilot 우세 조건·가중치 민감도 탐색의 시작/실행 HEAD는 `699801e`(수동 GUI 복원 검증 보존)다. 원래 Pilot 실측 commit과 새 분석 source hash·고정 계획·독립 저장 검증을 별도로 기록했다. 공식 점수/모델 전환이나 새 실측 commit이 아니다.

이번 수동 GUI 복원 실행·저장 검증의 시작/실행 HEAD는 `df09f49`(수동 Smart 검증·일부 실제 scroll/click 보존)이다. 실제 저장 복원 bytes와 원래 작업 로그/GUI 상태·검증 source hash를 새 근거에 기록했다.

이번 수동 Smart 실행/저장 검증 및 agent 일부 화면 scroll/click의 시작/실행 HEAD는 `508aec2`(재부팅 복구 근거·수동 계획 보존)이다. 새 검증 프로그램 hash와 실제 package/log/model/config/source 근거를 보존했으며 새 압축/모델 평가 실행과 구분한다.

이번 재부팅/daemon recovery 후 GUI 재개와 내장 도구 확인의 시작 HEAD는 `6f4743f`(공식 proxy 초기화 실패·재개 절차 보존)이다. 새 두 시도의 launch/관찰 및 확인/미완료 범위와 보호 hash를 2026-10-28 근거에 보존했다. 제품 코드와 기존 연구 산출물은 변경하지 않았다.

이번 사용자 표시 확인·공식 proxy 재로딩 시도/재개 경로 확인의 시작 HEAD는 `d41661c`(직전 capture 복구 재시도 보존)이다. 실제 proxy는 초기화 timeout으로 reload를 보내지 못했고 관련 CLI/schema·프로그램·미완료 범위를 새 근거에 보존했다.

이번 GUI 캡처 재복구 시도의 시작 HEAD는 `da4f877`(이전 GUI 재개/캡처 불일치 보존)이다. 새 창 선택·Raise·커널 reset/재초기화 및 프로세스 상태 확인을 새 진단 JSON에 보존했으며 근본 원인/정상 캡처/실제 GUI QA 완료와 구분한다.

이번 GUI 중단 재개/현재 캡처 진단의 시작 HEAD는 `684b2bc`(합성 입력 재생성·겹침 감사 보존)이다. 새 observer source hash와 실제 launch·원래 실패·현재 미완료 범위를 별도로 보존했다. GUI 제품 코드·모델·공식 config·기존 실험 결과는 바꾸지 않았다.

이번 합성 재생성·hash 겹침 감사의 시작/실행 HEAD는 `cb9cd9d`(후보 파일별 검토 보존)이다. 실제 재생성은 그 이전 실험의 기록 commit 두 개에 저장된 source/config를 사용했으며 그 hash와 새 감사 source hash를 별도로 보존했다. 당시 bytes의 독립 확인이나 연구 성능 측정 commit으로 취급하지 않는다.

이번 후보 파일별 검토·검토본 게시/검증의 시작/실행 HEAD는 `4610aa3`(추가 원본 수집·통합 draft 검증)이다. 새 검사/게시/검증 및 명시적 판정 source hash를 새 근거에 기록했다. 후보 원본과 기존 모델/결과를 변경하지 않았으며 연구 성능 평가의 실행 commit으로 취급하지 않는다.

이번 추가 원본 수집·통합 draft 검증의 시작/실행 HEAD는 `edf2dcf`(1차 보고서 정리)다. 새 수집/검증 script는 commit 전 정확한 source hash를 기록했고, upstream Git commit·UCI DOI/archive hash는 별도로 보존했다. 연구 압축/모델 평가의 실행 commit으로 취급하지 않는다.

이번 1차 수집 보고서 정리의 시작 HEAD이자 실제 수집/검증 근거 보존 commit은 `65deab0`이다. 보고서의 새 표는 기존 저장 파일을 Python으로 읽어 생성했으며 추가 수집/연구 실측의 실행 commit으로 취급하지 않는다.

이번 실제 파일 1차 후보 수집의 시작 HEAD이자 마지막 manifest 구현 commit은 `173bb47`이다. 고정 upstream commit·원본 bytes/hash·실제 획득/검증 script hash는 이번 package에 별도로 보존했다. 이번 수집을 연구 압축/모델 평가의 실행 commit으로 취급하지 않는다.

이번 manifest 도구 구현·CLI/인위적 검증의 시작 HEAD는 `c0efb44`(node_repl 진단·부분 복구 기록)다. 최종 구현은 commit 전 source hash로 확인했고 정확한 명령·fixture 산출물·테스트와 기존 보호 파일 hash를 기록했다. 실제 corpus나 모델 성능 실험의 실행 commit으로 취급하지 않는다.

이번 node_repl 진단·부분 복구의 시작 HEAD는 `d474f54`(unseen 사전 설계 보존)다. 임시 폴더 복구와 독립 MCP 재현·미완료인 현재 연결 상태를 분리해 기록하며 연구 코드·모델·결과를 변경하지 않았다.

이번 unseen 사전 설계·읽기 전용 계약 확인의 시작 HEAD이자 마지막 관련 GUI 구현 보존은 `e1e9d41`이다. 기존 모델·실험 산출물·source hash와 검증 프로그램을 새 계획 근거 JSON에 보존했다. 이번에는 연구 실험·학습을 실행하지 않았으며 설계 문서 자신의 commit hash를 넣기 위한 반복 commit은 만들지 않는다.

이번 Tk GUI 구현·실제 창/callback 검증의 시작 HEAD는 `ea3892d`(GUI 작업 실행 계층 보존)이다. 실제 검증은 commit 전 작업 트리 상태이며 정확한 소스 hash·원시 산출물·표시 행·테스트와 최초 중단 근거를 기록했다.

이번 GUI 작업 실행 계층 구현·실제 실행의 시작 HEAD는 `8a8d3c8`(GUI/Demo 설계 보존)이다. 새 계층의 실제 검증은 commit 전 작업 트리 상태였으며 소스 hash·명령·원시 결과·최종 테스트를 기록했다. 마지막 통합 CLI 구현 보존은 `f1d8388`이고 그 작업의 시작 HEAD는 `c0394a0`(Compare CLI 보존)이다. Compare 작업의 시작 HEAD는 `085f1ab`, 압축 해제 작업의 시작 HEAD는 `409c9fd`다. 마지막 memory 후보 분석 보존 commit은 `0761b098142433476ef29f9bcc4e70454ef7562b`이고 그 분석 호출 당시 HEAD는 `3927a35c06e6c00fbae0eaaf2bd53d4cbd65e4da`(전용 독립 감사 보존)다. 독립 감사의 실제 호출 HEAD는 `f4dc8c7`이며 측정 실행 HEAD와 구분한다. 문서 자신의 commit hash를 넣기 위한 반복 commit은 만들지 않는다.

동일 환경 반복 검증 attempt02의 최초 Run 1~6 실제 측정 코드·HEAD는 `a8c3e47edc4f9d231605434c464b036240b7b2ed`이고 최초 여섯 run 수집 보존 commit은 `d0f801d`다. 이후 사용자 지시의 Run 2 전체 재측정·교체 실행 HEAD는 `9a261e46d01f61e986d98eedc11f634eda19c863`이며 기존 측정 함수·worker·설정 hash를 유지했다. 이번 결과 보존 commit은 그 실행 commit과 구분한다. 그 직전 실패한 새 설계 attempt01의 증거는 `b249d53`에 보존했다. 새 설계·runner 초기 구현은 `7a0ea69`이다.

기존 완료 memory 실행의 구현·실험 기준 commit은 `3e9b2673a116b045a5e225203e0d175429192c09` (`Harden memory validation finalization and preserve failure evidence`)이며, 결과·audit 보존 commit은 `3ad85c9`이다. Runtime baseline 전체 실측·audit·진단의 실행 코드 commit은 `729b97b09771ea2a50e955b22f5023d49b61733a`이며, 결과·보고서 보존 commit은 `3f7e91ff36266cf2c0271a8ffc3b6a9d5edcafa4`이다. 채택 검토 commit은 `d8b329ad4305322a3bf49aa21d680585220cbb73`이다. 후속 검증 사전 설계 commit은 `82550b8`, timing worker 구현 commit은 `b1d0413`, runner 구현 commit은 `a47ba95`, 독립 audit 구현 commit은 `6bea53a`, 분석기 검증 commit은 `a51907f`, 실측 준비 보존 commit은 `103d1cb`이다. Attempt01의 실제 init·Run 1 측정 실행 HEAD는 `f66f5c0b7e1a41ffb1af66f42d961451e5bf8ac7`이다. 이전 미완료 attempt 증거는 앞선 commit에 보존돼 있다. 이번에는 동일 환경 설계 여섯 run의 마감 증거와 최신 진행 상태를 보존하며 문서 자신의 commit hash를 넣기 위한 반복 commit은 만들지 않는다.

기존 보존 실행이 기록한 마지막 관련 측정 구현·실행 코드 commit:

```text
c54b8f5f9b7ae114206b43ce1e23fe4b69666203
Implement persistent validation-only memory measurement matrix
```

관련 이력:

- `cb9cd9d`: 후보 60개 권리/개인정보 맥락·원본 관계 검토, CPython notice 보완·승인 inventory/draft·독립 보존 검증. 이번 합성 겹침 감사의 시작 HEAD.
- `4610aa3`: 추가 실제 원본 30개·총 60개/18개 그룹의 통합 미선정 draft·출처/획득/독립 검증 근거 보존. 이번 후보 파일별 검토 작업의 시작 HEAD.
- `edf2dcf`: 1차 수집 보고서의 그룹/파일 목록·부족분·추가 수집 순서와 문서 검증 근거 보존. 이번 추가 원본 수집/통합 draft 검증의 시작 HEAD.
- `65deab0`: 실제 후보 30개/6개 원본 그룹의 고정 출처·원본 보존·미선정 draft·획득/독립 검증 근거 보존. 이번 1차 수집 보고서 정리의 시작 HEAD.
- `173bb47`: 실제 파일 후보 manifest 도구 구현·전용 23개/fixture CLI 9건·실패/선정 상태 검증 보존. 이번 실제 파일 1차 후보 수집의 시작 HEAD.
- `c0efb44`: node_repl 누락 임시 경로 진단·부분 복구·독립 재현·현재 연결 재시작 대기 기록 보존. 이번 manifest 도구 구현의 시작 HEAD.
- `d474f54`: 실제 파일 unseen 평가 사전 설계·기존 모델/baseline·보호 파일의 읽기 전용 계약 확인 보존. 이번 node_repl 오류 복구의 시작 HEAD.
- `e1e9d41`: Tk GUI/Demo·전용 15개+계층 18개 테스트·실제 callback/CLI 흐름·최초 중단 근거 보존. 이번 unseen 평가 사전 설계의 시작 HEAD. GUI OS 입력·시각 QA는 미완료.
- `ea3892d`: GUI 단일 작업 실행 계층·결과/로그 판정·전용 18개 및 실제 요청 14건 검증 보존. 이번 Tk GUI 구현·검증의 시작 HEAD.
- `8a8d3c8`: GUI/Demo 화면·실행 흐름·결과/오류·검증 계획과 환경/계약 확인 보존. 이번 GUI 작업 실행 계층 작업의 시작 HEAD.
- `f1d8388`: 통합 CLI·전용 12개/회귀 34개 검증·최종 실제 호출 22건과 원시 비교 근거 보존. 직전 GUI/Demo 설계 작업의 시작 HEAD.
- `c0394a0`: 독립 Compare CLI·전용 16개/회귀 16개 검증·README 실제 비교와 원시 반복/점수 보존. 직전 통합 CLI 작업의 시작 HEAD.
- `085f1ab`: 독립 압축 해제 CLI·전용 13개/기존 압축 5개 검증·기존 여섯 package 실제 복원 보존. 직전 Compare CLI 작업의 시작 HEAD.
- `409c9fd`: Memory 참고 지표 보존·추가 구현 보류 사용자 결정과 진행 상태 기록. 직전 독립 압축 해제 CLI 작업의 시작 HEAD.
- `0761b09`: 동일 환경·Run 2 교체 후보 분석기·전용 11개/계산부 회귀 13개 검증·실제 사전 기준 미충족 결과 보존. 직전 사용자 결정 기록 작업의 시작 HEAD.
- `3927a35`: 동일 환경·Run 2 교체 전용 독립 감사 구현·전용 fixture 24개·실제 감사 보고서 보존. 직전 후보 분석 작업의 시작 HEAD.
- `f4dc8c7`: Run 2 전체 재측정 결과 교체·원본 전체 보존·저장 검증. 직전 독립 감사 작업의 시작 HEAD.
- `9a261e4`: 사용자 지시의 Run 2 전체 재측정·원본 보관·활성 결과 교체 도구, 사전 변경 기록과 전용 fixture 검증. 실제 재측정 실행 HEAD.
- `d0f801d`: 최초 attempt02 여섯 run 수집 마감과 Run 2 timeout 증거 보존. 이번 Run 2 교체 작업의 시작 HEAD.
- `a8c3e47`: collector revision 2 metadata I/O 보완·47개 전용 테스트 검증. 동일 환경 반복 검증 attempt02 전체 측정 HEAD.
- `b249d53`: 새 설계 attempt01의 metadata 교체 실패·원시 증거 보존.
- `7a0ea69`: 별도 동일 환경 반복 설계·runner 구현과 전용 검증.
- `82041e8`: 기존 3일 설계 attempt01의 Run 1 원시 증거·제한된 검증·Run 2 시작 창 경과 사실 보존. 새 동일 환경 반복 설계 작업의 시작 HEAD.
- `f66f5c0`: 즉시 착수 기록·사건 답변 대기 상태를 고정한 commit. Attempt01의 실제 init·Run 1 측정 실행 HEAD.
- `103d1cb`: memory 안정성 실측 준비 문서·환경 snapshot·진행 기록 보존. 착수 기록 작업의 시작 HEAD.
- `a51907f`: memory 안정성 후속 검증 분석기 초안 검토·전용 fixture 검증과 보존. 이번 실측 준비의 시작 기준 HEAD.
- `6bea53a`: memory 안정성 후속 검증 독립 audit 및 전용 fixture 검증. 이번 분석기 검토·검증의 시작 기준 HEAD.
- `a47ba95`: memory 안정성 후속 검증 runner 및 전용 fixture 검증. 이번 독립 audit 구현의 시작 기준 HEAD.
- `b1d0413`: memory 안정성 후속 검증 timing worker 및 전용 테스트. 이번 runner 구현의 시작 기준 HEAD.
- `82550b8`: memory 대표값·정답 안정성 후속 검증 사전 설계. 이번 timing worker 구현의 시작 기준 HEAD.
- `d8b329a`: memory 공식 채택 보류 권고·추가 검증 필요성·전환 조건 검토. 이번 후속 검증 사전 설계의 시작 기준 HEAD.
- `3f7e91f`: runtime baseline 원시 증거·audit·진단·보고서 Git 보존 및 읽기 전용 재검증. 이번 채택 검토의 시작 기준 HEAD.
- `729b97b`: runtime baseline 진단 분석 및 fixture 검증. 이번 전체 실측·audit·진단의 실행 기준 HEAD.
- `c9bf6e6`: runtime baseline 별도 audit 및 fixture 검증. 이번 진단 분석 작업의 시작 기준 HEAD.
- `9d3f120`: runtime baseline runner 및 fixture 테스트 구현. 이번 별도 audit 작업의 시작 기준 HEAD.
- `018758c`: runtime baseline worker 및 전용 테스트 구현. 이번 runner 작업의 시작 기준 HEAD.
- `584fc68`: 별도 runtime baseline 검증 설계. 새 worker 작업의 시작 기준 HEAD.
- `3ad85c9`: 2026-09-22 전체 memory 검증 행렬 및 audit 결과 보존. 현재 별도 runtime baseline 설계의 시작 기준 HEAD.
- `3e9b267`: 종료 metadata 원자적 저장·오류 기록 보강 및 관련 fixture 테스트 28개 검증. 2026-09-22 전체 행렬의 실행 코드 기준.
- `210b38d`: 완료된 memory 검증 기록의 audit 도구 및 인위적 fixture 검증 정리.
- `708c9cb`: 미완료 memory 실행 원본·보존용 Git 속성·진행 기록 보존. 이번 audit 구현·테스트는 그 후속 작업이며 문서 자신의 commit hash를 넣기 위한 반복 commit은 만들지 않는다.
- `70294a6`: 특징 기반 Smart Mode 구현. 최초 문서 작성 당시 마지막 구현 commit.
- `811385b`: 1,008 sample Pilot 실패 분석 결과 기록.
- `81adc0d`: Random Forest 평가 결과 기록.
- `c8e18b5`: Decision Tree 평가 결과 기록.
- `6b6a7bb`: baseline 평가 결과 기록.
- `572760b`: 독립 peak memory 측정 정의.
- Pilot 원시 실험 metadata의 실행 코드 commit: `4d2d637bea96a4a1ddbbedb2c077fd0474ca8c19`.

최초 문서 작성 전 `main` 작업 트리는 깨끗했다. 샌드박스의 Pilot 하위 폴더 접근 제한으로 삭제처럼 표시된 항목은 실제 권한으로 재확인했으며 삭제가 아니었다. 2026-09-16 증거 보존 작업 시작 시에는 audit 스크립트가 staged이고 memory 결과 폴더가 untracked였다. 이후 세션은 당시 상태를 그대로 가정하지 말고 `git status`와 최근 commit을 다시 확인한다.
