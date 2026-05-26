"""SPEC-MF-SCHED-001: daily_kr 분기 테스트.

acceptance.md Section 2 (KR 휴장 인지) + Section 6 (dry-run) 커버.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# daily_kr는 market_flow/ 내부 모듈 — conftest.py에서 sys.path에 추가됨
from market_flow import daily_kr  # noqa: E402


def _kr_holiday_msg(now: datetime) -> str:
    weekday = "월화수목금토일"[now.astimezone(KST).weekday()]
    return f"[KR] {now.astimezone(KST).date().isoformat()} ({weekday}) 오늘은 휴장입니다"


def test_kr_holiday_sends_one_liner_childrens_day(monkeypatch):
    # 2025-05-05 어린이날 (월요일)
    now = datetime(2025, 5, 5, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with patch("market_flow.daily_kr.send") as mock_send, \
         patch("market_flow.daily_kr.fetch_today") as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        mock_send.assert_called_once_with(_kr_holiday_msg(now))
        mock_fetch.assert_not_called()


def test_kr_holiday_sends_one_liner_liberation_day(monkeypatch):
    # 2025-08-15 광복절 (금요일)
    now = datetime(2025, 8, 15, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with patch("market_flow.daily_kr.send") as mock_send, \
         patch("market_flow.daily_kr.fetch_today") as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        mock_send.assert_called_once_with(_kr_holiday_msg(now))
        mock_fetch.assert_not_called()


def test_kr_trading_day_sends_report(monkeypatch):
    # 2025-05-26 월요일 정상 거래일
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {
        "bizdate": "20250526",
        "kospi": {"foreign": 100, "institutional": 200, "personal": -300,
                  "program_arb": 10, "program_nonarb": 20, "program_total": 30},
        "kosdaq": {"foreign": 50, "institutional": 60, "personal": -110,
                   "program_arb": 5, "program_nonarb": 10, "program_total": 15},
        "kospi_daily": [],
    }
    with patch("market_flow.daily_kr.send") as mock_send, \
         patch("market_flow.daily_kr.fetch_today", return_value=fake_data) as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        mock_fetch.assert_called_once()
        # 휴장 메시지가 아닌 정상 보고서가 발송되어야 함
        assert mock_send.call_count == 1
        sent_text = mock_send.call_args.args[0]
        assert "오늘은 휴장입니다" not in sent_text
        assert "코스피" in sent_text or "마감" in sent_text


def test_kr_holiday_dry_run_via_env(monkeypatch, capsys):
    # 휴장 + MARKET_FLOW_DRY_RUN=1 → telegram_push.send는 실제로 호출되지만
    # 내부에서 stdout 분기. 본 테스트는 telegram_push.send를 mock하지 않고
    # urllib.request.urlopen을 mock하여 실제 텔레그램 API 미접촉을 검증한다.
    now = datetime(2025, 5, 5, 18, 10, tzinfo=KST)
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    with patch("market_flow.telegram_push.urllib.request.urlopen") as mock_urlopen, \
         patch("market_flow.daily_kr.fetch_today") as mock_fetch:
        daily_kr.main(now=now)
        mock_urlopen.assert_not_called()
        mock_fetch.assert_not_called()
        captured = capsys.readouterr()
        assert _kr_holiday_msg(now) in captured.out


def test_kr_preserves_positional_date_argv(monkeypatch):
    """argv 위치 인자(YYYYMMDD)가 기존 동작을 유지해야 한다."""
    # 인자로 받은 날짜는 fetch_today에 전달되지만 휴장 판정은 'now'에 의존.
    # 위치 인자가 있을 때도 main()이 정상 작동하는지 확인.
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {
        "bizdate": "20250526",
        "kospi": {"foreign": 0, "institutional": 0, "personal": 0,
                  "program_arb": 0, "program_nonarb": 0, "program_total": 0},
        "kosdaq": {"foreign": 0, "institutional": 0, "personal": 0,
                   "program_arb": 0, "program_nonarb": 0, "program_total": 0},
        "kospi_daily": [],
    }
    with patch("market_flow.daily_kr.send") as mock_send, \
         patch("market_flow.daily_kr.fetch_today", return_value=fake_data) as mock_fetch:
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(argv=["20250526"], now=now)
        # fetch_today가 위치 인자 "20250526"으로 호출되어야 한다
        mock_fetch.assert_called_once_with("20250526")
