"""SPEC-MF-TEST-001: daily_us.main() 통합 스모크.

dry-run 환경에서 fetch_us_close 모킹으로 main() 호출 시 SystemExit 없이
미국장 텔레그램 본문이 stdout 으로 출력되는지 검증.

SPEC-MF-SCHED-001 의 ``tests/test_daily_us.py`` 는 DST 게이트/휴장에
집중. 본 파일은 "거래일 정상 흐름 + dry-run 출력 토큰" 검증에 집중.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from market_flow import daily_us  # noqa: E402

ET = ZoneInfo("America/New_York")


def _us_entry(label, close=100.0, pct=1.0, vol_ratio=None, date="2026-05-22"):
    return {
        "label": label,
        "close": close,
        "pct": pct,
        "vol_ratio": vol_ratio,
        "date": date,
    }


def _fake_us_data():
    return {
        "indices": {
            "^GSPC": _us_entry("S&P500", close=5000.0, pct=0.5),
            "^IXIC": _us_entry("나스닥", close=16000.0, pct=0.8),
            "^DJI": _us_entry("다우", close=39000.0, pct=0.3),
            "^RUT": _us_entry("러셀2000", close=2000.0, pct=-0.2),
        },
        "volatility": {
            "^VIX": _us_entry("VIX", close=15.0, pct=-2.0),
            "^VVIX": _us_entry("VVIX", close=80.0, pct=-1.0),
            "^SKEW": _us_entry("SKEW", close=140.0, pct=0.5),
        },
        "risk_onoff": {
            "HYG": _us_entry("고수익채권", close=75.0, pct=0.3),
            "IEF": _us_entry("7-10Y국채", close=95.0, pct=0.0),
        },
        "macro": {
            "^TNX": _us_entry("10Y금리", close=4.5, pct=0.5),
            "^TYX": _us_entry("30Y금리", close=4.7, pct=0.6),
            "DX-Y.NYB": _us_entry("DXY", close=104.0, pct=0.2),
            "KRW=X": _us_entry("원달러", close=1370.0, pct=-0.1),
            "CL=F": _us_entry("WTI", close=78.5, pct=1.0),
            "GC=F": _us_entry("금", close=2400.0, pct=0.5),
        },
        "sectors": {
            "XLK": _us_entry("기술", close=200.0, pct=1.2),
            "XLF": _us_entry("금융", close=50.0, pct=0.6),
            "XLV": _us_entry("헬스케어", close=140.0, pct=-0.3),
        },
        "watch": {
            "QQQ": _us_entry("나스닥100", close=500.0, pct=1.0, vol_ratio=1.6),
            "SMH": _us_entry("반도체", close=300.0, pct=2.0, vol_ratio=1.2),
        },
    }


def test_daily_us_main_dry_run_outputs_report(monkeypatch, capsys):
    """거래일 + dry-run → SystemExit 없이 미국장 본문 stdout."""
    # 2025-09-15 EDT 시즌 평일
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    # MARKET_SCHEDULE 미설정 → DST 게이트 우회
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)

    with (
        patch(
            "market_flow.daily_us.fetch_us_close", return_value=_fake_us_data()
        ) as mock_fetch,
        patch("market_flow.telegram_push.urllib.request.urlopen") as mock_urlopen,
        patch("market_flow.daily_us.is_us_trading_day", return_value=True),
    ):
        daily_us.main(now=now)

    mock_urlopen.assert_not_called()
    mock_fetch.assert_called_once()

    out = capsys.readouterr().out
    assert "🇺🇸" in out
    assert "미국장 마감" in out
    assert "S&P500" in out or "나스닥" in out
    assert "✅ 미국장 푸시" in out


def test_daily_us_main_uses_argv_target_date(monkeypatch):
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)

    with (
        patch(
            "market_flow.daily_us.fetch_us_close", return_value=_fake_us_data()
        ) as mock_fetch,
        patch("market_flow.telegram_push.urllib.request.urlopen"),
        patch("market_flow.daily_us.is_us_trading_day", return_value=True),
    ):
        daily_us.main(argv=["2025-09-12"], now=now)
    mock_fetch.assert_called_once_with("2025-09-12")
