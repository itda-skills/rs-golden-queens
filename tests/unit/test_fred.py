"""SPEC-MF-TEST-001: fetchers/fred 단위 테스트 (#10 I6).

FRED CSV 파싱(헤더·결측 '.'·전일대비), 단일행/빈 응답, 네트워크 실패 degrade 를
검증한다. urllib.request.urlopen 은 mock 으로 차단.
"""

from __future__ import annotations

import math
import urllib.error
from unittest.mock import MagicMock, patch

from market_flow.fetchers import fred


def _mock_resp(text):
    m = MagicMock()
    m.read.return_value = text.encode("utf-8")
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    return m


_CSV = (
    "observation_date,BAMLH0A0HYM2\n2026-05-26,2.72\n2026-05-27,2.71\n2026-05-28,2.74\n"
)


class TestFetchFredLatest:
    def test_latest_value_and_change(self):
        with patch(
            "market_flow.fetchers.fred.urllib.request.urlopen",
            return_value=_mock_resp(_CSV),
        ):
            r = fred.fetch_fred_latest("BAMLH0A0HYM2")
        assert r["date"] == "2026-05-28"
        assert r["value"] == 2.74
        assert r["prev"] == 2.71
        assert r["change"] == round(2.74 - 2.71, 2)  # 발행 시점 소수 2자리 확정(SoT)

    def test_change_minus_zero_normalized(self):
        # value-prev 가 round2 에서 -0.0 이어도 +0.0 으로 정규화(텔레그램·웹 부호 일치)
        csv = "observation_date,X\n2026-05-27,2.001\n2026-05-28,2.000\n"
        with patch(
            "market_flow.fetchers.fred.urllib.request.urlopen",
            return_value=_mock_resp(csv),
        ):
            r = fred.fetch_fred_latest("X")
        assert r["change"] == 0.0
        assert math.copysign(1.0, r["change"]) == 1.0  # +0.0, not -0.0

    def test_change_rounded_to_two_decimals(self):
        # 발행 시점 round2 — 0.0099 같은 미세차도 0.01 로 확정(경계 모호 제거)
        csv = "observation_date,X\n2026-05-27,2.70\n2026-05-28,2.7099\n"
        with patch(
            "market_flow.fetchers.fred.urllib.request.urlopen",
            return_value=_mock_resp(csv),
        ):
            r = fred.fetch_fred_latest("X")
        assert r["change"] == 0.01

    def test_skips_missing_dot_rows(self):
        csv = "observation_date,X\n2026-05-26,2.70\n2026-05-27,.\n2026-05-28,2.75\n"
        with patch(
            "market_flow.fetchers.fred.urllib.request.urlopen",
            return_value=_mock_resp(csv),
        ):
            r = fred.fetch_fred_latest("X")
        assert r["value"] == 2.75
        assert r["prev"] == 2.70  # '.' 행 건너뛰고 직전 유효값과 비교

    def test_single_row_no_change(self):
        with patch(
            "market_flow.fetchers.fred.urllib.request.urlopen",
            return_value=_mock_resp("observation_date,X\n2026-05-28,2.74\n"),
        ):
            r = fred.fetch_fred_latest("X")
        assert r["value"] == 2.74
        assert r["prev"] is None
        assert r["change"] is None

    def test_empty_returns_none(self):
        with patch(
            "market_flow.fetchers.fred.urllib.request.urlopen",
            return_value=_mock_resp("observation_date,X\n"),
        ):
            assert fred.fetch_fred_latest("X") is None

    def test_all_missing_returns_none(self):
        csv = "observation_date,X\n2026-05-27,.\n2026-05-28,.\n"
        with patch(
            "market_flow.fetchers.fred.urllib.request.urlopen",
            return_value=_mock_resp(csv),
        ):
            assert fred.fetch_fred_latest("X") is None

    def test_network_failure_degrades_to_none(self):
        with (
            patch(
                "market_flow.fetchers.fred.urllib.request.urlopen",
                side_effect=urllib.error.URLError("down"),
            ),
            patch("market_flow._retry.time.sleep"),
        ):
            assert fred.fetch_fred_latest("X") is None


class TestHighYieldOas:
    def test_uses_correct_series_id(self):
        with patch(
            "market_flow.fetchers.fred.fetch_fred_latest", return_value={"value": 2.7}
        ) as f:
            fred.fetch_high_yield_oas()
        f.assert_called_once_with("BAMLH0A0HYM2")
