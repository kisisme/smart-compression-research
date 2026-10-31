# 후보 모델 학습·실제 파일 평가 기준

상태: 실행 전 기준. 사용자가 기준 확정→별도 모델 학습→새 실제 파일 검증의 진행을 요청했다.
[기계 판독 계획](usage_model_study_plan_20261031.json)과 [기존 고정 시나리오](usage_scenarios_frozen_20261031.json)를 따른다.
현재 [공식 v2](../research_protocol_v2.md)·[설정](../config/experiment_config.json)과 memory 참고 방침은 유지한다.

총비용 시나리오 전체를 각각의 후보 정답 정의로 사용한다. 특정 선택 비율이나 좋은 결과를 얻은 조건만 고르지 않는다.
Decision Tree/Random Forest 설정은 기존 config 그대로 고정한다. 입력은 기존 압축 전 통계 특징뿐이다.
외부 사용 조건은 모델을 고르는 profile이며 측정값·정답·경로/파일 형식을 입력에 추가하지 않는다.
기존 seed-group train/test 분할을 재검증하고 train 부분만 학습한다. Pilot 전체를 탐색했으므로 test 결과는 개발 진단이다.

실제 후보는 이미 권리/개인정보 맥락 검토된 전체 목록을 명시적으로 선정한다. 원본 hash·quota·그룹·
필수 notice/citation/PSF 조건과 기존 재생성 합성 겹침 근거를 연결해 corpus를 동결한다.
일반 manifest의 evaluation_ready=false를 임의 변경하지 않고 연구별 실행 조건을 별도 기록한다.
과거 합성 원본 bytes/hash 미저장, 출처 간 알려진 관계와 비확률 quota 수집의 한계도 유지한다.
새 자료를 다시 나누거나 학습에 쓰지 않는다. 모델/특징/예측은 네 압축기 benchmark 전에 동결한다.

주 비교량은 원본 그룹을 동일 비중으로 한 후보 모델의 train-majority 대비 정책비용 regret 차이다.
항상 gzip/bz2/lzma/zstd, training-majority, 두 모델, oracle을 모두 보고한다.
accuracy·고정 네 클래스 Macro F1·혼동행렬·크기/시간·정책 비용·regret와 형식/그룹 coverage도 보존한다.
불리한 결과·미등장 클래스·높은 confidence의 오답·실패도 남기고 confidence를 정답 확률로 해석하지 않는다.
후보 함수를 학습/검증하는 실험이며 공식 운영값 채택이나 전체 실제 파일 모집단의 개선 증명이 아니다.

순수 codec 결과에 더해 상주 모델의 검증용 package 엔진을 별도로 실측한다.
파일 읽기·hash·특징 추출·예측 후 선택한 압축기 하나만 실행하고, byte 복원 검증·payload/manifest 저장까지 시간을 잰다.
다시 읽어 복원·크기/hash 검증·원래 파일명 저장하는 시간도 별도로 잰다. 각 phase 원시 ns와 중앙값 ms를 보존한다.
모든 모델과 고정 zstd에 같은 정의를 적용하고 package bytes와 전체 경로 시간으로 비용을 재계산한다.
모델 read/hash/load는 별도로 반복 측정하며 warm 측정 밖이다. Python 시작·cold cache·실제 GUI/CLI 배포 속도로 주장하지 않는다.
고정 순서·운영체제 캐시·fsync 미사용 등의 한계와 실측 원시 파일을 남긴다.

기존 Compare Mode의 codec 조건·복원 검증·원시 반복을 그대로 사용한다.
실패나 source/input 변경이 있으면 부분/오류 근거를 보존하며 재시도·파일 교체·유리한 반복 선별을 하지 않는다.
원본·과거 결과·모델은 그대로 두고 새 실험 경로를 쓴다. 단계마다 hash와 저장 검증·Git 보존 후 다음 단계로 진행한다.
GUI 수동 Compare 저장 검증/전체 시각 QA는 이 연구 엔진 검증과 별개의 미완료 항목이다.
