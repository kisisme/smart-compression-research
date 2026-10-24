# GUI 작업 실행 계층

`src/gui_jobs.py`는 [GUI 설계](gui_demo_design_v1.md)의 widget 없는 작업 계층이다.
Tk·모델 역직렬화·특징·codec·scoring 모듈을 부모 프로세스에서 import/실행하지 않고,
사용자가 선택한 기존 통합 CLI를 자식 프로세스에서 실행한다. GUI 화면은 아직 연결하지 않았다.

## API와 실행

- `JobRequest`: frozen 요청. `operation`은 `smart`, `decompress`, `compare`다. 입력·출력 경로를 절대 경로로 고정하고 Smart의 `mode`·`model_kind`를 명시한다. `model_dir`은 Smart에서만 사용할 수 있다.
- `build_command(request)`: `sys.executable -B <root>/main.py ...` 인자 tuple을 만든다. Shell 문자열을 만들지 않는다.
- `run_job(request, log_root=...)`: 동기 worker API. GUI thread에서는 직접 호출하지 않는다. 사전 검사·프로세스·응답·산출물 확인·실행 기록 후 `JobResult`를 반환한다.
- `JobRunner.submit(request)`: non-daemon thread에서 하나의 작업을 실행하고 job ID를 반환한다. 실행 중 중복 요청은 거부한다. 명시적으로 요청한 기능만 실행하며 자동 측정 재시도가 없다.
- `JobRunner.poll()`: terminal 결과를 nonblocking으로 꺼낸다. 결과가 없으면 `None`이다. GUI의 Tk `after()`에서 호출하고 현재 job ID를 확인한 뒤 화면에 적용한다.
- `JobRunner.busy`: 작업 실행 중 여부. `wait(timeout)`은 테스트/비-GUI 호출자용이며 GUI 이벤트 처리에서는 사용하지 않는다.

```python
from pathlib import Path
from src.gui_jobs import JobRequest, JobRunner

runner = JobRunner()
request = JobRequest("smart", Path("README.md"), Path("data/temp/gui_smart"),
                     mode="archive", model_kind="decision_tree")
active_job_id = runner.submit(request)
# 실제 화면에서는 after() callback에서 runner.poll()을 확인한다.
# 예측이나 측정을 수행하는 submit을 창 생성 시 자동 호출하지 않는다.
```

새 출력 경로·비어 있지 않은 파일/유효한 package·명시적 옵션을 확인한다. 자세한 모델·codec
검증은 기존 CLI가 수행한다. 모델 파일과 summary는 snapshot을 위한 bytes/hash만 읽으며
부모에서 pickle을 역직렬화하지 않는다. `cwd`는 프로젝트 root, `shell=False`, stdout/stderr는
캡처하고 `PYTHONIOENCODING=utf-8`을 전달한다. Windows 자식 콘솔은 `CREATE_NO_WINDOW`로 숨긴다.

## 결과 판정

| `JobResult.status` | 의미와 화면에서의 사용 |
|---|---|
| `succeeded` | 종료 0·정상 검증 응답·일치하는 산출물·입력/모델/설정/source 불변을 확인. 이 상태만 정상 완료/추천으로 표시 |
| `partial` | 종료 1의 유효한 실패 Compare 보고서. 진단 행을 보존하며 정상 선택 없음 |
| `invalidated` | 종료 1의 무효화 Compare 보고서. 정상 선택 없음 |
| `failed` | 사전 검사·프로세스 시작·비정상 종료/작업 실패. 기존 성공 산출물을 새 성공으로 읽지 않음 |
| `inconclusive` | 성공 종료와 응답/파일이 맞지 않거나 응답을 해석할 수 없음, source 변경 또는 publication 실패. 정상 결과 데이터 없음 |

Smart는 요청의 원본 hash·크기·mode·모델/summary hash·config hash, manifest/응답의
검증·선택·confidence 일치와 실제 payload 크기/hash를 확인한다. 복원은 입력 package의
manifest/payload snapshot과 응답·복원 파일 크기/hash를 대조한다. 원본 경로를 따라 읽지 않는다.
Compare는 stdout/보고서·artifact hash·검증 상태·mode별 선택/점수의 일관성 및 publication
실패 표시를 확인한다. 측정 중앙값이나 연구 점수를 새로 계산하는 독립 audit는 아니다.

`data`는 정상 Smart manifest, 복원 응답, 또는 확인한 Compare 보고서다. Partial/invalidated의
선택은 비어 있어야 하고, failed/inconclusive에는 정상 표시용 data를 반환하지 않는다.
`return_code`, stdout/stderr 원문 bytes와 `message`는 진단용으로 유지한다. GUI는 raw stdout의
성공 문구만 보고 status를 덮어쓰면 안 된다. stderr 경고가 있어도 정상 파일/응답 검증과는 구분한다.

## 기록과 중복/저장 오류

기본 로그는 Git 제외 경로 `data/temp/gui_sessions/<job-id>/job.json`에 배타적으로 생성한다.
요청·명령·작업/종료 상태·UTC 시각·입력/모델/source snapshot·결과·stdout/stderr를 보존한다.
텍스트 표시에 UTF-8 replacement가 사용돼도 원래 bytes는 base64로 함께 보존한다.
전체 환경 변수를 저장하지 않는다. 입력 package나 backend 출력 아래의 로그 저장은 거부한다.

Backend 파일 처리와 GUI 로그 저장을 별도로 판정한다. 정상 파일을 만든 뒤 로그 저장만 실패하면
`status=succeeded`를 유지하고 `log_path=None`, `log_error`로 경고한다. 가능한 부분 로그는 지우지
않고, backend를 재시도하거나 산출물을 삭제하지 않는다. 기존 session ID 충돌 때도 이전 로그를
덮어쓰지 않는다. 예상하지 못한 worker 예외는 busy를 해제하고 실패 결과로 queue에 전달한다.

취소·백분율·실시간 codec 진행·Tk 화면·Demo 예측 대조는 이 계층에서 제공하지 않는다.
화면은 후속 구현에서 이 API와 실제 backend 상태를 사용한다. Memory는 계속 참고 지표이며
새 측정·4지표 score·새 모델 학습을 수행하지 않는다.

## 검증 — 2026-10-24

시작 HEAD는 설계 보존 commit `8a8d3c8`이다. 전용 테스트
`.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_gui_jobs.py -v`의 최종 18개가
3.128초에 통과했다. 인위적인 payload·모델 bytes·응답·CSV fixture는 GUI 계약 검사용이며
연구 측정이나 실제 codec 결과가 아니다. 실제 codec 실행은 별도 CLI 연결 검증으로 확인했다.

요청 불변·인자/UTF-8/숨긴 프로세스·사전 차단·잘못된 JSON/검증/산출물·입력/모델/source 변경·
정상/부분/무효 결과·로그 저장/동기화/ID 충돌·단일 non-daemon worker·중복 거부·예외 후
busy 해제·job ID/queue를 검증했다. Fresh Python에서는 GUI/ML/codec/scoring 모듈의 import를
차단한 채 계층 import와 순수 요청 구성이 성공했다. 전체 저장소 suite는 실행하지 않았다.

실제 JobRunner를 통해 저장된 두 Pilot 모델 × 세 mode의 Smart 압축→복원 여섯 건,
Compare 한 건, 기존 출력 차단 한 건을 실행했다. 총 14개 요청 중 정상 자식 작업 13개와
자식 프로세스 시작 전 실패 1개를 확인했다. 모든 복원 bytes가 원본과 일치했고 각 queue 결과와
새 로그가 일치했다. Compare 원시 반복 40개·집계 4개·mode 정답 3개를 Python으로 재검증했다.
입력·모델·설정·구현 등 보호 파일 38개의 SHA-256 불변도 확인했다.

실제 파일과 원래 실행 기록은 Git 제외 경로
`data/temp/gui_jobs_validation_20261024T034613427419Z/`에 보존했다.
[실제 결과·명령·원시 비교 산출물·보호 hash·테스트 기록](gui_jobs_validation_20261024.json)을
별도로 Git 보존한다. 새 계층은 실제 실행 당시 commit 전 상태였으며 정확한 소스 hash와
최종 구현의 일치를 확인했다. 이는 worker/CLI 동작 검증이며 GUI 창·UI 응답성·모델 성능·
새 Pilot의 검증 완료를 뜻하지 않는다.
