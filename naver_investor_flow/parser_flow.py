"""
parser_flow.py — 일별 시장 매매동향 HTML 파서

REQ-010: flow_day 파싱
REQ-010.2: 11컬럼 → dict 매핑
REQ-010.3: 억원 단위 정수
NFR-3: EUC-KR 한글 무손실
"""

from __future__ import annotations

import re
from html.parser import HTMLParser


def _parse_int(text: str) -> int:
    """콤마 제거 후 정수 변환. 빈 문자열이나 '-'는 0 반환."""
    text = text.strip().replace(",", "").replace("\xa0", "")
    if not text or text == "-":
        return 0
    return int(text)


def _date_to_iso(text: str) -> str:
    """'YY.MM.DD' → 'YYYY-MM-DD' 변환 (20YY 가정)."""
    text = text.strip()
    # 26.05.22 형식
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", text)
    if m:
        yy, mm, dd = m.group(1), m.group(2), m.group(3)
        return f"20{yy}-{mm}-{dd}"
    return text


class _FlowDayParser(HTMLParser):
    """flow_day 테이블 파서 (상태 기계).

    HTML 구조:
    <table class="type_1"> (summary 포함)
        헤더 행 (th 포함 tr)
        blank_07 행
        데이터 행 × N (date2 class td가 있는 tr)
        blank_08/09/division_line 행
    </table>
    """

    def __init__(self) -> None:
        super().__init__()
        self._in_target_table: bool = False
        self._in_tr: bool = False
        self._in_td: bool = False
        self._current_cells: list[str] = []
        self._current_text: str = ""
        self._is_header_tr: bool = False
        self._is_skip_row: bool = False
        self.rows: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr_dict = dict(attrs)
        if tag == "table":
            summary = attr_dict.get("summary", "")
            cls = attr_dict.get("class", "")
            # 두 가지 패턴 모두 처리
            if "순매수에 관한 표" in summary or ("type_1" in cls and not self._in_target_table):
                self._in_target_table = True
        elif tag == "tr" and self._in_target_table:
            self._in_tr = True
            self._current_cells = []
            self._is_header_tr = False
            self._is_skip_row = False
            cls = attr_dict.get("class", "")
            if "udline" in cls:
                self._is_header_tr = True
        elif tag == "td" and self._in_tr:
            td_class = attr_dict.get("class", "")
            colspan = attr_dict.get("colspan", "")
            # 구분/공백 행 무시
            if colspan or any(
                skip in td_class
                for skip in ["blank_07", "blank_08", "blank_09",
                             "division_line", "blank_10"]
            ):
                self._is_skip_row = True
            else:
                self._in_td = True
                self._current_text = ""
        elif tag == "th" and self._in_tr:
            self._is_header_tr = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_target_table:
            self._in_target_table = False
        elif tag == "tr" and self._in_target_table:
            if (
                not self._is_header_tr
                and not self._is_skip_row
                and len(self._current_cells) == 11
            ):
                row = self._build_row(self._current_cells)
                if row is not None:
                    self.rows.append(row)
            self._in_tr = False
            self._current_cells = []
            self._is_header_tr = False
            self._is_skip_row = False
        elif tag == "td" and self._in_td:
            self._current_cells.append(self._current_text.strip())
            self._in_td = False
            self._current_text = ""

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._current_text += data

    def _build_row(self, cells: list[str]) -> dict | None:
        """11셀 → dict 변환."""
        # cells[0] = 날짜, cells[1..10] = 수치들
        date_raw = cells[0]
        if not date_raw or not re.match(r"^\d{2}\.\d{2}\.\d{2}$", date_raw.strip()):
            return None
        return {
            "date": _date_to_iso(date_raw),
            "individual_eok": _parse_int(cells[1]),
            "foreign_eok": _parse_int(cells[2]),
            "institution_total_eok": _parse_int(cells[3]),
            "institution_breakdown": {
                "financial_inv": _parse_int(cells[4]),
                "insurance": _parse_int(cells[5]),
                "trust": _parse_int(cells[6]),
                "bank": _parse_int(cells[7]),
                "other_finance": _parse_int(cells[8]),
                "pension": _parse_int(cells[9]),
            },
            "foreign_etc_eok": _parse_int(cells[10]),
        }


def parse_flow_day(html: str) -> list[dict]:
    """flow_day HTML → dict 리스트 파싱.

    Args:
        html: 네이버 금융 investorDealTrendDay HTML (EUC-KR 디코딩 완료)

    Returns:
        최대 10개 행의 dict 리스트. 빈 테이블이면 [].
    """
    parser = _FlowDayParser()
    parser.feed(html)
    return parser.rows
