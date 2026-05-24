# SPEC-REPORT-001 (Compact)

## REQ

- **REQ-001 (Ubiquitous)**: 시스템은 일일 보고서 마크다운 템플릿을 외부 파일에서 로드한다 — 우선순위: (1) `NIF_TEMPLATE_PATH` ENV, (2) 패키지 기본값 `naver_investor_flow/templates/daily_report.md` (importlib.resources). 렌더링은 stdlib only (`str.format()` 권장).

- **REQ-002 (Ubiquitous)**: 시스템은 컨텍스트 변수 스키마를 두 형태로 제공한다 — `templates/context-schema.md` (사람 가독), `templates/context-schema.json` (JSON Schema). 두 파일은 동기화되며 테스트가 이를 강제한다.

- **REQ-003 (Ubiquitous)**: 행 수 한도(`flow_day_rows`, `rank_top_n`)는 `templates/context-config.json`에 명시한다 — 코드 내 숫자 리터럴 금지.

- **REQ-004 (Event-Driven)**: 템플릿 경로 부재 / 로드 실패 / 슬롯 누락(`KeyError`) 발생 시 — 시스템은 보존된 `_build_report_fallback(context)`(현 `build_report()` 본문 그대로)로 폴백하고 stderr에 한 줄 경고를 출력한다. collect 실행은 중단되지 않는다.

- **REQ-005 (Unwanted)**: 비-stdlib 의존성 도입 금지 / flow_day=억원 vs deal_rank=백만원 비대칭 통일 금지 / 디스클레이머 제거·변경 금지 / `cli.py` 출력 변경 금지 / 렌더 결과 디스크 영구 저장 금지.

---

## Acceptance Scenarios

1. **기본 템플릿 = 레거시 출력**: `render(context)` 결과가 `_build_report_fallback(context)`와 byte-for-byte 동일.
2. **ENV 오버라이드**: `NIF_TEMPLATE_PATH` 설정 시 커스텀 템플릿이 로드되고 디스클레이머는 유지.
3. **파일 없음 → 폴백**: 존재하지 않는 ENV 경로 → stderr 경고 + 폴백 출력, 예외 없음.
4. **단위 비대칭 보존**: 출력에 "억원"은 flow_day 섹션에만, "백만원"은 rank 섹션에만 등장. 두 단위가 한 섹션 안에서 섞이지 않음.
5. **행 수 한도 외부화**: `context-config.json`에서 `flow_day_rows=3`, `rank_top_n=5` 설정 시 출력 행 수가 정확히 반영. 코드에 `[:5]`, `[:3]` 리터럴 없음.
6. **스키마/템플릿 동기화**: 기본 템플릿의 슬롯 집합 = `context-schema.json` properties 집합.
7. **CLI 불변**: `flow_day`, `deal_rank` 서브커맨드의 json/table/csv 출력이 SPEC 적용 전후 동일.

---

## Files

**MODIFY**
- `naver_investor_flow/collect.py` — `build_report` → `render_report` 위임, `_build_report_fallback` 보존

**NEW**
- `naver_investor_flow/report_engine.py` — 템플릿 로드·슬롯 빌드·렌더·폴백 오케스트레이션
- `naver_investor_flow/templates/__init__.py`
- `naver_investor_flow/templates/daily_report.md` — 기본 템플릿 (현 출력과 byte-equivalent)
- `naver_investor_flow/templates/context-schema.md` — 사람 가독 변수 명세
- `naver_investor_flow/templates/context-schema.json` — JSON Schema (draft-07)
- `naver_investor_flow/templates/context-config.json` — `{"flow_day_rows": 5, "rank_top_n": 3}`

**NEW TESTS**
- `tests/test_report_engine.py` — 슬롯 채움, ENV 오버라이드, 폴백, 스키마 동기화, 행수 한도
- `tests/test_collect_render.py` — collect 통합, 폴백 회귀, 단위 비대칭

**UNCHANGED**
- `cli.py`, `formatter.py`, `parser_flow.py`, `parser_rank.py`, `http_client.py`, `notify_telegram.py`

---

## Exclusions (What NOT to Build)

- Jinja2 / Mako / Mustache 등 외부 템플릿 엔진
- CLI `flow_day` / `deal_rank` 서브커맨드 출력 변경
- Telegram 4096자 한도 분할 처리
- 다국어(i18n) 지원
- 단위 통일 (억원 ↔ 백만원)
- 디스클레이머 제거·이동
- 렌더 결과·중간물 디스크 영구 저장
- HTML / PDF 출력
- 렌더 중 외부 네트워크 호출
- 템플릿 핫리로드 watcher
