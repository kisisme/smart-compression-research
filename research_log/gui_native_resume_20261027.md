# GUI 중단 작업 재개·현재 캡처 문제 — 2026-10-27

상태: **기존 Node 초기화 오류는 현재 미재현 / GUI 실제 입력·시각 QA는 미완료**.
시작 HEAD는 `684b2bc731af8c12b97f562821b67360b75912be`다. [이번 진단 JSON](gui_native_resume_20261027.json)을 보존한다.

사용자 요청에 따라 완료하지 못한 작업을 우선 확인했다. 이전 Run 2 timeout은 전체 재측정/교체·독립 감사가 완료된 기록이고,
기존 GUI callback 검증의 최초 timeout도 새 경로의 완료 검증으로 이어졌다. Memory 추가 구현은 사용자가 선택한 보류이므로 자동 재개하지 않았다.
마지막 합성 겹침 감사의 제한 권한 테스트 오류도 실제 권한 재실행·독립 저장 검증이 완료돼 열린 오류로 보지 않았다.
현재 남아 있는 중단 작업은 GUI의 OS 입력·선택창·스크린샷/DPI 확인이었다.

현재 연결에서 최소 JavaScript와 `@oai/sky` import·Windows 창 조회·accessibility 조회가 성공했다.
이전 `kernel assets`/Node 시작 오류는 이번에 재현되지 않았다. 누가/언제 재시작했는지 또는 영구 원인이 해결됐는지는 확인하지 않았다.
프로젝트 GUI를 실제 실행하고 [읽기 전용 관찰 도구](../tests/observe_gui_native.py)로 초기 상태·Tk 버전/배율·geometry를 기록했다.
이 도구는 GUI callback·입력값·모델/압축을 자동 실행하지 않는다. 전체 input은 README 사본이고 실제 unseen 후보와 구분한다.

검증용 긴 폴더 이름이 공백으로 끝나 최초 launch 시도가 실패했다. Console 재실행에서 `FileNotFoundError`를 확인했고,
검증용 이름에 마지막 단어를 붙여 끝 공백을 없앤 다음 새 경로에서 GUI가 매핑됐다. 기존 시도 디렉터리는 보존했다.
이는 새 관찰 도구의 fixture 구성 오류였으며 제품 GUI나 연구 생성기를 바꾼 것은 아니다.

새 문제는 `get_window_state`가 GUI의 window/app/title과 accessibility tree를 반환하면서도 screenshot에 PyCharm을 보여 준다는 점이다.
대상 창 활성화와 창 목록 재조회/재선택 후 한 차례 재시도도 같았다. 화면이 GUI임을 확인하지 못했으므로 좌표나 무명 accessibility element를 추측해 클릭하지 않았다.
캡처/API·foreground·DPI·권한 가운데 무엇이 원인인지 확정하지 않으며 다른 캡처/입력 수단으로 우회하지 않았다.
잘못된 앱이 나온 screenshot payload는 저장소에 저장하지 않았고 반환 metadata와 관찰 판단만 남겼다.

[computer-use SKILL](C:/Users/s0109/.codex/plugins/cache/openai-bundled/computer-use/26.1021.31345/skills/computer-use/SKILL.md)이 연결한
[guidance](C:/Users/s0109/.codex/plugins/cache/openai-bundled/computer-use/26.1021.31345/docs/guidance.md)의 복구 지침은
“Refresh the app/window selection and retry once; report the exact error if recovery fails.”라고 명시한다.
따라서 현재 사용자에게 GUI를 직접 앞으로 가져온 뒤 보이는지 확인을 요청했고 추가 입력은 중단했다.
ChatGPT 자체 UI 자동 조작도 같은 지침상 금지돼 있다. MCP 재시작이 필요할 경우 공식 OpenAI 문서의
[Settings → MCP servers → Restart](https://learn.chatgpt.com/docs/extend/mcp) 경로를 사용자가 직접 수행해야 한다.
현재 증상에 Restart가 효과 있다고 검증하거나 반드시 재시작해야 한다고 단정하지 않았다.

현재 observer에서 연구 자식 작업은 0개이고, 보호 파일 249개는 일치한다.
새 observer는 GUI를 열고 이벤트를 처리했지만 native 클릭·파일/폴더 선택창·한국어/긴 경로의 실제 표시·화면 배치 검증은 하지 못했다.
스크린샷과 현재 창이 일치하는 것을 확인한 뒤에만 실제 입력 검증을 재개한다. 마지막 새 GUI 창은 사용자 확인을 위해 열어 두었으며 실행 중 압축 작업은 없다.
기존 자동 테스트를 이번에 다시 실행하지 않았고 새 테스트 통과나 GUI 전체 검증 완료를 주장하지 않는다.
후보 선정/동결은 이번에 진행하지 않았다. 이 중단 작업의 화면 확인이 가능해지면 먼저 마친 뒤 데이터셋 동결을 이어간다.

## 후속 복구 시도 — 2026-10-27

사용자가 남은 문제 해결을 다시 요청해 현재 연결에서 재검증했다. 시작 HEAD는 `da4f87796aa644507f4c4a038c1577b101efb570`이며,
원래 진단 JSON은 변경하지 않고 [추가 복구 근거](gui_capture_retry_20261027.json)를 새로 보존했다.
현재 창을 새로 선택한 뒤 accessibility가 제공한 공식 `Raise` 동작을 호출했으나 screenshot은 여전히 PyCharm이었다.
JavaScript 커널을 reset하고 Sky를 다시 import한 새 연결에서도 같은 증상이었다. JavaScript 커널 reset은 MCP 서버 Restart와 다르다.

읽기 전용 프로세스 확인에서 GUI는 `Responding=True`였고 조회된 Node REPL과 같은 Windows 세션에 있었다.
이는 창이 사용자에게 보이거나 실제 버튼 입력이 가능하다는 증명은 아니며, GUI 정지나 별도 세션이 원인이라는 근거도 얻지 못했다.
근본 원인은 여전히 미확인이다. 사용자에게 실제 GUI 표시/foreground를 확인 요청했고 캡처가 맞지 않는 상태에서 추가 입력은 보내지 않았다.
현재 원래 보호 파일 249개의 hash가 일치하고 제품 코드·모델·설정·기존 결과는 바꾸지 않았다.
이번에도 native QA·선택창·시각 확인·테스트 suite·실제 데이터셋 동결을 완료했다고 기록하지 않는다.

## 사용자 표시 확인·연결 재로딩 시도와 재개 경로

사용자는 GUI가 보이며 PyCharm 가림 가능성이 있다고 알려 주었다. 새 창 선택/활성화와 대기 뒤 재캡처도 PyCharm을 보여 주었다.
최대화 입력은 도구의 `user input was detected in this window; call get_window_state before continuing` 응답으로 차단됐다.
그 뒤 상태를 새로 읽고 한 차례 재시도해도 같았으며 실제 최대화가 실행됐다고 기록하지 않는다. 사용자의 ‘오키’만으로 실제 최소화 완료를 단정하지 않는다.

창 가림만 반복 점검하지 않고 공식 OpenAI 문서의 [app-server MCP reload](https://learn.chatgpt.com/docs/app-server)를 확인했다.
설치 CLI `0.163.0`의 schema를 새 임시 경로에 생성해 `config/mcpServer/reload`의 null params와 초기화/현재 thread 확인 인자를 검토했다.
현재 thread 연결임을 확인한 경우에만 reload를 요청하도록 검사 프로그램을 작성했다. 현재 설치된 CLI의 로컬 `app-server proxy`는
`initialize did not respond`로 실패했으므로 **재로딩 요청 자체를 보내지 않았다**. 새 proxy client만 정리했고 기존 daemon/앱·MCP 설정을 변경하거나 종료하지 않았다.
[새 연결 근거](gui_connection_handoff_20261027.json)에 실제 probe 결과·실행 프로그램·schema hash를 보존한다.
기존 보호 파일 249개의 hash가 그대로였으며 모델·공식 config·후보/결과를 변경하지 않았다. 이번에는 연구 실행·학습·추가 테스트 suite를 수행하지 않았다.

현재 연결 안에서 캡처 정상화를 확인하지 못했다. 설치된 `codex resume --help`에서 대화 선택과 `--no-daemon`의
“Run without the shared background server, even if it is already running” 의미를 직접 확인했다.
사용자가 현재 Codex를 정상 종료한 뒤 같은 프로젝트에서 `codex resume --no-daemon`을 실행해 이 대화를 고르면 공유 daemon을 재사용하지 않는 연결에서 점검할 수 있다.
이는 다음 복구 절차이며 효과를 이미 검증한 해결책은 아니다. Codex 자체 UI/CLI를 Windows 자동화로 조작하는 것은 computer-use 지침상 금지돼 사용자에게 이 조작을 넘긴다.

재개 시 현재 창을 새로 조회한다. GUI가 없으면 `tests/observe_gui_native.py`를 **새 output-root**로 실행한다.
이전 root/launch/관찰 원본은 덮어쓰지 않는다. 캡처가 실제 GUI와 일치하면 native 입력·선택창·메시지창·현재 배율/긴 경로 QA를 수행하고,
계속 다르면 GUI 오류라고 단정하지 말고 새 연결의 결과를 기록한다. 사용자 화면 확인을 테스트 완료나 capture 해결로 바꾸어 기록하지 않는다.
