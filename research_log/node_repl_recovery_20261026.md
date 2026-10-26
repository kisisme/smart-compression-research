# node_repl 초기화 오류 진단·부분 복구 — 2026-10-26

상태: **임시 폴더 복구 완료 / 현재 MCP 연결 재시작·정상 동작 재검증 대기**.
프로젝트 GUI 오류 수정이나 연구 실험이 아니라, Codex의 로컬 도구 실행 환경 진단이다.
시작 HEAD는 `d474f54`다. [진단 근거 JSON](node_repl_recovery_20261026.json)에
분리된 프로세스의 원래 응답과 테스트 프로그램 원문을 보존한다.

## 확인한 사실

1. `@oai/sky`를 import하지 않는 `nodeRepl.write(...)`도 현재 연결에서
   `failed to write kernel assets: 지정된 경로를 찾을 수 없습니다. (os error 3)`로 실패했다.
   GUI·압축·특징·모델 호출 이전에 실패한다.
2. 현재 설정의 실행 파일/모듈 경로는 존재했다. 같은 설정을 새 MCP 프로세스에서 실행하면
   기본 TEMP와 새 workspace TEMP에서 모두 최소 JavaScript가 정상 동작했다.
3. 요청 전후 CPU 시간을 대조해 실패 요청을 처리하는 `node_repl.exe` PID 37600을 식별했다.
   이 프로세스는 `a9ba6825a525118c`의 구 runtime을 사용했다. 현재 설정은
   `1fb7137c46617d50` runtime을 가리킨다. 구 runtime도 새 프로세스에서는 동작했다.
4. 해당 프로세스에서 임시 경로 문자열만 확인했으며
   `C:\Users\s0109\AppData\Local\Temp\.tmpqycGtw`가 없는 것을 확인했다.
   전체 메모리 덤프를 저장하지 않았고 인증 값·다른 앱의 환경을 출력하지 않았다.
5. 별도 새 테스트 프로세스가 만든 빈 `.tmp*` 폴더만 제거하면 원래 오류가 재현됐다.
   그 빈 폴더를 다시 만들면 같은 테스트 프로세스가 `isolated_temp_recovery_ok`를 반환했다.
   테스트 파일은 연구 데이터가 아니다.
6. 실제 누락된 `.tmpqycGtw`에 빈 폴더만 생성했다. 기존 파일/설정은 덮어쓰지 않았다.
   현재 연결이 `kernel.js` 등 assets를 생성하면서 원래 단계를 통과했고,
   다음 오류는 `failed to start Node runtime: ... (os error 3)`로 바뀌었다.

임시 폴더가 사라진 행위자·시각은 확인하지 않았다. 절전·Windows 정리·앱 updater 중
어느 하나의 탓이라고 확정하지 않는다.

## 남아 있는 실행 경로 불일치

현재 프로세스의 `CODEX_CLI_PATH`는 존재하지 않는
`.../OpenAI/Codex/bin/9614f1d9b40d9c4f/codex.exe`를 가리킨다.
디스크의 현재 MCP 설정은 존재하는 `.../bin/2993767bd1dfb009/codex.exe`를 가리킨다.
현재 프로세스의 Node 실행 파일과 작업 디렉터리는 존재했다.

이 stale 프로세스의 경로 불일치를 제거하려면 현재 설정으로 연결을 다시 시작해야 한다.
다만 별도 MCP의 단순 JavaScript는 `CODEX_CLI_PATH`만 없는 경로로 바꿔도 동작했다.
따라서 그 단순 테스트를 현재 세션의 sandbox 실행과 동일하다고 취급하거나,
CLI 경로 하나가 다음 오류의 유일한 원인이라고 확정하지 않는다. 재시작 후 현재 연결을 검증해야 한다.

구버전 hash 디렉터리에 새 바이너리를 복사하거나 junction으로 위장하지 않았다.
프로세스 메모리·인증·권한·sandbox·MCP 설정을 수정하지 않았고 실행 중인 앱/daemon을 강제 종료하지 않았다.

## 재시작과 검증

[공식 MCP 안내](https://learn.chatgpt.com/docs/extend/mcp)는 desktop의
Settings → MCP servers와 서버 Restart를 설명한다.
사용자에게 `node_repl` 서버 Restart를 요청했다. 현재 설정의 경로는 유효하므로 값을 임의 교체하지 않는다.

앱 전체 종료 없이 처리하기 위해 [공식 app-server API](https://learn.chatgpt.com/docs/app-server)의
`config/mcpServer/reload`도 검토했다. 설치된 CLI로 스키마를 생성해 인자를 확인했지만,
`app-server proxy`의 `initialize`가 timeout됐다. 이후 reload 메서드는 전송되지 않았으며
설정 재로딩 성공으로 기록하지 않는다.

Codex 자체 UI의 Restart 버튼은 자동 조작하지 않는다. 적용한
[computer-use SKILL.md](C:/Users/s0109/.codex/plugins/cache/openai-bundled/computer-use/26.1021.31345/skills/computer-use/SKILL.md)의
[연결 지침](C:/Users/s0109/.codex/plugins/cache/openai-bundled/computer-use/26.1021.31345/docs/guidance.md)은
“Do not automate the ChatGPT desktop app UI”라고 금지한다. 사용자에게 필요한 조작과 이유를 알렸다.

재시작 완료 뒤 같은 연결에서 다음 순서로 확인한다.

1. 최소 JavaScript가 성공하는지 확인하고 오류 단계가 다시 나타나면 원래 응답을 보존한다.
2. 문서에 따른 `@oai/sky` 초기화와 Windows 창 조회를 확인한다.
3. 이 연결 검증을 통과한 뒤 남아 있는 GUI OS 입력·선택창·스크린샷 QA를 진행한다.

현재는 이 재시작/현재 연결 확인과 GUI QA를 완료하지 않았다. 분리 프로세스 성공을
현재 연결 또는 Windows 화면 자동화 성공으로 바꾸어 기록하지 않는다.
이번에는 연구 코드·모델·공식 config·기존 실험 결과를 수정하거나 새 연구 측정·학습·단위 테스트를 실행하지 않았다.
