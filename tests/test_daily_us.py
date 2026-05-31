"""SPEC-MF-SCHED-001: daily_us 분기 테스트.

acceptance.md Section 1 (DST 게이트), 3 (US 휴장), 7.1 (이중 발송 회귀) 커버.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

ET = ZoneInfo("America/New_York")

from market_flow import daily_us  # noqa: E402


def _fake_data(now: datetime) -> dict:
    """정상 발송 경로용 mock — 모든 섹션 1종(해당일 date)으로 채워

    전멸(E5)·부분실패(I8)·stale(E1) 경고가 붙지 않는 '완전 정상' 데이터.
    """
    d = now.astimezone(ET).date().isoformat()

    def q(ticker: str, label: str) -> dict:
        return {
            ticker: {
                "label": label,
                "close": 100.0,
                "pct": 0.5,
                "vol_ratio": None,
                "date": d,
            }
        }

    return {
        "indices": q("^GSPC", "S&P500"),
        "volatility": q("^VIX", "VIX"),
        "risk_onoff": q("HYG", "고수익채권"),
        "macro": q("^TNX", "10Y금리"),
        "sectors": q("XLK", "기술"),
        "watch": q("QQQ", "나스닥100"),
    }


def _us_holiday_msg(now: datetime) -> str:
    weekday = "월화수목금토일"[now.astimezone(ET).weekday()]
    return f"[US] {now.astimezone(ET).date().isoformat()} ({weekday}) 오늘은 휴장입니다"


# ──────────────────────────────────────────────
#  DST 게이트
# ──────────────────────────────────────────────


def test_edt_season_edt_job_passes(monkeypatch):
    # 2025-09-15 EDT 시즌 평일, MARKET_SCHEDULE=edt → 통과 + 정상 발송
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "edt")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = _fake_data(now)
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch(
            "market_flow.daily_us.fetch_us_close", return_value=fake_data
        ) as mock_fetch,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_fetch.assert_called_once()
        mock_send.assert_called_once()


def test_edt_season_est_job_blocked(monkeypatch):
    now = datetime(2025, 9, 15, 17, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "est")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close") as mock_fetch,
    ):
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
    fake_data = _fake_data(now)
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch(
            "market_flow.daily_us.fetch_us_close", return_value=fake_data
        ) as mock_fetch,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_fetch.assert_called_once()
        mock_send.assert_called_once()


def test_est_season_edt_job_blocked(monkeypatch):
    now = datetime(2025, 12, 15, 17, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "edt")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close") as mock_fetch,
    ):
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
    fake_data = _fake_data(now)
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close", return_value=fake_data),
    ):
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
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close") as mock_fetch,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_send.assert_called_once_with(_us_holiday_msg(now))
        mock_fetch.assert_not_called()


def test_us_independence_day_sends_one_liner(monkeypatch):
    now = datetime(2025, 7, 4, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "edt")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close") as mock_fetch,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_send.assert_called_once_with(_us_holiday_msg(now))
        mock_fetch.assert_not_called()


def test_us_thanksgiving_friday_is_normal_send(monkeypatch):
    """11/28 반장일은 거래일 → 정상 발송."""
    now = datetime(2025, 11, 28, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "est")
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = _fake_data(now)
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch(
            "market_flow.daily_us.fetch_us_close", return_value=fake_data
        ) as mock_fetch,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_fetch.assert_called_once()
        assert mock_send.call_count == 1
        sent = mock_send.call_args.args[0]
        assert "오늘은 휴장입니다" not in sent


def test_us_holiday_dry_run(monkeypatch, capsys):
    now = datetime(2025, 12, 25, 16, 30, tzinfo=ET)
    monkeypatch.setenv("MARKET_SCHEDULE", "est")
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    with (
        patch("market_flow.telegram_push.urllib.request.urlopen") as mock_urlopen,
        patch("market_flow.daily_us.fetch_us_close") as mock_fetch,
    ):
        daily_us.main(now=now)
        mock_urlopen.assert_not_called()
        mock_fetch.assert_not_called()
        out = capsys.readouterr().out
        assert _us_holiday_msg(now) in out


# ──────────────────────────────────────────────
#  이중 발송 회귀 차단 (Scenario 7.1)
# ──────────────────────────────────────────────


def test_no_double_send_on_edt_season(monkeypatch):
    """EDT 시즌에 EDT 잡 + EST 잡 순차 호출 → send 총 1회만 호출."""
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = _fake_data(now)
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close", return_value=fake_data),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        # EDT 잡 (통과)
        monkeypatch.setenv("MARKET_SCHEDULE", "edt")
        daily_us.main(now=now)
        # EST 잡 (차단)
        monkeypatch.setenv("MARKET_SCHEDULE", "est")
        with pytest.raises(SystemExit):
            daily_us.main(now=now)
        assert mock_send.call_count == 1


# ──────────────────────────────────────────────
#  데이터 정합 (#10 P0-a)
# ──────────────────────────────────────────────


def test_all_sections_empty_sends_failure_notice(monkeypatch):
    """E5: 전체 미수집이면 'None 미국장 마감' 빈 표 대신 명시 실패 안내 + 발행 스킵."""
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    empty = {
        "indices": {},
        "volatility": {},
        "risk_onoff": {},
        "macro": {},
        "sectors": {},
        "watch": {},
    }
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close", return_value=empty),
        patch("market_flow.daily_us.maybe_publish") as mock_pub,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        mock_send.assert_called_once()
        sent = mock_send.call_args.args[0]
        assert "수집 실패" in sent
        assert "None" not in sent
        mock_pub.assert_not_called()  # None 스냅샷(snapshots/us/None.json) 발행 차단


def test_stale_target_mode_warns_and_skips_publish(monkeypatch):
    """E1/#4: target 모드(과거일 재발행)에서 데이터일≠요청일 → 경고 + 발행 스킵."""
    now = datetime(2025, 9, 16, 16, 30, tzinfo=ET)  # argv 로 덮어씀
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    # 요청은 2025-09-16 인데 yfinance가 직전 거래일(09-15) 데이터를 반환
    stale = _fake_data(datetime(2025, 9, 15, 16, 30, tzinfo=ET))  # date=2025-09-15
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close", return_value=stale),
        patch("market_flow.daily_us.maybe_publish") as mock_pub,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(argv=["2025-09-16"], now=now)
        sent = mock_send.call_args.args[0]
        assert "데이터 기준일 2025-09-15" in sent
        assert "요청일 2025-09-16" in sent
        mock_pub.assert_not_called()  # stale → 잘못된 날짜 발행 차단


def test_latest_mode_no_false_stale(monkeypatch):
    """E1/#3: latest 모드는 yfinance 최신 거래일을 신뢰 — false stale 경고 없이 정상 발행."""
    now = datetime(2025, 9, 16, 16, 30, tzinfo=ET)  # 화요일 장중/지연 실행 가정
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    # 데이터가 직전 거래일(09-15)자여도 target 미지정(latest) → 경고 없음
    data = _fake_data(datetime(2025, 9, 15, 16, 30, tzinfo=ET))
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close", return_value=data),
        patch("market_flow.daily_us.maybe_publish") as mock_pub,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)  # argv 없음 = latest
        sent = mock_send.call_args.args[0]
        assert "데이터 기준일" not in sent  # false stale 경고 없음
        mock_pub.assert_called_once()  # 정상 발행


def test_partial_sections_appends_missing_warning(monkeypatch):
    """I8: 일부 섹션 미수집을 본문에 노출 (조용한 부분실패 차단)."""
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    data = _fake_data(now)
    data["volatility"] = {}  # 변동성·워치ETF 미수집
    data["watch"] = {}
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close", return_value=data),
        patch("market_flow.daily_us.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        sent = mock_send.call_args.args[0]
        assert "일부 섹션 미수집" in sent
        assert "변동성" in sent
        assert "워치ETF" in sent


def test_partial_missing_indices_watch_keeps_title(monkeypatch):
    """#1: indices·watch 미수집이어도 제목이 None이 되지 않고 부분 경고가 붙는다."""
    now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    data = _fake_data(now)
    data["indices"] = {}  # 제목 날짜를 찾던 두 섹션을 비운다
    data["watch"] = {}
    with (
        patch("market_flow.daily_us.send") as mock_send,
        patch("market_flow.daily_us.fetch_us_close", return_value=data),
        patch("market_flow.daily_us.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        sent = mock_send.call_args.args[0]
        # formatter 가 모든 섹션에서 날짜를 찾으므로 'None 미국장 마감'이 되지 않음
        assert "None 미국장" not in sent
        assert "9/15" in sent  # volatility 등에서 추출한 제목 날짜
        assert "일부 섹션 미수집" in sent
        assert "지수" in sent


def test_image_mode_caption_uses_snapshot_date(monkeypatch):
    """#8: 이미지 모드 caption 날짜가 now 가 아니라 snapshot date(데이터 기준일)를 따른다."""
    now = datetime(2025, 9, 16, 16, 30, tzinfo=ET)  # 화요일
    monkeypatch.delenv("MARKET_SCHEDULE", raising=False)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    monkeypatch.setenv("MARKET_FLOW_RENDER", "image")
    # 데이터는 09-15 자 (latest 모드 → 신선도 경고는 없음)
    data = _fake_data(datetime(2025, 9, 15, 16, 30, tzinfo=ET))
    with (
        patch("market_flow.daily_us.send_photo") as mock_photo,
        patch("market_flow.daily_us.fetch_us_close", return_value=data),
        patch("market_flow.daily_us.render_us_daily_html", return_value="<html/>"),
        patch("market_flow.render.renderer.html_to_png", return_value=b"PNG"),
        patch("market_flow.daily_us.maybe_publish"),
    ):
        mock_photo.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_us.main(now=now)
        caption = mock_photo.call_args.kwargs["caption"]
        assert "9/15" in caption  # snapshot date 기준
        assert "9/16" not in caption  # now 기준이 아님
