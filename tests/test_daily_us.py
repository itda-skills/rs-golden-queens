"""SPEC-MF-SCHED-001: daily_us 분기 테스트.

acceptance.md Section 1 (DST 게이트), 3 (US 휴장), 7.1 (이중 발송 회귀) 커버.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

ET = ZoneInfo("America/New_York")

import daily_us  # noqa: E402


US_HOLIDAY_MSG = "[US] 오늘은 휴장입니다"


# ──────────────────────────────────────────────
#  DST 게이트
# ──────────────────────────────────────────────

def test_edt_season_edt_job_passes(monkeypatch):
    # 2025-09-15 EDT 시즌 평일, MARKET_SCHEDULE=edt → 통과 + 정상 발송
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "edt")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {"indices": {}, "volatility": {}, "risk_onoff": {}, "macro": {},
                 "sectors": {}, "watch": {}}
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close", return_value=fake_data) as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_fetch.assert_called_once()
        mock_send.assert_called_once()


def test_edt_season_est_job_blocked(monkeypatch):
    now = datetime(2025, 9, 15, 17, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "est")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close") as mock_fetch:
        with pytest.raises(SystemExit) as exc:
            daily_us.main(now=now)
        assert exc.value.code == 0
        mock_send.assert_not_called()
        mock_fetch.assert_not_called()


def test_est_season_est_job_passes(monkeypatch):
    # 2025-12-15 월요일 EST 시즌
    now = datetime(2025, 12, 15, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "est")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {"indices": {}, "volatility": {}, "risk_onoff": {}, "macro": {},
                 "sectors": {}, "watch": {}}
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close", return_value=fake_data) as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_fetch.assert_called_once()
        mock_send.assert_called_once()


def test_est_season_edt_job_blocked(monkeypatch):
    now = datetime(2025, 12, 15, 17, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "edt")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close") as mock_fetch:
        with pytest.raises(SystemExit) as exc:
            daily_us.main(now=now)
        assert exc.value.code == 0
        mock_send.assert_not_called()
        mock_fetch.assert_not_called()


def test_manual_dispatch_no_schedule_env_passes(monkeypatch):
    """workflow_dispatch 수동 실행 시 MARKET_SCHEDULE 미설정 → 게이트 무시."""
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {"indices": {}, "volatility": {}, "risk_onoff": {}, "macro": {},
                 "sectors": {}, "watch": {}}
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close", return_value=fake_data):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_send.assert_called_once()


# ──────────────────────────────────────────────
#  US 휴장
# ──────────────────────────────────────────────

def test_us_christmas_sends_one_liner(monkeypatch):
    now = datetime(2025, 12, 25, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "est")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close") as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_send.assert_called_once_with(US_HOLIDAY_MSG)
        mock_fetch.assert_not_called()


def test_us_independence_day_sends_one_liner(monkeypatch):
    now = datetime(2025, 7, 4, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "edt")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close") as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_send.assert_called_once_with(US_HOLIDAY_MSG)
        mock_fetch.assert_not_called()


def test_us_thanksgiving_friday_is_normal_send(monkeypatch):
    """11/28 반장일은 거래일 → 정상 발송."""
    now = datetime(2025, 11, 28, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "est")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {"indices": {}, "volatility": {}, "risk_onoff": {}, "macro": {},
                 "sectors": {}, "watch": {}}
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close", return_value=fake_data) as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_fetch.assert_called_once()
        assert mock_send.call_count == 1
        sent = mock_send.call_args.args[0]
        assert sent != US_HOLIDAY_MSG


def test_us_holiday_dry_run(monkeypatch, capsys):
    now = datetime(2025, 12, 25, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "est")
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    with patch("telegram_push.urllib.request.urlopen") as mock_urlopen, \
         patch("daily_us.fetch_us_close") as mock_fetch:
        daily_us.main(now=now)
        mock_urlopen.assert_not_called()
        mock_fetch.assert_not_called()
        out = capsys.readouterr().out
        assert US_HOLIDAY_MSG in out


# ──────────────────────────────────────────────
#  이중 발송 회귀 차단 (Scenario 7.1)
# ──────────────────────────────────────────────

def test_no_double_send_on_edt_season(monkeypatch):
    """EDT 시즌에 EDT 잡 + EST 잡 순차 호출 → send 총 1회만 호출."""
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {"indices": {}, "volatility": {}, "risk_onoff": {}, "macro": {},
                 "sectors": {}, "watch": {}}
    with patch("daily_us.send") as mock_send, \
         patch("daily_us.fetch_us_close", return_value=fake_data):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        # EDT 잡 (통과)
        monkeypatch.setenv("MARKET_SCHEDULE", "edt")
        daily_us.main(now=now)
        # EST 잡 (차단)
        monkeypatch.setenv("MARKET_SCHEDULE", "est")
        with pytest.raises(SystemExit):
            daily_us.main(now=now)
        assert mock_send.call_count == 1
