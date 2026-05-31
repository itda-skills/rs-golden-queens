"""SPEC-MF-TEST-001: fetchers/us_market 단위 테스트.

market_flow/fetchers/us_market.py 의 _fetch_yf yfinance 어댑터 / fetch_us_close /
fetch_watch_history 동작을 검증한다. ``yfinance.download`` 는 mock 으로
차단되어 실 야후 호출이 발생하지 않는다.

NOTE: yfinance 응답은 다중 ticker 시 MultiIndex 컬럼 (Open/Close/Volume/...,
ticker) 의 DataFrame, 단일 ticker 시 평탄 컬럼 DataFrame. 본 테스트는
plan.md R6 옵션 B 에 따라 pickle fixture 대신 코드 내 DataFrame 을
명시적으로 구성한다 — 실 응답 스키마 회귀 안전망은 live 마커 테스트가 담당.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from market_flow.fetchers import us_market  # noqa: E402

# ──────────────────────────────────────────────
#  DataFrame 빌더 (yfinance 응답 합성)
# ──────────────────────────────────────────────


def _build_multi_df(tickers, close_data, volume_data=None, dates=None):
    """다중 ticker yfinance DataFrame 합성 (MultiIndex 컬럼).

    Args:
        tickers: ticker 심볼 리스트 (예: ["^GSPC", "^IXIC"])
        close_data: {ticker: [close_values]} dict
        volume_data: {ticker: [volume_values]} dict (옵션)
        dates: DatetimeIndex (옵션)
    """
    n = len(next(iter(close_data.values())))
    if dates is None:
        dates = pd.date_range("2026-05-01", periods=n, freq="B")

    frames = {}
    for t in tickers:
        frames[("Close", t)] = close_data.get(t, [None] * n)
        if volume_data is not None:
            frames[("Volume", t)] = volume_data.get(t, [0] * n)
    return pd.DataFrame(frames, index=dates)


def _build_single_df(close_values, volume_values=None, dates=None):
    """단일 ticker yfinance DataFrame (평탄 컬럼)."""
    n = len(close_values)
    if dates is None:
        dates = pd.date_range("2026-05-01", periods=n, freq="B")
    data = {"Close": close_values}
    if volume_values is not None:
        data["Volume"] = volume_values
    return pd.DataFrame(data, index=dates)


# ──────────────────────────────────────────────
#  _fetch_yf — 기본 구조
# ──────────────────────────────────────────────


class TestFetchYfBasic:
    def test_returns_dict_with_expected_keys(self):
        tickers = [("^GSPC", "S&P500"), ("^IXIC", "나스닥")]
        df = _build_multi_df(
            ["^GSPC", "^IXIC"],
            {"^GSPC": [100.0, 110.0], "^IXIC": [200.0, 220.0]},
            {"^GSPC": [1000, 2000], "^IXIC": [3000, 4000]},
        )
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        for t, _ in tickers:
            assert t in result
            assert set(result[t].keys()) == {
                "label",
                "close",
                "pct",
                "vol_ratio",
                "date",
            }

    def test_pct_calculation(self):
        tickers = [("^GSPC", "S&P500")]
        df = _build_single_df([100.0, 110.0])
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        # (110 - 100) / 100 * 100 = 10.0
        assert result["^GSPC"]["pct"] == pytest.approx(10.0)
        assert result["^GSPC"]["close"] == 110.0

    def test_label_propagated(self):
        tickers = [("^GSPC", "S&P500")]
        df = _build_single_df([100.0, 110.0])
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        assert result["^GSPC"]["label"] == "S&P500"

    def test_date_iso_format(self):
        tickers = [("^GSPC", "S&P500")]
        dates = pd.date_range("2026-05-20", periods=2, freq="B")
        df = _build_single_df([100.0, 110.0], dates=dates)
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        # 마지막 날짜의 ISO 형식 (YYYY-MM-DD)
        assert result["^GSPC"]["date"] == str(dates[-1].date())


# ──────────────────────────────────────────────
#  _fetch_yf — vol_ratio 계산
# ──────────────────────────────────────────────


class TestFetchYfVolRatio:
    def test_vol_ratio_with_six_days(self):
        """6개 거래량 데이터 → vol_ratio = vol[-1] / mean(vol[-6:-1])."""
        tickers = [("^GSPC", "S&P500")]
        # 종가 6개, 거래량 6개. 마지막 거래량 = 200, 앞 5개 평균 = 100 → 2.0
        df = _build_single_df(
            close_values=[100.0] * 5 + [110.0],
            volume_values=[100, 100, 100, 100, 100, 200],
        )
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        assert result["^GSPC"]["vol_ratio"] == pytest.approx(2.0)

    def test_vol_ratio_none_when_fewer_than_six_volumes(self):
        """거래량 5개 → vol_ratio = None."""
        tickers = [("^GSPC", "S&P500")]
        df = _build_single_df(
            close_values=[100.0, 110.0, 120.0, 130.0, 140.0],
            volume_values=[100, 100, 100, 100, 100],
        )
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        assert result["^GSPC"]["vol_ratio"] is None


# ──────────────────────────────────────────────
#  _fetch_yf — 예외 / 경계
# ──────────────────────────────────────────────


class TestFetchYfEdgeCases:
    def test_returns_none_when_close_has_fewer_than_two(self):
        """dropna 후 close 가 1개 이하면 ticker = None."""
        tickers = [("^GSPC", "S&P500")]
        df = _build_single_df([100.0])  # 1개만
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        assert result["^GSPC"] is None

    def test_returns_none_when_close_all_nan(self):
        tickers = [("^GSPC", "S&P500")]
        df = _build_single_df([float("nan"), float("nan")])
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        assert result["^GSPC"] is None

    def test_per_ticker_exception_does_not_propagate(self):
        """일부 ticker 에서 KeyError 등 발생 시 해당 ticker 만 None, 나머지 정상."""
        tickers = [("^GSPC", "S&P500"), ("^MISSING", "없음")]
        # ^MISSING ticker 가 DataFrame 에 없도록 합성
        df = _build_multi_df(
            ["^GSPC"],  # ^MISSING 미포함
            {"^GSPC": [100.0, 110.0]},
            {"^GSPC": [1000, 2000]},
        )
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        # 정상 ticker 는 dict, 누락 ticker 는 None
        assert isinstance(result["^GSPC"], dict)
        assert result["^MISSING"] is None

    def test_no_volume_column_results_in_none_vol_ratio(self):
        """Volume 컬럼 자체가 없으면 vol_ratio = None."""
        tickers = [("^GSPC", "S&P500")]
        df = _build_single_df([100.0, 110.0], volume_values=None)  # Volume 없음
        with patch("market_flow.fetchers.us_market.yf.download", return_value=df):
            result = us_market._fetch_yf(tickers)
        assert result["^GSPC"]["vol_ratio"] is None


# ──────────────────────────────────────────────
#  _fetch_yf — target_date 처리
# ──────────────────────────────────────────────


class TestFetchYfTargetDate:
    def test_target_date_passed_through_to_yf_download(self):
        tickers = [("^GSPC", "S&P500")]
        df = _build_single_df([100.0, 110.0])
        with patch(
            "market_flow.fetchers.us_market.yf.download", return_value=df
        ) as mock_dl:
            us_market._fetch_yf(tickers, target_date="2026-05-20")
            # start/end 인자가 전달되었는지 확인
            _, kwargs = mock_dl.call_args
            assert "start" in kwargs
            assert "end" in kwargs


# ──────────────────────────────────────────────
#  fetch_us_close — 6개 카테고리 통합
# ──────────────────────────────────────────────


class TestFetchUsClose:
    def test_returns_category_keys_with_oas(self):
        """yfinance 6개 카테고리 + 하이일드 OAS(#10 I6) 키 존재. FRED 는 mock."""
        with (
            patch("market_flow.fetchers.us_market._fetch_yf", return_value={"X": None}),
            patch(
                "market_flow.fetchers.us_market.fetch_high_yield_oas",
                return_value={"value": 2.7},
            ),
        ):
            result = us_market.fetch_us_close()
        assert set(result.keys()) == {
            "indices",
            "volatility",
            "risk_onoff",
            "macro",
            "sectors",
            "watch",
            "high_yield_oas",
        }

    def test_calls_fetch_yf_six_times(self):
        with (
            patch(
                "market_flow.fetchers.us_market._fetch_yf", return_value={}
            ) as mock_yf,
            patch(
                "market_flow.fetchers.us_market.fetch_high_yield_oas",
                return_value=None,
            ),
        ):
            us_market.fetch_us_close()
        assert mock_yf.call_count == 6

    def test_propagates_target_date(self):
        with (
            patch(
                "market_flow.fetchers.us_market._fetch_yf", return_value={}
            ) as mock_yf,
            patch(
                "market_flow.fetchers.us_market.fetch_high_yield_oas",
                return_value=None,
            ) as mock_oas,
        ):
            us_market.fetch_us_close(target_date="2026-05-22")
        # 6번 호출 모두 target_date 전달
        for call in mock_yf.call_args_list:
            assert call.args[1] == "2026-05-22"
        # 과거일 재발송엔 OAS 를 붙이지 않는다(FRED 최신값 ↔ 그 날짜 어긋남 방지)
        mock_oas.assert_not_called()


# ──────────────────────────────────────────────
#  fetch_watch_history
# ──────────────────────────────────────────────


class TestFetchWatchHistory:
    def test_invokes_fetch_yf_with_watch_catalog(self):
        with patch(
            "market_flow.fetchers.us_market._fetch_yf", return_value={}
        ) as mock_yf:
            us_market.fetch_watch_history()
        mock_yf.assert_called_once()
        # 첫 인자가 WATCH 카탈로그
        assert mock_yf.call_args.args[0] is us_market.WATCH
