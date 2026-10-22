# 사내 실행 가이드

모든 경로와 `ALLOWED_TEST_LIB`를 사내 승인 값으로 바꿉니다. 아래 예제는 실제 실행 결과가 아니며, 지정된 버전에서 NOT_TESTED입니다. 로그·JSONL·Probe 결과는 사내에 보관합니다. 생성 전 두 Cell 이름을 예약하고 다른 작업자/프로세스가 만들거나 편집하지 않게 합니다. 공유 라이브러리에서 check/open 사이 경쟁을 원자적으로 막는 Cadence API는 외부에서 검증하지 못했습니다.

## 1. 환경 확인

사내 Linux에서 정상 Virtuoso 프로젝트 디렉터리(`cds.lib`, 사내 초기화/PDK 설정을 사용하던 디렉터리)에서 시작합니다. `python scripts/check_environment.py --output /approved/logs/env-001.json`으로 Python 상태를 기록합니다. 이는 Python 점검이며 Virtuoso 라이선스나 API 성공 판정은 아닙니다.

`locale -a`에서 실제 설치된 UTF-8 locale을 선택해 Virtuoso를 시작합니다. 예: `LC_ALL=C.UTF-8 virtuoso` (해당 locale이 있을 때만). 이미 실행한 CIW에서 환경변수 문자열만 바꾸는 것은 스트림 인코딩 지원의 증거가 아닙니다. 실제 한글·따옴표·역슬래시 이름을 포함한 별도 허용 테스트를 Python Reader로 검사하십시오. Exporter는 UTF-8 locale 표시가 없으면 중단합니다.

CIW:

```lisp
load("/approved/pgcheck/skill/pgcheck_probe.il")
pgcProbe("/approved/logs/probe-001.log" "ALLOWED_TEST_LIB" "KNOWN_EXISTING_CELL" "schematic")
```

기존 Cell을 지정할 수 없으면 `pgcProbe("/approved/logs/probe-001.log")`로 함수 존재만 점검합니다. callable은 함수 서명/의미/해당 버전 지원을 보증하지 않습니다. 사내 설치 문서의 함수 서명과 Probe의 개별 `READ_OK`/실패를 확인합니다.

## 2. T01 dry-run 및 생성

```lisp
load("/approved/pgcheck/skill/pgcheck_t01.il")
pgcGenerateT01("ALLOWED_TEST_LIB" nil "/approved/logs/t01-dry-001.log")
; 기본값도 dry-run:
pgcGenerateT01("ALLOWED_TEST_LIB")
; 사내 담당자가 명시적으로 생성할 때만 t:
pgcGenerateT01("ALLOWED_TEST_LIB" t "/approved/logs/t01-create-001.log")
```

이 명령은 **DB 쓰기 작업**입니다. 새 Library를 만들지 않습니다. 두 대상 Cell 또는 세 View 중 하나라도 이미 있으면 중단합니다. 기존 결과를 지우고 재시도하지 않습니다. 부분 생성 실패 시 로그의 열린 대상과 CIW 오류를 확인하고, 담당자가 상태를 판단합니다. 생성기는 삭제/자동 롤백을 하지 않습니다. 자동 생성 API가 맞지 않으면 [수동 절차](manual-t01.md)를 사용합니다.

성공 후 schematic/symbol을 GUI에서 열어 핀/와이어를 확인하고 Check & Save를 수행한 저장 상태를 사내에 기록합니다. **Check & Save는 새 테스트 Cell에만** 합니다. 원본 설계는 사용자가 별도로 저장/검사한 안정된 스냅샷을 선택합니다.

## 3. CIW 읽기 전용 Export

출력 부모 폴더 `/approved/runs`는 미리 준비하고 실제 실행 폴더는 만들지 않습니다.

```lisp
load("/approved/pgcheck/skill/pgcheck_json.il")
load("/approved/pgcheck/skill/pgcheck_export.il")
pgcJsonSelfTest()
pgcExport("ALLOWED_TEST_LIB" "PGC_T01_TOP" "schematic" "/approved/runs/ciw-t01-001" "ciw-t01-001")
```

Exporter는 DB를 `r`로 열고 원본에 `schCheck`, `dbSave`, repair를 하지 않습니다. 편집 중인 View와 다른 작업자의 변경이 없는 상태에서 실행합니다. 이전에 편집 모드로 열린 DB 핸들이 재사용되는 동작도 사내에서 확인해야 합니다. Config View는 직접 사용하지 않습니다. child 분석 view는 명시적 `schematic`이며 배치 symbol과 별도 필드로 기록합니다. 심볼/분석 단자의 차이, 데이터 접근 실패, 지원하지 않는 의미는 unresolved로 남깁니다.

중단된 출력은 삭제하지 말고 새 실행 이름을 사용합니다. manifest 누락은 실패입니다. `status=complete`는 내보내기가 끝났다는 뜻이며 사내 검증이나 설계의 전기적 정당성을 증명하지 않습니다.

## 4. Python 검증과 통합

```sh
cd /approved/pgcheck
python scripts/validate_export.py /approved/runs/ciw-t01-001 --t01 --report /approved/logs/validate-001.json
python scripts/phase0.py --export /approved/runs/ciw-t01-001 --t01 --report /approved/logs/phase0-001.json
```

T01의 독립 기대값: Cell 정의 2개, occurrence 3개(root 포함), occurrence별 Net 10개, connection 16개(cell_port 10 + instance_port 6), unresolved 0개입니다. basic의 pin helper는 논리 circuit occurrence에서 제외합니다.

`validate` PASS는 JSONL/참조/T01 데이터 비교 성공입니다. `phase0`의 생성 안전성·CIW·승인 항목은 담당자 증거가 필요하므로 NOT_TESTED로 남고 전체 BLOCKED가 정상입니다. [체크리스트](internal-checklist.md)에 실제 사내 결과를 기록한 후 사용자 승인으로 Phase 0를 종료합니다.

## 5. Batch 시도와 진단

```sh
# 실행하지 않고 생성된 bootstrap과 인자만 확인 (NOT_TESTED, 코드 2)
python scripts/run_batch.py --library ALLOWED_TEST_LIB --output /approved/runs/batch-t01-plan-001 --diagnostics /approved/logs/batch-plan-001 --plan
# 실제 시도. 현재 디렉터리의 사내 초기화를 유지함
python scripts/run_batch.py --library ALLOWED_TEST_LIB --output /approved/runs/batch-t01-001 --diagnostics /approved/logs/batch-001 --timeout 300
```

SKILL 원본은 CIW와 동일합니다. Python은 shell을 통하지 않고 인자 배열로 `virtuoso -nograph -restore bootstrap.il -log CDS.log`를 실행합니다. `batch-result.json`, `bootstrap.il`, `process.log`, `CDS.log`를 사내에 보관합니다. 출력과 진단 폴더는 각각 새 경로여야 합니다. `--virtuoso /approved/path/virtuoso`로 실행 파일을 지정할 수 있습니다.

타임아웃이면 해당 직접 프로세스는 Python이 종료하지만 사이트 초기화가 별도 자식 프로세스를 띄웠다면 사내 관리자가 남은 세션을 확인해야 합니다. 라이선스/디스플레이/초기화/권한 실패는 로그로 구분합니다. Batch 실패를 우회하려고 `.cdsinit`, `cds.lib`, PDK나 lock 파일을 자동 수정하지 않습니다. 이 단계가 BLOCKED여도 필수 CIW 항목이 통과했다면 원인·우회 방법을 기록하고 사용자 승인을 받을 수 있습니다.

Batch 후보 명령의 공개 근거는 [Cadence의 Unix shell SKILL 실행 답변](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/43102/execute-skill-script-from-unix-shell)입니다. 지정 IC25.1 환경의 지원 및 라이선스 동작은 별도 확인 대상입니다.
