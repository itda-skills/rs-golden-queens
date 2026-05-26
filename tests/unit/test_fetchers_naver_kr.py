"""SPEC-MF-TEST-001: fetchers/naver_kr 단위 테스트.

market_flow/fetchers/naver_kr.py 의 모바일 JSON 파서 / 데스크탑 HTML 파서 /
fetch_today 통합 동작을 검증한다. ``urllib.request.urlopen`` 은 모두
mock 으로 차단되어 실 네이버 호출이 발생하지 않는다.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from market_flow.fetchers import naver_kr  # noqa: E402


def _mock_urlopen_response(text):
    """``urllib.request.urlopen`` 의 응답 객체를 합성.

    fetcher 는 ``r.read().decode(encoding, errors="replace")`` 로 사용한다.
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = text.encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _mock_urlopen_bytes(raw_bytes):
    """euc-kr 인코딩 등 raw 바이트 응답을 위한 헬퍼."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = raw_bytes
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ──────────────────────────────────────────────
#  fetch_daily_summary (모바일 API)
# ──────────────────────────────────────────────

class TestFetchDailySummary:
    def test_returns_seven_keys(self, naver_mobile_kospi_json):
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_response(naver_mobile_kospi_json),
        ):
            result = naver_kr.fetch_daily_summary("KOSPI")
        assert set(result.keys()) == {
            "bizdate",
            "personal",
            "foreign",
            "institutional",
            "program_arb",
            "program_nonarb",
            "program_total",
        }

    def test_strips_commas_and_plus_sign(self, naver_mobile_kospi_json):
        # fixture: personalValue="+1,234" → 1234
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_response(naver_mobile_kospi_json),
        ):
            result = naver_kr.fetch_daily_summary("KOSPI")
        assert result["personal"] == 1234

    def test_none_value_remains_none(self, naver_mobile_kospi_json):
        # fixture: foreignValue=null → None
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_response(naver_mobile_kospi_json),
        ):
            result = naver_kr.fetch_daily_summary("KOSPI")
        assert result["foreign"] is None

    def test_empty_string_becomes_none(self, naver_mobile_kospi_json):
        # fixture: institutionalValue="" → None
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_response(naver_mobile_kospi_json),
        ):
            result = naver_kr.fetch_daily_summary("KOSPI")
        assert result["institutional"] is None

    def test_bizdate_preserved(self, naver_mobile_kospi_json):
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_response(naver_mobile_kospi_json),
        ):
            result = naver_kr.fetch_daily_summary("KOSPI")
        assert result["bizdate"] == "20260525"

    def test_program_keys_parsed(self, naver_mobile_kospi_json):
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_response(naver_mobile_kospi_json),
        ):
            result = naver_kr.fetch_daily_summary("KOSPI")
        assert result["program_arb"] == -2500
        assert result["program_nonarb"] == 3100
        assert result["program_total"] == 600

    def test_kosdaq_parses_all_numeric(self, naver_mobile_kosdaq_json):
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_response(naver_mobile_kosdaq_json),
        ):
            result = naver_kr.fetch_daily_summary("KOSDAQ")
        assert result["personal"] == -500
        assert result["foreign"] == 700
        assert result["institutional"] == -200

    def test_invalid_market_raises_assertion(self):
        with pytest.raises(AssertionError):
            naver_kr.fetch_daily_summary("NYSE")


# ──────────────────────────────────────────────
#  _parse_trend_rows
# ──────────────────────────────────────────────

class TestParseTrendRows:
    def test_empty_body_returns_empty_list(self):
        assert naver_kr._parse_trend_rows("", time_col=True) == []

    def test_time_col_true_first_key_is_time(self):
        body = (
            "<tr>"
            "<td>15:30</td><td>+1</td><td>+2</td><td>+3</td><td>+4</td>"
            "<td>+5</td><td>+6</td><td>+7</td><td>+8</td><td>+9</td><td>+10</td>"
            "</tr>"
        )
        rows = naver_kr._parse_trend_rows(body, time_col=True)
        assert len(rows) == 1
        assert "time" in rows[0]
        assert rows[0]["time"] == "15:30"
        assert "date" not in rows[0]

    def test_time_col_false_first_key_is_date(self):
        body = (
            "<tr>"
            "<td>05.25</td><td>+1</td><td>+2</td><td>+3</td><td>+4</td>"
            "<td>+5</td><td>+6</td><td>+7</td><td>+8</td><td>+9</td><td>+10</td>"
            "</tr>"
        )
        rows = naver_kr._parse_trend_rows(body, time_col=False)
        assert "date" in rows[0]
        assert rows[0]["date"] == "05.25"

    def test_skips_rows_with_fewer_than_11_cells(self):
        body = (
            "<tr><td>15:30</td><td>+1</td><td>+2</td></tr>"  # 3 cells only — skip
            "<tr>"
            "<td>15:00</td><td>+1</td><td>+2</td><td>+3</td><td>+4</td>"
            "<td>+5</td><td>+6</td><td>+7</td><td>+8</td><td>+9</td><td>+10</td>"
            "</tr>"
        )
        rows = naver_kr._parse_trend_rows(body, time_col=True)
        assert len(rows) == 1
        assert rows[0]["time"] == "15:00"

    def test_dash_cell_becomes_zero(self):
        body = (
            "<tr>"
            "<td>15:30</td><td>-</td><td>+2</td><td>+3</td><td>+4</td>"
            "<td>+5</td><td>+6</td><td>+7</td><td>+8</td><td>+9</td><td>+10</td>"
            "</tr>"
        )
        rows = naver_kr._parse_trend_rows(body, time_col=True)
        # 두 번째 셀(personal)이 "-" → 0
        assert rows[0]["personal"] == 0

    def test_numeric_normalization_strips_commas_and_plus(self):
        body = (
            "<tr>"
            "<td>15:30</td><td>+1,234</td><td>-5,678</td><td>+3</td><td>+4</td>"
            "<td>+5</td><td>+6</td><td>+7</td><td>+8</td><td>+9</td><td>+10</td>"
            "</tr>"
        )
        rows = naver_kr._parse_trend_rows(body, time_col=True)
        assert rows[0]["personal"] == 1234
        assert rows[0]["foreign"] == -5678

    def test_all_11_value_keys_present(self):
        body = (
            "<tr>"
            "<td>05.25</td><td>+1</td><td>+2</td><td>+3</td><td>+4</td>"
            "<td>+5</td><td>+6</td><td>+7</td><td>+8</td><td>+9</td><td>+10</td>"
            "</tr>"
        )
        rows = naver_kr._parse_trend_rows(body, time_col=False)
        expected = {
            "date", "personal", "foreign", "institutional", "finance",
            "insurance", "trust", "bank", "other_fin", "pension", "other_corp",
        }
        assert set(rows[0].keys()) == expected


# ──────────────────────────────────────────────
#  fetch_kospi_intraday / fetch_kospi_daily — fixture 기반
# ──────────────────────────────────────────────

class TestFetchKospiHtmlPaths:
    def test_intraday_returns_rows_with_time_key(self, naver_intraday_html):
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_bytes(naver_intraday_html.encode("euc-kr", errors="replace")),
        ):
            rows = naver_kr.fetch_kospi_intraday("20260525")
        assert len(rows) >= 2  # 정상 행 2개, 부족한 행 1개 무시
        for r in rows:
            assert "time" in r
            assert isinstance(r["personal"], int)

    def test_intraday_dash_cell_becomes_zero(self, naver_intraday_html):
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_bytes(naver_intraday_html.encode("euc-kr", errors="replace")),
        ):
            rows = naver_kr.fetch_kospi_intraday("20260525")
        # 두 번째 행 (15:00) 의 finance 셀이 "-" → 0
        row_15h = next(r for r in rows if r["time"] == "15:00")
        assert row_15h["finance"] == 0

    def test_daily_returns_rows_with_date_key(self, naver_daily_html):
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_bytes(naver_daily_html.encode("euc-kr", errors="replace")),
        ):
            rows = naver_kr.fetch_kospi_daily("20260525")
        assert len(rows) == 6
        for r in rows:
            assert "date" in r
            assert "foreign" in r

    def test_daily_numeric_values_are_int(self, naver_daily_html):
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_bytes(naver_daily_html.encode("euc-kr", errors="replace")),
        ):
            rows = naver_kr.fetch_kospi_daily("20260525")
        row_first = rows[0]
        assert row_first["date"] == "05.25"
        assert row_first["personal"] == -1000
        assert row_first["foreign"] == 2000


# ──────────────────────────────────────────────
#  fetch_today (4개 소스 통합)
# ──────────────────────────────────────────────

class TestFetchToday:
    def test_combines_four_sources(self, monkeypatch):
        """fetch_today 는 4개 함수를 모두 호출하고 결과를 dict 로 묶는다."""
        fake_summary = {"bizdate": "20260525", "personal": 1, "foreign": 2,
                        "institutional": 3, "program_arb": 0, "program_nonarb": 0,
                        "program_total": 0}
        fake_intraday = [{"time": "15:30"}]
        fake_daily = [{"date": "05.25"}]
        monkeypatch.setattr(naver_kr, "fetch_daily_summary", lambda m: fake_summary)
        monkeypatch.setattr(naver_kr, "fetch_kospi_intraday", lambda b: fake_intraday)
        monkeypatch.setattr(naver_kr, "fetch_kospi_daily", lambda b: fake_daily)

        result = naver_kr.fetch_today("20260525")
        assert set(result.keys()) == {"bizdate", "kospi", "kosdaq",
                                       "kospi_intraday", "kospi_daily"}
        assert result["bizdate"] == "20260525"
        assert result["kospi"] is fake_summary
        assert result["kospi_intraday"] is fake_intraday
        assert result["kospi_daily"] is fake_daily

    def test_uses_today_when_bizdate_none(self, monkeypatch):
        """bizdate=None 시 datetime.now().strftime("%Y%m%d") 사용."""
        captured = {}
        monkeypatch.setattr(naver_kr, "fetch_daily_summary", lambda m: {})
        monkeypatch.setattr(naver_kr, "fetch_kospi_intraday",
                             lambda b: captured.setdefault("intraday_bizdate", b) or [])
        monkeypatch.setattr(naver_kr, "fetch_kospi_daily",
                             lambda b: captured.setdefault("daily_bizdate", b) or [])

        result = naver_kr.fetch_today(None)
        # 둘 다 같은 bizdate 가 전달되어야 함
        assert captured["intraday_bizdate"] == captured["daily_bizdate"]
        # YYYYMMDD 형식이어야 함 (8자리 숫자)
        assert len(result["bizdate"]) == 8
        assert result["bizdate"].isdigit()
