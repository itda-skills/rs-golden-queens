"""거래일 캘린더 스냅샷 빌더 + calendar_utils 기간 조회 테스트."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from market_flow import calendar_utils as cu
from market_flow import publish_channel as C
from market_flow import publisher as P

_KST = ZoneInfo("Asia/Seoul")
_NOW = dt.datetime(2026, 5, 30, 18, 0, tzinfo=_KST)


class TestTradingDays:
    def test_kr_excludes_holiday(self):
        days = cu.kr_trading_days(dt.date(2026, 5, 1), dt.date(2026, 5, 31))
        assert "2026-05-05" not in days  # 어린이날
        assert "2026-05-29" in days
        assert "2026-05-02" not in days  # 토요일

    def test_us_returns_iso_strings(self):
        days = cu.us_trading_days(dt.date(2026, 5, 1), dt.date(2026, 5, 31))
        assert all(len(d) == 10 and d[4] == "-" for d in days)
        assert "2026-05-28" in days


class TestCalendarSnapshot:
    def test_shape(self):
        snap = P.build_calendar_snapshot(_NOW, months_back=2, months_fwd=1)
        assert snap["schema_version"] == P.SCHEMA_VERSION
        assert "market" not in snap
        assert set(snap.keys()) >= {"generated_at", "range", "kr", "us"}
        assert snap["range"]["start"] == "2026-03-01"
        assert snap["range"]["end"] == "2026-06-30"

    def test_path(self):
        snap = P.build_calendar_snapshot(_NOW)
        assert P.snapshot_path(snap) == "snapshots/calendar.json"


class TestCalendarPublishHelpers:
    def test_index_preserves_markets(self):
        snap = P.build_calendar_snapshot(_NOW)
        out = C.update_index({"kr": ["2026-05-29"]}, snap, _NOW)
        assert out["kr"] == ["2026-05-29"]  # 시장 목록 보존
        assert "calendar" not in out  # index엔 캘린더 목록 없음
        assert out["updated_at"]

    def test_latest_sets_calendar_entry(self):
        snap = P.build_calendar_snapshot(_NOW)
        out = C.update_latest({}, snap, _NOW)
        assert out["calendar"] == {"path": "snapshots/calendar.json"}

    def test_entry_id_is_calendar(self):
        snap = P.build_calendar_snapshot(_NOW)
        assert C._entry_id(snap) == "calendar"
