"""SPEC-MF-SCHED-001: weekly 분기 테스트.

acceptance.md Section 4 (주간 리포트 이월 발송) 커버.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

from market_flow import weekly  # noqa: E402

FAKE_KOSPI_DAILY = [
    {
        "date": "09.19",
        "personal": -100,
        "foreign": 50,
        "institutional": 50,
        "finance": 10,
        "insurance": 5,
        "trust": 5,
        "bank": 5,
        "other_fin": 5,
        "pension": 10,
        "other_corp": 10,
    },
]

FAKE_KOSDAQ_DAILY = [
    {"date": "09.19", "personal": -30, "foreign": 10, "institutional": 20}
]


def test_weekly_sends_on_friday_normal(monkeypatch):
    # 2025-09-19 금요일 정상 거래일
    now = datetime(2025, 9, 19, 18, 30, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.weekly.send") as mock_send,
        patch(
            "market_flow.weekly.fetch_kospi_daily", return_value=FAKE_KOSPI_DAILY
        ) as mock_fetch,
        patch(
            "market_flow.weekly.fetch_kosdaq_daily", return_value=FAKE_KOSDAQ_DAILY
        ) as mock_kosdaq,
        patch("market_flow.weekly.KISClient"),
        patch("market_flow.weekly._watch_5d_pct", return_value={"QQQ": 1.5}),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        weekly.main(now=now)
        mock_fetch.assert_called_once()
        mock_kosdaq.assert_called_once()
        mock_send.assert_called_once()


def test_weekly_skips_on_thursday_when_friday_is_trading_day(monkeypatch):
    # 2025-09-18 목요일, 다음날 금요일은 정상 거래일 → 침묵 스킵
    now = datetime(2025, 9, 18, 18, 30, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.weekly.send") as mock_send,
        patch("market_flow.weekly.fetch_kospi_daily") as mock_fetch,
        patch("market_flow.weekly._watch_5d_pct") as mock_watch,
    ):
        weekly.main(now=now)
        mock_send.assert_not_called()
        mock_fetch.assert_not_called()
        mock_watch.assert_not_called()


def test_weekly_sends_on_thursday_when_friday_holiday(monkeypatch):
    # 2025-08-14 목요일, 8/15 광복절 → 목요일에 이월 발송
    now = datetime(2025, 8, 14, 18, 30, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.weekly.send") as mock_send,
        patch(
            "market_flow.weekly.fetch_kospi_daily", return_value=FAKE_KOSPI_DAILY
        ) as mock_fetch,
        patch(
            "market_flow.weekly.fetch_kosdaq_daily", return_value=FAKE_KOSDAQ_DAILY
        ) as mock_kosdaq,
        patch("market_flow.weekly.KISClient"),
        patch("market_flow.weekly._watch_5d_pct", return_value={"QQQ": 1.0}),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        weekly.main(now=now)
        mock_fetch.assert_called_once()
        mock_kosdaq.assert_called_once()
        mock_send.assert_called_once()


def test_weekly_skips_on_friday_holiday(monkeypatch):
    # 2025-08-15 금요일 광복절 → 오늘이 거래일 아님 → 스킵
    now = datetime(2025, 8, 15, 18, 30, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.weekly.send") as mock_send,
        patch("market_flow.weekly.fetch_kospi_daily") as mock_fetch,
    ):
        weekly.main(now=now)
        mock_send.assert_not_called()
        mock_fetch.assert_not_called()


def test_weekly_dry_run_on_last_trading_day(monkeypatch, capsys):
    now = datetime(2025, 9, 19, 18, 30, tzinfo=KST)
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    with (
        patch("market_flow.telegram_push.urllib.request.urlopen") as mock_urlopen,
        patch("market_flow.weekly.fetch_kospi_daily", return_value=FAKE_KOSPI_DAILY),
        patch("market_flow.weekly.fetch_kosdaq_daily", return_value=FAKE_KOSDAQ_DAILY),
        patch("market_flow.weekly.KISClient"),
        patch("market_flow.weekly._watch_5d_pct", return_value={"QQQ": 1.5}),
    ):
        weekly.main(now=now)
        mock_urlopen.assert_not_called()
        out = capsys.readouterr().out
        # 주간 리포트 본문이 stdout에 출력되어야 함
        assert "주간" in out or "코스피" in out
        assert "코스닥" in out


def test_weekly_continues_when_kosdaq_fetch_fails(monkeypatch, capsys):
    now = datetime(2025, 9, 19, 18, 30, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.weekly.send") as mock_send,
        patch("market_flow.weekly.fetch_kospi_daily", return_value=FAKE_KOSPI_DAILY),
        patch(
            "market_flow.weekly.fetch_kosdaq_daily",
            side_effect=RuntimeError("kis down"),
        ),
        patch("market_flow.weekly.KISClient"),
        patch("market_flow.weekly._watch_5d_pct", return_value={"QQQ": 1.5}),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        weekly.main(now=now)

    mock_send.assert_called_once()
    captured = capsys.readouterr()
    assert "코스닥 일별 수집 실패" in captured.err
    assert "✅ 주간 리포트 푸시" in captured.out


def test_watch_5d_pct_single_ticker(monkeypatch):
    # WATCH 가 1종이면 yf.download 가 평탄 Close 컬럼을 줘도 KeyError 없이 처리해야
    # 한다(#10 I-cleanup 단일/멀티 가드). 현재 WATCH 는 8종이라 미발화 잠복 경로.
    import pandas as pd

    monkeypatch.setattr(weekly, "WATCH", [("QQQ", "나스닥100")])
    df = pd.DataFrame(
        {"Close": [100.0, 100.0, 100.0, 100.0, 100.0, 110.0]},
        index=pd.date_range("2026-05-20", periods=6, freq="B"),
    )
    with patch("market_flow.weekly.yf.download", return_value=df):
        out = weekly._watch_5d_pct()
    assert set(out.keys()) == {"QQQ"}
    assert round(out["QQQ"], 6) == 10.0  # (110/100 - 1) * 100
