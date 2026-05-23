"""
parser_rank.py — 종목별 외국인·기관 매매 랭킹 HTML 파서

REQ-020: deal_rank 파싱
REQ-020.2: 5컬럼 + href 정규식 → 6자리 종목코드
REQ-020.3: 백만원 단위
NFR-3: EUC-KR 한글 무손실
AC-12: 종목코드 0-padding 유지
"""

from __future__ import annotations

import re
from html.parser import HTMLParser


def _parse_int(text: str) -> int:
    """콤마 제거 후 정수 변환."""
    text = text.strip().replace(",", "").replace("\xa0", "")
    if not text or text == "-":
        return 0
    return int(text)


def _extract_code(href: str) -> str | None:
    """href에서 종목코드 6자리 추출.

    예: /item/main.naver?code=005930 → "005930"
    매칭 실패 시 None 반환 (EXC-5).
    """
    m = re.search(r"code=(\d{6})", href)
    if m:
        return m.group(1)
    return None


class _RankParser(HTMLParser):
    """deal_rank 테이블 파서 (상태 기계).

    HTML 구조 (실제 네이버 금융):
    <table class="type_1">          ← 외부 래퍼
      ...
      <table summary="...순매수..." class="type_1">  ← 실제 데이터 테이블
        <tr><th>종목명</th>...</tr>
        <tr class="blank_10">...</tr>
        <tr>  ← 데이터 행
          <td><p><a href="...code=005930..." title='삼성전자'>삼성전자</a></p></td>
          <td class="number">3,672</td>
          <td class="number">1,095,426</td>
          <td class="number">36,168,689</td>
        </tr>
        <tr class="blank_06">...</tr>
        <tr class="division_line">...</tr>
      </table>
    </table>
    """

    def __init__(self) -> None:
        super().__init__()
        self._in_target_table: bool = False
        self._depth: int = 0           # table 중첩 깊이
        self._in_tr: bool = False
        self._in_td: bool = False
        self._in_anchor: bool = False
        self._is_header_tr: bool = False
        self._is_skip_row: bool = False
        self._current_href: str | None = None
        self._current_anchor_text: str = ""
        self._current_cells: list[dict] = []  # {"text": ..., "href": ..., "name": ...}
        self._current_cell: dict = {}
        self.rows: list[dict] = []
        self._rank: int = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr_dict = dict(attrs)
        if tag == "table":
            if not self._in_target_table:
                summary = attr_dict.get("summary", "")
                if "순매수" in summary or "순매도" in summary:
                    self._in_target_table = True
                    self._depth = 1
            elif self._in_target_table:
                self._depth += 1
        elif tag == "tr" and self._in_target_table and self._depth == 1:
            self._in_tr = True
            self._current_cells = []
            self._is_header_tr = False
            self._is_skip_row = False
        elif tag == "th" and self._in_target_table:
            self._is_header_tr = True
        elif tag == "td" and self._in_target_table and self._in_tr:
            colspan = attr_dict.get("colspan", "")
            td_class = attr_dict.get("class", "")
            if colspan or any(
                skip in td_class
                for skip in ["blank_06", "blank_08", "blank_09", "blank_10",
                             "division_line"]
            ):
                self._is_skip_row = True
            else:
                self._in_td = True
                self._current_cell = {"text": "", "href": None, "name": None}
        elif tag == "a" and self._in_td:
            href = attr_dict.get("href", "")
            title = attr_dict.get("title", "")
            self._in_anchor = True
            self._current_href = href
            # title 속성에 종목명이 있는 경우
            if title:
                self._current_cell["name"] = title
            self._current_cell["href"] = href
            self._current_anchor_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._in_target_table:
                self._depth -= 1
                if self._depth <= 0:
                    self._in_target_table = False
        elif tag == "tr" and self._in_target_table:
            if (
                not self._is_header_tr
                and not self._is_skip_row
                and len(self._current_cells) == 4
            ):
                row = self._build_row(self._current_cells)
                if row is not None:
                    self.rows.append(row)
            self._in_tr = False
            self._current_cells = []
        elif tag == "td" and self._in_td:
            self._current_cells.append(dict(self._current_cell))
            self._in_td = False
            self._current_cell = {}
        elif tag == "a" and self._in_anchor:
            # anchor 텍스트를 종목명으로 (title 없을 때 fallback)
            if not self._current_cell.get("name"):
                self._current_cell["name"] = self._current_anchor_text.strip()
            self._in_anchor = False
            self._current_anchor_text = ""

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._current_anchor_text += data
        elif self._in_td:
            self._current_cell["text"] = (
                self._current_cell.get("text", "") + data
            )

    def _build_row(self, cells: list[dict]) -> dict | None:
        """4셀 → dict 변환.

        cells[0]: 종목명 td (href + name)
        cells[1]: 수량 td
        cells[2]: 금액 td
        cells[3]: 당일거래량 td
        """
        name = cells[0].get("name") or cells[0].get("text", "").strip()
        if not name:
            return None

        href = cells[0].get("href", "") or ""
        code = _extract_code(href)

        try:
            quantity = _parse_int(cells[1]["text"])
            amount_mn_krw = _parse_int(cells[2]["text"])
            volume = _parse_int(cells[3]["text"])
        except (ValueError, KeyError):
            return None

        self._rank += 1
        return {
            "rank": self._rank,
            "name": name,
            "code": code,
            "quantity": quantity,
            "amount_mn_krw": amount_mn_krw,
            "volume": volume,
        }


def parse_deal_rank(html: str) -> list[dict]:
    """deal_rank HTML → dict 리스트 파싱.

    Args:
        html: 네이버 금융 sise_deal_rank_iframe HTML (EUC-KR 디코딩 완료)

    Returns:
        최대 30개 ranked dict 리스트. 빈 테이블이면 [].
    """
    parser = _RankParser()
    parser.feed(html)
    return parser.rows[:30]
