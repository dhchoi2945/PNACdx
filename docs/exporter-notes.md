# Exporter 구현 및 API 조사 기록

## 실행 경계

`skill/pgcheck_json.il`을 먼저, `skill/pgcheck_export.il`을 다음에 로드한다.
DB가 필요 없는 인코더 자체 점검은 CIW에서 `pgcJsonSelfTest()`로 실행한다.
이는 실제 Virtuoso 실행 없이 외부에서 PASS로 보고할 수 있는 항목이 아니다.

```lisp
load("/approved/pgcheck/skill/pgcheck_json.il")
load("/approved/pgcheck/skill/pgcheck_export.il")
pgcJsonSelfTest()
pgcExport("ALLOWED_LIB" "PGC_T01_TOP" "schematic" "/approved/results/run-001" "run-001")
```

출력 디렉터리는 존재하면 안 된다. 부모 디렉터리는 미리 존재해야 한다.
`createDir` 자체의 성공을 요구하므로 다른 실행이 같은 디렉터리를 먼저 만들면 중단한다.
기존 실행 결과는 열거나 수정하지 않는다. 추출 실패 시 이번 실행의 부분 파일은 남긴다.
JSONL 스트림의 쓰기, `drain`, `close`를 확인한 뒤 `manifest.pending`를 쓰고
동일 디렉터리의 `manifest.json`으로 게시한다. 게시 전 실패하면 유효한 최종 manifest가 없다.
일반적인 저장장치의 전원 장애까지 견디는 트랜잭션을 보장하지는 않는다.

모든 설계 열기는 `dbOpenCellViewByType(... nil "r")`를 사용한다.
Exporter는 `schCheck`, `dbCheck`, 저장, 재바인딩, 평탄화 또는 DB 삭제를 호출하지 않는다.
이미 열려 있는 CellView는 메모리의 미저장 변경을 포함할 수 있다.
`saved_status`, `connectivity_status`, `internal_acceptance`는 `NOT_TESTED`로 기록한다.
원본 저장/Connectivity 유효성 판단을 대신하지 않는다.

## 추출 모델

- Cell 정의는 Library/Cell/View별로 한 번 기록한다.
- 루트와 각 배치를 별도 Instance Occurrence로 기록한다. ID는 실행 내 일련번호다.
- 각 Occurrence에 Local Net을 별도로 만든다. DB Net 객체의 동일성으로만 연결하며 이름으로 합치지 않는다.
- `instance_port`는 부모 DB의 InstTerm→Net, `cell_port`는 해당 CellView의 Terminal→Net을 읽는다.
- Master Terminal과 선택된 Schematic Terminal의 이름/방향 및 InstTerm의 Master Terminal 참조를 확인한다.
- Missing InstTerm, 조회 실패, Terminal 불일치는 `unresolved`다. 성공적으로 읽은 nil Net만 `unconnected`다.
- Child 분석 View는 명시적으로 `schematic`이다. 해당 View가 없는 primitive/모델 전용 leaf도 추정하지 않고 미해결로 남긴다.
- 정확히 `basic/{ipin,opin,iopin,sympin}/symbol`만 Pin 보조 Instance로 제외한다.
- 선택적 `xy`/`orient` 조회 실패는 `placement: null`과 manifest 경고가 된다. 좌표 단위는 검증되지 않아 null이다.

Global Signal과 Inherited Terminal/Signal은 읽기 전용으로 조사하되 해석하지 않는다.
`netSet`은 임의 이름의 Property일 수 있어 `valueType`도 검사한다.
Bus/Array 이름, 광고된 `numInst`, CellView의 `mosaics` 컬렉션을 검사하고 전개하지 않는다.
API 지원/조회 실패, 발견된 고급 의미, Cycle, 깊이 제한(64)은 미해결로 기록한다.
지원되지 않는 의미가 있는 데이터를 완전한 elaborated netlist로 해석하면 안 된다.
사이트가 추가한 의미 및 모델별 Netlisting 동작은 이 기본 DB Snapshot의 범위를 벗어난다.

## 문자열과 인코딩

JSON 인코더는 따옴표, 역슬래시와 ASCII 제어 문자를 이스케이프한다.
구조적 경로는 구성요소의 `~`를 `~0`, `/`를 `~1`로 변환한다.
Virtuoso를 시작하기 전 유효한 UTF-8 Locale이 필요하다.
`LC_ALL`, `LC_CTYPE`, `LANG` 순으로 검사하며 이름에 `UTF-8`/`UTF8`이 있어야 한다.
Locale 이름은 실제 바이트 인코딩의 증명이 아니다. 변환 API를 추정해 호출하지 않으며,
사내 Python Reader의 UTF-8 strict decode 및 JSON 검증을 반드시 실행한다.
`pgcJsonSelfTest()`도 파일 바이트와 비ASCII 이름의 사내 왕복 검증을 대신하지 않는다.

## 근거 및 검증 수준

아래 자료는 공개된 API 사용 사례 및 사전 조사 근거다. IC25.1-64b.SM_ISR7.10의 지원을
확정하는 시험 결과는 아니다. 적용 전 `pgcProbe`와 내부 문서에서 확인해야 한다.

| 항목 | 1차 출처 | 구현 반영 |
|---|---|---|
| Instance, InstTerm, Net 순회 | [Cadence: Getting devices instance model, terminals and nets](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/51905/getting-devices-instance-model-terminals-and-nets/1383902) | DB의 관계를 읽고 이름 추정을 피함 |
| Global은 CellView별 Signal의 속성 | [Cadence: How to access global signals cds_globals](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/36515/how-to-access-global-signals-cds_globals/1348918) | `cv~>signals`, Signal의 `isGlobal` 조사 |
| Inherited Terminal과 NetSet 조회 | [Cadence: Assign voltage source for inherited connection](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/39894/assign-voltage-source-for-inherited-connection/1356153) | `dbGetCellViewInheritedTerm/Sig`을 보호 호출하고 해석을 중단 |
| Property는 별도 객체, CDF fallback 주의 | [Cadence: Changing instance properties through SKILL](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/23100/changing-instance-properties-though-skill) | 광고된 DB Attribute와 실제 Property 객체의 `valueType`을 읽음 |
| 선택적 배치 원점 | [Cadence: Coordinates of selected instances](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/10675/skill-code-for-finding-coordinates-of-selected-instances-in-the-layout) | 보호된 `xy` 조회; 실패는 null |
| 파일 출력과 Flush | [Cadence: Writing into file using SKILL](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/41876/writing-into-file-using-skill), [Cadence: File I/O operations](https://community.cadence.com/cadence_blogs_8/b/pcb/posts/guide-to-file-input-output-operations-in-allegro-skill) | 쓰기/Flush/Close 결과 확인; 후자는 Allegro 사례로 Virtuoso 확인 필요 |
| 파일 이름 변경 | [Cadence: Passing variables to a script](https://community.cadence.com/cadence_technology_forums/pcb-design/f/allegro-x-pcb-editor/22554/is-it-possible-to-pass-variables-to-script-from-inside-skill-function) | `renameFile` callability 확인; Allegro 사례이므로 Virtuoso는 미검증 |
| `return`은 `prog` 내부 사용 | [Cadence: How to return from a SKILL procedure](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/46716/how-to-return-from-a-skill-procedure) | 조기 반환 함수에 `prog` 사용 |

외부에서 수행한 점검은 소스의 문자열/주석을 구분한 괄호 및 대괄호 짝 검사뿐이다.
실제 SKILL 파싱, API 동작, DB 연결, 인코더 실행, 파일 게시 및 비ASCII 왕복은 모두
사내 실행 전까지 `NOT_TESTED`다. 실제 설계 데이터와 사내 시험 결과의 외부 제출을 요구하지 않는다.
