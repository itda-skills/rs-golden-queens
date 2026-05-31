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
            "sectors",
            "money_flow",
            "foreign_inst",
        }
        # KIS 데이터(섹터·수급·가집계)가 없으면 None 으로 발행된다 (P0-c/I4)
        assert snap["payload"]["sectors"] is None
        assert snap["payload"]["money_flow"] is None
        assert snap["payload"]["foreign_inst"] is None

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

    def test_sectors_and_money_flow_published(self, kr_data):
        """P0-c SoT: 텔레그램이 보내는 섹터 ETF·동적 수급을 발행 payload 에도 담는다."""
        data = dict(kr_data)
        data["sectors"] = [
            {
                "code": "091160",
                "label": "반도체",
                "close": 12345.0,
                "pct": 1.2,
                "vol_ratio": 1.6,
                "trade_value_eok": 500.0,
                "date": "20260529",
            }
        ]
        data["money_flow"] = {
            "etfs": [
                {
                    # 표시 필드
                    "code": "069500",
                    "name": "KODEX200",
                    "grade": "A",
                    "price": 30000,
                    "ret_5": 1.5,
                    "trade_value_eok": 1000,
                    "foreign_eok": 100.0,
                    "orgn_eok": 50.0,
                    "combined_eok": 150.0,
                    "both_buy": True,
                    # 발행에서 제외되어야 할 내부 필드 (screen() 실제 컬럼 전체)
                    "is_etf": True,
                    "ret_20": 2.0,
                    "ma5_eok": 900.0,
                    "r_5_20": 1.1,
                    "r_5_60": 1.2,
                    "score_grade": 22.0,
                    "score_foreign": 25.0,
                    "score_orgn": 20.0,
                    "score_both": 10.0,
                    "score_mom": 10.0,
                    "mf_score": 80.0,
                }
            ],
            "stocks": [],
        }
        snap = P.build_kr_snapshot(data, _NOW_KST)
        p = snap["payload"]

        # 섹터는 값 그대로 (색/이모지 없음)
        assert p["sectors"][0]["label"] == "반도체"
        assert p["sectors"][0]["pct"] == 1.2
        assert p["sectors"][0]["vol_ratio"] == 1.6

        # 수급은 표시 필드만 — 화이트리스트 정합(내부 점수/플래그 한 개도 새지 않음)
        etf = p["money_flow"]["etfs"][0]
        assert etf["code"] == "069500"
        assert etf["grade"] == "A"
        assert etf["combined_eok"] == 150.0
        assert etf["both_buy"] is True
        assert set(etf.keys()) == set(P._KR_MF_FIELDS)
        assert p["money_flow"]["stocks"] == []

        # 색/이모지 문자열은 발행하지 않는다 (값에서 재현)
        blob = P.to_json(snap)
        for ch in ("🔴", "🔵", "🔥", "▲", "▼"):
            assert ch not in blob

    def test_money_flow_none_when_absent(self, kr_data):
        """수급 데이터가 None(과거일 재발송·KIS 스킵)이면 money_flow=None."""
        data = dict(kr_data)
        data["money_flow"] = None
        data["sectors"] = None
        snap = P.build_kr_snapshot(data, _NOW_KST)
        assert snap["payload"]["money_flow"] is None
        assert snap["payload"]["sectors"] is None

    def test_foreign_inst_published_facts_only(self, kr_data):
        """I4: 가집계를 발행하되 사실 금액 필드만(라벨·시그널 문자열 미저장)."""
        data = dict(kr_data)
        data["foreign_inst"] = {
            "buy": [
                {
                    "code": "005930",
                    "name": "삼성전자",
                    "foreign_eok": 700.0,
                    "orgn_eok": 300.0,
                    "combined_eok": 1000.0,
                }
            ],
            "sell": [],
        }
        snap = P.build_kr_snapshot(data, _NOW_KST)
        fi = snap["payload"]["foreign_inst"]
        item = fi["buy"][0]
        assert item["code"] == "005930"
        assert item["combined_eok"] == 1000.0
        assert set(item.keys()) == set(P._KR_FI_FIELDS)
        assert fi["sell"] == []
        # '장중 추정'·'가집계' 라벨 문자열은 발행 데이터에 없다(웹이 맥락을 자체 렌더)
        blob = P.to_json(snap)
        assert "장중 추정" not in blob and "가집계" not in blob

    def test_foreign_inst_none_when_absent(self, kr_data):
        data = dict(kr_data)
        data["foreign_inst"] = None
        snap = P.build_kr_snapshot(data, _NOW_KST)
        assert snap["payload"]["foreign_inst"] is None

    def test_money_flow_sell_published_without_buy_fields(self, kr_data):
        """I1: 순매도 블록을 발행하되 매수 개념(grade·both_buy)은 담지 않는다."""
        data = dict(kr_data)
        data["money_flow"] = {
            "etfs": [],
            "stocks": [],
            "etfs_sell": [
                {
                    "code": "069500",
                    "name": "KODEX 200",
                    "price": 30000,
                    "ret_5": -1.5,
                    "trade_value_eok": 1000,
                    "foreign_eok": -700.0,
                    "orgn_eok": -200.0,
                    "combined_eok": -900.0,
                    # 발행에서 제외되어야 할 매수 개념·내부 필드
                    "grade": "D",
                    "both_buy": False,
                    "is_etf": True,
                    "mf_score": 10.0,
                },
            ],
            "stocks_sell": [],
        }
        snap = P.build_kr_snapshot(data, _NOW_KST)
        mf = snap["payload"]["money_flow"]
        sell = mf["etfs_sell"][0]
        assert sell["code"] == "069500"
        assert sell["combined_eok"] == -900.0
        # 순매도 화이트리스트 정합 — 매수 개념(grade·both_buy)·내부 필드는 한 개도 없음
        assert set(sell.keys()) == set(P._KR_MF_SELL_FIELDS)
        assert "grade" not in sell and "both_buy" not in sell
        assert mf["stocks_sell"] == []

    def test_nan_serialized_as_null_not_nan_token(self, kr_data):
        """NaN/Inf 는 유효 JSON(null)으로 — 'NaN' 토큰은 웹 res.json()이 거부한다.

        pandas 유래 값에 NaN 이 섞여도 발행 스냅샷은 표준 JSON 이어야 한다.
        """
        data = dict(kr_data)
        data["sectors"] = [
            {
                "code": "091160",
                "label": "반도체",
                "close": 12345.0,
                "pct": float("nan"),  # 결측 등락
                "vol_ratio": float("inf"),
                "trade_value_eok": 500.0,
                "date": "20260529",
            }
        ]
        data["money_flow"] = {
            "etfs": [
                {
                    "code": "069500",
                    "name": "KODEX200",
                    "grade": "A",
                    "price": 30000,
                    "ret_5": 1.5,
                    "trade_value_eok": 1000,
                    "foreign_eok": float("nan"),
                    "orgn_eok": 50.0,
                    "combined_eok": 150.0,
                    "both_buy": True,
                }
            ],
            "stocks": [],
        }
        snap = P.build_kr_snapshot(data, _NOW_KST)
        blob = P.to_json(snap)
        # 표준이 아닌 토큰이 새어나가지 않는다
        assert "NaN" not in blob
        assert "Infinity" not in blob
        # 표준 파서로 왕복 가능 + NaN→null
        reparsed = json.loads(blob)
        assert reparsed["payload"]["sectors"][0]["pct"] is None
        assert reparsed["payload"]["sectors"][0]["vol_ratio"] is None
        assert reparsed["payload"]["money_flow"]["etfs"][0]["foreign_eok"] is None


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

    def test_json_safe_coerces_datetime_and_nan(self):
        """제네릭 안전망: datetime/date → ISO, NaN/Inf → null (표준 JSON 보장)."""
        import datetime as _dt

        out = P.to_json(
            {"d": _dt.date(2026, 5, 29), "nan": float("nan"), "inf": float("inf")}
        )
        assert "NaN" not in out and "Infinity" not in out
        reparsed = json.loads(out)
        assert reparsed["d"] == "2026-05-29"
        assert reparsed["nan"] is None
        assert reparsed["inf"] is None

    def test_sorted_keys_deterministic(self, kr_data):
        snap = P.build_kr_snapshot(kr_data, _NOW_KST)
        assert P.to_json(snap) == P.to_json(snap)
        # 키 정렬 확인
        assert P.to_json(snap).index('"date"') < P.to_json(snap).index('"market"')
