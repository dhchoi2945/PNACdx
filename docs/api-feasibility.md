# Phase 0 SKILL API 가능성 조사

조사 기준일: 2026-10-22. 대상: Cadence Virtuoso IC25.1-64b.SM_ISR7.10.

구현 코드는 제공하지만 이 개발 환경에는 Virtuoso 실행기, 라이선스 및 해당 릴리스의 사내 문서가 없다. **IC25.1에서의 SKILL 로드·실행·DB 의미 검증은 모두 NOT_TESTED**이다. 공개된 Cadence 답변은 후보 API와 접근법의 근거이며, 대상 버전에서 지원된다는 인증이 아니다. 실제 설계 및 테스트 결과를 외부에 제공할 필요가 없다. 아래 조사는 사내 설치 문서로 재확인하고 사내에만 기록한다.

## 근거 수준

| 구분 | 의미 |
|---|---|
| 공개 1차 근거 | Cadence Community에 게시된 Cadence 기술 답변 또는 공식 블로그에서 사용 예를 확인함 |
| PRESENCE callable | 현재 세션에서 함수 이름을 호출할 수 있음. 시그니처·라이선스·실제 동작은 미확인 |
| READ_OK | 특정 객체의 보호된 읽기 1회가 예외 없이 끝남. nil은 속성 지원 또는 의미상 부재의 증거가 아님 |
| 사내 기능 확인 | 사내에서 실제 결과를 수동 oracle과 비교해 별도로 기록해야 함 |

`pgcProbe(outputFile @optional lib cell view)`는 append 방식으로 로컬 텍스트 보고서를 작성한다. lib/cell 생략 시 함수 존재 여부만 점검한다. 제공한 CellView는 `dbOpenCellViewByType(... "r")`로 읽고, `errset`으로 개별 조회 오류를 격리한다. 원본 DB에서 `schCheck`, `dbSave`, 변경 API, HDB 변경 API, 외부 명령을 실행하지 않는다. DB open 과정의 사이트 자체 load trigger 동작은 관리자가 확인해야 한다.

```lisp
load("/approved/pgcheck/skill/pgcheck_probe.il")
pgcProbe("/approved/local-runs/probe-01.log")
pgcProbe("/approved/local-runs/probe-02.log" "ALLOWED_TEST_LIB" "PGC_T01_TOP" "schematic")
```

보고서 작성 성공은 Phase 0 PASS를 뜻하지 않는다. 구조가 존재하지 않는 빈 테스트 CellView에서는 sample 조회가 생략될 수 있다. 전체 설계를 순회하는 조사가 아니며 대표 객체 1개와 CellView의 목록 속성을 조사한다. 출력에는 이름·속성 등 사내 데이터가 포함될 수 있으므로 사내 저장소에서만 보관한다.

## 기본 데이터 및 생성

| 기능 | 확인한 근거와 구현 선택 | 사내 확인 및 관련 함수 |
|---|---|---|
| CellView 읽기 및 생성 | 공개 Cadence 예제에서 `dbOpenCellViewByType`, `dbCreateInst`, DB connectivity API 또는 `schCreatePin`/`schCreateWire`를 제안한다. Exporter는 읽기 모드, Generator는 대상 부재 확인 후 append 모드를 쓴다. | Probe `pgcpInspectCv`; Generator `pgctPreflight`, `pgctOpenNew` |
| 덮어쓰기 방지 | Cadence 답변은 write 모드가 기존 내용을 지운다고 설명한다. Generator는 write 모드를 사용하지 않으며 cell 단위 충돌도 거부한다. | 동일 이름이 다른 view만 가진 경우도 생성 중단 확인. 동시 작성자 배제 필요 |
| Symbol 생성 | Cadence 답변에 net/term/pin rectangle로 symbol을 구성하고 symbol master term을 사용해 instTerm을 연결한 예제가 있다. Generator는 단순 rectangle symbol과 세 pin만 만든다. | `pgctBuildSymbol`, `pgctSymbolPin`; 핀 위치·방향·표시 수동 확인 |
| 실제 연결 | 에디터 없이 낮은 수준의 instance를 만들 때 instTerm을 직접 생성해야 할 수 있다는 Cadence 설명이 있다. Generator는 `dbCreateInstTerm`과 실제 schematic wire/label을 모두 만든다. | `pgctConnect`, `pgctCheckSave`, `pgctVerifyTop`; check 후 실제 DB net 객체 비교 |
| DB 속성 | Cadence 답변은 `dbGet`, `dbGetq`, `~>` 및 설치 문서의 DB 객체 설명을 안내한다. 속성 읽기의 nil을 자동 성공으로 해석하지 않는다. | `pgcpRead`; 사내 `cdnshelp` 또는 설치 `doc/skdfref`에서 확인 |

근거: [Schematic 생성 API 제안](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/36821/schematic-creation-using-skill/1349758), [append/write 차이와 sch API의 GUI 의존성](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/24070/how-to-run-dbopencellviewbytype-in-ocean-mode), [symbol pin과 instTerm 생성 예제](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/48342/dbcreateinstterm-terminal-not-in-instance-s-master), [에디터 없는 instTerm 및 global signal 설명](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/62236/how-to-create-netlist-for-global-ground-with-schematic-which-generated-by-skill/1399373), [DB 객체 속성과 설치 문서](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/10739/d_cellview).

## 고급 항목: 조사 범위, 구현 완료 아님

| 항목 | 확인한 사실 | Phase 0 정책 및 다음 사내 조사 |
|---|---|---|
| Config View / HDB | Cadence 예제는 `hdbOpen` 및 top library/cell/view 조회로 config의 top을 얻는다. 별도 HDB API가 binding rule을 다룬다. | Probe는 후보 함수의 존재만 조사하며 HDB를 열거나 elaboration하지 않는다. Exporter의 명시적 schematic 선택은 config의 occurrence별 실제 binding을 보장하지 않는다. 로컬 설치의 HDB traversal 예제와 문서를 먼저 확인한다. |
| Global Net | Cadence 답변은 global 여부가 signal의 `isGlobal` 속성으로 표현됨을 설명한다. 이름만으로 충분하다고 볼 수 없다. | Probe는 sample net의 `signals` 및 sample signal `isGlobal`을 읽는다. 같은 이름의 net을 계층 전체에서 합치지 않는다. 실전 global 해석은 미지원·미해결로 남긴다. |
| Inherited Connection | Cadence 답변은 `dbGetCellViewInheritedTerm`, `dbGetTermNetExpr`, `dbParseTermNetExpr`와 instance property 검토를 제시하지만, 예제는 한 단계만 다루며 다단계 상속은 별도 문제라고 명시한다. | Probe는 inherited terminal/signal 조회 후보만 보호 호출한다. net expression 기본값을 실제 최종 연결로 추정하지 않는다. 다단계 netSet override·switch view·숨은 terminal을 별도 사내 testcase로 검증해야 한다. |
| Bus | Cadence 답변에 bus net의 member signal과 explicit member net이 다름을 설명한 예제가 있다. | scalar T01만 필수. bit 순서·범위·bundle·member 관계를 펼쳐 처리하지 않는다. `numBits`, `signals`, `sigNames`는 조사 값이며 의미 지원 인증이 아니다. |
| Instance Array | 배열 및 mosaic의 객체 표현은 일반 scalar occurrence와 다를 수 있다. 이번 조사에서 IC25의 공식 배열 확장 계약을 확인하지 못했다. | Probe는 `numInst`, `mosaic`, CellView `mosaics` 후보 속성을 읽는다. scalar처럼 임의 확장하지 않는다. IC25 설치 문서와 별도 array testcase에서 조사한다. |
| 저장 상태와 연결 유효성 | Cadence 답변의 `dbIsConnCurrent`는 마지막 extraction 이후 변경 여부를 확인하지만 symbol master 변경을 모두 판단하는 지표는 아니다. `modifiedButNotSaved`는 별도 후보 속성이다. | Probe는 변경하지 않고 상태만 기록한다. instHeader `masterChangeCount`와 master `modifiedCounter` 조회도 조사한다. 원본에 check/save를 자동 수행하지 않는다. 불명확한 상태를 완료 검증으로 승격하지 않는다. |
| 좌표·단위 | instance의 원점·orientation·transform 및 CellView 단위 속성을 조회할 수 있는지 조사한다. | IC25의 단위 해석은 미검증. 좌표 실패는 placement null 및 명확한 경고로 처리하며 원점 단위를 임의 지정하지 않는다. |

근거: [Config top 조회 예제](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/16767/open-config-view-schematic-through-skill/1178607), [Inherited connection API와 한 단계 한계](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/39894/assign-voltage-source-for-inherited-connection/1356153), [global signal 속성 및 schematic extractor](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/14630/properties-on-individual-signals-from-a-net/24981), [Bus member net 구분](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/48350/try-to-create-bus-by-dbcreatenet-in-pcell), [dbIsConnCurrent와 master 변경 counter](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/26174/check-the-instance-symbol-change-in-schematic?pifragment-3104=1), [저장 상태 조회 논의](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/51566/how-to-check-if-schematic-layout-views-need-saving-due-to-updates).

## 사내 판정 순서

1. approved 경로의 소스를 검토하고 CIW에서 Probe를 로드한다. 로드 오류는 FAIL, 실행기/라이선스/설치 제약은 BLOCKED, 실행 전 항목은 NOT_TESTED로 기록한다.
2. 설치 문서에서 후보 API의 정확한 인자·반환값·view type·객체 속성을 확인한다. `callable=t`만으로 다음 단계를 PASS 처리하지 않는다.
3. dry-run과 충돌 방지 테스트 후 명시적으로 T01을 생성한다. 다른 사용자가 두 cell 이름을 만들지 않도록 사내 운영 절차로 예약한다.
4. Check and Save 결과, 실제 instTerm/term net, symbol/schematic port 대응을 수동으로 비교한다. 생성기 반환 t는 생성기의 로컬 검사 통과만 의미한다.
5. 같은 데이터를 CIW exporter와 Python validator로 검증한다. Batch는 별도 시도하고 환경 제약은 기록한다. 최종 완료 및 사용자 승인은 사내 판단으로 남긴다.

호환성 문제를 수정할 때는 `pgcpRead`(속성 조회), `pgctSymbolPin`(symbol pin), `pgctPin`(schematic pin), `pgctWire`/`pgctLabel`(배선/라벨), `pgctCheckSave`(check/save 반환 계약)를 우선 확인한다. private API를 임의로 추가하거나 원본 DB를 고쳐 probe를 통과시키지 않는다. Probe/Generator의 source에 shell 실행·인터넷 호출·telemetry는 없다.
