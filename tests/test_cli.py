"""
M-5: main.py CLI 통합 테스트
- argparse 서브커맨드 정상 동작
- 잘못된 인자 exit code 64
- HTTP 오류 exit code 2
- 네트워크 오류 exit code 4
- 파싱 오류 exit code 3
- 인코딩 오류 exit code 5
- 빈 응답 exit code 0
- --format 옵션
- --limit 옵션
- flow_day --bizdate 옵션
"""

import sys
import os
import unittest
import json
import subprocess
from unittest.mock import patch

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_main(*args, input_=None) -> tuple[str, str, int]:
    """main.py를 서브프로세스로 실행하여 (stdout, stderr, exitcode) 반환."""
    result = subprocess.run(
        [sys.executable, "-m", "naver_investor_flow"] + list(args),
        capture_output=True,
        text=True,
        input=input_,
        cwd=_REPO_ROOT,
    )
    return result.stdout, result.stderr, result.returncode


# ──────────────────────────────────────────────
# 직접 import 기반 테스트 (mock 사용)
# ──────────────────────────────────────────────


def _add_scripts_path():
    # conftest.py가 sys.path를 처리하므로 no-op
    pass


class TestCliArguments(unittest.TestCase):
    """argparse 인자 검증"""

    def test_no_subcommand_exits_nonzero(self):
        """서브커맨드 없이 실행 시 비정상 종료"""
        _, _, code = run_main()
        self.assertNotEqual(code, 0)

    def test_deal_rank_missing_market_exits_64(self):
        """--market 없으면 exit 64"""
        _, stderr, code = run_main("deal_rank", "--investor", "foreign", "--side", "buy")
        self.assertEqual(code, 64)
        self.assertIn("market", stderr.lower())

    def test_deal_rank_missing_investor_exits_64(self):
        """--investor 없으면 exit 64"""
        _, stderr, code = run_main("deal_rank", "--market", "kospi", "--side", "buy")
        self.assertEqual(code, 64)

    def test_deal_rank_missing_side_exits_64(self):
        """--side 없으면 exit 64"""
        _, stderr, code = run_main("deal_rank", "--market", "kospi", "--investor", "foreign")
        self.assertEqual(code, 64)

    def test_deal_rank_invalid_market_exits_64(self):
        """허용 값 외 --market → exit 64"""
        _, stderr, code = run_main(
            "deal_rank", "--market", "krx", "--investor", "foreign", "--side", "buy"
        )
        self.assertEqual(code, 64)
        self.assertIn("kospi", stderr.lower())

    def test_deal_rank_invalid_investor_exits_64(self):
        """허용 값 외 --investor → exit 64"""
        _, stderr, code = run_main(
            "deal_rank", "--market", "kospi", "--investor", "retail", "--side", "buy"
        )
        self.assertEqual(code, 64)

    def test_deal_rank_invalid_side_exits_64(self):
        """허용 값 외 --side → exit 64"""
        _, stderr, code = run_main(
            "deal_rank", "--market", "kospi", "--investor", "foreign", "--side", "hold"
        )
        self.assertEqual(code, 64)


class TestExitCodes(unittest.TestCase):
    """exit code matrix 검증"""

    def setUp(self):
        _add_scripts_path()

    def test_http_error_exit_code_2(self):
        """HTTP 오류 → exit code 2"""
        from naver_investor_flow.cli import main
        from naver_investor_flow.http_client import HttpError
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=HttpError(code=403, url="http://test")):
            with self.assertRaises(SystemExit) as ctx:
                main(["flow_day", "--format", "json"])
            self.assertEqual(ctx.exception.code, 2)

    def test_network_error_exit_code_4(self):
        """네트워크 오류 → exit code 4"""
        from naver_investor_flow.cli import main
        from naver_investor_flow.http_client import NetworkError
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=NetworkError("timeout")):
            with self.assertRaises(SystemExit) as ctx:
                main(["flow_day", "--format", "json"])
            self.assertEqual(ctx.exception.code, 4)

    def test_encoding_error_exit_code_5(self):
        """인코딩 오류 → exit code 5"""
        from naver_investor_flow.cli import main
        from naver_investor_flow.http_client import EncodingError
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=EncodingError("encoding failed")):
            with self.assertRaises(SystemExit) as ctx:
                main(["flow_day", "--format", "json"])
            self.assertEqual(ctx.exception.code, 5)

    def test_parse_error_exit_code_3(self):
        """파싱 오류 → exit code 3"""
        from naver_investor_flow.cli import main
        from naver_investor_flow.parser_flow import ParseError
        with patch("naver_investor_flow.cli.http_client.fetch_html", return_value="<html></html>"):
            with patch("naver_investor_flow.cli.parser_flow.parse_flow_day", side_effect=ParseError("parse failed")):
                with self.assertRaises(SystemExit) as ctx:
                    main(["flow_day", "--format", "json"])
                self.assertEqual(ctx.exception.code, 3)

    def test_empty_result_exit_code_0(self):
        """빈 결과 → exit code 0"""
        from naver_investor_flow.cli import main
        with patch("naver_investor_flow.cli.http_client.fetch_html", return_value="<html></html>"):
            with patch("naver_investor_flow.cli.parser_flow.parse_flow_day", return_value=[]):
                with self.assertRaises(SystemExit) as ctx:
                    main(["flow_day", "--format", "json"])
                self.assertEqual(ctx.exception.code, 0)


class TestFlowDayCli(unittest.TestCase):
    """flow_day CLI 동작"""

    def setUp(self):
        _add_scripts_path()

    def _mock_html(self):
        """테스트용 mock HTML"""
        return """<html><body>
<table summary="일자별 순매수에 관한 표 입니다." class="type_1">
<tr class="udline"><th rowspan="2">날짜</th><th rowspan="2">개인</th>
<th rowspan="2">외국인</th><th rowspan="2">기관계</th>
<th colspan="6">기관</th><th rowspan="2">기타법인</th></tr>
<tr class="udline"><th>금융투자</th><th>보험</th><th>투신</th>
<th>은행</th><th>기타금융기관</th><th>연기금등</th></tr>
<tr><td colspan="11" class="blank_07"></td></tr>
<tr>
  <td class="date2">26.05.22</td>
  <td>10,655</td><td>-19,221</td><td>7,583</td>
  <td>7,815</td><td>-635</td><td>1,435</td>
  <td>6</td><td>123</td><td>-1,161</td><td>984</td>
</tr>
</table></body></html>"""

    def test_flow_day_json_output(self):
        """flow_day JSON 출력 기본"""
        from naver_investor_flow.cli import main
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", return_value=self._mock_html()):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit) as ctx:
                    main(["flow_day", "--format", "json"])
        self.assertEqual(ctx.exception.code, 0)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["mode"], "flow_day")
        self.assertEqual(result["unit"], "억원")

    def test_flow_day_bizdate_passed(self):
        """--bizdate 파라미터가 URL에 포함되는지 검증"""
        from naver_investor_flow.cli import main
        captured_urls = []

        def mock_fetch(url, **kwargs):
            captured_urls.append(url)
            return self._mock_html()

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=mock_fetch):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    main(["flow_day", "--bizdate", "20260520"])
        self.assertTrue(any("20260520" in url for url in captured_urls))

    def test_flow_day_bizdate_auto_inject_when_omitted(self):
        """bizdate 미지정 시 오늘 날짜를 자동 주입한다.
        네이버는 bizdate 파라미터가 없으면 1.6KB 빈 페이지를 반환하므로
        반드시 YYYYMMDD를 채워야 데이터를 받을 수 있다 (라이브 검증).
        """
        from naver_investor_flow.cli import main
        import datetime
        captured_urls = []

        def mock_fetch(url, **kwargs):
            captured_urls.append(url)
            return self._mock_html()

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=mock_fetch):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    main(["flow_day", "--format", "json"])

        today = datetime.date.today().strftime("%Y%m%d")
        self.assertTrue(
            any(f"bizdate={today}" in url for url in captured_urls),
            f"오늘 날짜({today})가 URL에 자동 주입되지 않음: {captured_urls}",
        )

    def test_flow_day_uses_trans_style_referer(self):
        """flow_day 호출 시 iframe 부모 페이지(sise_trans_style.naver)를 Referer로 전달"""
        from naver_investor_flow.cli import main
        captured_kwargs = []

        def mock_fetch(url, **kwargs):
            captured_kwargs.append(kwargs)
            return self._mock_html()

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=mock_fetch):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    main(["flow_day", "--format", "json"])
        self.assertEqual(len(captured_kwargs), 1)
        self.assertEqual(
            captured_kwargs[0].get("referer"),
            "https://finance.naver.com/sise/sise_trans_style.naver",
        )

    def test_flow_day_limit(self):
        """--limit 1이면 1행만"""
        from naver_investor_flow.cli import main
        import io
        from contextlib import redirect_stdout

        # 2행짜리 HTML
        html_2rows = self._mock_html().replace(
            "</tr>\n</table>",
            "</tr>\n<tr>\n<td class=\"date2\">26.05.21</td>\n"
            "<td>-100</td><td>200</td><td>300</td>"
            "<td>100</td><td>50</td><td>80</td><td>10</td><td>20</td><td>40</td><td>0</td>"
            "</tr>\n</table>"
        )
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", return_value=html_2rows):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit) as ctx:
                    main(["flow_day", "--format", "json", "--limit", "1"])
        self.assertEqual(ctx.exception.code, 0)
        result = json.loads(buf.getvalue())
        self.assertEqual(len(result["data"]), 1)


class TestDealRankCli(unittest.TestCase):
    """deal_rank CLI 동작"""

    def setUp(self):
        _add_scripts_path()

    def _mock_rank_html(self):
        return """<html><body>
<table class="type_1">
  <table summary="날짜에 따른 외국인 순매수 상위 목록 표 입니다." class="type_1">
  <tr><th>종목명</th><th>수량</th><th>금액</th><th>당일거래량</th></tr>
  <tr><td colspan="4" class="blank_10"></td></tr>
  <tr>
    <td><p><a href="/item/main.naver?code=005930" title='삼성전자'>삼성전자</a></p></td>
    <td class="number">3,672</td><td class="number">1,095,426</td><td class="number">36,168,689</td>
  </tr>
  </table>
</table>
</body></html>"""

    def test_deal_rank_json_output(self):
        """deal_rank JSON 출력"""
        from naver_investor_flow.cli import main
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", return_value=self._mock_rank_html()):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit) as ctx:
                    main(["deal_rank", "--market", "kospi",
                          "--investor", "foreign", "--side", "buy"])
        self.assertEqual(ctx.exception.code, 0)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["mode"], "deal_rank")
        self.assertEqual(result["unit_amount"], "백만원")
        self.assertNotIn("unit", result)

    def test_deal_rank_url_includes_correct_params(self):
        """kospi/foreign/buy → sosok=01&investor_gubun=9000&type=buy"""
        from naver_investor_flow.cli import main
        captured_urls = []

        def mock_fetch(url, **kwargs):
            captured_urls.append(url)
            return self._mock_rank_html()

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=mock_fetch):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    main(["deal_rank", "--market", "kospi",
                          "--investor", "foreign", "--side", "buy"])
        self.assertTrue(any("sosok=01" in u for u in captured_urls))
        self.assertTrue(any("investor_gubun=9000" in u for u in captured_urls))
        self.assertTrue(any("type=buy" in u for u in captured_urls))

    def test_deal_rank_kosdaq_institution(self):
        """kosdaq/institution → sosok=02&investor_gubun=1000"""
        from naver_investor_flow.cli import main
        captured_urls = []

        def mock_fetch(url, **kwargs):
            captured_urls.append(url)
            return self._mock_rank_html()

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=mock_fetch):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    main(["deal_rank", "--market", "kosdaq",
                          "--investor", "institution", "--side", "sell"])
        self.assertTrue(any("sosok=02" in u for u in captured_urls))
        self.assertTrue(any("investor_gubun=1000" in u for u in captured_urls))

    def test_deal_rank_uses_deal_rank_referer(self):
        """deal_rank 호출 시 iframe 부모 페이지(sise_deal_rank.naver)를 Referer로 전달"""
        from naver_investor_flow.cli import main
        captured_kwargs = []

        def mock_fetch(url, **kwargs):
            captured_kwargs.append(kwargs)
            return self._mock_rank_html()

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("naver_investor_flow.cli.http_client.fetch_html", side_effect=mock_fetch):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    main(["deal_rank", "--market", "kospi",
                          "--investor", "foreign", "--side", "buy"])
        self.assertEqual(len(captured_kwargs), 1)
        self.assertEqual(
            captured_kwargs[0].get("referer"),
            "https://finance.naver.com/sise/sise_deal_rank.naver",
        )


if __name__ == "__main__":
    unittest.main()
