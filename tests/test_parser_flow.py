"""
M-2: parser_flow.py 단위 테스트
- fixture 기반 파싱 (라이브 캡처 HTML)
- 행 수 검증 (10행)
- 날짜 포맷 변환 (YY.MM.DD → YYYY-MM-DD)
- 정수 파싱 (콤마 제거, 음수 처리)
- 빈 테이블 처리
- 필드 타입 및 이름 검증
"""

import sys
import os
import unittest

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

_FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _load_fixture(name: str) -> str:
    path = os.path.join(_FIXTURES_DIR, name)
    with open(path, "rb") as f:
        return f.read().decode("euc-kr")


# 미니 HTML fixture - 2행 데이터 (음수 포함, 콤마 있는 숫자)
MINI_HTML = """<html><body>
<table summary="일자별 순매수에 관한 표 입니다." class="type_1">
<tr class="udline">
  <th rowspan="2">날짜</th><th rowspan="2">개인</th><th rowspan="2">외국인</th>
  <th rowspan="2">기관계</th><th colspan="6">기관</th><th rowspan="2">기타법인</th>
</tr>
<tr class="udline">
  <th>금융투자</th><th>보험</th><th>투신<br>(사모)</th>
  <th>은행</th><th>기타금융기관</th><th>연기금등</th>
</tr>
<tr><td colspan="11" class="blank_07"></td></tr>
<tr>
  <td class="date2">26.05.22</td>
  <td class="rate_up3">10,655</td>
  <td class="rate_down3">-19,221</td>
  <td class="rate_up3">7,583</td>
  <td class="rate_up3">7,815</td>
  <td class="rate_down3">-635</td>
  <td class="rate_up3">1,435</td>
  <td class="rate_up3">6</td>
  <td class="rate_up3">123</td>
  <td class="rate_down3">-1,161</td>
  <td class="rate_up3">984</td>
</tr>
<tr>
  <td class="date2">26.05.21</td>
  <td class="rate_down3">-26,754</td>
  <td class="rate_down3">-2,212</td>
  <td class="rate_up3">29,008</td>
  <td class="rate_up3">26,231</td>
  <td class="rate_down3">-600</td>
  <td class="rate_up3">4,452</td>
  <td class="rate_up3">49</td>
  <td class="rate_down3">-165</td>
  <td class="rate_down3">-959</td>
  <td class="rate_down3">-43</td>
</tr>
</table>
</body></html>"""

EMPTY_HTML = """<html><body>
<table summary="일자별 순매수에 관한 표 입니다." class="type_1">
<tr class="udline">
  <th rowspan="2">날짜</th><th rowspan="2">개인</th><th rowspan="2">외국인</th>
  <th rowspan="2">기관계</th><th colspan="6">기관</th><th rowspan="2">기타법인</th>
</tr>
<tr class="udline">
  <th>금융투자</th><th>보험</th><th>투신</th>
  <th>은행</th><th>기타금융기관</th><th>연기금등</th>
</tr>
<tr><td colspan="11" class="blank_07"></td></tr>
</table>
</body></html>"""


class TestParseFlowDayMini(unittest.TestCase):
    """미니 fixture로 파서 기본 동작 검증"""

    def setUp(self):
        from naver_investor_flow.parser_flow import parse_flow_day
        self.rows = parse_flow_day(MINI_HTML)

    def test_returns_two_rows(self):
        """2행 파싱"""
        self.assertEqual(len(self.rows), 2)

    def test_first_row_date_iso_format(self):
        """날짜 ISO 변환: 26.05.22 → 2026-05-22"""
        self.assertEqual(self.rows[0]["date"], "2026-05-22")

    def test_second_row_date_iso_format(self):
        """날짜 ISO 변환: 26.05.21 → 2026-05-21"""
        self.assertEqual(self.rows[1]["date"], "2026-05-21")

    def test_individual_eok_positive(self):
        """개인 양수 (콤마 제거 후 정수)"""
        self.assertEqual(self.rows[0]["individual_eok"], 10655)

    def test_foreign_eok_negative(self):
        """외국인 음수 (음수 부호 유지)"""
        self.assertEqual(self.rows[0]["foreign_eok"], -19221)

    def test_institution_total_eok(self):
        """기관계 값"""
        self.assertEqual(self.rows[0]["institution_total_eok"], 7583)

    def test_institution_breakdown_financial_inv(self):
        """기관 breakdown - 금융투자"""
        self.assertEqual(self.rows[0]["institution_breakdown"]["financial_inv"], 7815)

    def test_institution_breakdown_insurance(self):
        """기관 breakdown - 보험 음수"""
        self.assertEqual(self.rows[0]["institution_breakdown"]["insurance"], -635)

    def test_institution_breakdown_trust(self):
        """기관 breakdown - 투신"""
        self.assertEqual(self.rows[0]["institution_breakdown"]["trust"], 1435)

    def test_institution_breakdown_bank(self):
        """기관 breakdown - 은행"""
        self.assertEqual(self.rows[0]["institution_breakdown"]["bank"], 6)

    def test_institution_breakdown_other_finance(self):
        """기관 breakdown - 기타금융기관"""
        self.assertEqual(self.rows[0]["institution_breakdown"]["other_finance"], 123)

    def test_institution_breakdown_pension(self):
        """기관 breakdown - 연기금"""
        self.assertEqual(self.rows[0]["institution_breakdown"]["pension"], -1161)

    def test_foreign_etc_eok(self):
        """기타법인"""
        self.assertEqual(self.rows[0]["foreign_etc_eok"], 984)

    def test_all_eok_fields_are_int(self):
        """모든 _eok 필드가 int 타입"""
        row = self.rows[0]
        int_fields = [
            "individual_eok", "foreign_eok", "institution_total_eok", "foreign_etc_eok"
        ]
        for field in int_fields:
            self.assertIsInstance(row[field], int, f"{field} must be int")

        breakdown = row["institution_breakdown"]
        for key in ["financial_inv", "insurance", "trust", "bank", "other_finance", "pension"]:
            self.assertIsInstance(breakdown[key], int, f"breakdown.{key} must be int")

    def test_required_keys_present(self):
        """필수 키 존재"""
        row = self.rows[0]
        required = [
            "date", "individual_eok", "foreign_eok",
            "institution_total_eok", "institution_breakdown", "foreign_etc_eok"
        ]
        for key in required:
            self.assertIn(key, row, f"Missing key: {key}")

    def test_institution_breakdown_keys(self):
        """institution_breakdown 하위 6개 키 존재"""
        breakdown = self.rows[0]["institution_breakdown"]
        expected_keys = ["financial_inv", "insurance", "trust", "bank", "other_finance", "pension"]
        for key in expected_keys:
            self.assertIn(key, breakdown, f"Missing breakdown key: {key}")

    def test_large_negative_number_with_comma(self):
        """대형 음수 콤마 파싱: -26,754 → -26754"""
        self.assertEqual(self.rows[1]["individual_eok"], -26754)


class TestParseFlowDayEmpty(unittest.TestCase):
    """빈 테이블 처리"""

    def test_empty_table_returns_empty_list(self):
        """데이터 없는 테이블 → 빈 리스트 반환"""
        from naver_investor_flow.parser_flow import parse_flow_day
        rows = parse_flow_day(EMPTY_HTML)
        self.assertEqual(rows, [])

    def test_empty_html_returns_empty_list(self):
        """HTML에 테이블 없음 → 빈 리스트"""
        from naver_investor_flow.parser_flow import parse_flow_day
        rows = parse_flow_day("<html><body></body></html>")
        self.assertEqual(rows, [])


class TestParseFlowDayFixture(unittest.TestCase):
    """라이브 캡처 fixture로 실제 파싱 검증"""

    @classmethod
    def setUpClass(cls):
        from naver_investor_flow.parser_flow import parse_flow_day
        html = _load_fixture("flow_day_sample.html")
        cls.rows = parse_flow_day(html)

    def test_fixture_returns_10_rows(self):
        """라이브 fixture는 10행"""
        self.assertEqual(len(self.rows), 10)

    def test_all_dates_iso_format(self):
        """모든 날짜가 YYYY-MM-DD 형식"""
        import re
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for row in self.rows:
            self.assertRegex(row["date"], pattern, f"Bad date format: {row['date']}")

    def test_first_date_is_most_recent(self):
        """첫 번째 날짜가 가장 최근"""
        dates = [row["date"] for row in self.rows]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_all_eok_values_are_int(self):
        """모든 억원 값이 int"""
        for row in self.rows:
            self.assertIsInstance(row["individual_eok"], int)
            self.assertIsInstance(row["foreign_eok"], int)
            self.assertIsInstance(row["institution_total_eok"], int)
            self.assertIsInstance(row["foreign_etc_eok"], int)

    def test_no_commas_in_values(self):
        """파싱 결과에 콤마 없음 (정수 변환 완료)"""
        for row in self.rows:
            # int 타입 검증이 콤마 없음 보장 — 추가로 문자열 누락 확인
            self.assertNotIsInstance(row["individual_eok"], str)

    def test_fixture_first_row_date(self):
        """라이브 fixture 첫 번째 날짜 = 2026-05-22"""
        self.assertEqual(self.rows[0]["date"], "2026-05-22")

    def test_fixture_first_row_individual(self):
        """라이브 fixture 첫 번째 개인 = 10655"""
        self.assertEqual(self.rows[0]["individual_eok"], 10655)

    def test_fixture_first_row_foreign(self):
        """라이브 fixture 첫 번째 외국인 = -19221"""
        self.assertEqual(self.rows[0]["foreign_eok"], -19221)


if __name__ == "__main__":
    unittest.main()
