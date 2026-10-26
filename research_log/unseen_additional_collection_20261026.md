# 실제 파일 추가 30개 수집·통합 draft 보고서 — 2026-10-26

**추가 원본 30개를 확보해 총 60개 후보의 통합 draft를 생성하고 독립 검증했다.** 여섯 형식 각 10개·원본 그룹 총 18개라는 수량 조건은 충족했다. 모든 후보의 권리·개인정보 검토는 여전히 `pending`, 선정 파일은 0개이며 실제 평가용 corpus 동결과 연구 평가는 미완료다.

## 수집 결과

| 형식 | 1차 후보 | 추가 후보 | 통합 후보 | 통합 원본 그룹 |
|---|---:|---:|---:|---:|
| text | 10 | 0 | 10 | 2 |
| csv | 0 | 10 | 10 | 8 |
| json | 5 | 5 | 10 | 2 |
| python | 10 | 0 | 10 | 2 |
| log | 0 | 10 | 10 | 2 |
| binary | 5 | 5 | 10 | 2 |

[기존 1차 보고서](unseen_collection_20261026.md)의 30개와 라이선스·inventory·draft는 원래 경로에 그대로 남겼다. 새 원본 경로는 `data/raw/real_unseen/real_candidates_20261026_02/`, 새 근거 경로는 `data/results/real_unseen/real_candidates_20261026_02/`다. 새 경로에는 기존 원본/notice의 바이트 사본을 독립적인 일반 파일로 만들었으며 hardlink를 쓰지 않았다. 기존 후보의 내용·원래 출처/버전/획득 시각·검토 상태를 유지하고 통합 inventory의 상대 경로에만 `prior/`를 붙였다.

새 원본 그룹은 12개, 기존을 합쳐 18개다. 그룹당 최대 5개이며 형식별 원본 그룹은 text/Python/JSON/log/binary 각 2개, CSV 8개다. 이 수량은 저장 inventory를 Python으로 읽고 계산했다. source group은 저장소/원래 관측 collection에 대한 잠정 구분이며 통계적 독립성을 증명하지 않는다.

추가 후보 bytes 합계는 3,553,944, 통합 합계는 5,284,799 bytes다. 통합 개별 크기는 16,836~604,166 bytes이며 모두 사전 범위 안이다. 통합 후보 간 전체 SHA-256 정확 중복은 0개다. 기존 합성 bytes와의 겹침 확인은 아직 수행하지 않았다.

## 원출처와 선정 근거

| 새 원본 그룹 | 형식 | 추가 후보 | 보존한 이용 조건 근거 |
|---|---|---:|---|
| [vscode](https://github.com/microsoft/vscode/tree/e2fb9a1be30766bd1d1cfd2107fe3e88666b7f4e) | json | 5 | MIT; 파일별 승인 대기 |
| [google_fonts](https://github.com/google/fonts/tree/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0) | binary | 5 | OFL-1.1; 파일별 승인 대기 |
| [mlperf_inference](https://github.com/mlcommons/inference_results_v4.1/tree/198fc46799b3328b36ee4bcbdebfa2db5a8e6183) | log | 5 | Apache-2.0; 파일별 승인 대기 |
| [mlperf_training](https://github.com/mlcommons/training_results_v5.1/tree/441d65f4445cd59687466533fd9f55399136e7a4) | log | 5 | Apache-2.0; 파일별 승인 대기 |
| [uci_wine](https://archive.ics.uci.edu/dataset/186/wine+quality) | csv | 2 | CC-BY-4.0; 파일별 승인 대기 |
| [uci_forest_fires](https://archive.ics.uci.edu/dataset/162/forest+fires) | csv | 1 | CC-BY-4.0; 파일별 승인 대기 |
| [uci_bike_sharing](https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset) | csv | 1 | CC-BY-4.0; 파일별 승인 대기 |
| [uci_seoul_bike](https://archive.ics.uci.edu/dataset/560/seoul+bike+sharing+demand) | csv | 1 | CC-BY-4.0; 파일별 승인 대기 |
| [uci_abalone](https://archive.ics.uci.edu/dataset/1/abalone) | csv | 1 | CC-BY-4.0; 파일별 승인 대기 |
| [uci_automobile](https://archive.ics.uci.edu/dataset/10/automobile) | csv | 1 | CC-BY-4.0; 파일별 승인 대기 |
| [uci_wilt](https://archive.ics.uci.edu/dataset/285/wilt) | csv | 2 | CC-BY-4.0; 파일별 승인 대기 |
| [uci_biodegradation](https://archive.ics.uci.edu/dataset/254/qsar+biodegradation) | csv | 1 | CC-BY-4.0; 파일별 승인 대기 |

[고정 계획](unseen_additional_collection_plan_20261026.json)에 다운로드 전 Git commit·파일 경로·Git blob hash/크기 또는 UCI DOI·원본 archive/member 목록을 기록했다. 경로·공개 출처·이용 조건 맥락·원래 형식/크기·정확 hash만 사용했으며 특징·압축 성능·예측·정답 점수는 계산하거나 후보 선정에 사용하지 않았다.

- **JSON:** VS Code의 실제 배포 확장 설정 `package.json`이다. root MIT notice와 Copilot 폴더의 별도 MIT notice를 함께 보존했다. 테스트/예시 JSON을 수량에 넣지 않았다.
- **binary:** Google Fonts의 서로 다른 다섯 글꼴 family에서 배포하는 완전한 TrueType 파일이다. family별 SIL OFL 1.1 notice를 각각 보존했다. 저장소 전체를 한 그룹으로 묶었으며 설치·렌더링·변환하지 않았다.
- **log:** MLPerf Inference v4.1과 Training v5.1의 공개 `results` 실행 기록이다. 두 고정 저장소의 root Apache-2.0 notice를 보존했다. Training/Inference는 서로 다른 benchmark collection으로 잠정 구분하되, 같은 MLCommons 조직 및 AMD 제출 자료라는 관계를 남겼다. 버전·시스템/폴더를 독립 그룹으로 늘리지 않았다. 경로순으로 탐색하면서 발견한 동일 Git blob 사본은 다운로드 전에 제외하고 이유를 계획에 남겼다. 파일별 추가 권리·경로/식별자·파생 관계 검토는 남아 있다.
- **CSV:** UCI의 원래 관측 collection 8개다. 같은 호스팅 사이트라는 사실과 각 원래 자료의 출처·DOI를 모두 기록했다. Wine Quality의 red/white와 Wilt의 training/testing은 각각 같은 그룹이다. 이 두 Wilt 파일명의 train/test 의미는 원래 원격탐사 연구의 구분이며, 우리 연구에서는 둘 다 외부 후보 파일이다. 이번 시스템을 학습하거나 새 split을 만드는 데 사용하지 않았다.

UCI archive 8개의 전체 원본과 source page snapshot, CC BY 4.0 legalcode를 원본 경로에 함께 보존했다. 지정한 member 전체를 그대로 읽었으며 파일명·encoding·개행·값을 바꾸지 않았다. `abalone.data`·`imports-85.data`는 원래부터 쉼표 구분 표이고 확장자를 바꾸지 않았다. `biodeg.csv`와 Wine Quality는 세미콜론 구분을 그대로 유지했다. Seoul CSV도 원래 bytes/encoding을 보존했다. 설명/다른 형식/범위 밖 member는 archive 안에 보존하되 후보 수량에 넣지 않았다.

각 UCI 자료의 citation·DOI·이용 조건 URL은 [attributions](../data/results/real_unseen/real_candidates_20261026_02/attributions.json)에, root/family license 원문과 source page는 Git 제외 원본 경로에 있다. 사이트의 라이선스 표시는 파일별 추가 권리/개인정보 승인의 대체물이 아니다.

## 제외하거나 보류한 원출처

- [Air Quality](https://archive.ics.uci.edu/dataset/360/air+quality)는 같은 공식 페이지에 CC BY 4.0과 연구 전용/상업 제외 조건이 함께 있어 이번 수집에서 제외했다. 이 모순을 임의로 해석해 승인하지 않았다.
- [Algerian Forest Fires](https://archive.ics.uci.edu/dataset/547/algerian+forest+fires+dataset)는 표시된 전체 CSV 크기가 최소 범위보다 작아 선택하지 않았다. [Istanbul Stock Exchange](https://archive.ics.uci.edu/dataset/247/istanbul+stock+exchange)는 원래 XLSX이므로 CSV로 변환해 quota를 채우지 않았다.
- Loghub의 비식별화/개인정보 불확실성과 Training v4.1의 미해결 이용 조건 기록은 1차 보고서와 계획에 남겼다. Training v5.1의 명시적인 고정 root license를 확인했지만, Training의 여러 버전을 별도 원본 그룹으로 세지 않았다.
- UCI Bike Sharing의 `hour.csv` 등 미선택 member는 archive metadata에 남았다. 대상 파일을 자르거나 합성/fixture로 대체하지 않았다.

## 실제 실행과 독립 검증

[획득 스크립트](collect_additional_unseen_20261026.py)와 [독립 검증 스크립트](verify_additional_unseen_20261026.py)의 실제 실행 HEAD는 `edf2dcf7e0829ad29a28018332d2b7f9ac3cb20c`이다. 새 스크립트/계획은 당시 commit 전 상태였으며 정확한 source hash를 근거 JSON에 보존했다. 고정 upstream commit은 별도로 기록한다.

최초 제한 실행은 기존 Pilot 파일 읽기에서 `PermissionError`로 중단돼 새 출력 경로를 만들지 못했다. 권한을 확보한 동일 명령은 추가 후보 30개·통합 60개·획득 오류 0개와 draft CLI 종료 0을 기록했다. 독립 검증도 종료 0이었다. [실행 기록](../data/results/real_unseen/real_candidates_20261026_02/run_notes.json)에 최초 중단을 함께 남겼다.

[독립 검증 JSON](../data/results/real_unseen/real_candidates_20261026_02/verification.json)은 다음을 확인했다.

- 고정 Git tree 크기·blob hash와 저장 원본 full SHA-256 일치, source notice의 blob hash 일치.
- UCI 전체 archive hash·선택 member의 원본 bytes/CRC 일치, 원래 구분자/encoding의 읽기 전용 파싱.
- JSON 파싱, 로그의 MLLOG 식별자, TrueType header/표 경계 확인. 입력 파일을 실행하지 않았다.
- 기존 30개 후보 필드/bytes 및 1차 원본/근거·기존 연구 결과/모델/도구를 포함한 보호 파일 114개 불변.
- 통합 inventory/draft snapshot·artifact/source hash·후보 상태·수량·그룹 상한·형식별 최소 그룹·정확 중복 확인.
- 원본·notice·archive·source page 등 새 원본 경로의 일반 파일 92개가 모두 Git 제외임을 확인.

email/home-path/private-IP/key-header 패턴은 내용 전체 검토를 대신하지 않는다. 값 대신 해당 line 번호만 기록했으며, flag 부재나 파싱 통과를 개인정보 승인으로 쓰지 않았다. binary의 embedded name/copyright, 로그의 식별자/경로, 자료별 추가 notice·제3자 권리·출처 간 파생 관계 검토는 남아 있다.

연구 특징 추출·압축 benchmark·모델 unpickle/예측/학습·memory 측정·연구 평가는 실행하지 않았다. UCI ZIP의 원본 member 추출은 자료 획득이며 연구 압축 실측과 구분한다. 변경에 맞춰 실제 다운로드·draft CLI·독립 검증을 했으며 기존 단위 테스트/전체 suite는 재실행하지 않았다.

## 근거 파일

- [통합 inventory](../data/results/real_unseen/real_candidates_20261026_02/inventory.json), [추가 30개 inventory](../data/results/real_unseen/real_candidates_20261026_02/additional_inventory.json), [통합 draft](../data/results/real_unseen/real_candidates_20261026_02/draft/manifest.json).
- [원시 획득 기록과 archive member metadata](../data/results/real_unseen/real_candidates_20261026_02/acquisition.json), [실제 draft CLI 기록](../data/results/real_unseen/real_candidates_20261026_02/draft_cli.json), [보존 확인](../data/results/real_unseen/real_candidates_20261026_02/preservation_check.json).
- [원본별 attribution](../data/results/real_unseen/real_candidates_20261026_02/attributions.json), [독립 검증](../data/results/real_unseen/real_candidates_20261026_02/verification.json). 전체 SHA-256·실제 획득 UTC·HTTP 응답 metadata·Git/DOI 버전을 연결한다.

## 부록: 추가 후보 30개의 실제 파일 목록

| 후보 ID | 원래 파일 또는 archive member 경로 | bytes | SHA-256 앞 12자리 |
|---|---|---:|---|
| `google_fonts_01` | `ofl/abeezee/ABeeZee-Regular.ttf` | 46,016 | `2901c8df2566` |
| `google_fonts_02` | `ofl/abel/Abel-Regular.ttf` | 35,220 | `8809dcad2531` |
| `google_fonts_03` | `ofl/aboreto/Aboreto-Regular.ttf` | 48,356 | `fc702d535857` |
| `google_fonts_04` | `ofl/acme/Acme-Regular.ttf` | 23,292 | `76fdb582f546` |
| `google_fonts_05` | `ofl/actor/Actor-Regular.ttf` | 64,944 | `a7cf62975a5e` |
| `mlperf_inference_01` | `closed/AMD/results/1xMI300X_2xEPYC-9374F/llama2-70b-99.9/Offline/performance/run_1/mlperf_log_detail.txt` | 164,270 | `6c6dc8a88367` |
| `mlperf_inference_02` | `closed/AMD/results/1xMI300X_2xEPYC-9374F/llama2-70b-99.9/Server/performance/run_1/mlperf_log_detail.txt` | 172,709 | `cd70d9725e7e` |
| `mlperf_inference_03` | `closed/AMD/results/8xMI300X_2xEPYC-9374F/llama2-70b-99.9/Offline/performance/run_1/mlperf_log_detail.txt` | 166,974 | `ad99d73ccaac` |
| `mlperf_inference_04` | `closed/AMD/results/8xMI300X_2xEPYC-9374F/llama2-70b-99.9/Server/performance/run_1/mlperf_log_detail.txt` | 172,670 | `562b18fd8bb7` |
| `mlperf_inference_05` | `closed/AMD/results/8xMI300X_2xEPYC-TURIN/llama2-70b-99.9/Offline/performance/run_1/mlperf_log_detail.txt` | 167,313 | `0c0012d120f1` |
| `mlperf_training_01` | `AMD/results/MI350X_EPYC_9575F_pytorch/llama31_8b/result_0.txt` | 28,216 | `8fbe693da188` |
| `mlperf_training_02` | `AMD/results/MI350X_EPYC_9575F_pytorch/llama31_8b/result_1.txt` | 28,220 | `085ee9b85bd3` |
| `mlperf_training_03` | `AMD/results/MI350X_EPYC_9575F_pytorch/llama31_8b/result_2.txt` | 30,952 | `6cf79a1a18dc` |
| `mlperf_training_04` | `AMD/results/MI350X_EPYC_9575F_pytorch/llama31_8b/result_3.txt` | 29,579 | `e32ae0831d57` |
| `mlperf_training_05` | `AMD/results/MI350X_EPYC_9575F_pytorch/llama31_8b/result_4.txt` | 29,577 | `9bf2b3283bc8` |
| `uci_abalone_01` | `abalone.data` | 191,873 | `de37cdcdcaaa` |
| `uci_automobile_01` | `automobile/imports-85.data` | 25,936 | `125db8bd36a8` |
| `uci_bike_sharing_01` | `day.csv` | 57,569 | `a6bcf826782d` |
| `uci_biodegradation_01` | `biodeg.csv` | 155,987 | `c66ac1a23aba` |
| `uci_forest_fires_01` | `forestfires.csv` | 25,478 | `0d6586a1fa52` |
| `uci_seoul_bike_01` | `SeoulBikeData.csv` | 604,166 | `373339b71a89` |
| `uci_wilt_01` | `training.csv` | 249,070 | `2e439f523f91` |
| `uci_wilt_02` | `testing.csv` | 28,930 | `00b50577283a` |
| `uci_wine_01` | `winequality-red.csv` | 84,199 | `4a402cf041b0` |
| `uci_wine_02` | `winequality-white.csv` | 264,426 | `76c3f809815c` |
| `vscode_01` | `extensions/copilot/package.json` | 288,175 | `0006be001968` |
| `vscode_02` | `extensions/css-language-features/package.json` | 30,479 | `5069d45656a0` |
| `vscode_03` | `extensions/git/package.json` | 138,827 | `ef1349f9dc21` |
| `vscode_04` | `extensions/markdown-language-features/package.json` | 73,048 | `e0a23d4e66aa` |
| `vscode_05` | `extensions/typescript-language-features/package.json` | 127,473 | `601bcd52beb8` |

위 표는 Python이 추가 inventory에서 생성했다. 짧은 hash는 식별 보조이며 검증에는 inventory의 전체 SHA-256을 사용한다. 원래 source URL·license 근거·획득 시각은 동일 후보 ID로 연결돼 있다.

## 다음 단일 작업

**후보 60개의 파일별 권리·개인정보·원본/파생 관계 검토:** root license와 자동 패턴 확인만으로 승인하지 않고 실제 내용·notice·원출처 관계를 검토해 후보별 판단과 근거를 새 기록에 남긴다. 제외가 발생하면 원래 후보/이유를 보존하고, 같은 조건의 대체 원본을 추가한다.

수량 조건 충족을 최종 선정/평가 준비 완료로 기록하지 않는다. 후보는 전부 미선정이며 `evaluation_ready=false`, `unseen_overlap_audit=not_performed`다. 검토·명시적 선정 이후 합성 겹침 확인·실제 corpus 동결·평가 runner는 후속 단위로 진행한다.
