# 사내 테스트 및 디버깅 체크리스트

상태는 **PASS / FAIL / BLOCKED / NOT_TESTED** 네 가지입니다. 아래 초기 상태는 실제 사내 결과가 아닙니다. 사내 담당자가 실행한 항목만 상태와 내부 증거 경로를 갱신합니다. 실제 설계·결과·로그를 외부 Codex에 제출할 필요가 없습니다.

기록: 사내 담당자 / 날짜 / `getVersion(t)` / 승인 Library / 소스 버전 / Probe 로그 경로 / CIW 로그 경로 / export 경로 / Python 보고서 경로를 사내에 보관합니다. 저장 전 원본과 변경되지 않는 스냅샷을 선택하고, 사내 실행 중 변경 금지를 확인합니다.

| 검사 | 초기 상태 | 사내 판정 방법 |
|---|---|---|
| API Probe 및 버전 일치 | NOT_TESTED | 지정 IC25.1 버전, 각 API 서명과 DB 속성을 설치 문서로 확인 |
| T01 dry-run | NOT_TESTED | 두 Cell/세 View 부재 확인, 실행 전후 DB 변화 없음 |
| T01 안전 생성 | NOT_TESTED | 명시적 t 실행, 허용 Library의 세 View만 생성, 저장 후 재오픈 확인 |
| 기존 Cell 덮어쓰기 방지 | NOT_TESTED | 생성 후 두 번째 생성 명령이 사전 검사에서 FAIL, 내용/수정 시각 불변; 별도 허용 Library에서 다른 View만 있는 이름도 거부 확인 |
| 생성 실패 진단 | NOT_TESTED | 사용 불가 pin master/API를 소스 사본에서 지정해 실패 기록; 삭제/덮어쓰기 없음, 부분 상태 표시 |
| CIW 직접 실행 | NOT_TESTED | 동일 Exporter load/실행 성공, 원본 DB 쓰기 없음 |
| 동일 셀의 두 occurrence | NOT_TESTED | 두 LOAD가 같은 cell_id, 다른 instance ID·path·로컬 net ID |
| 서로 다른 VDD | NOT_TESTED | U_LOAD0.VDD→VDD_A, U_LOAD1.VDD→VDD_B |
| 공유 GND | NOT_TESTED | 두 VSS→부모 VSS_A의 동일 net ID |
| Signal 연결 | NOT_TESTED | 두 EN→부모 CTRL |
| Parent/Child Port–Net | NOT_TESTED | instance_port 6개 및 cell_port 10개, 방향 일치 |
| JSONL/Python UTF-8 | NOT_TESTED | validate --t01 PASS, 별도 승인 이름 이스케이프 테스트 |
| 참조 무결성 | NOT_TESTED | validate PASS, 독립 T01 PASS; counts 2/3/10/16/0 |
| 미연결/추출 실패 구분 | NOT_TESTED | 별도 허용 시험에서 nil net만 unconnected, 누락 instTerm/읽기 실패 unresolved |
| 선택 좌표 | NOT_TESTED | 부모 로컬 xy/orient; 실패 시 placement:null 및 경고; 완료 필수 아님 |
| Batch 시도 | NOT_TESTED | batch-result와 로컬 로그 저장; 환경 실패 가능, 필수 아님 |
| 사내 검토 | NOT_TESTED | 위 필수 기준의 증거를 사내 담당자가 확인 |
| 사용자 승인 | NOT_TESTED | 사내 검토 후 승인자/날짜/범위를 내부 기록 |

필수 항목 하나라도 FAIL/BLOCKED/NOT_TESTED이면 Phase 0 완료라고 표시하지 않습니다. 좌표와 Batch의 실패는 원인과 제한을 기록하되 필수 통과 조건은 아닙니다. 필수 CIW 기준과 사용자 승인을 모두 충족하기 전 Phase 1 구현을 시작하지 않습니다.

## 오류별 점검·수정 위치

| 증상 | 먼저 확인할 원인 | 관련 코드/조치 |
|---|---|---|
| 함수 undefined/인자 수 오류 | 설치 모듈·라이선스·함수 버전/서명 | `pgcheck_probe.il`: pgcpPresence/pgcpInspectCv, 사내 SKILL 참조 문서; 지원 단정 금지 |
| dry-run/생성 preflight FAIL | 기존 Cell, Library 누락, 출력 로그 권한 | `pgcheck_t01.il`: pgctPreflight/pgctApiPreflight; 기존 Cell 삭제 금지 |
| 생성 일부 실패 | pin master, layer/purpose, sch API, 쓰기 권한 | pgctOpenNew/pgctBuildSymbol/pgctBuildLoad/pgctBuildTop; 로그 PARTIAL_CREATION의 대상을 GUI로 확인 |
| Wire는 보이나 연결이 없음 | pin 위치·와이어 snap·label·check 상태 | pgctWire/pgctConnect/pgctCheckSave/pgctVerifyTop; 수동 생성 절차와 대조 |
| Exporter unresolved/누락 | 분석 schematic 부재, symbol terminal mismatch, 실패한 attr, 고급 의미 | `pgcheck_export.il`의 pgcE* 함수와 unresolved code; 임의 nil→unconnected 변경 금지 |
| 동일 Net 이름이 섞임 | occurrence 대신 이름으로 결합했는지 | `validator.py`: NET_SCOPE/CONNECTION_NET_SCOPE/NET_COVERAGE; occurrence_id 우선 확인 |
| Parent/port 오류 | 부모 ID/path, selected cell, terminal_id | PARENT_REF/PARENT_CYCLE/PARENT_PATH/TERMINAL_SCOPE/PORT_COVERAGE |
| JSON 문법·UTF-8 실패 | 잘못된 locale, 제어문자, 중간 종료, BOM | `pgcheck_json.il` pgcJ*와 `reader.py`; 원본 보존 후 새 디렉터리로 재실행 |
| manifest 없음/불완전 | 중간 오류, 디스크 부족, 출력 포트 실패 | 이전 결과 보존, CIW 로그 확인; 완료로 수동 변경하지 않음 |
| 실제 net이 맞는데 T01 FAIL | 독립 기대값과 실제 연결·방향·추출 해석 불일치 | `t01.py`의 고정 EXPECTED/TOP_PORTS/LOAD_PORTS; 기대값을 exporter 결과에 맞춰 자동 변경 금지 |
| Batch만 실패 | 라이선스, -nograph 지원, DISPLAY, .cdsinit, cwd/cds.lib | `batch.py` run_batch, batch-result/process.log/CDS.log; CIW로 같은 exporter 검증 |
| 좌표 없음 | xy/orient 접근 불가 또는 단위 미확인 | placement:null/units:null과 manifest 경고; 추정 단위 기입 금지 |

읽기 전용 Exporter 안에 schCheck/save/DB repair를 넣어 문제를 숨기지 않습니다. 저장/연결 검사 문제는 사내 담당자가 원본을 다루는 별도 절차에서 해결합니다. 수정 후 합성 단위 테스트와 영향받은 사내 항목만 다시 검증하고 증거를 새 실행 디렉터리에 남깁니다.
