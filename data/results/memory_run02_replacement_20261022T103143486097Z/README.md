# Run 2 전체 재측정·활성 결과 교체 기록

- 사전 변경 기록: `research_log/memory_run02_replacement_amendment.md`.
- 실행 HEAD: `9a261e46d01f61e986d98eedc11f634eda19c863`.
- 활성 결과: `../memory_repeatability_v1_20261019T124938284221Z_attempt02/run_02/`.
- `original_snapshot/`: 교체 전 attempt 전체. `original_manifest.json`으로 모든 원본 파일을 확인한다.
- `new_run_02/`: 실제 새 측정 원본. 활성 Run 2와 동일한 측정 산출물이다.
- `displaced_active_files/`: 설치 때 이동한 이전 활성 파일. 원본 snapshot도 별도로 유지한다.
- `installation.json`, `replacement.json`: 설치 transaction과 최종 결과.
- `publication_preinstall_checkpoint/`: 활성 기록에 최초 삽입됐던 설치 전 검증 checkpoint 사본.
- `post_replacement_verification.json`: 최종 저장 검증과 실제 집계·시각. 독립 프로토콜 감사는 아니다.
- `finalize_and_verify_replacement.py`: 현재 교체 기록을 설치 결과로 마감하고 저장 파일을 대조한 코드.
  원시 측정이나 측정 metadata를 변경하지 않는다. 이미 완료했으므로 반복 실행하지 않는다.

원래 여섯 run의 실패 이력과 교체 후 활성 결과를 구분한다. 논리적 슬롯 2의 새 측정은 Run 6 뒤에
실행했다. 과거 per-run checkpoint에 들어 있는 경로·hash는 `original_snapshot/`의 당시 파일과
대조한다. 원래 수집이 처음부터 정상 성공이었다고 주장하지 않는다.

진행 중 읽기 전용 `Win32_PerfFormattedData_PerfProc_Process` 조회에서 Defender(MsMpEng),
PyCharm 등의 CPU 활동이 관측됐다. 이는 연속 관측이나 지연 원인의 확정이 아니며 프로세스나
측정 설정을 바꾸지 않았다. 실행 전후 관측과 해당 시간 범위 전원 로그는 JSON에 남아 있다.

Memory는 `validation_only`, `score_inclusion=false`다. 변경 설계 전용 독립 감사·후보 분석·공식
채택·4지표 전환은 후속 작업이다.
