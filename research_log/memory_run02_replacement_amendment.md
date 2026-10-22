# Run 2 전체 재측정·활성 결과 교체 사전 변경 기록

작성일: 2026-10-22. 변경 ID: `memory_repeatability_run02_replacement_v1`.

## 사용자 지시와 범위

사용자가 절전과 겹친 Run 2 timeout에 관해 논의한 뒤 “전체 재측정으로 다시 하고,
덮어씌우는걸로 가자”라고 지시했다. 여기서 전체는 **Run 2 전체**이며 여섯 run 전체가 아니다.
새 측정 전에 이 지시와 교체 방식을 기록한다.

대상은 `data/results/memory_repeatability_v1_20261019T124938284221Z_attempt02`의
논리적 Run 2 슬롯이다. 원래 Run 2의 세 timeout은 Windows Modern Standby 사건과 겹친다.
절전 영향을 받은 운영 사건으로 전체 run을 재측정하는 이유이며, 모든 지연의 원인을 확정하거나
압축 성능에 유리한 결과만 고르는 근거가 아니다.

## 실행·교체 계약

- 원본 attempt 전체를 별도 replacement session의 `original_snapshot/`에 복사하고 모든 파일의
  SHA-256을 대조한다. 기존 Git 보존 commit `d0f801d`도 유지한다.
- 원래 입력·seed·압축 설정·반복 수·Run 2 job 순서·worker·측정 코드와 집계 정의를 유지한다.
  실패한 세 job만 보충하지 않고 memory와 timing을 모두 새로 측정한다.
- 기존 runner의 완료/재개 제한을 완화하지 않는다. 별도 adapter가 기존 순수 입력 준비,
  worker 호출·검증과 집계 함수를 재사용한다. Adapter·변경 기록의 hash와 실제 실행 HEAD를
  원래 측정 코드 commit과 구분해 남긴다. 기존 소스·공식 config는 수정하지 않는다.
- 새 측정은 `new_run_02/`에 저장한 뒤 전체 저장 무결성·참조 일치·복원 검증·양수 값·원시
  중앙값·단위 변환·phase memory 최댓값을 확인하고 활성 `run_02/`로 교체한다.
- 한 번만 시도한다. 실패나 절전 사건이 다시 관측되면 새 기록을 보존하고 자동으로 재측정하거나
  기존 활성 결과를 교체하지 않는다. 교체 실패도 원본 snapshot·새 원시값·transaction 기록을 남긴다.
- Run 1·3·4·5·6의 원시 파일과 metadata는 변경하지 않는다. 교체 직전과 직후 hash로 확인한다.
  활성 Run 2 및 연결된 현재 summary·coordinator·증거 manifest는 교체 사실을 명시하며 갱신한다.
  원래 보고서와 각 run의 과거 checkpoint는 snapshot에 보존한다.
- 최초 Run 2의 실제 수집 시각으로 소급하지 않는다. 논리적 슬롯은 2이나 실제 활성 측정 순서는
  `1 → 3 → 4 → 5 → 6 → replacement 2`다. 기존의 1~6 순서 계약을 원래 충족했다고 주장하지 않는다.
- 교체 후 상태는 `completed_after_run_replacement`다. 기존 attempt가 원래부터 정상 성공이었다고
  바꾸지 않는다. 활성 결과의 정상 여부와 원래 수집의 실패를 별도 필드로 기록한다.
  기존 3일 audit나 기존 순서 검사를 완화해 통과시키지 않는다. 변경 설계 전용 독립 audit는 후속 작업이다.

## 절전·환경 기록

측정 부모의 주 thread에서 `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`를
설정하고 종료 시 이전 thread 상태를 복원한다. 영구 전원 설정은 바꾸지 않는다. 이 요청은 자동
idle 절전 억제이며 덮개 닫기·사용자 수동 절전을 막는 보장이 아니다.
[Microsoft API 문서](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate).

실행 전후 전원·부팅 시각·프로세스 snapshot을 남긴다. System 채널의 절전/재개 사건은 새 측정
시간 범위로 조회하며 조회 실패도 성공으로 바꾸지 않는다. 다른 Python 작업이 있거나 기본 환경이
원래 plan과 다르면 시작하지 않는다. 사용자 게임·일반 활동·업데이트 유무는 새로 확인받지 않은
상태이며 프로세스 관측을 사용자 확인이나 연속 관측으로 표현하지 않는다.

Memory는 계속 `validation_only`, `score_inclusion=false`다. 이번 재측정·교체는 독립 감사,
후보 score/regret 분석, memory 공식 채택 또는 4지표 전환을 뜻하지 않는다.
