"""market_flow/publisher.py 단위 테스트.

발행 스냅샷 빌더의 결정론적 출력을 검증한다. 외부 의존성 없음 — 순수 함수.
스키마는 schema_version 1 (rs-golden-queens-data/SCHEMA.md).
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from market_flow import publisher as P

_KST = ZoneInfo("Asia/Seoul")
_ET = ZoneInfo("America/New_York")

_NOW_KST = datetime(2026, 5, 29, 18, 10, 0, tzinfo=_KST)  # 금요일
_NOW_ET = datetime(2026, 5, 28, 7, 0, 0, tzinfo=_ET)


# ──────────────────────────────────────────────
#  fixtures (fetcher 반환 구조 축약)
# ──────────────────────────────────────────────


@pytest.fixture
def kr_data():
    return {
        "bizdate": "20260529",
        "kospi": {
            "personal": -10975,
            "foreign": -17314,
            "institutional": 27697,
            "program_arb": 4114,
            "program_nonarb": -8157,
            "program_total": -4042,
        },
        "kosdaq": {
            "personal": 3417,
            "foreign": -505,
            "institutional": -2956,
            "program_arb": 2,
            "program_nonarb": -1168,
            "program_total": -1166,
        },
        "kospi_intraday": [
            {"time": "15:04", "foreign": -17314}
        ],  # 발행에서 제외되어야 함
        "kospi_daily": [
            {
                "date": "26.05.29",
                "personal": -10975,
                "foreign": -17314,
                "institutional": 27697,
                "finance": 26365,
                "insurance": -426,
                "trust": 513,
                "bank": 57,
                "other_fin": -38,
                "pension": 1226,
                "other_corp": 592,
            },
        ],
    }


@pytest.fixture
def us_data():
    return {
        "indices": {
            "^GSPC": {
                "label": "S&P500",
                "close": 7563.63,
                "pct": 0.575,
                "vol_ratio": 1.03,
                "date": "2026-05-28",
            }
        },
        "volatility": {
            "^VIX": {
                "label": "VIX",
                "close": 15.74,
                "pct": -3.38,
                "vol_ratio": None,
                "date": "2026-05-28",
            }
        },
        "risk_onoff": {
            "HYG": {
                "label": "고수익채권",
                "close": 80.23,
                "pct": 0.12,
                "vol_ratio": 0.93,
                "date": "2026-05-28",
            }
        },
        "macro": {
            "^TNX": {
                "label": "10Y금리",
                "close": 4.45,
                "pct": -0.58,
                "vol_ratio": None,
                "date": "2026-05-28",
            }
        },
        "sectors": {
            "XLK": {
                "label": "기술",
                "close": 186.85,
                "pct": 1.31,
                "vol_ratio": 0.94,
                "date": "2026-05-28",
            }
        },
        "watch": {
            "QQQ": {
                "label": "나스닥100",
                "close": 735.60,
                "pct": 0.84,
                "vol_ratio": 0.93,
                "date": "2026-05-28",
            }
        },
    }


# ──────────────────────────────────────────────
#  공통 필드
# ──────────────────────────────────────────────


class TestCommonFields:
    def test_kr_has_required_fields(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        for k in (
            "schema_version",
            "market",
            "date",
            "generated_at",
            "is_holiday",
            "payload",
            "sources",
        ):
            assert k in snap
        assert snap["schema_version"] == P.SCHEMA_VERSION
        assert snap["market"] == "kr"
        assert snap["is_holiday"] is False

    def test_generated_at_is_isoformat(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        assert snap["generated_at"] == "2026-05-29T18:10:00+09:00"


# ──────────────────────────────────────────────
#  KR
# ──────────────────────────────────────────────


class TestKr:
    def test_bizdate_to_iso_date(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        assert snap["date"] == "2026-05-29"

    def test_payload_keeps_kospi_kosdaq_daily(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        assert set(snap["payload"].keys()) == {
            "bizdate",
            "kospi",
            "kosdaq",
            "kospi_daily",
        }

    def test_intraday_excluded(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        assert "kospi_intraday" not in snap["payload"]

    def test_no_emoji_or_color_strings(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        blob = P.to_json(snap)
        for ch in ("🔴", "🔵", "⚪", "▲", "▼"):
            assert ch not in blob

    def test_sources_have_bizdate_url(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        urls = [s["url"] for s in snap["sources"]]
        assert any("bizdate=20260529" in u for u in urls)

    def test_path(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        assert P.snapshot_path(snap) == "snapshots/kr/2026-05-29.json"


# ──────────────────────────────────────────────
#  US (결측 vol_ratio=None 포함)
# ──────────────────────────────────────────────


class TestUs:
    def test_date_from_payload(self, us_data):
        snap = P.build_us_snapshot(us_data, _NOW_ET)
        assert snap["date"] == "2026-05-28"

    def test_payload_sections(self, us_data):
        snap = P.build_us_snapshot(us_data, _NOW_ET)
        assert set(snap["payload"].keys()) == {
            "indices",
            "volatility",
            "risk_onoff",
            "macro",
            "sectors",
            "watch",
        }

    def test_null_vol_ratio_preserved(self, us_data):
        snap = P.build_us_snapshot(us_data, _NOW_ET)
        assert snap["payload"]["volatility"]["^VIX"]["vol_ratio"] is None

    def test_path(self, us_data):
        snap = P.build_us_snapshot(us_data, _NOW_ET)
        assert P.snapshot_path(snap) == "snapshots/us/2026-05-28.json"

    def test_missing_date_returns_none(self):
        snap = P.build_us_snapshot({"indices": {}}, _NOW_ET)
        assert snap["date"] is None


# ──────────────────────────────────────────────
#  Weekly
# ──────────────────────────────────────────────


class TestWeekly:
    def test_iso_week(self, kr_data):
        snap = P.build_weekly_snapshot(kr_data["kospi_daily"], {"SMH": 6.23}, _NOW_KST)
        assert snap["week"] == "2026-W22"
        assert snap["market"] == "weekly"

    def test_watch_5d_list_shape(self, kr_data):
        snap = P.build_weekly_snapshot(
            kr_data["kospi_daily"], {"SMH": 6.23, "ITA": 5.50}, _NOW_KST
        )
        w = snap["payload"]["watch_5d"]
        assert {"ticker": "SMH", "pct_5d": 6.23} in w
        assert len(w) == 2

    def test_path_uses_week(self, kr_data):
        snap = P.build_weekly_snapshot(kr_data["kospi_daily"], {}, _NOW_KST)
        assert P.snapshot_path(snap) == "snapshots/weekly/2026-W22.json"


# ──────────────────────────────────────────────
#  휴장
# ──────────────────────────────────────────────


class TestHoliday:
    def test_kr_holiday(self):
        snap = P.build_holiday_snapshot(
            "kr", "[KR] 2026-05-25 (월) 오늘은 휴장입니다", _NOW_KST
        )
        assert snap["is_holiday"] is True
        assert snap["payload"] is None
        assert snap["message"].startswith("[KR]")
        assert snap["date"] == "2026-05-29"

    def test_us_holiday_uses_et_date(self):
        snap = P.build_holiday_snapshot("us", "[US] ...", _NOW_ET)
        assert snap["date"] == "2026-05-28"
        assert snap["market"] == "us"


# ──────────────────────────────────────────────
#  직렬화
# ──────────────────────────────────────────────


class TestToJson:
    def test_roundtrip(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        assert json.loads(P.to_json(snap)) == snap

    def test_sorted_keys_deterministic(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        assert P.to_json(snap) == P.to_json(snap)
        # 키 정렬 확인
        assert P.to_json(snap).index('"date"') < P.to_json(snap).index('"market"')
