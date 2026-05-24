"""collect.py 단위 테스트.

라이브 호출 없이 mock으로:
- build_report가 8조합 + flow_day 헤더를 마크다운으로 정확 생성
- fetch_flow_day가 bizdate 미지정 시 KST 오늘 날짜 자동 주입
- fetch_deal_rank가 8조합 URL을 올바르게 빌드
- main()이 텔레그램 환경변수 없을 때 stdout만 출력
- main()이 모든 페치 실패 시 exit code 1
"""

import datetime
import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from naver_investor_flow import collect


SAMPLE_FLOW = [
    {
        "date": "2026-05-22",
        "individual_eok": 10655,
        "foreign_eok": -19221,
        "institution_total_eok": 7583,
        "institution_breakdown": {
            "financial_inv": 7815, "insurance": -635, "trust": 1435,
            "bank": 6, "other_finance": 123, "pension": -1161,
        },
        "foreign_etc_eok": 984,
    },
    {
        "date": "2026-05-21",
        "individual_eok": -26754,
        "foreign_eok": -2212,
        "institution_total_eok": 29008,
        "institution_breakdown": {"financial_inv": 0, "insurance": 0, "trust": 0, "bank": 0, "other_finance": 0, "pension": 0},
        "foreign_etc_eok": 0,
    },
]


def _sample_rank_rows(name: str, code: str, amt: int) -> list[dict]:
    return [
        {"rank": 1, "name": name, "code": code, "quantity": 100, "amount_mn_krw": amt, "volume": 1000},
        {"rank": 2, "name": "테스트2", "code": "111111", "quantity": 50, "amount_mn_krw": amt // 2, "volume": 500},
        {"rank": 3, "name": "테스트3", "code": "222222", "quantity": 30, "amount_mn_krw": amt // 3, "volume": 300},
    ]


class TestFetchFlowDay(unittest.TestCase):
    def test_uses_kst_today_when_bizdate_omitted(self):
        captured = []

        def fake_fetch_html(url, referer=None):
            captured.append((url, referer))
            return "<html></html>"

        with patch("naver_investor_flow.collect.http_client.fetch_html", side_effect=fake_fetch_html):
            with patch("naver_investor_flow.collect.parser_flow.parse_flow_day", return_value=[]):
                collect.fetch_flow_day()

        url, referer = captured[0]
        kst = datetime.timezone(datetime.timedelta(hours=9))
        expected_date = datetime.datetime.now(kst).strftime("%Y%m%d")
        self.assertIn(f"bizdate={expected_date}", url)
        self.assertEqual(referer, collect.REFERER_FLOW)

    def test_explicit_bizdate_passes_through(self):
        captured = []
        def fake_fetch_html(url, referer=None):
            captured.append(url)
            return "<html></html>"
        with patch("naver_investor_flow.collect.http_client.fetch_html", side_effect=fake_fetch_html):
            with patch("naver_investor_flow.collect.parser_flow.parse_flow_day", return_value=[]):
                collect.fetch_flow_day(bizdate="20260520")
        self.assertIn("bizdate=20260520", captured[0])


class TestFetchDealRank(unittest.TestCase):
    def test_url_8_combinations(self):
        seen = []

        def fake_fetch_html(url, referer=None):
            seen.append((url, referer))
            return "<html></html>"

        with patch("naver_investor_flow.collect.http_client.fetch_html", side_effect=fake_fetch_html):
            with patch("naver_investor_flow.collect.parser_rank.parse_deal_rank", return_value=[]):
                for combo in collect.DEAL_RANK_COMBOS:
                    collect.fetch_deal_rank(*combo)

        self.assertEqual(len(seen), 8)
        for (url, referer), (market, investor, side) in zip(seen, collect.DEAL_RANK_COMBOS):
            self.assertIn(f"sosok={collect.MARKET_MAP[market]}", url)
            self.assertIn(f"investor_gubun={collect.INVESTOR_MAP[investor]}", url)
            self.assertIn(f"type={side}", url)
            self.assertEqual(referer, collect.REFERER_RANK)


class TestBuildReport(unittest.TestCase):
    def test_includes_header_and_disclaimer(self):
        rank = [(combo, _sample_rank_rows("샘플", "000001", 1000)) for combo in collect.DEAL_RANK_COMBOS]
        report = collect.build_report(
            SAMPLE_FLOW, rank, bizdate="20260523", fetched_at="2026-05-23T18:10:00+09:00"
        )
        self.assertIn("네이버 투자자 매매동향", report)
        self.assertIn("기준일 20260523", report)
        self.assertIn("사실 데이터, 투자 권유 아님", report)

    def test_all_8_combos_appear_in_order(self):
        rank = [(combo, _sample_rank_rows("샘플", "000001", 1000)) for combo in collect.DEAL_RANK_COMBOS]
        report = collect.build_report(
            SAMPLE_FLOW, rank, bizdate="20260523", fetched_at="x"
        )
        # 8조합 헤더가 모두 등장하고 순서 일관
        idx_prev = -1
        for market, investor, side in collect.DEAL_RANK_COMBOS:
            header = f"▎{collect.LABEL_MARKET[market]} {collect.LABEL_INVESTOR[investor]} {collect.LABEL_SIDE[side]} TOP3"
            idx = report.find(header)
            self.assertNotEqual(idx, -1, f"{header} 누락")
            self.assertGreater(idx, idx_prev, f"{header} 순서 어긋남")
            idx_prev = idx

    def test_flow_day_top5_displayed(self):
        rank = [(combo, []) for combo in collect.DEAL_RANK_COMBOS]
        report = collect.build_report(SAMPLE_FLOW, rank, bizdate="20260523", fetched_at="x")
        self.assertIn("2026-05-22", report)
        self.assertIn("개인 +10,655", report)
        self.assertIn("외국인 -19,221", report)

    def test_empty_flow_day_shows_marker(self):
        rank = [(combo, []) for combo in collect.DEAL_RANK_COMBOS]
        report = collect.build_report([], rank, bizdate="20260523", fetched_at="x")
        self.assertIn("일별 시장 매매", report)
        self.assertIn("(데이터 없음)", report)

    def test_empty_rank_combo_shows_marker(self):
        rank = [(combo, []) for combo in collect.DEAL_RANK_COMBOS]
        report = collect.build_report(SAMPLE_FLOW, rank, bizdate="20260523", fetched_at="x")
        # 8조합 모두 (데이터 없음) 표시
        self.assertGreaterEqual(report.count("(데이터 없음)"), 8)

    def test_missing_code_shows_dashes(self):
        rows = [{"rank": 1, "name": "노코드", "code": None, "quantity": 1, "amount_mn_krw": 100, "volume": 1}]
        rank = [(collect.DEAL_RANK_COMBOS[0], rows)] + [(c, []) for c in collect.DEAL_RANK_COMBOS[1:]]
        report = collect.build_report([], rank, bizdate="x", fetched_at="x")
        self.assertIn("노코드 (------)", report)


class TestMain(unittest.TestCase):
    def test_main_no_telegram_env_stdout_only(self):
        """텔레그램 환경변수 없으면 send_message 호출 안 함, exit 0"""
        with patch("naver_investor_flow.collect.fetch_flow_day", return_value=SAMPLE_FLOW):
            with patch("naver_investor_flow.collect.fetch_deal_rank",
                       return_value=_sample_rank_rows("S", "000001", 1000)):
                with patch.dict("os.environ", {}, clear=True):
                    with patch("naver_investor_flow.notify_telegram.send_message") as mock_send:
                        buf_out, buf_err = io.StringIO(), io.StringIO()
                        with redirect_stdout(buf_out), redirect_stderr(buf_err):
                            code = collect.main()
        self.assertEqual(code, 0)
        mock_send.assert_not_called()
        self.assertIn("네이버 투자자 매매동향", buf_out.getvalue())
        self.assertIn("미설정", buf_err.getvalue())

    def test_main_no_telegram_flag_skips_send_even_with_env(self):
        """--no-telegram 플래그는 env가 있어도 send_message 호출을 막는다."""
        with patch("naver_investor_flow.collect.fetch_flow_day", return_value=SAMPLE_FLOW):
            with patch("naver_investor_flow.collect.fetch_deal_rank",
                       return_value=_sample_rank_rows("S", "000001", 1000)):
                with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": "C"}, clear=True):
                    with patch("naver_investor_flow.collect.notify_telegram.send_message") as mock_send:
                        buf_out, buf_err = io.StringIO(), io.StringIO()
                        with redirect_stdout(buf_out), redirect_stderr(buf_err):
                            code = collect.main(["--no-telegram"])
        self.assertEqual(code, 0)
        mock_send.assert_not_called()
        self.assertIn("네이버 투자자 매매동향", buf_out.getvalue())
        # stderr 에 dry-run 표시 (no-telegram 명시)
        self.assertIn("--no-telegram", buf_err.getvalue())

    def test_main_with_telegram_env_calls_send(self):
        """환경변수 있으면 send_message 호출"""
        with patch("naver_investor_flow.collect.fetch_flow_day", return_value=SAMPLE_FLOW):
            with patch("naver_investor_flow.collect.fetch_deal_rank",
                       return_value=_sample_rank_rows("S", "000001", 1000)):
                with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": "C"}, clear=True):
                    with patch("naver_investor_flow.collect.notify_telegram.send_message", return_value=True) as mock_send:
                        buf_out, buf_err = io.StringIO(), io.StringIO()
                        with redirect_stdout(buf_out), redirect_stderr(buf_err):
                            code = collect.main()
        self.assertEqual(code, 0)
        mock_send.assert_called_once()
        # 첫 인자가 보고서 본문
        args, kwargs = mock_send.call_args
        body = args[0] if args else kwargs.get("text", "")
        self.assertIn("네이버 투자자 매매동향", body)

    def test_main_all_fetches_fail_returns_exit_1(self):
        """모든 페치 실패 시 exit code 1"""
        def boom(*a, **kw):
            raise RuntimeError("simulated")
        with patch("naver_investor_flow.collect.fetch_flow_day", side_effect=boom):
            with patch("naver_investor_flow.collect.fetch_deal_rank", side_effect=boom):
                with patch.dict("os.environ", {}, clear=True):
                    buf_out, buf_err = io.StringIO(), io.StringIO()
                    with redirect_stdout(buf_out), redirect_stderr(buf_err):
                        code = collect.main()
        self.assertEqual(code, 1)

    def test_main_partial_failure_returns_0(self):
        """flow 실패해도 rank 성공이면 exit 0 (graceful)"""
        def boom(*a, **kw):
            raise RuntimeError("flow boom")
        with patch("naver_investor_flow.collect.fetch_flow_day", side_effect=boom):
            with patch("naver_investor_flow.collect.fetch_deal_rank",
                       return_value=_sample_rank_rows("S", "000001", 1000)):
                with patch.dict("os.environ", {}, clear=True):
                    buf_out, buf_err = io.StringIO(), io.StringIO()
                    with redirect_stdout(buf_out), redirect_stderr(buf_err):
                        code = collect.main()
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
