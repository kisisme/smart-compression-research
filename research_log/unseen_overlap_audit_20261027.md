# 기존 합성 입력 재생성·후보 hash 겹침 감사 — 2026-10-27

상태: **기록된 합성 조건에 대한 재생성·정확 hash 감사 완료 / 실제 corpus 선정·동결·연구 평가는 미완료**.
시작/실행 HEAD는 `cb9cd9d23fc3e51cb517118cd3dae7cbd91fe12e`이며, [직전 후보 검토](unseen_candidate_review_20261026.md)의 승인 inventory를 사용했다.

## 실제 결과

저장된 [summary](../data/results/real_unseen/synthetic_overlap_20261027_01/summary.json)·[재생성 근거](../data/results/real_unseen/synthetic_overlap_20261027_01/reconstruction_evidence.json)를 Python으로 읽어 아래 표를 작성했다.

| 기존 실험 | 재생성 표본 | 당시 실행 commit | base seed | 기록된 생성 매개변수 |
|---|---:|---|---:|---|
| validation_72 | 72 | `e44fea992bb6c70330e3b4de235764be36bb0b5f` | 20260911 | 일치 |
| pilot_1008 | 1,008 | `4d2d637bea96a4a1ddbbedb2c077fd0474ca8c19` | 20260983 | 일치 |

- 합성 입력 1,080개 전체를 재생성했고 full SHA-256은 1,080개로 서로 다르다.
- 검토 후보 60개 전체와의 정확 bytes hash 중복은 **0건**이다. 비교별 일치 목록·제외 사유는 [candidate_overlap.json](../data/results/real_unseen/synthetic_overlap_20261027_01/candidate_overlap.json)에 있다. 겹침에 따른 이번 제외는 없다.
- 기존 결과·모델·후보/notice와 직전 검토 근거를 포함하는 보호 파일 246개가 실행 전후 및 독립 검증에서 그대로였다.
- 선정은 0개이며 corpus는 아직 동결하지 않았다. `evaluation_ready=false`다. 기존 승인 inventory/draft의 당시 `not_performed` 상태는 역사적 기록으로 보존했고 이번 별도 감사 근거를 연결한다.

## 재생성 근거와 실행 범위

당시 metadata의 clean Git commit과 원래 `samples.csv`·`compression_results.csv` hash를 먼저 대조했다.
두 commit의 generator·experiment runner·config 원문 및 Git blob/full SHA-256을 새 `historical_sources/`에 보존했다.
Generator와 runner는 현재 코드와 CRLF 차이를 제외한 내용이 같다. 원래 runner에서 실험 계획 함수만 분리해 실행하고,
기록된 sample ID·generator·seed·size 순서를 확인했다. 각 표본의 생성 매개변수도 실제 생성 반환값과 비교했다.
Generator는 당시 config snapshot을 읽으며, 모든 당시 config key/value가 현재 config에도 일치하는지 확인했다.
현재 config 전체는 memory/model 설정의 후속 추가로 과거와 다른 파일이다. 이를 같은 전체 config라고 기록하지 않았다.

당시/현재 Python은 모두 CPython 3.14.4이다. 기록 OS는 `Windows-11-10.0.26200-SP0`, 이번 OS는 `Windows-11-10.0.26300-SP0`로 build 차이가 있다.
생성기는 Python stdlib만 사용한다. 현재 `random.py` hash는 summary에 기록했으나 과거 stdlib hash는 없다.
과거 생성 input 원본·hash도 저장하지 않았으므로 **이번 해시는 기록된 조건으로 재생성한 bytes의 해시**다.
이를 당시 bytes의 독립 증명이나 의미상 유사성/익명성/원본 그룹 독립성의 증명으로 표현하지 않는다.
SHA-256 일치의 범위에서만 중복을 판정하고 알려진 원본 관계는 직전 검토 기록을 유지한다.

특징 추출·모델 로딩/예측·압축/해제 benchmark·재학습·memory 측정을 실행하지 않았다.
공식 3지표와 memory 참고 지표 방침을 유지한다. 이번 재생성 bytes는 메모리에서 순차 처리했고 원시 합성 파일을 새 학습 자료로 저장하지 않았다.

## 구현·검증

- [감사 도구](audit_unseen_overlap_20261027.py): 기존 출력 재사용 거부, 보호 파일 hash 확인, 당시 source/config snapshot, 재생성 매개변수/계획 일치, 전체 후보 비교, 실패/부분 index 보존.
- [전용 인위적 테스트](../tests/test_unseen_overlap_audit.py) 10개 통과. 실제 연구 표본과 구분한다. 정확 일치/불일치·다중 일치 보존·dirty/잘못된 commit·버전/계획/설정/매개변수/크기 불일치 거부·실패 보존/출력 재사용 거부를 확인했다.
- 최초 제한 권한 실행은 임시 폴더 접근 제한으로 오류가 있었고 실제 권한 재실행이 통과했다. 테스트 코드를 고쳐 통과시킨 것은 아니다. [실행 확인 기록](../data/results/real_unseen/synthetic_overlap_20261027_01/execution_checks.json)에 이를 함께 보존했다.
- [독립 저장 검증 도구](verify_unseen_overlap_20261027.py)가 index 수량·ID·full hash 형식·Git blob/고정 source·후보 현재 bytes·겹침 목록/집계·보호 파일·미선정 상태를 재확인했다. 결과는 [verification.json](../data/results/real_unseen/synthetic_overlap_20261027_01/verification.json)이다. 두 번째 전체 재생성이나 과거 원본 bytes 증명은 수행하지 않았다.
- 감사 실행 후 수치를 개선하기 위한 후보 교체·특징/점수/시간 관찰·가중치 변경은 하지 않았다. 후보 중복이 있었다면 일치 목록과 제외 근거를 보존하도록 구현했다.

실제 호출:

```powershell
.venv\Scripts\python.exe -B research_log/audit_unseen_overlap_20261027.py --output-dir data/results/real_unseen/synthetic_overlap_20261027_01
.venv\Scripts\python.exe -B research_log/verify_unseen_overlap_20261027.py
```

위 출력은 보존되므로 재실행 시 감사에는 새로운 출력 경로가 필요하다. 고정 verifier는 이번 보존 package 전용이며 기존 verification도 덮어쓰지 않는다.

## 다음 단일 작업

**후보의 명시적 선정과 실제 corpus 동결**. 검토 inventory/draft·이번 전체 overlap 감사·필수 notice/citation·후보 현재 hash를 다시 확인하고,
수집 metadata만으로 선정/제외 근거와 ID 목록을 보존한다. 기존 도구로 새 frozen manifest를 작성한 뒤 독립 hash 감사를 수행하고,
검토/재생성 감사의 한계와 notice/citation을 함께 고정한다. Generic manifest의 `declared_metadata_only`와 `evaluation_ready=false` 의미를 유지하며 별도 근거를 명시한다.
특징/예측/압축 전에 corpus와 관련 Git 근거를 보존한다. 평가 runner 구현과 실제 성능 평가는 후속 단위다.
