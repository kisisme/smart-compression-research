# 실제 파일 unseen 평가 사전 설계 v1 — 2026-10-26

상태: **사전 설계 완료 / corpus 수집·동결·평가 runner·실측·모델 평가는 미완료**.
이번 문서는 결과가 없는 실행 계획이다. 아래 수량은 수집 목표이며 확보된 파일 수가 아니다.
공식 기준은 [프로토콜 v2](../research_protocol_v2.md) 16·23~25절과
[활성 config](../config/experiment_config.json)다. 기존 Pilot·모델·설정은 변경하지 않는다.
Memory는 계속 `validation_only`이며 공식 score 편입·추가 측정을 보류한다.

## 1. 평가 질문과 기존 코드의 범위

합성 데이터로 학습한 저장 모델을 고정했을 때, 새 실제 파일에서 Pilot 학습 최빈 baseline보다
낮은 공식 3지표 score/regret를 얻는지 평가한다. 두 모델과 세 mode를 모두 보고한다.
결과를 보고 모델·특징·압축 수준·가중치·시험 파일을 유리하게 바꾸지 않는다.

기존 [학습 코드](../src/train_model.py)는 합성 generator·seed 그룹의 train/test 분할과
`.fit()`을 전제로 한다. 실제 파일에 가짜 seed/generator를 붙여 이 경로에 넣지 않는다.
새 평가 runner는 별도로 구현하며 **재학습 없이 저장 모델을 읽어 예측**한다.
GUI 입력·시각 QA는 도구 초기화 실패로 남아 있지만, 이 독립적인 사전 설계에는 영향을 주지 않는다.
GUI QA를 완료했다고 기록하거나 연구 평가를 시작하지 않는다.

## 2. 수집 범위와 선택 규칙

1차 실제 파일 holdout의 목표는 **60개 파일**이다. 비교 결과를 보지 않고 다음 조건으로 수집한다.

| 항목 | v1 고정안 |
|---|---|
| 형식 | 일반 text, CSV, JSON, Python source, log, binary. 저장 enum은 `text,csv,json,python,log,binary` |
| 형식별 수 | 각 10개. 압축기 정답 클래스 비율을 맞추는 기준은 아님 |
| 원본 그룹 | 전체 최소 12개, 형식마다 최소 2개 |
| 원본 그룹당 상한 | 형식을 합쳐 최대 5개 파일 |
| 크기 | 원본 bytes 기준 16,384~1,048,576, 양 끝 포함 |
| 원본 보존 | 완전한 파일 그대로 사용. 자르기·이어 붙이기·복제·padding·재직렬화·줄바꿈/encoding 변환 금지 |
| 선정에 사용 가능 | 출처·권리·형식·원본 관계·크기·bytes hash·경로 등 수집 metadata |
| 선정에 사용 금지 | 통계 특징 값, 모델 예측/confidence, 압축 크기/시간, score, 실제 best |

이 크기 범위는 기존 Pilot의 범위 안에서 실제 파일의 통계적 조합을 시험하기 위한 제한이다.
더 작거나 큰 파일의 일반화·대용량 스트리밍을 검증하는 설계는 아니다.
binary에는 원래부터 binary인 실제 파일을 사용하고, 이미 압축된 형식인지 metadata로 구분한다.
난수·합성 generator·테스트 fixture·빈 파일을 실제 파일로 세지 않는다.

저작권/사용 조건과 공개 출처를 확인할 수 있고 개인정보·비밀정보가 없는 자료만 후보에 넣는다.
구체적인 출처·라이선스·버전은 **아직 선정하지 않았다**. 공개되어 있다는 이유만으로 사용 가능하다고
간주하지 않는다. 외부 자료를 정할 때 원출처와 이용 조건을 확인하고 source inventory에 근거를 남긴다.
프로젝트 코드/README·기존 GUI/CLI smoke 입력·수동 작성한 fixture는 이번 holdout에서 제외한다.

후보 inventory를 `(format, origin_group_id, input_sha256, relative_path)` 순서로 보존하고,
수집 metadata만으로 조건을 만족하는 선정 ID 목록과 선정/제외 사유를 작성한다.
선정은 권리·출처와 범주를 검토하는 수집 단계이며 모집단의 확률 표본 추출이 아니다.
동결 도구는 명시된 선정 ID와 모든 quota/그룹 조건을 검증하며 파일을 자동 교체하지 않는다.
조건을 만족할 수 없으면 수집을 미완료로 남긴다. 결과를 보기 전 설계 변경을 별도 버전으로 기록하거나
후보를 추가한 새 inventory 버전을 만들고 다시 동결한다. 조건 미충족을 숨겨 60개 완료로 기록하지 않는다.

## 3. 원본 그룹·중복·unseen의 의미

`origin_group_id`는 원래 저장소·문서/데이터 collection·공통 원본 단위를 나타낸다.
같은 저장소의 폴더/버전·mirror·같은 데이터의 다른 encoding/직렬화·chunk/파생 파일은 같은 그룹이다.
여러 출처 사이에 파생 관계가 발견되면 연결된 관계 전체를 한 그룹으로 합친다.
파일 확장자나 다운로드 URL이 다르다는 이유로 별도 원본으로 세지 않는다.

정확히 같은 bytes는 SHA-256으로 전역 중복 확인한다. 동일 hash 후보가 여러 개면 정렬상 첫 항목을
대표로 삼고 나머지는 `exact_duplicate_of`로 보존한다. 압축/예측 결과를 보기 전의 수집 규칙이다.
알려진 매우 유사한 파생본은 그룹/관계 metadata에 남기며 별도의 독립 원본처럼 해석하지 않는다.
자동 의미 유사도 탐지까지 보장하지 않으므로, 미확인 유사성이 남을 수 있음을 한계로 보고한다.

이번에는 기존 합성 학습/개발 데이터와 분리한 외부 holdout 전체를 평가한다.
실제 파일을 새로 80:20으로 나누거나 일부를 재학습에 사용하지 않는다.
기존 Pilot과 초기 검증 sample의 bytes hash는 기록된 generator·seed·size·parameters 및 소스/환경을
대조해 재생성 가능한 범위에서 Python으로 확인하고, 후보와 정확히 겹치는 입력은 제외 근거를 남긴다.
재생성 근거가 맞지 않으면 겹침 확인 완료로 기록하지 않는다. 이 점검 구현/실행도 아직 미완료다.

향후 실제 파일로 모델을 개선한다면 이 holdout은 이미 관찰한 개발 데이터가 된다.
새 최종 평가에는 원본 그룹 자체가 다른 새 holdout을 마련한다. 같은 원본의 다른 파일만으로
새 unseen이라고 주장하지 않는다. 원본 그룹 구분은 파일별 의존성을 줄이기 위한 기록이며
그룹 사이의 통계적 독립성을 입증한 것은 아니다.

## 4. 수집 manifest와 동결

원본의 계획 경로는 새 `data/raw/real_unseen/<corpus-id>/`이다. 기존 경로에는 쓰지 않는다.
현재 `.gitignore`의 `data/raw/` 규칙을 사용해 실제 원본은 Git 제외 대상으로 둔다.
출처·hash·선정 manifest·재현 근거는 별도의 새
`data/results/real_unseen/<corpus-id>/manifest/`에 보존할 계획이다. 원본 bytes를 이 기록에 섞지 않는다.

필수 후보 기록:

```text
candidate_id, relative_path, original_filename, format, origin_group_id
source_locator, source_version, acquired_at_utc, license_id, license_evidence
original_size, input_sha256, is_precompressed, derivative_of
rights_review_status, privacy_review_status, reviewed_at_utc
selection_status, exclusion_reason, exact_duplicate_of
```

선정된 파일은 full SHA-256에 기반한 `sample_id`를 사용한다. 짧은 hash만으로 동일성을 판단하지 않는다.
선정/제외 후보 목록·원본 그룹 관계·출처/권리 확인·파일 hash/크기·선정 규칙 버전을 저장하고,
이를 묶은 corpus manifest의 SHA-256과 Git commit을 **특징 추출·예측·측정 전에** 동결한다.
재현 가능한 원본 파일과 hash가 없는 링크 목록만으로 corpus 완료 판정을 하지 않는다.
선정 파일은 권리/개인정보 검토가 `approved`여야 한다. 문자열의 존재를 권리 확인으로 간주하지 않고
검토 근거와 시각을 확인한다. `pending` 후보는 inventory에 보존하되 동결된 시험 파일로 쓰지 않는다.
Corpus 변경은 새 ID와 새 manifest로 남기고 기존 목록을 덮어쓰지 않는다.

동결 도구는 root 안의 일반 파일만 읽는다. 절대/드라이브 경로·`..` 탈출·symlink/junction·
같은 실제 경로의 별칭/중복·읽는 도중 변경을 거부하고 Windows의 대소문자 경로 동등성을 고려한다.
입력 bytes의 크기와 full SHA-256은 Python으로 직접 확인한다.
선정 ID·형식 quota·그룹 상한/최소 수·권리/개인정보 상태·중복·파일 hash·계획 버전을 모두 만족할 때만
`frozen`으로 게시한다. 후보 작성 단계의 `draft`를 정상 corpus처럼 사용하지 않는다.
기존 출력 거부·새 디렉터리의 부분 게시/실패 근거 보존을 검증하며 모델/특징/압축을 호출하지 않는다.

## 5. 고정 모델·baseline·예측

기존 `data/results/pilot_1008/`의 다음 항목을 읽기 전용으로 고정한다.

- `decision_tree/decision_tree_<mode>.pkl`와 해당 summary.
- `random_forest/random_forest_<mode>.pkl`와 해당 summary.
- `baseline/baseline_summary.json`, `baseline_models.json`, `split_assignments.csv` 및 연결된 Pilot 라벨.

[Smart의 `load_selector`](../smart_compress.py) 계약을 사용해 모델/summary hash·Python/package·
특징 순서·실제 estimator 종류·설정·관련 소스가 맞는지 확인한다. 로컬에서 생성한 신뢰 가능한
모델만 읽는다. 새 runner 때문에 검증을 약화하거나 호환되지 않는 모델을 조용히 다시 학습하지 않는다.

Baseline은 저장된 **Pilot train 부분의 최빈 알고리즘**이다. 학습 분할과 원래 라벨로 이를 재검증한다.
[읽기 전용 확인 기록](unseen_evaluation_design_v1_checks.json)에서 세 mode 모두 zstd임을 확인했다.
Unseen 파일의 정답으로 baseline을 새로 정하지 않는다. 따라서 항상 zstd와 값이 같아도 두 전략명을
별도로 보존하되 서로 독립적인 우수 사례로 세지 않는다.

ML 입력은 기존 `FEATURE_NAMES`의 순서가 있는 12개 압축 전 특징뿐이다. `format`, 그룹·경로·출처·
크기 구간·측정값·정답/score는 별도 metadata이며 추가 ML 입력으로 넣지 않는다.
특징과 예측에 사용한 원본 hash를 저장하고 두 모델×세 mode의 예측을 **benchmark 전에 동결**한다.
확률 벡터는 모델의 class 순서를 확인해 네 알고리즘 열로 매핑하며, confidence는 보정된 정답 확률이 아니다.
낮은 confidence 재선택·hybrid fallback·새 calibration·모델 선택/재학습을 하지 않는다.

## 6. 측정·정답과 실패 보존

[Compare](../compare_compress.py)의 기존 계약으로 같은 동결 입력을 네 알고리즘으로 비교한다.
입력/설정/소스 hash·정상 상태·산출물 hash·실패 게시 표시를 검증한 뒤 저장된 원시 반복에서
중앙값과 공식 score를 다시 계산한다. 기존 코드와 다른 측정 정의를 새로 만들지 않는다.

- 압축 설정: gzip 9, bz2 9, lzma preset 6, zstd 3.
- 각 알고리즘의 압축/해제 각 5회, `perf_counter_ns`, 원시 ns·중앙값 ms.
- 파일 순서는 `(origin_group_id, sample_id)` 오름차순, 알고리즘 순서는 `gzip,bz2,lzma,zstd`.
  기존 Compare의 고정 순서에 따른 환경/순서 한계를 기록하고 결과를 보고 순서를 바꾸지 않는다.
- 측정은 메모리 bytes에 대한 codec 시간이다. 특징·예측·파일 I/O·hash/검증 비용과 구분한다.
- 네 알고리즘 모두 정상이고 복원 bytes가 일치할 때만 세 mode의 점수/정답을 만든다.
  현재 공식 가중치·로그 상대 손실·exact tie 순서를 사용하며 epsilon/사후 가중치를 추가하지 않는다.

실패·미실행 slot·정상/무효 상태·원래 stderr/exception과 부분 산출물을 보존한다.
파일/모델/소스/config가 달라지면 해당 실행을 무효로 표시한다.
절전/재부팅/중단이 확인된 session은 근거와 함께 무효로 남기며 새 전체 run 경로에서 재실행한다.
느리거나 불리한 시간이라는 이유만으로 절전/이상치로 간주하지 않고, 선택적 반복 교체·outlier 제거·
자동 재시도를 하지 않는다. 재실행 여부/사유는 성능 결과에 따른 선택과 구분해 기록한다.

네 측정이나 필요한 예측이 하나라도 빠지면 전체 정상 완료/모델 개선 결론을 내리지 않는다.
진단용 집계는 모든 비교 전략에 공통으로 유효한 파일만 같은 분모로 사용하고,
`conditional_on_complete_cases`와 제외 수·원래 원인·형식/그룹별 coverage를 표시한다.
실패율을 지우거나 이 조건부 표를 전체 60개의 정식 결과로 부르지 않는다.

## 7. 비교 지표와 해석

각 mode에서 항상 gzip/bz2/lzma/zstd, 동결 majority baseline, 동결 Decision Tree/Random Forest,
oracle의 여덟 전략을 **동일 파일과 측정값**으로 비교한다.

필수 표는 accuracy·고정 네 클래스의 Macro F1(`zero_division=0`)·4×4 혼동행렬·정답 support,
평균 compression ratio/압축 ms/해제 ms/score, 평균·중앙값·최대 oracle regret이다.
Regret는 `그 파일에서 전략이 고른 알고리즘의 score - oracle best score`다.
Score와 regret의 평균을 혼동하지 않으며 oracle score 자체가 0일 필요는 없다.
시험에 없는 클래스도 기존 Macro F1 정의에서 제외하지 않는다.

1차 비교량은 **원본 그룹을 동일 비중으로 둔 mean regret의 baseline 대비 차이**다.
각 그룹 안에서 파일별 `model_regret - baseline_regret`의 평균을 구한 뒤 그룹 사이의 평균을 낸다.
음수면 이 corpus에서 손실이 작았다는 뜻이다. 파일 동일 비중의 pooled 지표도 함께 보고한다.
형식·원본 그룹·크기 구간별 진단을 함께 제시하되 유리한 하위집단만으로 전체를 대표하지 않는다.
크기 구간은 `16,384 ≤ size < 65,536`, `65,536 ≤ size < 262,144`,
`262,144 ≤ size ≤ 1,048,576` bytes다.

두 모델×세 mode를 모두 보고하며 결과 후 최상의 한 조합만 선택하지 않는다.
별도 검정/신뢰구간은 v1의 확정 범위가 아니다. 효과 크기의 기술적 비교로 제한하고
통계적 유의성·전체 실제 파일 모집단의 개선을 주장하지 않는다. 형식 quota는 자연 분포가 아니다.
예측이 정답과 달라도 score가 exact tie이면 regret가 0일 수 있다.
어떤 압축기의 독점·baseline 미개선·높은 confidence 오답도 그대로 결과에 남긴다.
특징 추출/예측을 포함한 end-to-end 속도 개선은 별도 후속 평가다.

## 8. 산출물·구현 순서·완료 조건

새 결과 경로 `data/results/real_unseen/<corpus-id>/<run-id>/`에 저장할 계획이다.
입력 corpus나 기존 Pilot/결과를 덮어쓰지 않는다. N은 동결된 입력 수이며 v1 목표는 60개다.
정상 완료 시 기대 행 수는 다음과 같다.

| 산출물 | 정상 기대 수/내용 |
|---|---|
| corpus snapshot·입력/모델/config/source manifest | 경로·full hash·버전·시각·Git/환경·계획/실제 상태 |
| `samples.csv` | N개 입력의 출처/그룹/형식/크기와 12개 특징 |
| `frozen_predictions.csv` | N×2모델×3mode, 예측·confidence·확률·모델/입력 hash |
| 원래 Compare 보고서/CSV | 파일마다 원문 보존, full 입력 hash와 corpus sample ID 연결 |
| `timing_repeats.csv` | N×4알고리즘×2phase×5 slot, 실패/미실행도 유지 |
| `compression_results.csv` | N×4, 정상/실패·복원 검증·중앙값 |
| `selection_labels.csv` | N×3, 네 알고리즘 정상인 파일만 정답 가능 |
| `strategy_choices.csv` | N×3mode×8전략, score·regret·정오답·측정 참조 |
| metrics·confusion·grouped·coverage·오류 보고서 | 분모/범위·전체/조건부 구분·파일/그룹 동일 비중·모든 실패 |

Compare의 짧은 sample ID를 그대로 corpus의 고유 ID로 간주하지 않는다. full hash로 연결하고
충돌을 거부한다. raw 측정·계산된 라벨·고정 모델 예측·평가 집계 파일을 구분한다.
성공·실패 게시 상태와 산출물 hash를 확인한 독립 저장 감사 후에만 정상 결과로 사용한다.

다음 단일 구현은 **후보 manifest 작성·원본 그룹/경로/hash 검증·동결 도구**다.
수집 전에 Git 제외 경로·출처/권리 기록을 마련하고 소량의 인위적 fixture로 계약을 검증한다.
그 다음 실제 후보 수집/검토·중복 확인·동결 → 별도 frozen prediction/Compare runner →
저장 감사/평가 순으로 진행한다. GUI OS 점검은 화면 도구 복구 시 별도로 완료한다.
기존 `src/train_model.py`·공식 config·저장 모델은 이 구현 때문에 수정하지 않는다.

이 사전 설계의 확인 근거는 [context 검사 JSON](unseen_evaluation_design_v1_checks.json)에 있다.
현재 소스/설정/모델/baseline·저장 라벨의 읽기 전용 계약과 hash를 대조했으며 검증 프로그램 원문도
포함한다. 이 단계에서 외부 파일 수집·합성 재생성·모델 로딩/예측·압축·새 학습·연구 실측·
GUI 입력·단위 테스트를 실행하지 않았다. 실행되지 않은 계획을 실제 평가 결과로 취급하지 않는다.

후속 구현 — 2026-10-26: [후보 manifest 도구](unseen_manifest.md)의 draft·freeze·audit와
전용 인위적 fixture/CLI 검증을 완료했다. 선정 상태·미선정 사유·full hash·명시적 선택과
수량/원본 그룹/검토 상태·경로/변경·실패 보존을 확인한다. `frozen`은 입력 목록만 고정하며
겹침 검사는 `not_performed`, `evaluation_ready=false`다. 실제 corpus 수집·unseen 확인·평가를
완료한 것으로 바꾸지 않는다. 구현된 JSON schema와 검증 근거는 위 도구 안내를 따른다.
