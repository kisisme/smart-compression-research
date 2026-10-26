# 실제 후보 60개 파일별 검토 보고서 — 2026-10-26

**후보 60개를 파일별로 검토해, 원본·notice·citation을 보존하는 무수정 로컬 연구 입력 범위에서 사용 가능으로 분류했다.** 권리·개인정보 맥락 검토 판정은 새 inventory에 반영했으며, 최종 선정·합성 겹침 확인·corpus 동결·모델 평가는 아직 수행하지 않았다.

## 판정의 범위와 방법

[검토 정책과 명시적 파일별 판정](unseen_candidate_decisions_20261026.json)에 승인 범위와 각 후보의 근거를 남겼다. 전체 파일을 읽는 구조 파싱/문자열·주석 스캔에, 원출처·license·표시된 맥락을 확인한 assistant 판단을 결합했다. 사람이 모든 source line을 수동 정독했다는 기록으로 쓰지 않는다. 자동 패턴의 부재만으로 승인하지 않았다.

공개 저자·저작권·문의처·메일링리스트 인용, 공개 기술 문서의 예시, 배포 프로그램의 telemetry 설정은 실제 비공개 사용자 기록·개인 계정 인증정보와 맥락을 구분했다. 이런 공개 metadata가 포함된 원본을 익명 자료 또는 개인정보 표시가 전혀 없는 자료라고 표현하지 않는다. 식별자 값을 수집·활용하는 연구가 아니며 원본을 실행하거나 외부 endpoint/키를 시험하지 않았다.

| 형식 | 검토 후보 | 권리 승인 | 개인정보 맥락 검토 승인 |
|---|---:|---:|---:|
| text | 10 | 10 | 10 |
| csv | 10 | 10 | 10 |
| json | 10 | 10 | 10 |
| python | 10 | 10 | 10 |
| log | 10 | 10 | 10 |
| binary | 10 | 10 | 10 |

표는 새 검토 기록을 Python으로 읽어 집계했다. 수량/그룹 조건은 60개·여섯 형식 각 10개·18개 원본 그룹을 유지했다. 모든 파일은 여전히 미선정 후보다. 승인 판정과 `selected_ids=[]`, `evaluation_ready=false`를 구분한다.

## 형식별 실제 검토

- **CSV:** 모든 셀을 원래 구분자/encoding으로 파싱하고, 숫자 이외의 값 전체와 날짜 표현을 원래 자료의 schema에 대조했다. 패류 측정의 F/I/M은 사람의 성별 기록이 아니다. 자동차 자료는 모델별 사양/위험도이고 보험 계약자 자료가 아니다. 자전거 자료는 일별/시간별 집계이며 개별 이용자 이동 기록을 포함하지 않는다. 화학·산불·원격탐사 자료의 분류값도 실제 사람 기록과 구분했다.
- **JSON:** 전체 JSON을 순회해 localization/배포 manifest 역할, 기본값과 schema, 출처·license·telemetry 관련 맥락을 확인했다. CLDR는 언어·통화·날짜·시간대 표시 데이터다. VS Code의 `apiKey` schema와 패치 설명의 예시 경로를 실제 저장된 사용자 credential과 구분했다.
- **Python:** AST/token과 전체 문자열/주석을 검사하고 source 역할·특이 literal·복사/권리 표시를 검토했다. NumPy의 큰 literal은 공개 API 문서였으며, 별도 외부 코드 유래 1건을 발견해 아래와 같이 보완했다.
- **text:** curl의 파일별 SPDX와 COPYING, Git의 COPYING을 대조했다. 저자 이력·공개 메일 인용과 Trace2 문서 예시의 경로/SID, 버전 문자열을 실제 비공개 사용자 로그로 오인하지 않았다. 공개 문서 예시에 실제 형태의 경로가 있음을 기록했고 가공·비식별화된 자료라고 주장하지 않았다.
- **log:** 모든 MLLOG record와 문자열 값을 확인했다. Training은 공개 제출 조직/장비명과 일반적인 container source 경로, Inference는 source 파일명·build hash·실행 thread/시간 metadata였다. 실제 prompt/개인 연락처/사용자 credential 기록은 확인되지 않았다. 기존 benchmark 숫자를 이번 압축 연구의 측정값으로 사용하지 않았다.
- **binary:** shapefile의 모든 record가 숫자 polyline/polygon 구조인지 확인했다. 후보는 DBF 사람 속성표가 없는 전지구 물리 지도 geometry다. TrueType의 모든 name-table record와 license/저자/제조사 metadata를 읽었으며 글꼴을 설치하거나 실행하지 않았다.

원래 CSV 문서의 citation 요청과 출처도 확인했다. UCI page/DOI 인용 외에 Bike Sharing·Wine Quality·Forest Fires의 원래 논문 인용을 추가했고, Wilt 원래 연구의 제목/저자/쪽수도 출판사 issue page로 대조했다. [사용 조건 목록](../data/results/real_unseen/real_candidate_review_20261026_01/usage_requirements.json)에 보존할 notice와 추가 citation을 후보 ID별로 연결했다.

## 검토에서 보완한 사항

**NumPy `numpy_04`:** 원본 `arrayprint.py` 574–600행에 Python 3.2 `reprlib.recursive_repr` 유래가 명시돼 있었다. [고정 CPython 3.2 source](https://github.com/python/cpython/blob/29360893df0931703cb2fe0c0fbc0fc963e64ead/Lib/reprlib.py)와 [해당 전체 LICENSE](https://github.com/python/cpython/blob/29360893df0931703cb2fe0c0fbc0fc963e64ead/LICENSE)를 비교·보존했다. 새 검토 inventory의 license 표시는 `BSD-3-Clause AND PSF-2.0`로 보완했다. PSF notice와 upstream NumPy의 인수 전달/`functools.wraps` 적응 내용을 사용 조건 기록에 남겼다. PSF 식별 근거는 [SPDX PSF-2.0](https://spdx.org/licenses/PSF-2.0.html)다. NumPy/CPython 원본 bytes는 수정하지 않았다.

**글꼴 `google_fonts_05`:** name ID 14의 오래된 URL이 명시적 license URL과 맞지 않았다. 내장 name ID 13의 OFL 1.1 문구와 같은 family의 전체 OFL.txt가 일치함을 확인해 판정했으며, 글꼴 내부 URL을 고치지 않았다. 다섯 family의 notice·copyright·Reserved Font Name을 유지한다. [OFL 공식 원문](https://openfontlicense.org/open-font-license-official-text/)의 원본 유지/notice 조건을 적용한다.

**VS Code 배포 설정:** `vscode_01/03/04/05`에 공개 publisher telemetry 값이 있었다. 고정 버전 [services.ts 193–194 및 332–335행](https://github.com/microsoft/vscode/blob/e2fb9a1be30766bd1d1cfd2107fe3e88666b7f4e/extensions/copilot/src/extension/extension/vscode-node/services.ts), `TelemetryService`, `MicrosoftTelemetrySender`를 따라 telemetry 전송 설정임을 확인했다. end-user token store와 구분해 분류했으며, 실제 값은 검토 보고서/판정표에 재전재하지 않았다. 공개 배포 설정이 있다는 사실만으로 임의의 `key` 값을 모두 안전하다고 승인하는 규칙을 만들지 않았다.

## 원본·파생 관계

[관계 기록](../data/results/real_unseen/real_candidate_review_20261026_01/relationships.json)에 9개 관계/처리 기록을 남겼다.

- Natural Earth 해안선·육지·바다는 [공식 설명](https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-coastline/)에서 경계가 맞춰졌음을 확인했다. 같은 그룹을 유지하며, 알려지지 않은 파생 방향을 임의로 `derivative_of`에 넣지 않았다.
- Wine red/white, Wilt의 upstream training/testing, Training 반복 run, Inference 시스템/scenario는 각각 같은 collection 그룹을 유지했다. 이번 연구에서는 Wilt 두 파일 모두 외부 후보이며 학습하지 않는다.
- MLCommons 조직/AMD 제출자 공통성은 기록하되 Training/Inference라는 서로 다른 실행 collection을 통계적으로 독립이라고 주장하지 않는다. Copilot의 별도 upstream repository 표기도 보존하고 전체 VS Code 배포 그룹을 유지했다.
- CPython 유래는 외부 code fragment 관계이며 새 corpus 그룹으로 늘리지 않았다. pandas의 NumPy/Numba 의존성 참조와 원본 관측자료 복제를 구분했다. 모든 코드의 계보를 완전 증명했다는 주장은 하지 않는다.

| 원본 그룹 | 후보 ID | 수량 | 적용 license |
|---|---|---:|---|
| cldr | `cldr_01`, `cldr_02`, `cldr_03`, `cldr_04`, `cldr_05` | 5 | Unicode-3.0 |
| curl | `curl_01`, `curl_02`, `curl_03`, `curl_04`, `curl_05` | 5 | curl |
| git | `git_01`, `git_02`, `git_03`, `git_04`, `git_05` | 5 | GPL-2.0-only |
| google_fonts | `google_fonts_01`, `google_fonts_02`, `google_fonts_03`, `google_fonts_04`, `google_fonts_05` | 5 | OFL-1.1 |
| mlperf_inference | `mlperf_inference_01`, `mlperf_inference_02`, `mlperf_inference_03`, `mlperf_inference_04`, `mlperf_inference_05` | 5 | Apache-2.0 |
| mlperf_training | `mlperf_training_01`, `mlperf_training_02`, `mlperf_training_03`, `mlperf_training_04`, `mlperf_training_05` | 5 | Apache-2.0 |
| natural_earth | `natural_earth_01`, `natural_earth_02`, `natural_earth_03`, `natural_earth_04`, `natural_earth_05` | 5 | LicenseRef-Natural-Earth-Public-Domain |
| numpy | `numpy_01`, `numpy_02`, `numpy_03`, `numpy_04`, `numpy_05` | 5 | BSD-3-Clause; BSD-3-Clause AND PSF-2.0 |
| pandas | `pandas_01`, `pandas_02`, `pandas_03`, `pandas_04`, `pandas_05` | 5 | BSD-3-Clause |
| uci_abalone | `uci_abalone_01` | 1 | CC-BY-4.0 |
| uci_automobile | `uci_automobile_01` | 1 | CC-BY-4.0 |
| uci_bike_sharing | `uci_bike_sharing_01` | 1 | CC-BY-4.0 |
| uci_biodegradation | `uci_biodegradation_01` | 1 | CC-BY-4.0 |
| uci_forest_fires | `uci_forest_fires_01` | 1 | CC-BY-4.0 |
| uci_seoul_bike | `uci_seoul_bike_01` | 1 | CC-BY-4.0 |
| uci_wilt | `uci_wilt_01`, `uci_wilt_02` | 2 | CC-BY-4.0 |
| uci_wine | `uci_wine_01`, `uci_wine_02` | 2 | CC-BY-4.0 |
| vscode | `vscode_01`, `vscode_02`, `vscode_03`, `vscode_04`, `vscode_05` | 5 | MIT |

## 보존·실행·검증

기준/실행 HEAD는 `4610aa3caab047aab5dc50e53528e79cd73a4515`다. 당시 commit 전 [검사](inspect_unseen_candidates_20261026.py)·[판정 반영](publish_unseen_review_20261026.py)·[독립 검증](verify_unseen_review_20261026.py) source의 정확한 hash를 보존했다.

초기 추가 근거 다운로드는 제한 환경의 연결 거부로 중단됐고 실패 경로를 보존했다. 승인 범위의 재실행은 별도 `data/raw/real_unseen/review_evidence_20261026_02/`에 고정 source/license 4개와 획득 기록을 저장했다. 공개 Python 3.2 docs endpoint의 접근 불가와 Wilt 논문 page의 HTTP 403도 기록했다. pinned CPython LICENSE/source 및 출판사 issue metadata를 사용했으며, 접근하지 못한 문서를 읽었다고 기록하지 않았다.

[독립 검증](../data/results/real_unseen/real_candidate_review_20261026_01/verification.json)에서 원본 60개 full hash·새 판정/notice 연결·원래 schema·권리/개인정보 상태·새 draft·관계 ID·정확 중복 0개를 대조했다. 최초 검사 보호 파일 221개와 추가 source 근거를 포함한 226개가 유지됐다. 입력 bytes·출처/버전·기존 결과는 그대로이며, 새 inventory에서 검토 상태/시각과 NumPy 한 파일의 license 근거만 바뀌었다.

상세 원문 맥락은 Git 제외 `data/temp/unseen_content_review_20261026_01/`에 남겼다. 게시한 판정표에는 값의 복사 대신 원본 hash·분류·line/구조 근거를 남겼다. 검사/검증 숫자는 Python 실행으로 얻었고 실제 draft CLI 및 독립 검증은 종료 0이었다. 기존 단위 테스트/전체 suite와 연구 특징·압축 benchmark·pickle/예측/학습·memory 측정은 실행하지 않았다.

## 새 검토 산출물과 다음 작업

새 경로는 `data/results/real_unseen/real_candidate_review_20261026_01/`다.

- [후보별 판정과 근거](../data/results/real_unseen/real_candidate_review_20261026_01/candidate_review.json), [사용 조건/필수 notice·citation](../data/results/real_unseen/real_candidate_review_20261026_01/usage_requirements.json), [관계 기록](../data/results/real_unseen/real_candidate_review_20261026_01/relationships.json).
- [새 검토 inventory](../data/results/real_unseen/real_candidate_review_20261026_01/inventory.json), [검토 반영 draft](../data/results/real_unseen/real_candidate_review_20261026_01/draft/manifest.json), [요약](../data/results/real_unseen/real_candidate_review_20261026_01/review_summary.json), [추가 원출처 근거](../data/results/real_unseen/real_candidate_review_20261026_01/source_evidence.json).

과거 두 수집본의 `pending` inventory/draft와 보고서는 당시 기록으로 보존했다. 새 검토본도 최종 선정 0개이며 `evaluation_ready=false`, `unseen_overlap_audit=not_performed`다. manifest 도구의 `provenance_review=declared_metadata_only` 표시는 도구 자체의 검증 범위이고, 이번 파일별 source/내용 판단은 별도 검토 근거에 있다.

다음 단일 작업은 **기존 72개 검증/Pilot 1,008개 합성 입력의 재생성 근거를 확인하고, 이 후보들과의 전체 hash 겹침 감사를 구현·실행하는 것**이다. 결과와 제외 사유를 보존한 뒤 명시적 선정/실제 corpus 동결로 진행한다. 동결/후속 배포에서는 새 사용 조건과 notice hash를 다시 확인하고 함께 보존해야 한다. 후보 성능을 보며 원본을 바꾸지 않는다.
