# 오프라인 환경 및 소스 반입

Python **3.10 이상**과 Virtuoso IC25.1-64b.SM_ISR7.10 사내 설치가 필요합니다. Python 런타임 의존 패키지는 없습니다. 개발 PC의 테스트는 Python 3.14에서 수행하며 사내 Python 버전에서도 동일 테스트를 다시 실행합니다.

1. 승인된 경로로 `pgcheck/`, `skill/`, `scripts/`, `schema/`, `tests/`, `docs/`, README와 pyproject.toml을 반입합니다. 실제 설계 데이터, 라이선스 값, 계정 비밀번호를 소스에 넣지 않습니다.
2. 프로젝트 루트에서 `python -m unittest discover -s tests -v`를 실행합니다. 패키지 설치나 관리자 권한 없이 실행 가능합니다.
3. 승인된 출력 부모 폴더와 로그 폴더를 사내에서 만듭니다. 결과와 로그를 공용 소스 저장소에 넣지 않습니다. `.gitignore`는 `runs/`, `local-results/`, `*.log`를 기본 제외합니다.
4. 사이트가 사용하던 Virtuoso 초기화, PDK, `cds.lib`, 라이선스를 유지합니다. 이 프로그램은 이 파일들을 변경하지 않습니다.
5. 실제 설치된 UTF-8 locale로 Virtuoso를 시작하고 Python에서 실제 파일을 엄격히 UTF-8 파싱합니다. Python은 파일마다 `encoding='utf-8'`를 명시합니다.

선택적으로 설치형 CLI가 필요하면 사내 승인 wheelhouse의 setuptools(61 이상)를 사용합니다. 기본 실행에는 이 설치 단계가 필요 없습니다.

```sh
python -m pip install --no-index --find-links /approved/wheelhouse --no-build-isolation .
```

이 명령 전에 사내 환경에 setuptools가 설치되어 있어야 합니다. 누락되면 승인된 오프라인 경로에서 설치하거나 설치 없이 소스 폴더에서 실행합니다. 인터넷 fallback을 요구하거나 구현하지 않습니다. 런타임에는 외부 통신·로그 전송·Telemetry가 없습니다. 문서의 공개 링크는 개발 참고 출처이며 사내 실행에 접속할 필요가 없습니다.

개발자가 직접 수정할 때 JSON 필드/ID 변경은 `docs/schema.md`, `pgcheck/schema.py`, `schema/*.schema.json`, SKILL Exporter, 합성 테스트를 함께 맞춥니다. Schema JSON은 Python의 SCHEMAS와 같은 정의입니다. `$schema` URI는 규격 식별자이며 Validator가 네트워크로 가져오지 않습니다.
