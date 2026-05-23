"""
M-3: parser_rank.py 단위 테스트
- 종목명/종목코드/수량/금액/당일거래량 파싱
- 종목코드 0-padding 유지 (005930 not 5930)
- 한글 종목명 무손실
- rank 1부터 시작
- blank/division 행 무시
- code 추출 실패 시 null
- 라이브 fixture 파싱
"""

import sys
import os
import unittest
import re

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

_FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _load_fixture(name: str) -> str:
    path = os.path.join(_FIXTURES_DIR, name)
    with open(path, "rb") as f:
        return f.read().decode("euc-kr")


# 미니 HTML fixture - 외국인 KOSPI 순매수
MINI_RANK_HTML = """<html><body>
<table cellpadding="0" cellspacing="0" class="type_1">
  <table summary="날짜에 따른 외국인 순매수 상위 목록 표 입니다." cellpadding="0" cellspacing="0" class="type_1">
  <caption>외국인 순매수</caption>
  <col width="30%"><col width="20%"><col width="20%"><col width="30%">
  <tr>
    <th>종목명</th><th>수량</th><th>금액</th><th>당일거래량</th>
  </tr>
  <tr><td colspan="4" class="blank_10"></td></tr>
  <tr>
    <td><p class="tit"><a href="/item/main.naver?code=005930" class="tltle" target="_top" title='삼성전자'>삼성전자</a></p></td>
    <td class="number">3,672</td>
    <td class="number">1,095,426</td>
    <td class="number">36,168,689</td>
  </tr>
  <tr>
    <td><p class="tit"><a href="/item/main.naver?code=005380" class="tltle" target="_top" title='현대차'>현대차</a></p></td>
    <td class="number">118</td>
    <td class="number">77,272</td>
    <td class="number">1,932,919</td>
  </tr>
  <tr>
    <td><p class="tit"><a href="/item/main.naver?code=000660" class="tltle" target="_top" title='SK하이닉스'>SK하이닉스</a></p></td>
    <td class="number">200</td>
    <td class="number">50,000</td>
    <td class="number">5,000,000</td>
  </tr>
  <tr><td colspan="4" class="blank_06"></td></tr>
  <tr><td colspan="4" class="division_line"></td></tr>
  </table>
</table>
</body></html>"""

# 종목코드 없는 행 포함 HTML
HTML_WITH_MISSING_CODE = """<html><body>
<table cellpadding="0" cellspacing="0" class="type_1">
  <table summary="날짜에 따른 외국인 순매수 상위 목록 표 입니다." class="type_1">
  <tr><th>종목명</th><th>수량</th><th>금액</th><th>당일거래량</th></tr>
  <tr><td colspan="4" class="blank_10"></td></tr>
  <tr>
    <td><p class="tit"><a href="/item/main.naver?code=005930">삼성전자</a></p></td>
    <td class="number">100</td>
    <td class="number">29,800</td>
    <td class="number">5,000,000</td>
  </tr>
  <tr>
    <td><p class="tit"><a href="/item/main.naver?no_code=here">코드없음종목</a></p></td>
    <td class="number">50</td>
    <td class="number">10,000</td>
    <td class="number">1,000,000</td>
  </tr>
  </table>
</table>
</body></html>"""


class TestParseRankMini(unittest.TestCase):
    """미니 fixture로 deal_rank 파서 기본 동작 검증"""

    def setUp(self):
        from naver_investor_flow.parser_rank import parse_deal_rank
        self.rows = parse_deal_rank(MINI_RANK_HTML)

    def test_returns_three_rows(self):
        """데이터 행 3개 파싱 (blank/division 제외)"""
        self.assertEqual(len(self.rows), 3)

    def test_rank_starts_at_one(self):
        """rank는 1부터 시작"""
        self.assertEqual(self.rows[0]["rank"], 1)

    def test_rank_increments(self):
        """rank 순차 증가"""
        ranks = [r["rank"] for r in self.rows]
        self.assertEqual(ranks, [1, 2, 3])

    def test_samsung_name(self):
        """삼성전자 종목명"""
        self.assertEqual(self.rows[0]["name"], "삼성전자")

    def test_samsung_code_with_zero_padding(self):
        """삼성전자 종목코드 0-padding 유지"""
        self.assertEqual(self.rows[0]["code"], "005930")
        # int가 아닌 string 확인
        self.assertIsInstance(self.rows[0]["code"], str)

    def test_hyundai_code(self):
        """현대차 005380"""
        self.assertEqual(self.rows[1]["code"], "005380")

    def test_skhynix_korean_name(self):
        """SK하이닉스 한글 종목명"""
        self.assertEqual(self.rows[2]["name"], "SK하이닉스")

    def test_skhynix_code(self):
        """SK하이닉스 000660"""
        self.assertEqual(self.rows[2]["code"], "000660")

    def test_quantity_is_int(self):
        """수량은 콤마 제거 후 int"""
        self.assertEqual(self.rows[0]["quantity"], 3672)
        self.assertIsInstance(self.rows[0]["quantity"], int)

    def test_amount_is_int(self):
        """금액은 콤마 제거 후 int (백만원)"""
        self.assertEqual(self.rows[0]["amount_mn_krw"], 1095426)
        self.assertIsInstance(self.rows[0]["amount_mn_krw"], int)

    def test_volume_is_int(self):
        """당일거래량은 int"""
        self.assertEqual(self.rows[0]["volume"], 36168689)
        self.assertIsInstance(self.rows[0]["volume"], int)

    def test_all_required_keys(self):
        """필수 키: rank, name, code, quantity, amount_mn_krw, volume"""
        required = ["rank", "name", "code", "quantity", "amount_mn_krw", "volume"]
        for row in self.rows:
            for key in required:
                self.assertIn(key, row, f"Missing key: {key}")

    def test_code_six_digits_regex(self):
        """모든 code가 6자리 숫자"""
        for row in self.rows:
            if row["code"] is not None:
                self.assertRegex(row["code"], r"^\d{6}$")


class TestParseRankMissingCode(unittest.TestCase):
    """종목코드 추출 실패 케이스"""

    def test_missing_code_is_none(self):
        """code 추출 실패 행은 code=None"""
        from naver_investor_flow.parser_rank import parse_deal_rank
        rows = parse_deal_rank(HTML_WITH_MISSING_CODE)
        # 두 번째 행 code가 None
        self.assertIsNone(rows[1]["code"])

    def test_other_fields_still_parsed(self):
        """code 실패해도 나머지 필드 정상 파싱"""
        from naver_investor_flow.parser_rank import parse_deal_rank
        rows = parse_deal_rank(HTML_WITH_MISSING_CODE)
        self.assertEqual(rows[1]["name"], "코드없음종목")
        self.assertEqual(rows[1]["quantity"], 50)


class TestParseRankEmpty(unittest.TestCase):
    """빈 테이블 처리"""

    def test_empty_html_returns_empty(self):
        """데이터 없으면 빈 리스트"""
        from naver_investor_flow.parser_rank import parse_deal_rank
        self.assertEqual(parse_deal_rank("<html></html>"), [])


class TestParseRankFixture(unittest.TestCase):
    """라이브 캡처 fixture (KOSPI 외국인 buy)"""

    @classmethod
    def setUpClass(cls):
        from naver_investor_flow.parser_rank import parse_deal_rank
        html = _load_fixture("deal_rank_sample.html")
        cls.rows = parse_deal_rank(html)

    def test_fixture_has_rows(self):
        """fixture에 최소 1개 이상 행"""
        self.assertGreater(len(self.rows), 0)

    def test_fixture_max_30_rows(self):
        """최대 30행"""
        self.assertLessEqual(len(self.rows), 30)

    def test_all_names_nonempty(self):
        """모든 종목명 비어있지 않음"""
        for row in self.rows:
            self.assertTrue(len(row["name"]) > 0, "Empty name found")

    def test_all_codes_six_digits_or_none(self):
        """모든 code가 6자리 또는 None"""
        for row in self.rows:
            if row["code"] is not None:
                self.assertRegex(row["code"], r"^\d{6}$")

    def test_samsung_in_fixture(self):
        """삼성전자(005930) fixture에 포함"""
        names = [r["name"] for r in self.rows]
        self.assertIn("삼성전자", names)

    def test_samsung_code_zero_padded(self):
        """삼성전자 코드 005930 (0-padding 확인)"""
        samsung = next(r for r in self.rows if r["name"] == "삼성전자")
        self.assertEqual(samsung["code"], "005930")

    def test_no_korean_mojibake(self):
        """한글 깨짐 없음"""
        for row in self.rows:
            self.assertNotIn("?", row["name"])
            self.assertNotIn("＊", row["name"])

    def test_amounts_are_positive_integers(self):
        """금액은 양의 정수 (백만원)"""
        for row in self.rows:
            self.assertIsInstance(row["amount_mn_krw"], int)
            self.assertGreater(row["amount_mn_krw"], 0)

    def test_volume_nonnegative(self):
        """당일거래량 비음수"""
        for row in self.rows:
            self.assertGreaterEqual(row["volume"], 0)

    def test_rank_sequential(self):
        """rank 1부터 순차"""
        ranks = [r["rank"] for r in self.rows]
        expected = list(range(1, len(self.rows) + 1))
        self.assertEqual(ranks, expected)


if __name__ == "__main__":
    unittest.main()
