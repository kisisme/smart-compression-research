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
