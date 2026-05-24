"""collect 모듈의 신규 render 경로 통합 테스트 (SPEC-REPORT-001).

- main() 이 report_engine.render 를 경유하는지
- render 가 실패하면 fallback 으로 collect 가 계속 진행되는지
- flow_day=억원, deal_rank=백만원 단위 비대칭이 유지되는지
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from naver_investor_flow import collect, report_engine


SAMPLE_FLOW = [
    {
        "date": "2026-05-22",
        "individual_eok": 10655,
        "foreign_eok": -19221,
        "institution_total_eok": 7583,
        "institution_breakdown": {},
        "foreign_etc_eok": 0,
    },
]


def _sample_rank_rows() -> list[dict]:
    return [
        {"rank": 1, "name": "삼성전자", "code": "005930", "quantity": 1, "amount_mn_krw": 1095426, "volume": 1},
        {"rank": 2, "name": "현대차", "code": "005380", "quantity": 1, "amount_mn_krw": 77272, "volume": 1},
        {"rank": 3, "name": "테스트", "code": "999999", "quantity": 1, "amount_mn_krw": 1000, "volume": 1},
    ]


class TestCollectMainUsesEngine(unittest.TestCase):
    def test_collect_main_uses_render_report(self):
        """main() 이 report_engine.render 결과를 stdout 으로 내보낸다."""
        sentinel = "SENTINEL_RENDERED_OUTPUT_42"
        with patch("naver_investor_flow.collect.fetch_flow_day", return_value=SAMPLE_FLOW):
            with patch("naver_investor_flow.collect.fetch_deal_rank", return_value=_sample_rank_rows()):
                with patch("naver_investor_flow.collect.report_engine.render", return_value=sentinel):
                    with patch.dict("os.environ", {}, clear=True):
                        buf_out = io.StringIO()
                        buf_err = io.StringIO()
                        with redirect_stdout(buf_out), redirect_stderr(buf_err):
                            code = collect.main()
        self.assertEqual(code, 0)
        self.assertIn(sentinel, buf_out.getvalue())


class TestCollectFallbackOnRenderFailure(unittest.TestCase):
    def test_collect_fallback_on_render_failure(self):
        """report_engine.render 가 예외를 던지면 collect 는 fallback 으로 보고서 작성."""
        def boom_render(context):
            raise RuntimeError("simulated engine crash")

        with patch("naver_investor_flow.collect.fetch_flow_day", return_value=SAMPLE_FLOW):
            with patch("naver_investor_flow.collect.fetch_deal_rank", return_value=_sample_rank_rows()):
                with patch("naver_investor_flow.collect.report_engine.render", side_effect=boom_render):
                    with patch.dict("os.environ", {}, clear=True):
                        buf_out = io.StringIO()
                        buf_err = io.StringIO()
                        with redirect_stdout(buf_out), redirect_stderr(buf_err):
                            code = collect.main()
        # collect 자체는 계속 진행
        self.assertEqual(code, 0)
        # stdout 에 보고서 본문 존재 (fallback 경로)
        out = buf_out.getvalue()
        self.assertIn("네이버 투자자 매매동향", out)
        self.assertIn("출처: finance.naver.com", out)
        # stderr 에 경고 1줄
        self.assertIn("render", buf_err.getvalue().lower() + buf_err.getvalue())


class TestUnitAsymmetryPreserved(unittest.TestCase):
    """REQ-005: flow_day=억원, deal_rank=백만원. 통일 금지."""

    def test_unit_asymmetry_preserved(self):
        ctx = report_engine.build_context(
            SAMPLE_FLOW,
            [(combo, _sample_rank_rows()) for combo in report_engine.DEAL_RANK_COMBOS],
            bizdate="20260524",
            fetched_at="2026-05-24T18:30:00+09:00",
        )
        rendered = report_engine.render(ctx)

        # flow_day 블록에는 '억원' 존재, '백만원' 부재
        flow_block = ctx["flow_day_table"]
        self.assertIn("억원", flow_block)
        self.assertNotIn("백만원", flow_block)

        # 각 rank 섹션에는 '백만원' 존재, '억원' 부재
        for combo in report_engine.DEAL_RANK_COMBOS:
            market, investor, side = combo
            key = f"rank_{market}_{investor}_{side}_top"
            section = ctx[key]
            self.assertIn("백만원", section, f"{key} 에 '백만원' 누락")
            self.assertNotIn("억원", section, f"{key} 에 '억원' 혼입")

        # 통합 출력에서도 양쪽 단위가 모두 등장
        self.assertIn("억원", rendered)
        self.assertIn("백만원", rendered)


if __name__ == "__main__":
    unittest.main()
