# Phase 0 구현·검증 현황

기준일: 2026-10-22 (Asia/Seoul). 대상 버전: Cadence Virtuoso IC25.1-64b.SM_ISR7.10.

**개발 산출물은 준비되었으며 Phase 0의 사내 완료 판정과 사용자 승인은 아직 이루어지지 않았습니다. Phase 1은 구현하지 않았습니다.**

## 구현된 기능

- 읽기 전용 API Probe, 로컬 Python 환경 점검, dry-run 기본 T01 Generator 및 저장 후 readback 검사.
- 전체 scalar schematic의 Cell/Terminal/Instance/Net, 두 유형의 Port–Net 연결, Master/선택 View 대응을 기록하는 SKILL Exporter. 추출 실패는 unresolved, 좌표 실패는 placement null과 경고.
- 실행별 새 출력 경로, JSONL/manifest 마지막 게시, UTF-8 locale 사전 검사 및 문자열 이스케이프 코드.
- 표준 라이브러리 Python Reader/Schema/Validator, 독립 T01 oracle, 합성 데이터 생성, CIW/Batch/통합 실행 인터페이스.
- 오프라인 구성, API 가능성 조사, 수동 T01 대체 절차, 사내 완료 기준·원인별 디버깅 문서.

## 이 환경에서 테스트한 기능

개발 환경: Windows AMD64, **CPython 3.14.3**. 실제 설계 데이터와 사내 테스트 결과를 사용하지 않았습니다.

| 검증 | 상태 | 실제 확인 내용 |
|---|---|---|
| 독립 Python 단위 테스트 | PASS | `python -m unittest discover -s tests -v`: **124개**, 6.419초, OK |
| Python 문법/컴파일 | PASS | pgcheck/scripts/tests compileall |
| JSONL/UTF-8 | PASS | 합성 데이터의 따옴표·역슬래시·제어문자·한글, BOM/잘못된 UTF-8/중복 key/NaN/무한대/lone surrogate 거부 |
| Schema/ID/참조/계층 | PASS | 필수 필드·capability·counts·ID 중복·참조·부모 순환·구조 경로·Net 범위·Port 누락/중복 검출 |
| 독립 T01 | PASS | 두 LOAD의 VDD 분리·VSS/CTRL 공유·cell_port·direction; 잘못된 연결을 FAIL로 검출 |
| 실행/덮어쓰기 방지 | PASS | 합성 출력·기존 보고서 거부, CLI exit code, 미해결 원인 보고, 사내 승인 상태 자동 PASS 방지 |
| Batch 단위 테스트 | PASS | subprocess 모의 실행만 사용. 성공/실패/실행기 부재/타임아웃/경로 중첩/인자 인용을 검사 |
| CLI 스모크 | PASS | synthetic 0/PASS, validate wrapper 0/PASS, phase0 gate 2/BLOCKED, env wrapper 0/PASS, Batch plan 2/NOT_TESTED |
| SKILL 정적 점검 | PASS | 4개 .il의 문자열·괄호 균형, procedure 이름 중복, read-only 모듈의 DB 변경 호출 부재 점검 |

SKILL 정적 점검은 **SKILL 파서·컴파일러·API·DB 의미 검증이 아닙니다**. Python 테스트에서 사용하는 `evidence=db`는 합성 입력값이며 실제 DB 관측을 주장하지 않습니다. 원시 개발 로그와 합성 스모크 출력은 개발 폴더 `local-results/`에 별도로 보관하며 반입 소스 ZIP에는 넣지 않습니다.

## 미검증 사항

| 항목 | 상태 |
|---|---|
| IC25.1에서 .il 파일 load/문법/API 인자·반환 계약 | NOT_TESTED |
| 실제 T01 자동 생성, Layer/Pin/Wire/Label 의미, 충돌·부분 생성 안전성 | NOT_TESTED |
| CIW Export 실제 Connectivity/DB 읽기 전용 동작 | NOT_TESTED |
| SKILL 출력 파일의 실제 UTF-8 왕복과 파일 flush/close/rename | NOT_TESTED |
| 저장 상태·연결 유효성 및 변경 중인 DB snapshot 일관성 | NOT_TESTED |
| 실제 좌표·원본 단위 | NOT_TESTED |
| 실제 Batch·라이선스·초기화·Linux Python 버전 호환성 | NOT_TESTED |
| 사내 검토 및 최종 사용자 승인 | NOT_TESTED |

실제 사내 항목을 PASS로 대신 기록하지 않았습니다. Batch의 환경 실패는 기록만 하고 필수 CIW 완료 조건을 통과한 사내 판단을 막지 않습니다. 통합 CLI의 전체 BLOCKED는 자동 증거의 한계를 나타내며, 사내 담당자의 체크리스트와 사용자 승인은 별도 내부 기록으로 완료할 수 있습니다.

## 알려진 제약

- Phase 0는 scalar·명시적 schematic 바인딩에 한정합니다. Config/HDB elaboration, Global/Inherited 해석, Bus/Array 확장은 구현하지 않았습니다. 발견하거나 의미 검사를 할 수 없으면 incomplete/unresolved로 남기며 추정 연결을 만들지 않습니다. 사이트 고유 의미를 완전히 탐지하는 resolver는 아닙니다.
- child schematic이 없으면 symbol에서 연결을 추정해 채우지 않습니다. 의도적 leaf라도 unresolved로 남습니다. basic의 알려진 pin helper만 정확한 identity로 제외합니다.
- Generator의 부재 확인과 append open은 원자적인 이름 예약이 아닙니다. 두 Cell의 동시 작성은 사내에서 배제해야 합니다. 실패 시 부분 DB는 삭제하지 않으며 로컬 진단 대상으로 남깁니다.
- Exporter는 source-session DB를 읽으므로 기존 열린 View의 미저장 상태가 포함될 수 있습니다. 원본을 자동 check/save하지 않습니다. manifest complete는 파일 추출 완료이며 저장·전기적 정확성·사내 승인 인증이 아닙니다.
- 좌표는 부모 기준 xy/orient만 시도하며 단위는 검증 전 null입니다. Wire/Label/Pin 그래픽 좌표를 출력하지 않습니다.
- 최대 계층 깊이는 64입니다. Python Reader는 검증을 위해 데이터를 메모리에 적재하므로 대규모 칩 용량·성능 검증은 수행하지 않았습니다.
- UTF-8 locale 이름은 바이트 인코딩의 증거가 아니므로 실제 파일은 사내 Python Reader로 검증해야 합니다. Batch 타임아웃 후 사이트가 만든 추가 프로세스는 사내에서 확인합니다.

사내 다음 단계는 [실행 가이드](run-guide.md)와 [체크리스트](internal-checklist.md) 순서입니다. 이 결과나 실제 설계의 외부 반출은 요구하지 않습니다.
