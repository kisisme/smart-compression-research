# 실제 파일 후보 1차 수집 보고서 — 2026-10-26

현재 상태는 **실제 원본 30개를 보존한 미선정 draft**다. 목표 60개·최소 12개 원본 그룹을 아직 충족하지 못한다. 권리/개인정보/파생 관계 검토·합성 데이터 겹침 검사·실제 corpus 동결·연구 평가는 미완료다. 이 수집을 모델 성능 결과나 평가 준비 완료로 해석하지 않는다.

## 보고서 범위와 진행 순서

이 보고서는 1차로 확보한 원본의 수량·출처·보존 상태와 남은 수집 조건을 정리한다. 최초 초안과 수집 근거는 `65deab0`에 보존돼 있으며, 이번에는 저장된 JSON을 Python으로 읽어 원본 그룹별 합계와 파일별 목록을 보강했다. 수집량과 검토/선정 완료량을 구분한다.

진행 순서는 **1차 수집 보고서 정리 → 부족한 형식의 추가 후보 30개 수집 → 전체 후보의 검토·선정 → 합성 겹침 확인·corpus 동결 → 평가 준비**다. 보고서 다음 작업은 추가 수집이다. 현재 30개의 권리·개인정보·파생 관계도 계속 검토해야 한다. “나머지 30개”는 현재 후보가 모두 최종 조건을 충족한다는 가정의 부족분이며, 검토에서 제외되는 후보가 생기면 대체 후보를 더 확보한다.

## 완료한 범위와 근거

- [사전 설계 v1](unseen_evaluation_design_v1.md)에 따라 성능을 보지 않고 출처·권리 맥락·원래 형식·크기·경로 metadata로 초기 후보를 정했다. 저장소 전체를 한 원본 그룹으로 묶고 그룹당 5개를 수집했다. 테스트/fixture·vendored Tempita·인공 좌표 격자/기준선 파일은 선정하지 않았다.
- [수집 계획](unseen_collection_plan_20261026.json)에 저장소별 고정 commit·원래 파일 경로·Git blob SHA-1·원래 크기를 기록했다. 다운로드 전에 이 계획을 저장했다. [출처 검토 기록](unseen_source_review_20261026.json)은 원본 역할·정확한 라이선스 근거·그룹 관계의 미확인 범위·미수집 로그 출처와 이유를 구분한다.
- [수집 스크립트](collect_unseen_candidates_20261026.py)는 HTTP 원본 바이트를 새 경로에 보존하고 재인코딩/개행 변환/절단/합성/연결을 하지 않았다. 수집한 Python 소스를 실행하거나 import하지 않았다. GitHub 연결은 바이너리 다운로드를 지원하지 않아 원본 저장에는 HTTPS 다운로드를 사용했다.
- 원본 경로: `data/raw/real_unseen/real_candidates_20261026_01/`. 후보 30개와 해당 고정 버전의 라이선스 원문 6개가 있으며 전부 Git 제외다. 원본과 notices는 로컬에 남기고 향후 자료를 배포한다면 함께 보존한다. `.shp`는 upstream의 완전한 개별 geometry 파일이며 sidecar를 합치거나 재생성하지 않았다.
- [후보 inventory](../data/results/real_unseen/real_candidates_20261026_01/inventory.json), [draft](../data/results/real_unseen/real_candidates_20261026_01/draft/manifest.json), [원시 획득 기록](../data/results/real_unseen/real_candidates_20261026_01/acquisition.json), [실제 CLI 출력](../data/results/real_unseen/real_candidates_20261026_01/draft_cli.json), [독립 검증](../data/results/real_unseen/real_candidates_20261026_01/verification.json)을 보존했다. 원본 크기·SHA-256·Git blob hash·고정 버전·다운로드 URL/UTC/HTTP 응답 metadata를 연결한다.

## Python으로 확인한 실제 수집 상태

| 형식 | 후보 | 원본 그룹 | 목표까지 부족 |
|---|---:|---:|---:|
| text | 10 | 2 | 0 |
| csv | 0 | 0 | 10 |
| json | 5 | 1 | 5 |
| python | 10 | 2 | 0 |
| log | 0 | 0 | 10 |
| binary | 5 | 1 | 5 |
| 전체 | 30 | 6 | 30 |

원본 그룹은 NumPy·pandas·Git·curl·Unicode CLDR JSON·Natural Earth 각 5개다. 전체 최소 그룹 수까지 6개가 더 필요하다. JSON과 binary는 형식별 최소 2개 원본 그룹도 미충족이다. 같은 저장소의 locale/폴더/지도 레이어를 나눠 그룹 수를 늘리지 않았다. 서로 다른 저장소라는 사실만으로 복제/파생 관계가 없다고 승인하지도 않았다.

후보 bytes 합계 1,730,855, 개별 크기 16,836~339,268 bytes이며 모두 사전 크기 범위 안이다. 후보 간 full SHA-256 정확 중복은 0개다. 이는 기존 합성 데이터와의 겹침 검사나 의미적 독립성 증명이 아니다. 모든 후보의 권리·개인정보 상태는 `pending`이고 선정 파일은 0개다.

## 원본 그룹별 수집 내역

| 원본 그룹 | 형식 | 후보 | 원본 bytes 합계 | 고정 commit |
|---|---|---:|---:|---|
| NumPy | python | 5 | 375,144 | `f9f1772ce010` |
| pandas | python | 5 | 215,199 | `180b19f1ab9b` |
| Git | text | 5 | 152,929 | `7e34d8174dcd` |
| curl | text | 5 | 184,386 | `bc677a8f16a5` |
| Unicode CLDR JSON | json | 5 | 180,789 | `91c267402229` |
| Natural Earth | binary | 5 | 622,408 | `ca96624a56bd` |

위 수량과 bytes 합계는 [inventory](../data/results/real_unseen/real_candidates_20261026_01/inventory.json)를 Python으로 읽어 계산했다. commit은 표에서 앞 12자리만 표시하며 [고정 수집 계획](unseen_collection_plan_20261026.json)에 전체 값을 보존한다. 각 저장소는 한 원본 그룹이다. 각 그룹의 후보 5개와 root license 원문을 보존했지만, 후보별 추가 권리·개인정보·파생 관계는 아직 승인하지 않았다.

## 출처와 남겨 둔 검토

원본 root license는 각각 [NumPy BSD](https://github.com/numpy/numpy/blob/f9f1772ce010001208475f751d19253469788410/LICENSE.txt), [pandas BSD](https://github.com/pandas-dev/pandas/blob/180b19f1ab9b2efcfe16baba967c9cde714f33f1/LICENSE), [Git GPL v2](https://github.com/git/git/blob/7e34d8174dcda3435d1404c9a30bef46afe6c13e/COPYING), [curl notice](https://github.com/curl/curl/blob/bc677a8f16a51e728136eff130509cfac57aad19/COPYING), [Unicode License v3](https://github.com/unicode-org/cldr-json/blob/91c267402229a59e3ef2774544f001bf959e8809/LICENSE), [Natural Earth public-domain 선언](https://github.com/nvkelso/natural-earth-vector/blob/ca96624a56bd078437bca8184e78163e5039ad19/LICENSE.md)에서 확인했다. 이 확인은 파일별 추가 notice·제3자 권리·개인정보 검토의 대체물이 아니다. 원문은 저장한 바이트의 Git blob hash까지 대조했다.

[Loghub](https://github.com/logpai/loghub)은 비식별화되지 않은 로그가 포함될 수 있음을 명시하므로 수집하지 않았다. MLCommons Training/Inference v4.1은 실제 결과 파일의 경로·크기 metadata만 확인했다. 적용되는 파일별 이용 조건과 개인정보 검토가 끝나지 않았으므로 다운로드하거나 quota에 세지 않았다. CSV 원출처도 이번 pool에는 추가하지 않았다. 후속 수집에서 조건을 충족하지 못하는 형식을 fixture·합성 파일로 채우거나 사후 기준을 완화하지 않는다.

[독립 검증 스크립트](verify_unseen_collection_20261026.py)는 저장 bytes/hash·inventory/draft snapshot·artifact hash·모든 원본의 Git 제외·원래 크기·정확 중복·형식 계약을 대조했다. Python은 실행 없는 AST 파싱, JSON은 파싱, shapefile은 magic/선언 길이/version을 확인했다. 텍스트의 email/private-IP/home-path/key-header 패턴은 값 대신 해당 line 번호만 기록했다. 이 패턴 검사는 전체 내용 검토가 아니며, flag 부재로 개인정보 승인을 하지 않았다. geometry 내용·외부 sidecar·문서의 예시 연락처/경로·출처 간 파생 관계도 후속 검토 대상이다.

## 실행·오류·보존 상태

실행 HEAD와 마지막 manifest 구현 commit은 `173bb47d00482684872103abc09a8d3ce6162003`이다. 획득/검증의 실제 스크립트 hash는 각 JSON에 기록했다. 기존 계획의 보호 파일 55개와 현재 도구/테스트/기준 문서의 집합 총 59개는 획득 전후와 독립 검증에서 동일했다. config·모델·연구 결과·기존 구현을 변경하지 않았다.

초기 제한 실행은 Pilot `baseline_models.json` 읽기에서 `PermissionError`로 중단돼 새 수집 경로를 만들지 못했다. 권한을 확보한 동일 명령은 다운로드 36건·오류 0건과 draft CLI 종료 0을 기록했다. 독립 검증의 최초 실행은 검증 스크립트가 상태명을 `review_pending`으로 잘못 기대해 중단됐다. 실제 도구 계약인 `selection_status=candidate`와 `review_not_approved`/`review_evidence_incomplete` issues를 확인하도록 수정했고, 재실행은 통과했다. 원본·inventory·draft를 이 오류에 맞춰 수정하지 않았다. [실행 중단/수정 기록](../data/results/real_unseen/real_candidates_20261026_01/run_notes.json)을 별도로 남긴다.

이번에는 기존 manifest 단위 테스트나 전체 suite를 재실행하지 않았다. 실제 다운로드·실제 draft CLI·독립 보존/형식 검증을 수행했다. 특징 추출·압축·예측·pickle 로딩·모델 재학습·memory 추가 측정·연구 실측을 하지 않았다. `evaluation_ready=false`, `unseen_overlap_audit=not_performed`이며 `freeze`/`audit` 연구 corpus 작업은 실행하지 않았다.

정확한 JSON/source hash가 checkout 개행 변환으로 달라지지 않도록 이번 획득 package와 관련 스크립트/계획에 한정한 `-text` 속성을 추가했다. 원본 bytes를 Git에 stage하지 않는다.

## 나머지 30개 수집 계획

| 형식 | 추가 후보 목표 | 필요한 새 원본 그룹 최소 수 |
|---|---:|---:|
| csv | 10 | 2 |
| log | 10 | 2 |
| json | 5 | 1 |
| binary | 5 | 1 |

현재 6개 그룹은 모두 그룹당 상한인 5개를 채웠다. 따라서 기존 저장소에서 파일을 더 가져와 부족분을 채우지 않는다. 전체 최소 12개 그룹과 추가 30개를 충족하려면 적어도 6개의 새 원본 그룹이 필요하다. 형식마다 최소 2개 그룹 조건도 확인한다. 같은 출처의 폴더·버전·mirror·파생본은 새 그룹으로 나누지 않는다.

추가 수집에서도 공개 원출처·이용 조건·원본 관계·개인정보를 먼저 검토하고, 원래 형식의 완전한 파일과 원래 크기 범위를 유지한다. 출처와 파일은 아직 확정하지 않았다. 특히 log는 실제 서비스/연구에서 발생한 원본인지와 공개 범위를 확인하며, 불명확한 자료를 수량 때문에 넣지 않는다. 검토가 끝나지 않은 후보는 승인 상태로 바꾸지 않는다.

이번 보고서 작성에서는 추가 파일을 다운로드하지 않았다. 이후에도 기존 30개·notices·inventory·draft는 보존하고 새 경로에 추가 수집과 제외 이유를 기록한다. 목록 통합 시 후보 전체의 크기·hash·정확 중복·그룹 상한·형식 quota를 다시 확인한다. 압축 성능이나 모델 예측을 보고 후보를 교체하지 않는다.

## 부록: 1차 후보 30개의 실제 파일 목록

| 후보 ID | upstream의 전체 파일 경로 | bytes | SHA-256 앞 12자리 |
|---|---|---:|---|
| `cldr_01` | `cldr-json/cldr-dates-full/main/en/dateFields.json` | 26,073 | `4fcaa5f74d74` |
| `cldr_02` | `cldr-json/cldr-dates-full/main/en/timeZoneNames.json` | 44,939 | `db04305a4bac` |
| `cldr_03` | `cldr-json/cldr-localenames-full/main/en/languages.json` | 20,815 | `a5960d2371bc` |
| `cldr_04` | `cldr-json/cldr-localenames-full/main/en/localeDisplayNames.json` | 17,470 | `29b07edcff9a` |
| `cldr_05` | `cldr-json/cldr-numbers-full/main/en/currencies.json` | 71,492 | `a6c41b28f403` |
| `curl_01` | `docs/CIPHERS-TLS12.md` | 38,498 | `78a9964545b3` |
| `curl_02` | `docs/ECH.md` | 19,110 | `4cc689059c06` |
| `curl_03` | `docs/FAQ.md` | 60,446 | `21789939dfb1` |
| `curl_04` | `docs/INSTALL-CMAKE.md` | 39,635 | `44fc74d7065e` |
| `curl_05` | `docs/INSTALL.md` | 26,697 | `c9440be6db41` |
| `git_01` | `Documentation/technical/api-trace2.adoc` | 44,494 | `a17b02c0be98` |
| `git_02` | `Documentation/technical/bundle-uri.adoc` | 26,750 | `c00e786e56cd` |
| `git_03` | `Documentation/technical/commit-graph.adoc` | 18,122 | `bf1e8aeeec83` |
| `git_04` | `Documentation/technical/hash-function-transition.adoc` | 36,339 | `5525e6da835a` |
| `git_05` | `Documentation/technical/large-object-promisors.adoc` | 27,224 | `b76baff2c662` |
| `natural_earth_01` | `110m_physical/ne_110m_coastline.shp` | 89,652 | `a1f8285d0e0a` |
| `natural_earth_02` | `110m_physical/ne_110m_geography_marine_polys.shp` | 339,268 | `e37b4d4e1009` |
| `natural_earth_03` | `110m_physical/ne_110m_land.shp` | 89,504 | `8689e6932b8e` |
| `natural_earth_04` | `110m_physical/ne_110m_ocean.shp` | 84,804 | `8006f16c5af4` |
| `natural_earth_05` | `110m_physical/ne_110m_rivers_lake_centerlines.shp` | 19,180 | `4a5d41e67457` |
| `numpy_01` | `numpy/__init__.py` | 25,251 | `da15041cceb1` |
| `numpy_02` | `numpy/_core/_add_newdocs.py` | 216,659 | `40fe45928ca5` |
| `numpy_03` | `numpy/_core/_internal.py` | 29,401 | `497f1ce325bc` |
| `numpy_04` | `numpy/_core/arrayprint.py` | 65,592 | `4e80a4f9d2ab` |
| `numpy_05` | `numpy/_core/defchararray.py` | 38,241 | `a174cd2354ef` |
| `pandas_01` | `pandas/_config/config.py` | 28,674 | `1b76a9475b70` |
| `pandas_02` | `pandas/_typing.py` | 16,836 | `98207bb411b9` |
| `pandas_03` | `pandas/core/_numba/extensions.py` | 18,513 | `b3ec1eeb3d57` |
| `pandas_04` | `pandas/core/algorithms.py` | 69,105 | `ac7b7dfd5d59` |
| `pandas_05` | `pandas/core/apply.py` | 82,071 | `a38b4dc76a2b` |

파일 목록은 후보 inventory에서 생성했다. 짧은 hash는 표의 식별 보조이며, 무결성 검증에는 inventory/draft의 전체 SHA-256을 사용한다. 각 후보의 공개 원문 URL·전체 commit·권리/개인정보 상태는 같은 후보 ID로 inventory에 연결돼 있다. 표의 모든 파일은 미선정 후보다.

## 다음 단일 작업

**부족 형식의 공개 원출처 검토·추가 초안 수집:** CSV·실제 log 및 별도 원본 그룹의 JSON/binary 후보를 검토한다. 현재 30개와 notices/draft는 보존하고 새 출력 경로를 사용한다. 형식별 quota·그룹 관계·권리/개인정보/내용 검토가 모두 충족될 때까지 실제 corpus 선정/동결을 하지 않는다. 합성 겹침 감사와 평가 runner/성능 평가는 이후 별도 작업이다.
