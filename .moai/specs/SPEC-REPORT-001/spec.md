---
id: SPEC-REPORT-001
version: 0.1.0
status: draft
created: 2026-05-24
updated: 2026-05-24
author: Chinseok
priority: medium
issue_number: 0
---

# SPEC-REPORT-001: Telegram 보고서 템플릿 외부화 (Slot-fill)

## HISTORY

- 2026-05-24 (v0.1.0): 초안 작성. `collect.py`의 `build_report()`가 코드 안에서 합성하던 Telegram 메시지를 외부 마크다운 템플릿(`templates/daily_report.md`)과 컨텍스트 스키마(`context-schema.json`)로 분리. stdlib only 제약, 단위 비대칭(억원/백만원) 보존, CLI 출력 불변, 디스클레이머 보존 등 [HARD] 제약 명시. issue_number는 추후 결정.

---

## Overview

### 배경

현재 `naver_investor_flow/collect.py`의 `build_report()` 함수(라인 76–125)는 Telegram으로 전송할 일일 보고서의 마크다운 문자열을 코드 내부에서 직접 합성한다. 헤더 형식, 섹션 구분자, 행 수 한도(`flow_rows[:5]`, `rows[:3]`), 라벨 매핑, 수치 포맷이 모두 파이썬 소스에 하드코딩되어 있다.

보고서 양식을 한 줄이라도 바꾸려면 코드를 수정·테스트·배포해야 하며, cron 환경에서 운영 중인 점을 고려하면 형식 실험을 위한 사이클 비용이 과도하다.

### 목표

`collect.py`가 합성하는 Telegram 보고서를 다음 두 축으로 외부화한다:

1. **보고서 형식**: 마크다운 템플릿 파일(`naver_investor_flow/templates/daily_report.md`)로 분리. 슬롯(`{변수명}`)을 채우는 stdlib 기반 slot-fill 방식.
2. **Context 데이터 구성**: 컨텍스트 변수의 이름·타입·단위·기본값을 명세하는 `context-schema.md`(사람 가독)와 `context-schema.json`(JSON Schema), 그리고 행 수 한도 등 조정 가능 값을 담은 `context-config.json`.

코드 수정 없이 템플릿과 설정 파일만 바꾸어 보고서 형식과 데이터 구성을 변경할 수 있도록 한다.

### 비목표 (Non-Goals)

- CLI 서브커맨드(`flow_day`, `deal_rank`) 출력 형식 변경
- Telegram 4096자 한도 자동 분할 (별도 SPEC에서 다룸)
- 다국어(i18n) 템플릿 지원 (별도 SPEC)
- 외부 템플릿 엔진 도입 (Jinja2, Mako 등 — 금지)

---

## EARS Requirements

### REQ-001: 템플릿 외부화 (Ubiquitous)

The system **shall** load the daily report markdown template from an external file, resolved in this priority order:

1. Path specified by the `NIF_TEMPLATE_PATH` environment variable, when set and non-empty.
2. Packaged default at `naver_investor_flow/templates/daily_report.md`, accessed via `importlib.resources.files`.

The template **shall** be a plain Markdown file containing slot placeholders compatible with Python's stdlib formatting (`str.format()` is the chosen mechanism — `string.Template` is acceptable but `str.format()` is preferred for consistency).

The system **shall** use only the Python standard library to load and render the template. No third-party templating dependency may be introduced.

### REQ-002: Context 스키마 명세 (Ubiquitous)

The system **shall** provide a context schema in two complementary forms within the `naver_investor_flow/templates/` directory:

1. `context-schema.md` — human-readable specification enumerating every slot variable with: name, type, unit (억원 / 백만원 / 없음), example value, and description.
2. `context-schema.json` — JSON Schema (draft-07 or later) suitable for programmatic validation of the context dict before rendering.

The two files **shall** stay in sync: a test in `tests/test_report_engine.py` **shall** assert that every slot referenced in the default template appears in both schema files, and vice versa. Adding a new slot to the template **shall** require updating the schema first; otherwise the test fails.

### REQ-003: 행 수 한도 외부화 (Ubiquitous)

The flow_day row-count limit (currently hard-coded as `flow_rows[:5]` in `collect.py`) and the deal_rank TOP-N per combo (currently `rows[:3]`) **shall** be specified in `naver_investor_flow/templates/context-config.json` as integer fields `flow_day_rows` (default 5) and `rank_top_n` (default 3). The values **shall** be loaded at render time and **shall not** appear as numeric literals in the rendering code.

### REQ-004: Fallback 동작 (Event-Driven)

**When** the resolved template path does not exist, **or** template file load fails (I/O error, decode error), **or** rendering fails because the template references a slot not present in the context dict (`KeyError` from `str.format`), **then** the system **shall** fall back to the prior inline-build behavior — preserved verbatim as a private function `_build_report_fallback(context: dict) -> str` derived from the current `build_report()` body (collect.py lines 76–125).

The system **shall** emit a single-line warning to stderr identifying the cause (template path, missing slot name, or I/O error message). The system **shall not** abort the collect run because of a template error; Telegram delivery must continue.

### REQ-005: 절대 제약 (Unwanted)

The template engine **shall not** introduce any non-stdlib dependency. **If** a contributor adds a third-party templating package to `requirements.txt` or `pyproject.toml` for this feature, **then** the change must be rejected.

The system **shall not** unify the flow_day unit (억원) and deal_rank unit (백만원) into a single common unit. The asymmetry is intentional and load-bearing; the existing negative assertions in `tests/test_formatter.py` that verify this asymmetry **shall** continue to pass without modification.

The template renderer **shall not** remove, alter, or relocate the disclaimer string ("출처: finance.naver.com (사실 데이터, 투자 권유 아님)"). The default template **shall** contain the disclaimer slot, and the slot's default value **shall** include the exact disclaimer text. **If** a custom template (loaded via `NIF_TEMPLATE_PATH`) omits the disclaimer slot, the fallback path (REQ-004) applies because the rendered output would be missing required content; alternatively, the renderer **may** append the disclaimer after rendering — the implementation chooses one approach and documents it in `plan.md`.

The CLI subcommands `flow_day` and `deal_rank` (defined in `cli.py`) **shall not** be affected by any changes introduced by this SPEC. Their json/table/csv outputs **shall** remain byte-for-byte identical for identical inputs.

The renderer **shall not** persist the rendered output, intermediate context dicts, or template content to disk. Output goes only to stdout and the Telegram delivery pipeline.

---

## Context Variables (Summary)

The full enumeration lives in `templates/context-schema.md` once implemented. This section is the canonical SPEC-level list:

**Header slots**
- `title_emoji` (str, default `"📊"`)
- `bizdate` (str, format `YYYYMMDD`)
- `fetched_at` (str, ISO 8601 KST)

**Flow-day slots**
- `flow_day_table` (str, pre-rendered markdown block — 한 줄당 한 영업일, 단위 억원)
- `flow_day_rows_limit` (int, from `context-config.json`)

**Deal-rank slots** (8 combos × market/investor/side)

The default template uses a single composite slot for simplicity, with eight slots offered as opt-in for layouts that need re-ordering:

- Composite (default): `rank_sections_block` (str, all 8 sections joined)
- Per-section (optional): `rank_kospi_individual_buy_top`, `rank_kospi_individual_sell_top`, `rank_kospi_foreign_buy_top`, `rank_kospi_foreign_sell_top`, `rank_kospi_institution_buy_top`, `rank_kospi_institution_sell_top`, `rank_kosdaq_foreign_buy_top`, `rank_kosdaq_foreign_sell_top` (each str)
- `rank_top_n` (int, from `context-config.json`)

**Footer slots**
- `divider` (str, default `"─────────"`)
- `disclaimer` (str, default `"출처: finance.naver.com (사실 데이터, 투자 권유 아님)"`)

---

## Files to Modify / Create

**MODIFY**
- `naver_investor_flow/collect.py` — split `build_report()`:
  - new public `render_report(context: dict) -> str` (delegates to `report_engine.render`)
  - existing logic preserved verbatim as `_build_report_fallback(context: dict) -> str`
  - `main()` calls `render_report` and falls back on exception

**NEW**
- `naver_investor_flow/templates/__init__.py` — empty package marker for `importlib.resources`
- `naver_investor_flow/templates/daily_report.md` — default template (renders byte-for-byte identical to current output)
- `naver_investor_flow/templates/context-schema.md` — human-readable variable spec
- `naver_investor_flow/templates/context-schema.json` — JSON Schema (draft-07)
- `naver_investor_flow/templates/context-config.json` — adjustable values (`flow_day_rows`, `rank_top_n`)
- `naver_investor_flow/report_engine.py` — template load, slot-builder helpers, render, fallback orchestration

**NEW TESTS**
- `tests/test_report_engine.py` — slot fill, missing-slot fallback, ENV override, schema/template sync
- `tests/test_collect_render.py` — `render_report` integration, fallback regression, unit-asymmetry preservation

**UNCHANGED**
- `cli.py`, `formatter.py`, `parser_flow.py`, `parser_rank.py`, `http_client.py`, `notify_telegram.py`

---

## MX Tag Plan

- `collect.build_report` (the body that will be relocated to `_build_report_fallback`) → `@MX:LEGACY` with `@MX:REASON: preserved as fallback for REQ-004; do not delete`
- New public `render_report` in `report_engine.py` → `@MX:NOTE` (intent: slot-fill template renderer) + `@MX:ANCHOR` (expected fan_in 2: `collect.main` and tests)
- `_build_report_fallback` in `collect.py` → `@MX:NOTE` referencing REQ-004 fallback contract
- `report_engine._load_template` → `@MX:WARN` if ENV path traversal protection is non-trivial; otherwise `@MX:NOTE`

---

## Exclusions (What NOT to Build)

The following items are explicitly **out of scope** for SPEC-REPORT-001 and **shall not** be addressed in its implementation:

1. **External template engines** — Jinja2, Mako, Mustache implementations, or any non-stdlib templating library. stdlib `str.format()` / `string.Template` only.
2. **CLI subcommand changes** — `cli.py` `flow_day` and `deal_rank` subcommands, including their json/table/csv output formats, must remain unchanged.
3. **Telegram 4096-character limit handling** — splitting, truncation, multi-message delivery. Deferred to a separate SPEC.
4. **Internationalization (i18n)** — multilingual templates, locale-aware formatting. Deferred.
5. **Unit unification** — converting 억원 ↔ 백만원 or introducing a common unit. The asymmetry is preserved by [HARD] rule.
6. **Disclaimer removal or relocation** — the disclaimer text and its position at the report footer is contractual.
7. **Disk persistence** — saving rendered output, intermediate context dicts, or template content to disk. Output is stdout + Telegram only.
8. **HTML or PDF output formats** — markdown for Telegram only.
9. **WebFetch / external network calls** during render — render is a pure function of context dict and template file.
10. **Template hot-reload watcher** — templates are loaded once per collect run.

---

## References

- Current implementation: `naver_investor_flow/collect.py` lines 76–125 (`build_report` function)
- Label maps: `naver_investor_flow/collect.py` lines 40–42 (`LABEL_MARKET`, `LABEL_INVESTOR`, `LABEL_SIDE`)
- Combo enumeration: `naver_investor_flow/collect.py` lines 29–38 (`DEAL_RANK_COMBOS`)
- Number formatters: `naver_investor_flow/collect.py` `_fmt_eok` / `_fmt_mn` (both use `f"{v:+,}"`; unit-string differs)
- Negative assertion to preserve: `tests/test_formatter.py` — verifies flow_day=억원 vs deal_rank=백만원 asymmetry
