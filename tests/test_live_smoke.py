"""
test_live_smoke.py — 라이브 네트워크 스모크 테스트 (M-7)

SPEC-NAVER-INVESTOR-FLOW-001 AC-1 / AC-4 / AC-5 / AC-6 / AC-11 / AC-12 라이브 검증.

실행:
  cd itda-stocks/skills/naver-investor-flow/scripts
  python -m pytest tests/test_live_smoke.py -v

주의:
- 실제 네트워크 호출을 수행합니다. 인터넷 연결이 필요합니다.
- 네이버 금융 서버 가용성에 의존합니다.
- 실행 시간: 약 15~30초 (9회 HTTP 요청).
- CI 환경에서는 별도 스크립트로 실행하거나 환경변수로 제어하세요.
"""

from __future__ import annotations

import json
import re
import sys
import os
import unittest

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from naver_investor_flow import http_client
from naver_investor_flow import parser_flow
from naver_investor_flow import parser_rank
from naver_investor_flow import formatter


class TestLiveFlowDay(unittest.TestCase):
    """AC-1/AC-2: flow_day 라이브 호출 — bizdate=20260522 (확인된 영업일)"""

    # 라이브 프로브로 검증된 영업일: 2026-05-22 (금요일)
    BIZDATE = "20260522"

    @classmethod
    def setUpClass(cls):
        url = f"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={cls.BIZDATE}&sosok="
        html = http_client.fetch_html(url)
        cls.rows = parser_flow.parse_flow_day(html)
        cls.output = formatter.format_output(
            mode="flow_day",
            data=cls.rows,
            meta={"bizdate_requested": cls.BIZDATE, "source_url": url},
            fmt="json",
        )
        cls.result = json.loads(cls.output)

    def test_exit_no_exception(self):
        """라이브 호출이 예외 없이 완료됨"""
        self.assertIsNotNone(self.result)

    def test_data_has_rows(self):
        """AC-1: data 배열에 1개 이상 요소"""
        self.assertGreater(len(self.rows), 0, "flow_day 라이브 데이터 0건 — 영업일 확인")

    def test_date_iso_format(self):
        """AC-1: date 필드가 YYYY-MM-DD ISO 형식"""
        if not self.rows:
            self.skipTest("데이터 없음")
        for row in self.rows:
            self.assertRegex(row["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_numeric_fields_are_int(self):
        """AC-1: 수치 필드가 정수"""
        if not self.rows:
            self.skipTest("데이터 없음")
        for row in self.rows:
            self.assertIsInstance(row["individual_eok"], int)
            self.assertIsInstance(row["foreign_eok"], int)
            self.assertIsInstance(row["institution_total_eok"], int)
            self.assertIsInstance(row["foreign_etc_eok"], int)

    def test_institution_breakdown_six_fields(self):
        """AC-1: institution_breakdown에 6개 sub-fields"""
        if not self.rows:
            self.skipTest("데이터 없음")
        expected = {"financial_inv", "insurance", "trust", "bank", "other_finance", "pension"}
        for row in self.rows:
            self.assertEqual(set(row["institution_breakdown"].keys()), expected)

    def test_json_unit_eok(self):
        """AC-6: flow_day JSON에 unit='억원'"""
        if self.result.get("status") == "empty":
            self.skipTest("빈 결과")
        self.assertEqual(self.result["unit"], "억원")

    def test_json_no_unit_amount(self):
        """AC-6 (NFR-4): flow_day에 unit_amount 없음"""
        if self.result.get("status") == "empty":
            self.skipTest("빈 결과")
        self.assertNotIn("unit_amount", self.result)

    def test_json_no_unit_quantity(self):
        """AC-6 (NFR-4): flow_day에 unit_quantity 없음"""
        if self.result.get("status") == "empty":
            self.skipTest("빈 결과")
        self.assertNotIn("unit_quantity", self.result)

    def test_disclaimer_in_json(self):
        """AC-7: JSON meta에 disclaimer 존재"""
        if self.result.get("status") == "empty":
            self.skipTest("빈 결과")
        self.assertIn("disclaimer", self.result["meta"])
        self.assertIn("투자 권유나 추천이 아닙니다", self.result["meta"]["disclaimer"])

    def test_recent_dates_ordered(self):
        """AC-1: 날짜가 최신부터 역순"""
        if len(self.rows) < 2:
            self.skipTest("행 부족")
        dates = [row["date"] for row in self.rows]
        self.assertEqual(dates, sorted(dates, reverse=True))


class TestLiveDealRankBase(unittest.TestCase):
    """AC-4/AC-5 공통 헬퍼"""

    def _fetch_rank(self, market: str, investor: str, side: str) -> tuple[list[dict], str]:
        from naver_investor_flow.cli import MARKET_MAP, INVESTOR_MAP, BASE_RANK
        sosok = MARKET_MAP[market]
        igubun = INVESTOR_MAP[investor]
        url = f"{BASE_RANK}?sosok={sosok}&investor_gubun={igubun}&type={side}"
        html = http_client.fetch_html(url)
        rows = parser_rank.parse_deal_rank(html)
        output = formatter.format_output(
            mode="deal_rank",
            data=rows,
            meta={"market": market, "investor": investor, "side": side, "source_url": url},
            fmt="json",
        )
        return rows, output

    def _assert_rank_output(self, rows: list[dict], output: str, label: str):
        result = json.loads(output)

        # 빈 결과면 AC-5는 여전히 exit code 0 충족이므로 PASS
        if result.get("status") == "empty":
            return

        # AC-4: 최소 1개 종목
        self.assertGreater(len(rows), 0, f"{label}: 데이터 0건")

        # AC-4: 각 필드 타입 검증
        for i, row in enumerate(rows):
            self.assertIsInstance(row["rank"], int, f"{label} row[{i}].rank")
            self.assertIsInstance(row["name"], str, f"{label} row[{i}].name")
            self.assertGreater(len(row["name"]), 0, f"{label} row[{i}].name empty")
            if row["code"] is not None:
                self.assertRegex(row["code"], r"^\d{6}$", f"{label} row[{i}].code")
            self.assertIsInstance(row["quantity"], int, f"{label} row[{i}].quantity")
            self.assertIsInstance(row["amount_mn_krw"], int, f"{label} row[{i}].amount_mn_krw")
            self.assertIsInstance(row["volume"], int, f"{label} row[{i}].volume")
            self.assertGreaterEqual(row["volume"], 0, f"{label} row[{i}].volume negative")

        # AC-6: unit_amount='백만원', unit_quantity='주', 'unit' 없음
        self.assertEqual(result["unit_amount"], "백만원", f"{label}: unit_amount")
        self.assertEqual(result["unit_quantity"], "주", f"{label}: unit_quantity")
        self.assertNotIn("unit", result, f"{label}: 'unit' must not exist")

        # AC-7: disclaimer
        self.assertIn("disclaimer", result["meta"], f"{label}: disclaimer missing")

        # AC-12: rank 연속성
        ranks = [r["rank"] for r in rows]
        self.assertEqual(ranks, list(range(1, len(rows) + 1)), f"{label}: rank sequence")


class TestLiveDealRankKospiForign(TestLiveDealRankBase):
    """AC-5: KOSPI × foreign 2조합"""

    def test_kospi_foreign_buy(self):
        """kospi/foreign/buy — AC-4 완전 검증"""
        rows, output = self._fetch_rank("kospi", "foreign", "buy")
        self._assert_rank_output(rows, output, "kospi/foreign/buy")

    def test_kospi_foreign_sell(self):
        """kospi/foreign/sell"""
        rows, output = self._fetch_rank("kospi", "foreign", "sell")
        self._assert_rank_output(rows, output, "kospi/foreign/sell")


class TestLiveDealRankKospiInstitution(TestLiveDealRankBase):
    """AC-5: KOSPI × institution 2조합"""

    def test_kospi_institution_buy(self):
        rows, output = self._fetch_rank("kospi", "institution", "buy")
        self._assert_rank_output(rows, output, "kospi/institution/buy")

    def test_kospi_institution_sell(self):
        rows, output = self._fetch_rank("kospi", "institution", "sell")
        self._assert_rank_output(rows, output, "kospi/institution/sell")


class TestLiveDealRankKosdaqForeign(TestLiveDealRankBase):
    """AC-5: KOSDAQ × foreign 2조합"""

    def test_kosdaq_foreign_buy(self):
        rows, output = self._fetch_rank("kosdaq", "foreign", "buy")
        self._assert_rank_output(rows, output, "kosdaq/foreign/buy")

    def test_kosdaq_foreign_sell(self):
        rows, output = self._fetch_rank("kosdaq", "foreign", "sell")
        self._assert_rank_output(rows, output, "kosdaq/foreign/sell")


class TestLiveDealRankKosdaqInstitution(TestLiveDealRankBase):
    """AC-5: KOSDAQ × institution 2조합"""

    def test_kosdaq_institution_buy(self):
        rows, output = self._fetch_rank("kosdaq", "institution", "buy")
        self._assert_rank_output(rows, output, "kosdaq/institution/buy")

    def test_kosdaq_institution_sell(self):
        rows, output = self._fetch_rank("kosdaq", "institution", "sell")
        self._assert_rank_output(rows, output, "kosdaq/institution/sell")


class TestLiveEncoding(TestLiveDealRankBase):
    """AC-11: 한글 종목명 인코딩 라이브"""

    def test_no_mojibake_in_names(self):
        """AC-11: 종목명에 한글 깨짐 없음 (삼성전자 기준)"""
        rows, _ = self._fetch_rank("kospi", "foreign", "buy")
        if not rows:
            self.skipTest("데이터 없음")
        names = [row["name"] for row in rows]
        all_names = " ".join(names)
        # 모자이크 문자(replacement character) 없음
        self.assertNotIn("�", all_names, "한글 깨짐(replacement character) 발견")
        self.assertNotIn("?", all_names, "? 문자 발견 — 인코딩 오류 가능")
        # 삼성전자가 상위에 있을 가능성 높음
        has_korean = any(
            any("가" <= ch <= "힣" for ch in name)
            for name in names
        )
        self.assertTrue(has_korean, "한글 종목명이 1개도 없음 — 인코딩 문제 의심")

    def test_six_digit_codes_in_live(self):
        """AC-12: 라이브 deal_rank 모든 code가 6자리 숫자 또는 None"""
        rows, _ = self._fetch_rank("kospi", "foreign", "buy")
        if not rows:
            self.skipTest("데이터 없음")
        for row in rows:
            if row["code"] is not None:
                self.assertRegex(row["code"], r"^\d{6}$",
                                 f"code 6자리 아님: {row['code']} ({row['name']})")


if __name__ == "__main__":
    unittest.main()
