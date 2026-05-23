"""
M-4: formatter.py 단위 테스트
- json/table/csv 출력 형식
- 디스클레이머 부착 (모든 포맷)
- flow_day: unit="억원", unit_amount/unit_quantity 없음
- deal_rank: unit_amount="백만원", unit_quantity="주", unit 없음
- NFR-4 단위 혼용 금지 negative assertion
"""

import sys
import os
import unittest
import json
import csv
import io

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# 테스트용 샘플 데이터
SAMPLE_FLOW_DATA = [
    {
        "date": "2026-05-22",
        "individual_eok": 10655,
        "foreign_eok": -19221,
        "institution_total_eok": 7583,
        "institution_breakdown": {
            "financial_inv": 7815,
            "insurance": -635,
            "trust": 1435,
            "bank": 6,
            "other_finance": 123,
            "pension": -1161,
        },
        "foreign_etc_eok": 984,
    },
    {
        "date": "2026-05-21",
        "individual_eok": -26754,
        "foreign_eok": -2212,
        "institution_total_eok": 29008,
        "institution_breakdown": {
            "financial_inv": 26231,
            "insurance": -600,
            "trust": 4452,
            "bank": 49,
            "other_finance": -165,
            "pension": -959,
        },
        "foreign_etc_eok": -43,
    },
]

SAMPLE_FLOW_META = {
    "bizdate_requested": "20260522",
    "bizdate_returned": "20260522",
    "source_url": "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20260522&sosok=",
    "fetched_at": "2026-05-23T14:30:00+09:00",
}

SAMPLE_RANK_DATA = [
    {
        "rank": 1,
        "name": "삼성전자",
        "code": "005930",
        "quantity": 3672,
        "amount_mn_krw": 1095426,
        "volume": 36168689,
    },
    {
        "rank": 2,
        "name": "현대차",
        "code": "005380",
        "quantity": 118,
        "amount_mn_krw": 77272,
        "volume": 1932919,
    },
]

SAMPLE_RANK_META = {
    "market": "kospi",
    "investor": "foreign",
    "side": "buy",
    "source_url": "https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=buy",
    "fetched_at": "2026-05-23T14:30:00+09:00",
}

DISCLAIMER_TEXT = "본 데이터는 네이버 금융에서 수집한 사실 자료이며, 투자 권유나 추천이 아닙니다."


class TestFormatFlowDayJson(unittest.TestCase):
    """flow_day JSON 출력 검증"""

    def setUp(self):
        from naver_investor_flow.formatter import format_output
        output = format_output(
            mode="flow_day",
            data=SAMPLE_FLOW_DATA,
            meta=SAMPLE_FLOW_META,
            fmt="json",
        )
        self.result = json.loads(output)

    def test_mode_field(self):
        """mode == 'flow_day'"""
        self.assertEqual(self.result["mode"], "flow_day")

    def test_unit_field_is_eok(self):
        """flow_day에 unit='억원'"""
        self.assertEqual(self.result["unit"], "억원")

    def test_no_unit_amount_in_flow(self):
        """flow_day에 unit_amount 없음 (NFR-4)"""
        self.assertNotIn("unit_amount", self.result)

    def test_no_unit_quantity_in_flow(self):
        """flow_day에 unit_quantity 없음 (NFR-4)"""
        self.assertNotIn("unit_quantity", self.result)

    def test_data_array_length(self):
        """data 배열 길이 = 2"""
        self.assertEqual(len(self.result["data"]), 2)

    def test_disclaimer_in_meta(self):
        """meta.disclaimer 존재"""
        self.assertIn("disclaimer", self.result["meta"])
        self.assertIn("투자 권유나 추천이 아닙니다", self.result["meta"]["disclaimer"])

    def test_first_row_date(self):
        """첫 번째 행 date"""
        self.assertEqual(self.result["data"][0]["date"], "2026-05-22")

    def test_first_row_individual(self):
        """첫 번째 행 individual_eok"""
        self.assertEqual(self.result["data"][0]["individual_eok"], 10655)

    def test_meta_bizdate(self):
        """meta.bizdate_requested 존재"""
        self.assertEqual(self.result["meta"]["bizdate_requested"], "20260522")


class TestFormatDealRankJson(unittest.TestCase):
    """deal_rank JSON 출력 검증"""

    def setUp(self):
        from naver_investor_flow.formatter import format_output
        output = format_output(
            mode="deal_rank",
            data=SAMPLE_RANK_DATA,
            meta=SAMPLE_RANK_META,
            fmt="json",
        )
        self.result = json.loads(output)

    def test_mode_field(self):
        """mode == 'deal_rank'"""
        self.assertEqual(self.result["mode"], "deal_rank")

    def test_unit_amount_is_mn_krw(self):
        """deal_rank에 unit_amount='백만원'"""
        self.assertEqual(self.result["unit_amount"], "백만원")

    def test_unit_quantity_is_share(self):
        """deal_rank에 unit_quantity='주'"""
        self.assertEqual(self.result["unit_quantity"], "주")

    def test_no_unit_field_in_rank(self):
        """deal_rank에 unit 없음 (NFR-4)"""
        self.assertNotIn("unit", self.result)

    def test_data_has_rank_one(self):
        """data[0].rank == 1"""
        self.assertEqual(self.result["data"][0]["rank"], 1)

    def test_samsung_code_preserved(self):
        """삼성전자 코드 005930 보존"""
        self.assertEqual(self.result["data"][0]["code"], "005930")

    def test_disclaimer_in_meta(self):
        """meta.disclaimer 존재"""
        self.assertIn("disclaimer", self.result["meta"])
        self.assertIn("투자 권유나 추천이 아닙니다", self.result["meta"]["disclaimer"])

    def test_market_in_meta(self):
        """meta.market 존재"""
        self.assertEqual(self.result["meta"]["market"], "kospi")


class TestFormatFlowDayTable(unittest.TestCase):
    """flow_day table 포맷 검증"""

    def setUp(self):
        from naver_investor_flow.formatter import format_output
        self.output = format_output(
            mode="flow_day",
            data=SAMPLE_FLOW_DATA,
            meta=SAMPLE_FLOW_META,
            fmt="table",
        )

    def test_disclaimer_in_table(self):
        """table 출력에 disclaimer 포함"""
        self.assertIn("투자 권유나 추천이 아닙니다", self.output)

    def test_date_in_table(self):
        """날짜 포함"""
        self.assertIn("2026-05-22", self.output)

    def test_numbers_in_table(self):
        """숫자 포함 (콤마 포함 가능)"""
        self.assertIn("10,655", self.output)


class TestFormatDealRankTable(unittest.TestCase):
    """deal_rank table 포맷 검증"""

    def setUp(self):
        from naver_investor_flow.formatter import format_output
        self.output = format_output(
            mode="deal_rank",
            data=SAMPLE_RANK_DATA,
            meta=SAMPLE_RANK_META,
            fmt="table",
        )

    def test_disclaimer_in_table(self):
        """table 출력에 disclaimer 포함"""
        self.assertIn("투자 권유나 추천이 아닙니다", self.output)

    def test_samsung_in_table(self):
        """삼성전자 포함"""
        self.assertIn("삼성전자", self.output)


class TestFormatFlowDayCsv(unittest.TestCase):
    """flow_day CSV 포맷 검증"""

    def setUp(self):
        from naver_investor_flow.formatter import format_output
        self.output = format_output(
            mode="flow_day",
            data=SAMPLE_FLOW_DATA,
            meta=SAMPLE_FLOW_META,
            fmt="csv",
        )

    def test_disclaimer_row_in_csv(self):
        """CSV 마지막 행에 disclaimer 포함"""
        self.assertIn("disclaimer", self.output)
        self.assertIn("투자 권유나 추천이 아닙니다", self.output)

    def test_csv_has_header_row(self):
        """CSV 첫 행이 헤더"""
        reader = csv.reader(io.StringIO(self.output))
        rows = list(reader)
        # 헤더 행 존재
        header = rows[0]
        self.assertIn("date", header)

    def test_date_in_csv(self):
        """날짜 값 포함"""
        self.assertIn("2026-05-22", self.output)


class TestFormatDealRankCsv(unittest.TestCase):
    """deal_rank CSV 포맷 검증"""

    def setUp(self):
        from naver_investor_flow.formatter import format_output
        self.output = format_output(
            mode="deal_rank",
            data=SAMPLE_RANK_DATA,
            meta=SAMPLE_RANK_META,
            fmt="csv",
        )

    def test_disclaimer_row_in_csv(self):
        """CSV에 disclaimer 행 포함"""
        self.assertIn("disclaimer", self.output)

    def test_code_preserved_in_csv(self):
        """종목코드 005930 보존 (CSV 파싱 후에도)"""
        self.assertIn("005930", self.output)

    def test_samsung_in_csv(self):
        """삼성전자 포함"""
        self.assertIn("삼성전자", self.output)


class TestFormatEmptyData(unittest.TestCase):
    """빈 데이터 처리"""

    def test_empty_flow_day_json(self):
        """빈 데이터 → status=empty"""
        from naver_investor_flow.formatter import format_output
        output = format_output(
            mode="flow_day",
            data=[],
            meta={},
            fmt="json",
        )
        result = json.loads(output)
        self.assertEqual(result["status"], "empty")

    def test_empty_rank_json(self):
        """빈 deal_rank → status=empty"""
        from naver_investor_flow.formatter import format_output
        output = format_output(
            mode="deal_rank",
            data=[],
            meta={},
            fmt="json",
        )
        result = json.loads(output)
        self.assertEqual(result["status"], "empty")


class TestDisclaimerText(unittest.TestCase):
    """디스클레이머 정본 검증"""

    def test_disclaimer_contains_required_text(self):
        """디스클레이머 정본 문자열"""
        from naver_investor_flow.formatter import DISCLAIMER
        self.assertIn("네이버 금융", DISCLAIMER)
        self.assertIn("투자 권유나 추천이 아닙니다", DISCLAIMER)
        self.assertIn("보장하지 않습니다", DISCLAIMER)

    def test_unit_mutual_exclusion_flow_rank(self):
        """flow_day와 deal_rank의 unit 스키마 mutually exclusive (NFR-4)"""
        from naver_investor_flow.formatter import format_output
        flow_out = json.loads(format_output("flow_day", SAMPLE_FLOW_DATA, SAMPLE_FLOW_META, "json"))
        rank_out = json.loads(format_output("deal_rank", SAMPLE_RANK_DATA, SAMPLE_RANK_META, "json"))
        # flow_day에 unit_amount/unit_quantity 없음
        self.assertNotIn("unit_amount", flow_out)
        self.assertNotIn("unit_quantity", flow_out)
        # deal_rank에 unit 없음
        self.assertNotIn("unit", rank_out)


if __name__ == "__main__":
    unittest.main()
