# SPEC-REPORT-001 Acceptance Criteria

## Acceptance Scenarios

### Scenario 1: Default template renders byte-for-byte identical to legacy output

**Given**
- `naver_investor_flow/templates/daily_report.md` exists in the installed package
- `context-schema.json` and `context-config.json` (with defaults `flow_day_rows=5`, `rank_top_n=3`) exist
- A fixture context dict with frozen `bizdate="20260524"`, `fetched_at="2026-05-24T18:30:00+09:00"`, 7 flow_day rows, and 8 fully-populated rank groups
- No `NIF_TEMPLATE_PATH` environment variable is set

**When**
- `report_engine.render(context)` is invoked

**Then**
- The returned string equals the output of `_build_report_fallback(context)` byte-for-byte
- All header fields appear: `📊`, `bizdate`, `fetched_at`
- The flow_day section shows exactly 5 rows (the first 5 of the 7 input rows), unit "억원"
- Each of the 8 rank sections shows exactly 3 rows, unit "백만원"
- The divider line `─────────` appears between body and disclaimer
- The disclaimer reads exactly `출처: finance.naver.com (사실 데이터, 투자 권유 아님)`
- The string ends with a single trailing newline

---

### Scenario 2: ENV override loads a custom template

**Given**
- A temporary file at `/tmp/test_custom_template.md` containing exactly: `CUSTOM {bizdate}\n{flow_day_table}\n{rank_sections_block}\n{disclaimer}\n`
- Environment variable `NIF_TEMPLATE_PATH=/tmp/test_custom_template.md` is set
- The same fixture context dict as Scenario 1

**When**
- `report_engine.render(context)` is invoked

**Then**
- The output starts with `CUSTOM 20260524`
- The flow_day table and rank sections are present (same content as Scenario 1)
- The disclaimer is present (preservation rule satisfied because the custom template included the slot)
- Default template is NOT loaded; verifiable by inserting a unique sentinel string into the custom template and asserting it appears in the output

---

### Scenario 3: Missing template file triggers fallback

**Given**
- Environment variable `NIF_TEMPLATE_PATH=/nonexistent/path/template.md` is set
- The same fixture context dict as Scenario 1

**When**
- `report_engine.render(context)` is invoked

**Then**
- A one-line warning is written to stderr, mentioning the path `/nonexistent/path/template.md` and the cause (e.g., `FileNotFoundError`)
- The returned string equals `_build_report_fallback(context)` exactly
- `render` does NOT raise an exception
- The disclaimer is present (delivered by fallback)

---

### Scenario 4: Unit asymmetry preserved (flow_day=억원 vs deal_rank=백만원)

**Given**
- Any valid template (default or custom that uses both `{flow_day_table}` and `{rank_sections_block}`)
- A context dict with realistic numeric values

**When**
- `report_engine.render(context)` is invoked

**Then**
- The substring `"억원"` appears in the rendered output, inside the flow_day section block
- The substring `"백만원"` appears in the rendered output, inside the rank sections block
- The string `"억원"` does NOT appear inside any rank section
- The string `"백만원"` does NOT appear inside the flow_day section block
- This is verified by splitting the output at section boundaries and checking each segment's unit content

---

### Scenario 5: Row limits driven by `context-config.json`

**Given**
- `context-config.json` is patched (via a tmp template directory injected through a test-only path override) to contain `{"flow_day_rows": 3, "rank_top_n": 5}`
- A context with 10 flow_day input rows and each rank group having 10 input rows
- The default template

**When**
- `report_engine.render(context)` is invoked

**Then**
- The flow_day section shows exactly 3 rows
- Each of the 8 rank sections shows exactly 5 rows
- No row-count literals (`5`, `3`) appear in `report_engine.py` source — verified by grep test asserting that `[:5]` and `[:3]` slicing on the input rows is absent (they are replaced by config-driven slicing)

---

### Scenario 6: Schema/template synchronization

**Given**
- `templates/daily_report.md` and `templates/context-schema.json` exist in the package

**When**
- `test_schema_template_sync` test is executed

**Then**
- Every slot extracted from `daily_report.md` via regex `\{([a-z_][a-z0-9_]*)\}` exists in `context-schema.json` `properties`
- Every key in `context-schema.json` `properties` appears as a slot in `daily_report.md` (no orphan schema entries)
- The two sets are exactly equal — the test fails on the slightest drift

---

### Scenario 7: CLI subcommands remain unchanged

**Given**
- `cli.py` `flow_day` subcommand invoked with `--format json`, `--format table`, `--format csv`
- `cli.py` `deal_rank` subcommand invoked with the same format options
- Identical input mock fixtures used both before and after the SPEC-REPORT-001 implementation

**When**
- Each subcommand is executed

**Then**
- The stdout output is byte-for-byte identical to the pre-SPEC output (captured as golden files in `tests/golden/cli_*.txt`)
- No CLI test in the existing suite regresses

---

## Edge Cases

### Edge Case 1: Empty flow_day rows

**Given** context with `flow_day_rows = []`
**When** render is invoked
**Then** the flow_day section header is still emitted, body is an empty line (or single dash placeholder — implementation may choose). No exception raised.

### Edge Case 2: A rank group has fewer than `rank_top_n` rows

**Given** a rank group with only 2 rows when `rank_top_n=3`
**When** render is invoked
**Then** the section shows the 2 available rows. No padding, no exception.

### Edge Case 3: `NIF_TEMPLATE_PATH` set to empty string

**Given** `NIF_TEMPLATE_PATH=""` (empty, but set)
**When** render is invoked
**Then** treated as unset; default packaged template is used. (Tested explicitly.)

### Edge Case 4: Template uses optional per-section rank slot without composite

**Given** a custom template that uses `{rank_kospi_foreign_buy_top}` directly instead of `{rank_sections_block}`
**When** render is invoked with a context that populates both forms
**Then** the per-section content renders correctly. Composite slot is unused but valid. No exception.

### Edge Case 5: Template missing the disclaimer slot

**Given** a custom template that does NOT include `{disclaimer}`
**When** render is invoked
**Then** Per REQ-005, the implementation MUST either:
- (a) Detect the absent disclaimer slot and trigger fallback (REQ-004 path), OR
- (b) Append the disclaimer string to the rendered output unconditionally
The chosen approach is documented in `plan.md` Task 2 and a test asserts the disclaimer appears in the final output.

### Edge Case 6: Non-UTF-8 bytes in custom template

**Given** `NIF_TEMPLATE_PATH` pointing to a file with invalid UTF-8 sequences
**When** render is invoked
**Then** `UnicodeDecodeError` is caught by REQ-004 fallback, stderr warning emitted, output equals legacy fallback.

### Edge Case 7: Context dict contains extra keys not referenced by template

**Given** a context dict with `unused_extra_field="x"` and a default template
**When** render is invoked
**Then** `str.format(**context)` silently ignores unused keys. No warning, no exception. Output unchanged.

### Edge Case 8: `context-config.json` corrupted or missing

**Given** `context-config.json` deleted or contains invalid JSON
**When** render is invoked
**Then** `_load_config` returns hardcoded safe defaults `{"flow_day_rows": 5, "rank_top_n": 3}`. A single stderr warning is emitted noting the config load failure. Render proceeds.

---

## Quality Gate Criteria

### Test Coverage
- `report_engine.py`: line coverage ≥ 85%, branch coverage ≥ 80%
- `collect.py`: existing coverage maintained; `_build_report_fallback` covered by Scenario 3 and any pre-existing test for `build_report`
- Schema sync test (Scenario 6) runs in standard `make test` (no live network)

### Lint & Format
- `ruff check naver_investor_flow/ tests/` exits with zero warnings
- No new files use star imports or `Any` type
- All public functions in `report_engine.py` have type hints

### LSP
- Zero LSP errors on touched files (per `.moai/config/sections/quality.yaml` run phase requirements)
- Zero new warnings introduced

### Integration
- `make test` exits 0 (full unit suite)
- `make test-live` exits 0 (includes Telegram dry-run if `TELEGRAM_BOT_TOKEN` configured)
- Manual smoke test: run `python -m naver_investor_flow.collect --dry-run` (or equivalent) and verify the printed report matches a previously captured baseline

### Security
- No `eval`, `exec`, or `os.system` introduced
- ENV path is resolved with `pathlib.Path.expanduser().resolve()` before use
- Template file is opened with explicit `encoding="utf-8"` and no `shell=True` constructs anywhere

### Documentation
- `context-schema.md` is complete: every slot has name, type, unit, default, description
- `plan.md` is updated if the missing-disclaimer behavior (Edge Case 5) decision changes during implementation

---

## Definition of Done

Implementation is **DONE** when all of the following are true:

1. All 7 acceptance scenarios pass automatically in `pytest`
2. All 8 edge cases are covered by tests (either dedicated test cases or asserted within scenario tests)
3. `tests/test_report_engine.py` exists and passes
4. `tests/test_collect_render.py` exists and passes
5. `tests/test_formatter.py` (existing) continues to pass without modification — unit asymmetry contract preserved
6. `naver_investor_flow/report_engine.py` exists with type-hinted public API: `render`, `build_context`, and documented helpers
7. `naver_investor_flow/collect.py` `build_report` is replaced by `render_report` calling the engine; `_build_report_fallback` exists with the original body preserved verbatim
8. `naver_investor_flow/templates/` directory contains 5 files: `__init__.py`, `daily_report.md`, `context-schema.md`, `context-schema.json`, `context-config.json`
9. Package data is registered so `importlib.resources.files("naver_investor_flow.templates")` works after `pip install -e .`
10. `make test` and `make test-live` both green
11. `ruff check .` clean
12. MX tags added per `spec.md` MX Tag Plan section: `@MX:LEGACY` on `_build_report_fallback`, `@MX:NOTE` + `@MX:ANCHOR` on `render_report`, `@MX:NOTE` on `_build_report_fallback` and `report_engine._load_template`
13. Commit message references `SPEC-REPORT-001` and includes a one-line summary of the user-facing change ("템플릿 기반 일일 보고서 렌더링 도입")
14. No code in `cli.py`, `formatter.py`, `parser_flow.py`, `parser_rank.py`, `http_client.py`, or `notify_telegram.py` is modified
15. The CLI `flow_day` and `deal_rank` subcommands produce byte-for-byte identical output to the pre-SPEC baseline (Scenario 7)
