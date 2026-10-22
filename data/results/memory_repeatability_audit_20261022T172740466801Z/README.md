# 동일 환경·Run 2 교체 결과 독립 감사

판정: **저장 기록 일관성 감사 통과**. 이 결과는 memory 공식 채택이나 4지표 전환이 아니다.

| 구분 | 원시 행 | 실패 반복 | 정상 pair | 실패 pair |
|---|---:|---:|---:|---:|
| 현재 활성 여섯 슬롯 | 40320 | 0 | 2016 | 0 |
| 보관된 최초 여섯 run | 40320 | 3 | 2013 | 3 |

- `audit.json`: 실제 독립 감사 결과, 검증 범위, 파일·소스 hash와 해석 한계.
- `invocation.json`: 실제 CLI·실행 HEAD·테스트 명령과 결과·테스트 소스 hash.
- `stdout.json`, `stderr.txt`: 실제 CLI 출력. 종료 코드 0, stderr는 비어 있으며 stdout JSON은 보고서와 같다.

감사 입력은 `memory_repeatability_v1_20261019T124938284221Z_attempt02`와
`memory_run02_replacement_20261022T103143486097Z`다. 기존 입력 파일·manifest는 변경하지 않았다.
원래 실패 이력과 활성 결과를 함께 검사했으며 논리적 Run 2의 새 측정은 Run 6 뒤에 실행됐음을
유지한다. 원본의 실패 3건을 정상 성공으로 바꾸지 않았다. 새 Run 2에 기록된 metadata 저장
재시도 사건 6개는 저장 전용 정책으로 처리한 것이며 측정 job 재시도가 아니다.

재현 명령은 `invocation.json`을 참조한다. 보고서 출력은 기존 입력 두 경로 밖의 새 파일로
지정하며 부모 폴더를 먼저 만든다. 기존 보고서나 입력 경로 내부에는 저장할 수 없다.

전용 인위적 전체 행렬 fixture 24개 테스트를 통과한 코드로 실제 감사를 실행했다. 초기 코드 및
fixture 보완 뒤 최종 전용 테스트를 전체 통과했으며 전체 저장소 suite는 실행하지 않았다.
호출 당시 HEAD는 `f4dc8c7`이고 새 감사·테스트는 commit 전 추가 파일이었다. 실행한 감사와
순수 helper·관련 소스의 정확한 SHA-256 및 테스트 소스 hash를 남기고 결과와 함께 Git에 보존한다.

감사는 압축기·worker·교체 adapter·기존 3일 `audit()`를 실행하지 않는다. 순수 입력 재생성과
저장된 worker JSON·원시값에서의 독립 계산을 사용한다. 복원 flag와 압축 크기·hash는 저장
증거이며 실제 압축·복원을 새로 수행해 인증한 것은 아니다. Hash와 기록된 Git/환경/사건도
실제 실행이나 연속 환경을 독립 인증하지 않는다.

과거 metadata의 `pending` 또는 `independent_protocol_audit_performed=false`는 당시 checkpoint로
남겨 두었다. 현재 감사 판정은 이 새 보고서를 참조한다. 후보 score·변동·regret 분석과 memory
채택 판단은 다음 작업이며 공식 기준은 계속 3지표, memory는 `validation_only`다.
