"""SPEC-MF-TEST-001: weekly.main() + _watch_5d_pct 통합 스모크.

dry-run 환경에서 fetch_kospi_daily 와 yf.download 모킹으로 main() 호출 시
주간 리포트가 stdout 으로 출력되는지 검증. 또한 _watch_5d_pct 의
5거래일 누적 등락 계산 로직을 yfinance mock 으로 직접 검증.

SPEC-MF-SCHED-001 의 ``tests/test_weekly.py`` 는 마지막 거래일 게이트에
집중. 본 파일은 "정상 발송 + dry-run 출력 토큰 + _watch_5d_pct 계산" 검증.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import weekly  # noqa: E402

KST = ZoneInfo("Asia/Seoul")


def _fake_kospi_daily():
    """fetch_kospi_daily 가 반환하는 5거래일 row 합성."""
    return [
        {"date": f"05.{20+i:02d}", "personal": -100 - i, "foreign": 50 + i,
         "institutional": 50, "finance": 10, "insurance": 5, "trust": 5,
         "bank": 5, "other_fin": 5, "pension": 10, "other_corp": 10}
        for i in range(5)
    ]


# ──────────────────────────────────────────────
#  main() 통합
# ──────────────────────────────────────────────

def test_weekly_main_dry_run_outputs_report(monkeypatch, capsys):
    """마지막 거래일 + dry-run → 주간 리포트 stdout 출력."""
    # 2025-09-19 금요일 정상 거래일
    now = datetime(2025, 9, 19, 18, 30, tzinfo=KST)
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")

    with patch("weekly.fetch_kospi_daily", return_value=_fake_kospi_daily()) as mock_kr, \
         patch("weekly._watch_5d_pct", return_value={"QQQ": 2.5, "SMH": -1.5}) as mock_watch, \
         patch("telegram_push.urllib.request.urlopen") as mock_urlopen, \
         patch("weekly.is_last_kr_trading_day_of_week", return_value=True):
        weekly.main(now=now)

    mock_urlopen.assert_not_called()
    mock_kr.assert_called_once()
    mock_watch.assert_called_once()

    out = capsys.readouterr().out
    assert "📅" in out
    assert "주간 매매동향 리포트" in out
    assert "코스피" in out
    assert "워치 ETF" in out
    assert "✅ 주간 리포트 푸시" in out


def test_weekly_main_skips_when_not_last_trading_day(monkeypatch, capsys):
    """is_last_kr_trading_day_of_week False → 침묵 스킵."""
    now = datetime(2025, 9, 18, 18, 30, tzinfo=KST)  # 목요일
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")

    with patch("weekly.fetch_kospi_daily") as mock_kr, \
         patch("weekly._watch_5d_pct") as mock_watch, \
         patch("telegram_push.urllib.request.urlopen") as mock_urlopen, \
         patch("weekly.is_last_kr_trading_day_of_week", return_value=False):
        weekly.main(now=now)

    # 모든 함수가 호출되지 않아야 함
    mock_kr.assert_not_called()
    mock_watch.assert_not_called()
    mock_urlopen.assert_not_called()

    out = capsys.readouterr().out
    # 침묵 스킵 — 어떤 출력도 없음
    assert "주간 리포트 푸시" not in out


# ──────────────────────────────────────────────
#  _watch_5d_pct (yfinance 모킹)
# ──────────────────────────────────────────────

def _build_watch_df(tickers, close_data):
    """다중 ticker yfinance DataFrame 합성 — Close MultiIndex."""
    n = len(next(iter(close_data.values())))
    dates = pd.date_range("2026-05-01", periods=n, freq="B")
    frames = {("Close", t): close_data.get(t, [None] * n) for t in tickers}
    return pd.DataFrame(frames, index=dates)


def test_watch_5d_pct_calculates_5day_cumulative_return():
    """_watch_5d_pct 는 (close[-1] / close[-6] - 1) * 100 을 반환한다."""
    # 6개 거래일 종가: QQQ 100 → 110 (10% 상승)
    closes = {
        "QQQ": [100.0, 102.0, 104.0, 106.0, 108.0, 110.0],
        "SMH": [200.0, 200.0, 200.0, 200.0, 200.0, 180.0],  # -10%
    }
    # WATCH 카탈로그 전부 동일 데이터 (간단화)
    all_tickers = [t for t, _ in weekly.WATCH]
    for t in all_tickers:
        if t not in closes:
            closes[t] = [50.0] * 6  # 0% 변동
    df = _build_watch_df(all_tickers, closes)

    with patch("weekly.yf.download", return_value=df):
        result = weekly._watch_5d_pct()

    assert "QQQ" in result
    assert result["QQQ"] == pytest.approx(10.0)
    assert "SMH" in result
    assert result["SMH"] == pytest.approx(-10.0)


def test_watch_5d_pct_skips_ticker_with_insufficient_data():
    """6개 미만 close 의 ticker 는 결과에서 누락된다."""
    all_tickers = [t for t, _ in weekly.WATCH]
    closes = {t: [100.0, 105.0] for t in all_tickers}  # 모두 2개만
    df = _build_watch_df(all_tickers, closes)

    with patch("weekly.yf.download", return_value=df):
        result = weekly._watch_5d_pct()
    # 어떤 ticker 도 6개 close 가 없으므로 결과는 빈 dict
    assert result == {}


def test_watch_5d_pct_handles_per_ticker_exception():
    """일부 ticker 누락 시 예외를 흡수하고 나머지 ticker 만 결과 포함."""
    # QQQ 만 정상 데이터, 나머지는 DataFrame 에 없음
    df = _build_watch_df(["QQQ"], {"QQQ": [100.0] * 5 + [110.0]})

    with patch("weekly.yf.download", return_value=df):
        result = weekly._watch_5d_pct()

    assert "QQQ" in result
    assert result["QQQ"] == pytest.approx(10.0)
    # 누락 ticker 는 결과에 없음 (예외 흡수)
    for t, _ in weekly.WATCH:
        if t != "QQQ":
            assert t not in result
