# 실제 파일 후보 manifest 도구 — 2026-10-26

`src/unseen_manifest.py`는 [unseen 사전 설계 v1](unseen_evaluation_design_v1.md)의
후보 목록 작성·검증·명시적 선정·동결·읽기 전용 감사를 구현한다.
표준 라이브러리만 사용하며 자료 다운로드·특징 추출·압축·모델 로딩/예측·학습을 호출하지 않는다.
이번에는 실제 corpus를 수집하지 않았다. 실행 검증에 사용한 파일은 전부 인위적 fixture다.

## 명령과 상태

프로젝트 루트에서 가상환경 Python으로 실행한다. 출력은 각각 존재하지 않는 새 폴더를 지정한다.
아래 corpus 경로는 향후 실제 수집용 예시이며 현재 존재하는 실제 데이터라는 뜻이 아니다.

```powershell
.\.venv\Scripts\python.exe -B -m src.unseen_manifest --help
.\.venv\Scripts\python.exe -B -m src.unseen_manifest draft --root data/raw/real_unseen/corpus_v1 --inventory inventory.json --output-dir data/results/real_unseen/corpus_v1/draft_001
.\.venv\Scripts\python.exe -B -m src.unseen_manifest freeze --draft-dir data/results/real_unseen/corpus_v1/draft_001 --selection selection.json --output-dir data/results/real_unseen/corpus_v1/manifest
.\.venv\Scripts\python.exe -B -m src.unseen_manifest audit --manifest-dir data/results/real_unseen/corpus_v1/manifest --expected-sha256 <freeze에서_보존한_64자리_SHA256>
```

| 명령/상태 | 계약 |
|---|---|
| `draft` | root의 실제 일반 파일을 읽어 크기·full SHA-256·후보 metadata·중복/검토 이슈를 저장. 빈 목록·수량 미달·검토 대기는 draft에 보존 가능 |
| `freeze` | 지정 draft의 hash에 연결된 명시적 ID 목록을 검증하고 새 `frozen` manifest 생성. 자동 후보 교체·수량 완화 없음 |
| `audit` | 별도로 보존한 기대 manifest hash가 필수. artifact·정책·선정·원본 파일을 재확인. 파일에 적힌 상태만 믿지 않음 |
| `publication_failed` | 새 출력에 남은 부분 파일·오류를 보존. manifest가 있더라도 실패 표시가 있으면 감사 거부 |

**`frozen`은 입력/선정 목록의 고정을 뜻한다.** 기존 합성 데이터와의 겹침 검사는 아직 없으며
모든 출력은 `unseen_overlap_audit=not_performed`, `evaluation_ready=false`다.
이 도구의 감사 성공을 실제 unseen 성능 평가·독립성·법적 권리 확인 완료로 해석하지 않는다.
형식/출처/권리/개인정보 검토는 선언된 metadata 계약을 확인하며 그 사실의 진위를 자동 판정하지 않는다.

`data_kind`는 `research_candidate` 또는 `test_fixture`를 명시한다. 인위적 fixture의
동결/감사가 성공해도 `test_fixture`를 유지한다. 실제 자료와 혼용하지 않는다.
명령 성공은 종료 0과 JSON, 계약/입출력 오류는 종료 1과 stderr다. 인자 오류는 argparse의 종료 2다.

## 입력 JSON

Inventory의 최상위 필드는 다음 네 개다. 후보가 아직 없으면 빈 목록의 draft를 만들 수 있다.

```json
{
  "inventory_version": 1,
  "corpus_id": "corpus_v1",
  "data_kind": "research_candidate",
  "candidates": []
}
```

각 후보에는 아래 metadata를 모두 작성한다. JSON의 null과 빈 문자열은 표시한 경우에 사용한다.

| 필드 | 의미/검증 |
|---|---|
| `candidate_id`, `origin_group_id` | ASCII 영문자로 시작하는 영문/숫자/underscore/hyphen ID, 최대 64자. 후보 ID 중복 거부 |
| `relative_path`, `format` | root 안의 `/` 구분 상대 경로, 형식 enum `text,csv,json,python,log,binary` |
| `source_locator`, `source_version` | 비어 있지 않은 원출처와 버전/고정 revision 근거 |
| `acquired_at_utc` | timezone이 UTC인 실제 수집 시각 |
| `license_id`, `license_evidence` | 검토 전 빈 문자열 가능. 선정 파일은 둘 다 근거 문자열 필요 |
| `rights_review_status`, `privacy_review_status` | `pending`, `approved`, `rejected`. 선정하려면 둘 다 approved |
| `reviewed_at_utc` | 검토 전 null 가능. 선정 파일은 UTC 검토 시각 필요 |
| `is_precompressed` | JSON boolean |
| `derivative_of` | 관련 후보 ID 또는 null. 알 수 없는 ID/순환 관계 거부 |
| `exclusion_reason` | 명시적 제외 사유 또는 빈 문자열. 사유가 있으면 선정 불가 |

`original_filename`, `original_size`, `input_sha256`는 선택적 선언 값이며 제공하면 실제 파일과 대조한다.
프로그램은 이 값과 `sample_id=uf_<full SHA-256>`, 중복 대표 ID·이슈·선정 상태를 직접 기록한다.
`selection_status`는 초안의 `candidate`/`excluded`, 동결의 `selected`/`not_selected`/`excluded`로 기록한다.
정확 중복은 `exact_duplicate_of:<ID>`, 유효하지만 명시적 선정 목록에서 빠진 후보는
`not_selected_in_explicit_selection` 사유를 남긴다. 원래의 명시적 제외 사유는 유지한다.
raw 입력에 임의의 특징·측정·점수·예측 필드나 위 선택 항목 외의 계산 필드를 추가하면 거부한다.

Selection JSON은 다음 형식이다. 실제 선정에는 60개의 서로 다른 알려진 후보 ID를 명시해야 한다.
아래 빈 목록은 구조 설명용이며 freeze에 통과하지 않는다.

```json
{
  "selection_version": 1,
  "corpus_id": "corpus_v1",
  "draft_manifest_sha256": "<draft 명령이 반환한 full SHA-256>",
  "candidate_ids": []
}
```

## 동결 조건과 보존

정확히 60개·여섯 형식 각 10개, 최소 12개 원본 그룹·그룹당 최대 5개·형식마다 최소 2개 그룹,
원본 16,384~1,048,576 bytes 및 검토 완료/근거·명시적 제외 없음·정확 중복 대표 규칙을 확인한다.
알려진 파생 관계와 정확 중복이 다른 원본 그룹으로 선언됐다면 수정 전까지 freeze를 거부한다.
모든 후보를 동일한 결정적 순서로 보존하고 선정 목록을 조용히 보충하거나 변경하지 않는다.

경로 탈출·절대/drive 경로·Windows 예약 이름·끝의 점/공백·symlink/junction/reparse point·
대소문자 별칭·동일 파일 hardlink 중복을 거부한다. 열린 handle의 실제 경로도 읽기/쓰기 전에 확인한다.
Windows 경로 확인은 [Microsoft의 GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)
계약을 사용한다. 네트워크 공유나 다른 OS의 모든 파일시스템을 검증한 것은 아니다.

후보·metadata·builder source가 읽기/게시 도중 바뀌면 정상 게시를 하지 않는다.
처음 구현의 Windows `stat`/`fstat` ctime 차이로 정상 파일을 변경으로 오판한 문제를 실제로 확인해 수정했다.
Windows에서는 두 API에 일관된 birth time을 파일 ID·크기·수정 시각과 함께 사용한다.
[Python 문서](https://docs.python.org/3.14/library/os.html#os.stat_result.st_birthtime_ns)도
Windows의 생성 시각에 `st_birthtime_ns`를 사용하도록 안내한다.
이 수정 뒤에도 변경/해시/동일 파일 검증을 유지하고 Windows 회귀 fixture로 확인했다.

출력은 원본 root·이전 draft 밖의 새 폴더에 배타적으로 게시한다. 원본 bytes를 복사/변형하지 않는다.
원래 inventory·selection·이전 draft bytes와 artifact hash, raw bytes 보존 `.gitattributes`를 저장하고
manifest를 마지막에 게시한다. 실패 시 부분 파일과 `publication_failed.json`을 보존하며 삭제/재시도하지 않는다.
Source byte hash가 같아야 draft→freeze→audit가 연결된다. 구현이 달라졌다면 과거 기록을 유지하고
새 draft를 만들거나 기록된 버전으로 과거 입력을 확인해야 한다.

## 최종 검증

[전용 테스트](../tests/test_unseen_manifest.py) 최종 23개가 **48.910초에 통과**했다.
인위적 파일의 전체 흐름·Unicode/공백 경로·중복/관계·수량/검토·정해진 hash·위험 경로/파일 변경·
저장 실패·source/metadata 변경·위조/손상·단일 파일 alias와 미선정 사유를 검증했다.
Fresh Python에서 연구/ML/codec/GUI 모듈 import를 차단한 채 import와 CLI help도 확인했다.
전체 저장소 suite는 실행하지 않았다.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_unseen_manifest.py -v
.\.venv\Scripts\python.exe -B tests/validate_unseen_manifest.py --record research_log/unseen_manifest_validation_20261026_final.json
```

[실제 CLI 검증 도구](../tests/validate_unseen_manifest.py)는 새 인위적 파일 경로에서 9개 명령을 실행했다.
help·draft·freeze·audit와 검토 대기 draft가 정상 종료했고 기존 출력·잘못된 digest·검토 대기 freeze·
손상 복사본 audit는 종료 1로 거부됐다. 원본 fixture bytes와 기존 연구 보호 파일 55개가 유지됐고
최종 source hash와 테스트 출력·원래 metadata 산출물은 [최종 JSON](unseen_manifest_validation_20261026_final.json)에 보존했다.
실제 파일은 `data/temp/unseen_manifest_validation_20261026T014612253392Z/`에 있다.
이 명령을 다시 실행하려면 새 record 경로를 지정해야 한다.

선정 상태 표기를 보강하기 전의 [최초 CLI 검증](unseen_manifest_validation_20261026.json)도 보존한다.
최종 소스의 검증 완료 근거와 구분하며 이전 기록을 덮어쓰지 않았다.
이번 동결 대상은 전부 `test_fixture`다. 실제 후보 수집·권리/그룹 검토·합성 데이터와의 겹침 검사·
실제 corpus 동결·연구 측정·모델 평가는 미완료다. Memory는 참고 지표로 유지한다.
GUI OS 점검도 여전히 node_repl의 Node 시작 오류로 미완료다.
