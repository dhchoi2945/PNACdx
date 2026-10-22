# T01 생성 및 수동 대체 절차

사내 Virtuoso IC25.1-64b.SM_ISR7.10 실행은 외부 개발 환경에서 **NOT_TESTED**이다. 아래 절차는 사내 사용자가 승인된 기존 테스트 Library에서 수행한다. 실제 설계나 사내 결과를 외부에 반출할 필요가 없다.

## 대상과 안전 조건

생성 대상은 지정 Library의 `PGC_T01_TOP/schematic`, `PGC_T01_LOAD/schematic`, `PGC_T01_LOAD/symbol`뿐이다. Generator는 새 Library를 만들지 않으며 `basic/ipin/symbol`, `basic/iopin/symbol`은 읽기만 한다. `basic`이 설치에 없거나 pin master가 사이트에서 달라졌으면 아래 수동 절차 또는 `pgctPin` 어댑터를 사용한다.

`PGC_T01_TOP` 또는 `PGC_T01_LOAD` cell이 어떤 view로든 이미 존재하면 중단한다. Generator는 세 대상 view의 존재 여부도 전부 점검한 후에만 쓰기를 시작한다. 생성 직전에도 확인하고 append 모드만 사용한다. 기존 cell 삭제·overwrite·실패 후 자동 rollback은 없다.

이 확인과 DB open은 원자적인 cell-name 예약이 아니다. **해당 두 cell 이름의 동시 작성을 사내 운영 절차로 배제한 후 생성한다.** 다른 프로세스가 확인 직후 빈 view를 만드는 극히 짧은 경합까지 이 소스가 배타적으로 막는다고 보장하지 않는다. 경쟁자가 생성한 비어 있지 않은 view가 열리면 내용 추가 전에 중단한다. 실패 시 생성 가능성이 있는 대상과 CIW 원인을 로컬 로그에 남기며 다음 실행은 기존 cell 충돌로 중단한다.

## CIW 자동 생성

회사 승인 경로를 예제의 경로와 Library 이름에 대입한다. 로그의 부모 디렉터리는 먼저 준비한다. `logFile`은 로컬 append 파일이다.

```lisp
load("/approved/pgcheck/skill/pgcheck_probe.il")
load("/approved/pgcheck/skill/pgcheck_t01.il")
pgcProbe("/approved/local-runs/probe-01.log")

; 기본 dry-run: DB 쓰기 없음. 반환 t는 사전 충돌 검사가 끝났다는 뜻.
pgcGenerateT01("ALLOWED_TEST_LIB")
pgcGenerateT01("ALLOWED_TEST_LIB" nil "/approved/local-runs/t01-dry.log")

; 두 cell 이름 예약 및 dry-run 검토 후 명시적 t만 생성 허용.
pgcGenerateT01("ALLOWED_TEST_LIB" t "/approved/local-runs/t01-create.log")
```

Generator는 symbol pin/net/term, LOAD schematic pin과 labeled wire, TOP의 두 instance와 pin/wire/label을 만든다. `dbCreateInstTerm`으로 실제 DB 연결을 만들고 `schCheck` 후 읽은 terminal/instTerm net 객체가 아래 독립 표와 같은지 비교한다. symbol/schematic의 pin direction도 확인한다. 저장한 세 view의 쓰기 handle을 닫고 읽기 모드로 다시 열어 같은 검사를 반복한다. 새 schematic만 check/save하고 원본 설계는 수정하지 않는다. 이 readback은 같은 Virtuoso 프로세스에서 수행하므로 장기 보존·다른 세션 호환성 확인은 사내 재실행으로 수행한다.

로컬 로그의 생성기 PASS는 세 view 저장 및 이 생성기의 DB 검사만 의미한다. CIW 시각 확인, Exporter 실행, Python 독립 oracle 검증, 최종 사용자 승인은 별도이다. API가 callable이어도 정확한 인자·레이어·도형 연결 의미는 대상 설치에서 확인해야 한다.

### 실패 진단

| 증상 | 관련 함수 / 점검 내용 |
|---|---|
| Library 없음 또는 cell 충돌 | `pgctPreflight`: 허용 Library 이름과 두 cell의 모든 view를 확인한다. 기존 cell을 자동 삭제하지 않는다. |
| basic pin master open 실패 | `pgctGenerateBody`: 설치 Library mapping 및 실제 ipin/iopin view명을 확인한다. 이 실패는 첫 DB 쓰기 이전이다. |
| symbol pin/shape 생성 실패 | `pgctSymbolPin`, `pgctBuildSymbol`: 설치 schematicSymbol view type과 `pin`, `device`, `instance` layer-purpose를 문서로 확인한다. |
| wire/pin API 실패 | `pgctPin`, `pgctWire`, `pgctLabel`: API 시그니처 및 Composer 기능/라이선스를 확인한다. GUI 없는 실행만 실패하면 CIW에서 우선 수행한다. |
| instTerm 없음 또는 net 불일치 | `pgctConnect`, `pgctVerifyTop`: symbol pin 중심, wire endpoint, label spelling, schCheck 메시지와 실제 instTerms를 확인한다. 누락을 미연결로 간주하지 않는다. |
| check/save 실패 | `pgctCheckSave`: 로컬 CIW 오류, write permission, lock, 라이선스, 연결 current 상태를 확인한다. 원본에 강제로 conn-current flag를 설정하지 않는다. |
| PARTIAL_CREATION | 로그의 opened targets, NEW_OPEN_ATTEMPT 및 Library Manager에서 실제 존재 view를 확인한다. open 이후 반환 전 실패한 target도 NEW_OPEN_ATTEMPT에 기록된다. 일부 writable DB handle은 진단을 위해 세션에 남을 수 있다. 자동 재실행·자동 삭제하지 않는다. 사내 담당자가 생성 상태를 판단한다. |

## 수동 대체 절차

자동 API가 사내 환경과 맞지 않으면 이 절차로 동일한 시험 대상을 만든다. 수동 생성 여부와 자동 생성 실패 원인은 사내 체크리스트에 기록한다. 자동 생성 기능 자체의 검증은 그때까지 NOT_TESTED 또는 BLOCKED이며 수동 성공으로 자동 생성 PASS를 대신하지 않는다.

1. Library Manager에서 승인된 기존 Library를 선택한다. 두 cell 이름을 검색하고 **어떤 view도 없는지** 확인한다. 존재하면 중단한다. 두 cell 이름의 동시 사용을 배제한다.
2. `PGC_T01_LOAD/schematic`을 새로 만든다. scalar pin 세 개 `VDD`, `VSS`, `EN`을 만든다. VDD/VSS direction은 `inputOutput`, EN은 `input`이다. 각 pin에서 짧은 wire를 그려 같은 이름의 net label을 단다. 각 net은 서로 분리한다. global 표시 `!`, inherited expression, bus 문법은 사용하지 않는다. Check and Save 후 각 cell terminal의 net 이름과 direction을 확인한다.
3. LOAD의 symbol view를 만든다. 이름과 direction이 같은 세 terminal을 만들고 box 및 보이는 pin을 배치한다. schematic pin과 symbol pin 대응을 확인한다. Generator의 배치와 맞추려면 symbol local 좌표를 VDD `(0, 2)`, VSS `(0, 0)`, EN `(0, -2)`로 지정하지만 수동 도형 좌표는 검증 계약의 필수값이 아니다. symbol을 저장한다.
4. `PGC_T01_TOP/schematic`을 새로 만든다. LOAD/symbol을 두 번 배치하고 instance 이름을 `U_LOAD0`, `U_LOAD1`로 정확히 지정한다. array를 사용하지 않는다.
5. TOP pin/local net 네 개를 만든다. VDD_A/VDD_B/VSS_A는 `inputOutput`, CTRL은 `input`이다. TOP pin에서 실제 wire를 그리고 아래 표대로 두 LOAD의 symbol pin에 실제 wire 또는 같은 local net label로 연결한다. VDD_A와 VDD_B는 다른 net이어야 한다. VSS_A와 CTRL은 두 instance가 공유한다.
6. Check and Save를 수행한다. 에러와 symbol/terminal mismatch를 해결한 뒤 DB 실제 연결값을 아래 표와 비교한다. 이름이 같아 보여도 다른 cellview의 net을 합치지 않는다.
7. CIW Exporter를 실행하고 사내 Python Validator의 T01 모드로 검증한다. 단순 도형만 있고 instTerm/term의 net이 없으면 FAIL이다. 미해결 추출 결과는 complete로 인정하지 않는다.

## 독립 기대값

| Instance | Port | Parent TOP local net |
|---|---|---|
| U_LOAD0 | VDD | VDD_A |
| U_LOAD0 | VSS | VSS_A |
| U_LOAD0 | EN | CTRL |
| U_LOAD1 | VDD | VDD_B |
| U_LOAD1 | VSS | VSS_A |
| U_LOAD1 | EN | CTRL |

TOP의 cell port 네 개는 같은 이름의 TOP local net에 연결된다. LOAD의 cell port 세 개는 LOAD의 `VDD`, `VSS`, `EN` local net에 연결된다. 두 LOAD는 같은 cell definition을 사용하지만 occurrence는 두 개이며, 각 LOAD 내부 net도 occurrence별로 구분한다. 선택한 분석 view는 LOAD/schematic이고 실제 배치된 master는 LOAD/symbol이다. `basic/ipin/iopin` 등 schematic pin 도형 helper instance는 논리 LOAD instance 수에 포함하지 않는다.

자동 생성 화면은 같은 이름 label로 연결된 여러 짧은 wire를 사용한다. 따라서 공유 VSS_A/CTRL의 모든 wire가 한 선으로 이어 보이지 않아도 label에 의한 실제 local connectivity가 존재해야 한다. 이 의미는 check 후 DB 객체로 확인한다.

## 필수 사내 기록

실행 전에는 각 항목을 NOT_TESTED로 둔다. 수행 후 PASS/FAIL/BLOCKED와 사내 로그 위치만 기록한다. 외부 결과 제출은 요구하지 않는다.

| 항목 | 초기 상태 |
|---|---|
| 대상 IC25.1 CIW에서 두 SKILL 소스 로드 | NOT_TESTED |
| dry-run에서 새 cell/view가 생기지 않음 | NOT_TESTED |
| 허용 기존 Library만 사용 | NOT_TESTED |
| 두 cell 중 하나가 기존에 존재할 때 어떤 view도 쓰지 않음 | NOT_TESTED |
| 다른 view만 있는 기존 cell도 충돌로 중단 | NOT_TESTED |
| 명시적 t로 세 view를 안전 생성 및 check/save | NOT_TESTED |
| 두 LOAD occurrence, 별도 VDD, 공유 VSS, EN/CTRL 및 cell-port 관계 확인 | NOT_TESTED |
| JSONL 출력/파싱/참조 무결성 및 독립 T01 oracle | NOT_TESTED |
| 좌표 지원 여부 및 미지원 시 명확한 경고 | NOT_TESTED |
| Batch 시도 결과 및 문제 기록 (필수 PASS 제외) | NOT_TESTED |
| 최종 사내 검증과 사용자 승인 | NOT_TESTED |
