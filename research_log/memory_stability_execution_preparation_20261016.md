# Memory 안정성 후속 검증 실측 준비안

작성 시작: 2026-10-16. 최종 점검: 2026-10-17. **준비 점검 완료 / 사용자 일정·전원 조건 확인 대기 / 새 attempt·실측 미실행.**

근거는 [사전 설계](memory_stability_validation_design.md), [runner](../src/memory_stability_validation.py),
[독립 audit](verify_memory_stability_validation.py), [분석기](analyze_memory_stability_validation.py)이다.
시작 구현 HEAD는 `a51907fe8d8c220b95502977a627cef51c21bfa7`이며 실제 작업 트리는 깨끗했다.
[준비 snapshot](memory_stability_preflight_20261016.json)에 관측 환경·소스 hash·기존 파일 보존 기준을 남겼다.
이 문서는 실행 절차와 미확정 조건을 정리하며 사전 설계·공식 config를 변경하지 않는다.

## 1. 완료한 준비 점검

2026-10-16 18:29경 KST의 읽기 전용 관측이다. 가용 메모리·배터리·디스크·프로세스 상태는 실행 직전 다시 확인한다.

| 항목 | 확인 결과 |
|---|---|
| Python | 저장소 `.venv\Scripts\python.exe`, 3.14.4, 64 bit, `-B` |
| OS·CPU | Windows-11-10.0.26300-SP0 / AMD64 / Intel64 Family 6 Model 170 Stepping 4 / 논리 CPU 18개 |
| 물리 메모리 총량 | 33,804,922,880 bytes. 가용량은 고정 조건이 아니며 snapshot에 당시 값만 기록 |
| 직접 의존성 | numpy 2.5.2, pandas 3.0.5, scikit-learn 1.9.0, matplotlib 3.11.1, zstandard 0.25.0. requirements와 모두 일치 |
| 의존성 정합성 | `.venv\Scripts\python.exe -B -m pip check` → `No broken requirements found.` |
| 고정 설정 | runner `_check_config()` 통과. 공식 3지표와 memory `validation_only` 유지 |
| 예정 계획 | runner의 메모리상 `build_plan()`과 audit의 독립 `fixed_plan()` 전체 내용 일치. 입력 생성·참조 준비·init·worker·codec은 호출 차단 |
| 예정 규모 | sample 84개 / run당 memory 반복 3,360개·timing 호출 3,360개 / 자식 job 3,696개 / 전체 자식 job 22,176개. 측정·성공 수가 아님 |
| 디스크 | Python 점검 당시 C: 여유 27,177,594,880 bytes. 필요한 최종 용량을 측정한 것은 아님 |
| 동시 연구 작업 | CIM으로 확인한 `python.exe`·`pythonw.exe` 목록이 비어 있었음. 다른 실행 파일·WSL·원격 작업이나 미래 실행 부재를 인증하지 않음 |
| 전원 | 활성 구성표 `균형 조정`, GUID `381b4222-f694-41f0-9685-ff5bb260df2e`. GetSystemPowerStatus의 ACLineStatus=0, 배터리 48% |
| 자동 절전 | AC 18,000초 / DC 180초. 최대 절전 AC 0초 / DC 57,600초. `powercfg /query` 출력의 설정값이며 실제 동작 관측은 아님 |

2026-10-17 11:09경 KST에 날짜 변경 후 재점검했다. 고정 환경·config·전원 구성표·절전 설정은 같았고,
AC는 여전히 미연결, 배터리는 23%, C: 여유는 24,375,877,632 bytes였으며 Python 프로세스 목록은 비어 있었다.
두 시점의 관측은 snapshot에 구분해 보존했다. 이 상태 역시 실측 직전의 상태를 보장하지 않는다.

환경 점검은 Python으로 수행했고 예정 수량·일정 계산도 Python으로 확인했다. 시스템 설정을 바꾸거나 프로세스를 종료하지 않았다.
전체 suite·전용 단위 테스트·측정 smoke test는 이번 문서 작업에서 재실행하지 않았다.
이전 구현 검증은 [진행 문서](../research_progress.md)의 각 실행 기록을 따른다.

## 2. 사용자 확인에 제시하는 일정안

**아래 날짜·시각은 제안이며 확정 일정이 아니다.** 사용자가 연속 세 날짜의 실행 가능 여부를 확인한 뒤 고정한다.
첫 run 실제 부모 시작 시각 `run_01/metadata.json:started_at_utc`가 `t0`이며, 예정 시각을 실제 시작 기록으로 대신하지 않는다.

| Run | 제안 날짜(KST) | 목표 시작 | 실제 허용 조건 |
|---|---|---|---|
| 1 | 2026-10-17 토 | 19:00 | 실제 시작을 `t0`로 기록 |
| 2 | 2026-10-17 토 | run 1 종료 +60분 | 종료 +30~90분, 같은 로컬 날짜 |
| 3 | 2026-10-18 일 | 19:00 | 실제 `t0+24시간±60분`, 다음 로컬 날짜 |
| 4 | 2026-10-18 일 | run 3 종료 +60분 | 종료 +30~90분, 같은 로컬 날짜 |
| 5 | 2026-10-19 월 | 19:00 | 실제 `t0+48시간±60분`, 연속된 셋째 로컬 날짜 |
| 6 | 2026-10-19 월 | run 5 종료 +60분 | 종료 +30~90분, 같은 로컬 날짜 |

Run 1이 정확히 19:00에 시작했다면 run 3·5의 허용 창은 각 날짜 18:00~20:00이다.
실제 시작이 다르면 실제 `t0`에서 창을 다시 계산한다. 둘째 run의 간격은 첫 run의 **시작이 아닌 종료** 기준이다.
새 전체 행렬의 run 소요 시간은 미측정이므로 고정 종료 시각이나 총 소요 시간을 약속하지 않는다.
자정을 넘으면 같은 날짜 조건을 충족할 수 없으므로 첫 run과 둘째 run을 마칠 수 있는 시간을 확보해야 한다.
자동 예약·자동 대기·백그라운드 실행은 준비하지 않았다. 각 run은 해당 시각에 수동 요청으로 실행한다.

## 3. 확정할 환경 조건

- **제안:** 동일 컴퓨터·가상환경·활성 전원 구성표를 유지하고, 실행 중 AC 전원을 연결한다. 현재 관측은 배터리 상태이므로 연결 가능 여부는 사용자 확인이 필요하다. Windows 설정의 실제 전원 모드도 별도로 확인해 사건 기록에 적는다. 활성 구성표 이름만으로 해당 모드를 추정하지 않는다.
- 실행 중 자동 절전·최대 절전·덮개 닫힘으로 중단되지 않는 조건을 마련한다. 현재 배터리 절전 설정은 3분이다. 설정을 바꿀 필요가 있다면 첫 실측 전에 결정·기록하고 세 날짜에 같은 조건을 유지한다. 이번 준비에서는 설정을 변경하지 않았다.
- 다른 연구 benchmark·학습·worker를 동시에 실행하지 않는다. 일반 활동, OS 업데이트, reboot와 기타 사건은 실제 있었던 내용을 매 run 기록한다. 지금의 빈 Python 목록을 미래의 `no_research_jobs_running=true` 확인으로 재사용하지 않는다.
- Python 실행 파일·버전·패키지·OS·architecture·CPU·물리 메모리 총량·설정·소스를 유지한다. 가용 메모리·부하는 run별 관측값이며 같은 값으로 맞추지 않는다. Reboot 자체를 사후 실패 기준으로 추가하지 않고 실제 사건을 기록한다.
- 이 준비 문서와 진행 기록을 먼저 local commit한다. **init 직전 작업 트리가 깨끗해야 한다. init 이후 같은 HEAD에서 여섯 run과 audit·분석을 마칠 때까지 코드·config·설계·문서를 수정하거나 commit하지 않는다.** Runner는 HEAD 변경과 attempt 폴더 밖의 변경을 거부한다. 실행 중 사건·진행은 attempt 안의 원시 metadata와 사건 파일에 남긴다.

AC 연결·중단 방지는 실행 운영안이며 기존 과학적 판정에 새로운 합격 임계값을 추가하는 것이 아니다.
날짜·환경 위반을 숨기거나 기준을 사후 완화하지 않으며 실패·중단 attempt도 보존한다.

## 4. 실행 직전 사건 JSON

각 run 직전에 여섯 필드를 실제 상황으로 채운 **새 파일**을 attempt 폴더 안에 만든다.
예정 경로는 `<study-dir>/operator_events_run_01.json`부터 `operator_events_run_06.json`까지이다.
기존 파일을 덮어쓰지 않는다. Attempt 밖에 untracked 사건 파일을 만들면 runner의 Git 검사에 걸릴 수 있다.

```json
{
  "power_mode": "실행 직전 실제 전원 모드·구성표와 AC 연결 여부 기록",
  "manual_reboot_since_previous_run": null,
  "concurrent_activity": "실제로 있었던 동시 활동; 없음을 확인했으면 none",
  "os_update_events": "실제 업데이트 사건; 없음을 확인했으면 none",
  "other_events": "기타 실제 사건; 없음을 확인했으면 none",
  "no_research_jobs_running": null
}
```

위 블록은 **미확인 양식**이며 실행용 사건 파일이 아니다. 두 null을 확인한 boolean으로 바꾸기 전에는 runner가 거부한다.
String 필드는 비어 있지 않은 실제 설명으로 바꾼다. `no_research_jobs_running`이 false이면 codec 시작 전에 중단된다.
첫 run은 이전 run이 없다는 점과 관련 reboot 정보를 `other_events`에 설명하고 실제 reboot 여부를 기록한다.
사건 JSON을 다음 run에 그대로 복사해 현재 사실로 사용하지 않는다. Metadata에는 각 run에 제출한 사건 내용이 보존된다.

## 5. 조건 확인 후 사용할 실행 절차

아래 명령은 사용 형식이며 이번 준비에서 실행하지 않았다. 저장소 루트의 동일 가상환경을 사용한다.

1. 사용자가 일정·전원·동시 연구 작업 중지 조건을 확인한다. 변경된 실제 환경을 읽기 전용으로 다시 점검하고 문서에 확정 내용을 남긴 뒤 commit한다.
2. `git status --short`가 비어 있는 실제 사용자 권한 환경에서 init한다. ID `attempt01`은 제안이며 자동 생성되는 UTC 시각과 결합한 새 폴더만 만든다.

```powershell
.venv\Scripts\python.exe -B -m src.memory_stability_validation init --attempt-id attempt01 --reason "User-confirmed memory stability schedule and execution conditions"
```

반환된 `study_dir`를 기록한다. Init은 고정 입력·계획을 준비하지만 연구 worker 실측을 시작하지 않는다.
기존 결과를 이어 쓰거나 경로를 바꾸어 덮어쓰지 않는다.

3. 각 run 직전 실제 환경·소스/HEAD·날짜 창·사건 파일을 확인하고 다음 명령을 한 번 실행한다. 아래 `<...>`는 실제 값으로 바꿀 자리이다.

```text
.venv\Scripts\python.exe -B -m src.memory_stability_validation run --study-dir <actual-study-dir> --events-file <actual-study-dir>/operator_events_run_01.json
```

같은 CLI가 다음 예정 run을 자동 선택하므로 번호를 건너뛰지 않는다. 다음 실행은 해당 run의 사건 파일을 사용한다.
**Runner는 적절한 시각까지 기다려 주지 않으며, 일정 위반을 기록한 채 측정을 진행할 수 있다.** `run` 호출 전에 창을 확인한다.
첫 다섯 run 뒤의 정상 coordinator 상태는 `awaiting_next_run`, 마지막은 `completed`이다.
종료 코드·실패 수·`recording_checks_passed`·`validity_issues`·소스 불변·종료 기록을 함께 확인한다.
이 검사는 독립 audit나 과학적 판정을 대신하지 않는다. Claim이 남거나 중단됐으면 임의 삭제·같은 run 재실행·중단 attempt 재개를 하지 않는다.

4. 여섯 run의 증거가 모두 준비되면 같은 HEAD에서 독립 audit와 분석을 수행한다. 출력은 존재하지 않는 경로만 사용한다.

```text
.venv\Scripts\python.exe -B -m research_log.verify_memory_stability_validation --experiment-dir <actual-study-dir> --output <actual-study-dir>/audit.json
.venv\Scripts\python.exe -B -m research_log.analyze_memory_stability_validation --experiment-dir <actual-study-dir> --output-dir <actual-study-dir>/candidate_analysis
```

미완료·실패·일정/환경 위반은 정상 결과나 부분 통과로 바꾸지 않는다. 재시도가 필요하면 사유와 사용자 확인을 남긴 새 attempt로 진행하고 이전 증거를 모두 보존한다.
최종 결과·audit·분석·진행 기록은 실측 단계가 끝난 후 별도 검증해 commit한다.

## 6. 남은 확인과 범위

사용자에게 제시한 일정안의 가능 여부, 같은 전원 조건과 AC 연결·절전 방지 가능 여부, 실제 Windows 전원 모드,
다른 연구 작업을 멈출 수 있는지가 미확정이다. 실제 per-run 사건 확인도 각 실행 직전에 남아 있다.
확인 전 새 attempt 생성·실측은 시작하지 않는다. 준비 완료를 조건 확정이나 실측 완료로 기록하지 않는다.

준비 검증에서는 Python으로 snapshot의 예정 수량·문서 링크·기존 파일 hash를 확인하고,
실행하지 않을 사건 양식의 여섯 필드와 null 거부를 runner에 대조했다. 일정 검사는 가상의 run 소요 10분을 넣어
제안 시작 창과 종료 후 간격이 맞는지만 확인했으며 실측 시간이나 소요 시간 추정으로 사용하지 않았다.
세 CLI의 `--help`로 명령 옵션도 확인했다.

공식 기준은 [프로토콜 v2](../research_protocol_v2.md)의 3지표이다. Memory는 `validation_only`, `score_inclusion=false`이며,
관측 조건을 만족해도 공식 채택·v3·새 label/model·새 Pilot 전환은 별도 작업이다.
