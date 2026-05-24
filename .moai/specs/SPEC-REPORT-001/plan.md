# SPEC-REPORT-001 Implementation Plan

## Approach Summary

Extract the Telegram daily report's markdown synthesis from `collect.build_report()` into a dedicated `report_engine` module that loads an external markdown template, fills named slots from a context dict, and falls back to the preserved inline build path on any failure. All work is stdlib-only and additive — existing CLI behavior is untouched.

The implementation follows TDD RED → GREEN → REFACTOR. Tests are written first so that the byte-for-byte equivalence between the template-rendered output and the current `build_report()` output is verifiable from the very first GREEN commit.

---

## Task Breakdown

### Task 1 (RED): Test scaffolding for `report_engine`

Create `tests/test_report_engine.py` with the following test cases — all expected to fail until Task 2 is complete:

- `test_render_with_default_template_matches_legacy_output`: Build a fixed context dict (frozen `bizdate`, `fetched_at`, sample flow rows, sample rank rows), call `report_engine.render(context)`, and assert the result equals the output of `_build_report_fallback(context)` (which is the relocated current `build_report()` body) — byte-for-byte.
- `test_env_override_loads_custom_template`: Set `NIF_TEMPLATE_PATH` via `monkeypatch.setenv` to a tmp path containing `{title_emoji} TEST {bizdate}`, call render, assert custom string is rendered.
- `test_missing_slot_triggers_fallback`: Use a tmp template referencing `{nonexistent_slot}`, call render with a context that lacks that key, assert the result equals the fallback output and stderr contains a warning mentioning the missing slot.
- `test_missing_template_file_triggers_fallback`: Set `NIF_TEMPLATE_PATH` to `/nonexistent/path.md`, assert fallback output and stderr warning.
- `test_schema_template_sync`: Parse `templates/daily_report.md`, extract `{name}` slots via regex (`r"\{([a-z_][a-z0-9_]*)\}"`), load `context-schema.json`, assert the two sets are equal.
- `test_context_config_drives_row_limits`: Patch `context-config.json` (via tmp template dir + path injection) with `flow_day_rows=3`, `rank_top_n=5`; assert rendered flow_day section has exactly 3 rows and each rank section has 5 rows.

WHY: Tests-first ensures the template renders byte-for-byte identical output. Without this assertion baked in, a subtle whitespace drift would silently change the cron output.

### Task 2 (GREEN): Implement `report_engine.py`

Create `naver_investor_flow/report_engine.py` with:

- `_resolve_template_path() -> pathlib.Path | None` — returns ENV path if set & exists, else packaged default path via `importlib.resources.files("naver_investor_flow.templates") / "daily_report.md"`.
- `_load_template(path) -> str` — read text with `encoding="utf-8"`. Raises on failure.
- `_load_config() -> dict` — load `context-config.json` (packaged), return `{"flow_day_rows": 5, "rank_top_n": 3}` defaults if absent.
- `_build_flow_day_table(flow_rows, limit) -> str` — produces the markdown block currently inlined in `collect.build_report`. Unit: 억원. Sign: `+` for net buy.
- `_build_rank_section(market, investor, side, rows, top_n) -> str` — single section for one combo. Unit: 백만원.
- `_build_rank_sections_block(rank_groups, top_n) -> str` — joins 8 sections in `DEAL_RANK_COMBOS` order.
- `build_context(raw_data: dict) -> dict` — assemble the full context dict from collect's raw data using helpers above.
- `render(context: dict) -> str` — load template, call `template.format(**context)`. On any `(FileNotFoundError, OSError, UnicodeDecodeError, KeyError)`, log one-line warning to stderr and return `_build_report_fallback(context)` (imported lazily from `collect` to avoid circular import; or move fallback into engine and have collect re-export).

Implementation notes:
- Path traversal protection: after `pathlib.Path(env_path).expanduser().resolve()`, no further validation is required for personal use; we trust the operator who sets the env var.
- Lazy stderr warning to avoid coupling to logging config.
- All strings are UTF-8; the default template MUST end with a newline to match current behavior.

### Task 3 (RED): Integration test for collect

Create `tests/test_collect_render.py`:

- `test_collect_main_uses_render_report`: monkeypatch `report_engine.render` to return a sentinel string; run `collect.main()` (with HTTP mocked); assert Telegram payload contains the sentinel.
- `test_collect_fallback_on_render_failure`: monkeypatch `report_engine.render` to raise; assert collect proceeds, Telegram payload equals `_build_report_fallback` output, stderr has warning.
- `test_unit_asymmetry_preserved`: render with realistic context; assert `"억원"` appears in flow_day section, `"백만원"` appears in rank sections, and neither unit appears in the other's section.

### Task 4 (GREEN): Refactor `collect.py`

- Move current `build_report` body verbatim into `_build_report_fallback(context: dict) -> str`. Tag with `@MX:LEGACY` + `@MX:REASON`.
- Add new `render_report(context: dict) -> str` that calls `report_engine.render(context)`. Tag with `@MX:NOTE` + `@MX:ANCHOR`.
- In `main()`, replace the inline build with `render_report(build_context(raw_data))`.
- Verify all existing tests still pass (especially `tests/test_formatter.py` negative assertions on unit asymmetry).

### Task 5: Create template & schema files

- `naver_investor_flow/templates/__init__.py` — empty.
- `naver_investor_flow/templates/daily_report.md` — drafted by reverse-engineering the current output. Slot names match `context-schema.json`.
- `naver_investor_flow/templates/context-schema.md` — table: name | type | unit | default | description for every slot.
- `naver_investor_flow/templates/context-schema.json` — JSON Schema draft-07, all slots in `properties`, required = all header/flow/rank/footer slots, additionalProperties=false.
- `naver_investor_flow/templates/context-config.json` — `{"flow_day_rows": 5, "rank_top_n": 3}`.

### Task 6 (REFACTOR): Cleanup & consistency

- Move `LABEL_MARKET`, `LABEL_INVESTOR`, `LABEL_SIDE`, `DEAL_RANK_COMBOS` from `collect.py` to `report_engine.py` (these are formatting-layer concerns). Re-export from `collect.py` if any other module imports them — grep confirms.
- Verify `make test` passes (unit suite, no network).
- Verify `make test-live` passes (integration including Telegram dry-run if configured).
- Verify `ruff check .` is clean.

### Task 7: Package data registration — N/A (저장소 정책 반영)

- 본 저장소는 **`pyproject.toml`이 존재하지 않으며**, sdist/wheel 빌드·`pip install` 경로를 의도적으로 사용하지 않는다 (HANDOFF [HARD] §2.1 stdlib-only + 설치 불요 정책).
- 실행 형태는 항상 소스 트리 기준 `python -m naver_investor_flow.collect`. 이 경우 `importlib.resources.files("naver_investor_flow.templates")`는 소스 디렉토리에서 직접 동작하므로 `package_data` 등록이 불필요하다.
- 미래에 패키지 빌드(sdist/wheel) 도입을 결정하는 경우에만 MANIFEST.in 또는 pyproject.toml의 `[tool.setuptools.package-data]`에 `naver_investor_flow/templates/*.md` 및 `*.json`을 추가해야 한다 — 본 SPEC 범위 밖.
- [HARD] 본 SPEC을 빌미로 pyproject.toml 또는 requirements.txt를 신설하지 말 것. 두 파일 모두 의도적으로 부재하다.

---

## Single Composite vs Eight Per-Section Rank Slots — Decision Point

Two viable shapes for the deal_rank section in the template:

**Option A — single composite slot `{rank_sections_block}`**
- Pro: Template stays compact (one line for the entire rank block).
- Pro: Combo ordering is owned by code (`DEAL_RANK_COMBOS`), guaranteed consistent.
- Con: User cannot reorder sections via template alone — must change code.

**Option B — eight per-section slots `{rank_kospi_individual_buy_top}`, ...**
- Pro: Template can reorder, omit, or interleave sections freely.
- Con: Template gets ~10 extra lines; missing one slot triggers fallback (REQ-004).
- Con: Eight slot names to keep in sync with `DEAL_RANK_COMBOS`.

**Recommendation**: Implement Option A as the default template. Expose Option B by also populating the 8 per-section slots into the context dict — they cost nothing extra at build time. A user creating a custom template via `NIF_TEMPLATE_PATH` can choose to use either the composite or the individual slots. The default template uses the composite for simplicity.

This decision is reflected in the context-schema: composite slot is **required**, per-section slots are **optional** (not required by JSON Schema).

---

## Technical Stack

- Python 3.10+ (already the project baseline)
- stdlib only: `pathlib`, `importlib.resources`, `json`, `os`, `sys`, `re` (for tests)
- Test framework: pytest (already present)
- No new runtime dependencies. No new dev dependencies.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Byte-for-byte drift between template and legacy output | Medium | High (cron output changes silently) | Task 1 test asserts equality; require this test to pass before any deploy |
| Missing slot in custom template silently produces wrong output | Low | High | `str.format` raises `KeyError`; REQ-004 fallback catches it and warns |
| ENV path traversal exploitation | Very Low | Low (single-user cron) | Resolve absolute path; trust operator who controls env vars |
| Package data not bundled in install | Medium | High (FileNotFoundError on install) | Task 7 registers package data; verify with `pip install -e . && python -c "import importlib.resources; print(importlib.resources.files('naver_investor_flow.templates') / 'daily_report.md')"` |
| Circular import between `collect` and `report_engine` (fallback lives in collect, engine calls it) | Medium | Medium | Move fallback into engine OR use lazy import inside the except branch |
| Schema/template drift over time | Medium | Low | `test_schema_template_sync` enforces equality; CI catches drift |
| Unit asymmetry accidentally removed during refactor | Low | High | `test_unit_asymmetry_preserved` + existing `test_formatter.py` negative assertions |

---

## Milestones (priority-ordered, no time estimates)

**Priority High**
- M1: Tasks 1–2 complete — `report_engine.render` works with default template, tests green
- M2: Task 3 + Task 4 complete — `collect.py` uses engine, all existing tests still green
- M3: Task 5 + Task 7 complete — template files in place, package data registered, fresh install works

**Priority Medium**
- M4: Task 6 complete — labels & combos relocated, `ruff check` clean, `make test` + `make test-live` green

**Priority Low**
- M5 (future SPEC, not in this scope): Eight per-section slot documentation in `context-schema.md`, example custom template demonstrating Option B layout

---

## Reference Implementation Pointers

- Current `build_report`: `naver_investor_flow/collect.py:76-125` — direct source for the default template body
- Number formatters: `naver_investor_flow/collect.py` `_fmt_eok`, `_fmt_mn` (both `f"{v:+,}"`, only unit string differs) — preserve as-is in engine
- Label maps: `naver_investor_flow/collect.py:40-42`
- Combo enumeration: `naver_investor_flow/collect.py:29-38`
- Negative assertion contract: `tests/test_formatter.py` (unit asymmetry tests)

---

## Quality Gates

- TRUST 5: Tested (test_report_engine.py + test_collect_render.py + existing suite), Readable (slot names self-describing), Unified (ruff clean), Secured (no shell-out, no eval, path resolution safe), Trackable (commit references SPEC-REPORT-001)
- Coverage: 85%+ on `report_engine.py`
- Lint: `ruff check .` clean
- Test: `make test` green, `make test-live` green
- LSP: zero errors, zero warnings on changed files
