"""SPEC-MF-TEST-001: fetchers/naver_kr 단위 테스트.

market_flow/fetchers/naver_kr.py 의 모바일 JSON 파서 / Npay 증권 일별 파서 /
fetch_today 통합 동작을 검증한다. ``urllib.request.urlopen`` 은 모두
mock 으로 차단되어 실 네이버 호출이 발생하지 않는다.
"""

from __future__ import annotations

import json
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
#  fetch_kospi_daily (Npay 증권 API)
# ──────────────────────────────────────────────


_EOK = 100_000_000


def _trend_item(bizdate, **codes):
    """API 일별 항목 합성 — codes 는 investorGubun 코드별 억원 값(c8000=-100 …)."""
    return {
        "bizdate": bizdate,
        "time": "",
        "netAmounts": [
            {"investorGubun": k[1:], "diffValue": str(v * _EOK)}
            for k, v in codes.items()
        ],
    }


# 제로섬·기관소계가 맞는 기본 행: 개인 -300, 외국인 -100(-90-10), 기관 +150, 기타법인 +250
_BALANCED = dict(
    c8000=-300,
    c9000=-90,
    c9001=-10,
    c1000=40,
    c2000=10,
    c3000=20,
    c3100=30,
    c4000=5,
    c5000=15,
    c6000=25,
    c7000=5,
    c7100=250,
)


def _page(items, last=True):
    return json.dumps({"content": items, "last": last})


def _patch_pages(*bodies):
    return patch(
        "market_flow.fetchers.naver_kr.urllib.request.urlopen",
        side_effect=[_mock_urlopen_response(b) for b in bodies],
    )


class TestFetchKospiDaily:
    def test_groups_codes_into_legacy_row(self):
        with _patch_pages(_page([_trend_item("20261001", **_BALANCED)])):
            rows = naver_kr.fetch_kospi_daily("20261001")
        assert rows == [
            {
                "date": "26.10.01",
                "personal": -300,
                "foreign": -100,  # 외국인 + 기타외국인
                "institutional": 150,  # 기관 세부 합
                "finance": 40,
                "insurance": 10,
                "trust": 50,  # 투신 + 사모
                "bank": 5,
                "other_fin": 15,
                "pension": 30,  # 연기금 + 국가·지자체
                "other_corp": 250,
            }
        ]

    def test_rows_satisfy_sum_identities(self):
        with _patch_pages(_page([_trend_item("20261001", **_BALANCED)])):
            (r,) = naver_kr.fetch_kospi_daily("20261001")
        inst_parts = ("finance", "insurance", "trust", "bank", "other_fin", "pension")
        assert r["personal"] + r["foreign"] + r["institutional"] + r["other_corp"] == 0
        assert sum(r[k] for k in inst_parts) == r["institutional"]

    def test_rounds_won_to_eok_after_grouping(self):
        item = {
            "bizdate": "20261001",
            "netAmounts": [
                {"investorGubun": "9000", "diffValue": "-550942000000"},
                {"investorGubun": "9001", "diffValue": "-4887000000"},
            ],
        }
        with _patch_pages(_page([item])):
            (r,) = naver_kr.fetch_kospi_daily("20261001")
        assert r["foreign"] == -5558

    def test_skips_rows_after_bizdate(self):
        # API 는 bizdate 와 무관하게 최신일부터 준다 — 요청일 이하만 채택(E7·재발송)
        items = [
            _trend_item("20261002", **_BALANCED),
            _trend_item("20261001", **_BALANCED),
            _trend_item("20260930", **_BALANCED),
        ]
        with _patch_pages(_page(items)):
            rows = naver_kr.fetch_kospi_daily("20261001")
        assert [r["date"] for r in rows] == ["26.10.01", "26.09.30"]

    def test_caps_at_ten_rows(self):
        items = [_trend_item(f"202609{d:02d}", **_BALANCED) for d in range(30, 10, -1)]
        with _patch_pages(_page(items, last=False)):
            rows = naver_kr.fetch_kospi_daily("20260930")
        assert len(rows) == 10
        assert rows[0]["date"] == "26.09.30"

    def test_pages_until_bizdate_rows_found(self):
        newer = [_trend_item("20261001", **_BALANCED)]
        older = [_trend_item("20260901", **_BALANCED)]
        with _patch_pages(_page(newer, last=False), _page(older)) as m:
            rows = naver_kr.fetch_kospi_daily("20260905")
        assert [r["date"] for r in rows] == ["26.09.01"]
        assert m.call_count == 2

    def test_requests_krx_kospi(self):
        with _patch_pages(_page([])) as m:
            naver_kr.fetch_kospi_daily("20261001")
        url = m.call_args.args[0].full_url
        assert url.startswith(
            "https://stock.naver.com/api/domestic/market/trend/daily?"
        )
        assert "tradeType=KRX" in url and "marketType=KOSPI" in url

    def test_empty_content_warns_and_returns_empty(self, capsys):
        with _patch_pages(_page([])):
            assert naver_kr.fetch_kospi_daily("20261001") == []
        assert "0행" in capsys.readouterr().err

    def test_garbage_value_becomes_zero_not_crash(self, capsys):
        item = _trend_item("20261001", **_BALANCED)
        item["netAmounts"][0]["diffValue"] = "N/A"  # 개인(8000)
        with _patch_pages(_page([item])):
            (r,) = naver_kr.fetch_kospi_daily("20261001")
        assert r["personal"] == 0
        assert "파싱 실패" in capsys.readouterr().err


# ──────────────────────────────────────────────
#  fetch_today (소스 통합)
# ──────────────────────────────────────────────


class TestFetchToday:
    def test_combines_sources(self, monkeypatch):
        """fetch_today 는 모바일 코스피·코스닥 + 코스피 일별을 dict 로 묶는다."""
        fake_summary = {
            "bizdate": "20260525",
            "personal": 1,
            "foreign": 2,
            "institutional": 3,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
        }
        fake_daily = [{"date": "05.25"}]
        monkeypatch.setattr(naver_kr, "fetch_daily_summary", lambda m: fake_summary)
        monkeypatch.setattr(naver_kr, "fetch_kospi_daily", lambda b: fake_daily)

        result = naver_kr.fetch_today("20260525")
        assert set(result.keys()) == {
            "bizdate",
            "kospi",
            "kosdaq",
            "kospi_daily",
        }
        assert result["bizdate"] == "20260525"
        assert result["kospi"] is fake_summary
        assert result["kospi_daily"] is fake_daily

    def test_uses_today_when_bizdate_none(self, monkeypatch):
        """bizdate=None 시 datetime.now().strftime("%Y%m%d") 사용."""
        captured = {}
        monkeypatch.setattr(naver_kr, "fetch_daily_summary", lambda m: {})
        monkeypatch.setattr(
            naver_kr,
            "fetch_kospi_daily",
            lambda b: captured.setdefault("daily_bizdate", b) or [],
        )

        result = naver_kr.fetch_today(None)
        # 일별 fetcher 에 전달된 bizdate 와 결과 bizdate 가 같아야 함
        assert captured["daily_bizdate"] == result["bizdate"]
        # YYYYMMDD 형식이어야 함 (8자리 숫자)
        assert len(result["bizdate"]) == 8
        assert result["bizdate"].isdigit()


# ──────────────────────────────────────────────
#  E4: 모바일 파싱 크래시 가드
# ──────────────────────────────────────────────


class TestParsingRobustness:
    # ── to_int 크래시 가드 (E4, 모바일) ──
    def test_mobile_to_int_garbage_returns_none_not_crash(self, capsys):
        body = json.dumps(
            {
                "dealTrendInfo": {
                    "bizdate": "20260525",
                    "personalValue": "N/A",  # 숫자 아님 → None
                    "foreignValue": "-17,314",
                    "institutionalValue": None,
                },
                "programTrendInfo": {},
            }
        )
        with patch(
            "market_flow.fetchers.naver_kr.urllib.request.urlopen",
            return_value=_mock_urlopen_response(body),
        ):
            result = naver_kr.fetch_daily_summary("KOSPI")
        assert result["personal"] is None  # 가비지 → None (크래시 아님)
        assert result["foreign"] == -17314  # 정상값은 그대로
        assert "파싱 실패" in capsys.readouterr().err
