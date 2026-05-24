"""report_engine 단위 테스트 (SPEC-REPORT-001).

검증 항목:
- 기본 템플릿 렌더 결과가 레거시 `_build_report_fallback` 출력과 byte-for-byte 동등
- ENV(`NIF_TEMPLATE_PATH`) 오버라이드로 사용자 커스텀 템플릿 로드
- 누락 슬롯/존재하지 않는 템플릿 파일 시 fallback + stderr 경고 1줄
- daily_report.md 슬롯 집합과 context-schema.json 키 집합 동기화
- context-config.json 의 `flow_day_rows`/`rank_top_n` 값이 렌더에 반영
- 빈 ENV 문자열은 미설정과 동일 처리
"""

from __future__ import annotations

import io
import json
import os
import re
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from naver_investor_flow import report_engine


SAMPLE_FLOW = [
    {
        "date": "2026-05-22",
        "individual_eok": 10655,
        "foreign_eok": -19221,
        "institution_total_eok": 7583,
        "institution_breakdown": {},
        "foreign_etc_eok": 0,
    },
    {
        "date": "2026-05-21",
        "individual_eok": -26754,
        "foreign_eok": -2212,
        "institution_total_eok": 29008,
        "institution_breakdown": {},
        "foreign_etc_eok": 0,
    },
    {
        "date": "2026-05-20",
        "individual_eok": 100,
        "foreign_eok": 200,
        "institution_total_eok": 300,
        "institution_breakdown": {},
        "foreign_etc_eok": 0,
    },
    {
        "date": "2026-05-19",
        "individual_eok": 400,
        "foreign_eok": 500,
        "institution_total_eok": 600,
        "institution_breakdown": {},
        "foreign_etc_eok": 0,
    },
    {
        "date": "2026-05-18",
        "individual_eok": 700,
        "foreign_eok": 800,
        "institution_total_eok": 900,
        "institution_breakdown": {},
        "foreign_etc_eok": 0,
    },
    {
        "date": "2026-05-17",
        "individual_eok": 1, "foreign_eok": 2, "institution_total_eok": 3,
        "institution_breakdown": {}, "foreign_etc_eok": 0,
    },
    {
        "date": "2026-05-16",
        "individual_eok": 4, "foreign_eok": 5, "institution_total_eok": 6,
        "institution_breakdown": {}, "foreign_etc_eok": 0,
    },
]


def _sample_rank_rows(name: str = "샘플", code: str = "000001", amt: int = 1000) -> list[dict]:
    return [
        {"rank": 1, "name": name, "code": code, "quantity": 100, "amount_mn_krw": amt, "volume": 1000},
        {"rank": 2, "name": "테스트2", "code": "111111", "quantity": 50, "amount_mn_krw": amt // 2, "volume": 500},
        {"rank": 3, "name": "테스트3", "code": "222222", "quantity": 30, "amount_mn_krw": amt // 3, "volume": 300},
    ]


def _full_rank_results() -> list[tuple[tuple[str, str, str], list[dict]]]:
    return [(combo, _sample_rank_rows()) for combo in report_engine.DEAL_RANK_COMBOS]


def _make_context(
    flow_rows: list[dict] | None = None,
    rank_results=None,
    bizdate: str = "20260524",
    fetched_at: str = "2026-05-24T18:30:00+09:00",
) -> dict:
    return report_engine.build_context(
        flow_rows=flow_rows if flow_rows is not None else SAMPLE_FLOW,
        rank_results=rank_results if rank_results is not None else _full_rank_results(),
        bizdate=bizdate,
        fetched_at=fetched_at,
    )


class TestDefaultTemplateByteForByte(unittest.TestCase):
    """REQ-001/REQ-005: 기본 템플릿 렌더 = 레거시 fallback 출력 (byte-for-byte)."""

    def test_render_with_default_template_matches_legacy_output(self):
        # NIF_TEMPLATE_PATH 미설정 환경 보장
        env = {k: v for k, v in os.environ.items() if k != "NIF_TEMPLATE_PATH"}
        ctx = _make_context()
        with patch.dict(os.environ, env, clear=True):
            rendered = report_engine.render(ctx)
        legacy = report_engine._build_report_fallback(ctx)
        self.assertEqual(rendered, legacy)
        # 헤더/디스클레이머/디바이더 모두 포함
        self.assertIn("📊", rendered)
        self.assertIn("20260524", rendered)
        self.assertIn("─────────", rendered)
        self.assertIn("출처: finance.naver.com (사실 데이터, 투자 권유 아님)", rendered)


class TestEnvOverride(unittest.TestCase):
    """REQ-001: NIF_TEMPLATE_PATH 로 커스텀 템플릿 로드."""

    def test_env_override_loads_custom_template(self):
        ctx = _make_context()
        with tempdir_template("SENTINEL_XYZ {title_emoji} {bizdate}\n{flow_day_table}\n{rank_sections_block}\n{disclaimer}\n") as path:
            with patch.dict(os.environ, {"NIF_TEMPLATE_PATH": str(path)}):
                rendered = report_engine.render(ctx)
        self.assertIn("SENTINEL_XYZ", rendered)
        self.assertIn("20260524", rendered)
        self.assertIn("출처: finance.naver.com", rendered)

    def test_empty_env_path_treated_as_unset(self):
        """Edge Case 3: 빈 문자열 ENV → 기본 템플릿 사용."""
        ctx = _make_context()
        with patch.dict(os.environ, {"NIF_TEMPLATE_PATH": ""}):
            rendered = report_engine.render(ctx)
        legacy = report_engine._build_report_fallback(ctx)
        self.assertEqual(rendered, legacy)


class TestFallback(unittest.TestCase):
    """REQ-004: 누락 슬롯/파일 없음/디코드 실패 시 fallback."""

    def test_missing_slot_triggers_fallback(self):
        ctx = _make_context()
        with tempdir_template("HEADER {nonexistent_slot}\n") as path:
            with patch.dict(os.environ, {"NIF_TEMPLATE_PATH": str(path)}):
                buf = io.StringIO()
                with redirect_stderr(buf):
                    rendered = report_engine.render(ctx)
        legacy = report_engine._build_report_fallback(ctx)
        self.assertEqual(rendered, legacy)
        self.assertIn("nonexistent_slot", buf.getvalue())

    def test_missing_template_file_triggers_fallback(self):
        ctx = _make_context()
        with patch.dict(os.environ, {"NIF_TEMPLATE_PATH": "/nonexistent/path/template.md"}):
            buf = io.StringIO()
            with redirect_stderr(buf):
                rendered = report_engine.render(ctx)
        legacy = report_engine._build_report_fallback(ctx)
        self.assertEqual(rendered, legacy)
        self.assertIn("/nonexistent/path/template.md", buf.getvalue())


class TestSchemaTemplateSync(unittest.TestCase):
    """REQ-002: daily_report.md 슬롯 집합 == context-schema.json properties 키 집합."""

    def test_schema_template_sync(self):
        from importlib import resources

        pkg = resources.files("naver_investor_flow.templates")
        template_text = (pkg / "daily_report.md").read_text(encoding="utf-8")
        schema = json.loads((pkg / "context-schema.json").read_text(encoding="utf-8"))

        template_slots = set(re.findall(r"\{([a-z_][a-z0-9_]*)\}", template_text))
        schema_keys = set(schema.get("properties", {}).keys())

        self.assertEqual(
            template_slots,
            schema_keys,
            f"슬롯 불일치 — template만: {template_slots - schema_keys}, schema만: {schema_keys - template_slots}",
        )

    def test_schema_disclaimer_default_exact(self):
        """REQ-005: 디스클레이머 정확 문구가 schema default 에 존재."""
        from importlib import resources

        pkg = resources.files("naver_investor_flow.templates")
        schema = json.loads((pkg / "context-schema.json").read_text(encoding="utf-8"))
        disclaimer = schema["properties"]["disclaimer"]["default"]
        self.assertEqual(disclaimer, "출처: finance.naver.com (사실 데이터, 투자 권유 아님)")


class TestContextConfig(unittest.TestCase):
    """REQ-003: context-config.json 값이 렌더에 반영."""

    def test_context_config_drives_row_limits(self):
        # _load_config 를 패치하여 한도를 강제 변경
        with patch.object(report_engine, "_load_config", return_value={"flow_day_rows": 3, "rank_top_n": 2}):
            # 10행 flow + 10행 rank
            flow_rows = [
                {"date": f"2026-05-{30 - i:02d}", "individual_eok": i, "foreign_eok": i, "institution_total_eok": i,
                 "institution_breakdown": {}, "foreign_etc_eok": 0}
                for i in range(10)
            ]
            big_rank = [(combo, [
                {"rank": j + 1, "name": f"종목{j}", "code": f"{j:06d}", "quantity": 1, "amount_mn_krw": 100, "volume": 1}
                for j in range(10)
            ]) for combo in report_engine.DEAL_RANK_COMBOS]
            ctx = _make_context(flow_rows=flow_rows, rank_results=big_rank)
            rendered = report_engine.render(ctx)

        # flow_day 3행만
        flow_block = ctx["flow_day_table"]
        self.assertEqual(flow_block.count("\n  2026-"), 3, f"flow rows != 3 in:\n{flow_block}")
        # 각 rank 섹션 2행만 (1.\n  2. 두 줄)
        for combo in report_engine.DEAL_RANK_COMBOS:
            market, investor, side = combo
            section_key = f"rank_{market}_{investor}_{side}_top"
            self.assertIn(section_key, ctx)
            section_text = ctx[section_key]
            # "  1." 와 "  2." 각각 1번씩, "  3." 없음
            self.assertEqual(section_text.count("  1."), 1)
            self.assertEqual(section_text.count("  2."), 1)
            self.assertEqual(section_text.count("  3."), 0)
        # rendered 에도 반영됨
        self.assertIn("  1.", rendered)


# -----------------------------------------------------------------------------
# 공용 헬퍼: 임시 파일에 템플릿을 쓰고 경로를 yield
# -----------------------------------------------------------------------------


@contextmanager
def tempdir_template(content: str):
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".md", delete=False
    ) as f:
        f.write(content)
        f.flush()
        path = Path(f.name)
    try:
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    unittest.main()
