"""발행 스냅샷 빌더 (web 아카이브용)

텔레그램 발송과 분리된, 웹 표시용 구조화 JSON 스냅샷을 만든다.
fetcher 반환 dict를 거의 그대로 ``payload`` 로 담되, 색·이모지 문자열은
저장하지 않는다 (소비 측이 값/부호로 색 컨벤션을 재현).

스키마 상세는 itda-skills/rs-golden-queens-data/SCHEMA.md (schema_version 1) 참조.

이 모듈은 순수 함수만 둔다 (네트워크/파일 IO 없음). 실제 발행(업로드)은
채널 어댑터(별도 모듈)가 담당한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

SCHEMA_VERSION = 1

_KST = ZoneInfo("Asia/Seoul")
_ET = ZoneInfo("America/New_York")

# KR payload 에 포함할 키 (kospi_intraday 는 장중 분단위라 아카이브 제외)
_KR_PAYLOAD_KEYS = ("bizdate", "kospi", "kosdaq", "kospi_daily")

_KR_SOURCES_TMPL = [
    (
        "네이버 일별",
        "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate}",
    ),
    ("모바일 통합", "https://m.stock.naver.com/domestic/index/KOSPI/total"),
]
_US_SOURCES = [
    {"label": "Yahoo Finance", "url": "https://finance.yahoo.com/markets/"},
    {"label": "S&P 섹터", "url": "https://finance.yahoo.com/sectors/"},
]
_WEEKLY_SOURCES_TMPL = [
    (
        "네이버 일별",
        "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate}",
    ),
    ("Yahoo Finance", "https://finance.yahoo.com/markets/"),
]


def _bizdate_to_iso(bizdate: str) -> str:
    """YYYYMMDD → YYYY-MM-DD. 형식이 다르면 원본 그대로 반환."""
    if isinstance(bizdate, str) and len(bizdate) == 8 and bizdate.isdigit():
        return f"{bizdate[:4]}-{bizdate[4:6]}-{bizdate[6:]}"
    return bizdate


def _iso_week(now: datetime) -> str:
    """ISO 8601 주차 문자열 (예: 2026-W22)."""
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _base(
    market: str, date_iso: str, now: datetime, *, is_holiday: bool
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "market": market,
        "date": date_iso,
        "generated_at": now.isoformat(timespec="seconds"),
        "is_holiday": is_holiday,
    }


def build_holiday_snapshot(market: str, message: str, now: datetime) -> dict[str, Any]:
    """휴장 스냅샷. payload 는 null, message 한 줄만 담는다.

    Args:
        market: "kr" | "us".
        message: ``calendar_utils.format_holiday_message`` 가 만든 한 줄.
        now: 발행 기준 시각 (timezone-aware).
    """
    tz = _KST if market == "kr" else _ET
    date_iso = now.astimezone(tz).date().isoformat()
    snap = _base(market, date_iso, now, is_holiday=True)
    snap["payload"] = None
    snap["message"] = message
    snap["sources"] = []
    return snap


def build_kr_snapshot(data: dict[str, Any], now: datetime) -> dict[str, Any]:
    """한국장 일일 스냅샷.

    Args:
        data: ``naver_kr.fetch_today()`` 반환 dict.
        now: 발행 기준 시각 (KST aware 권장).
    """
    bizdate = str(data.get("bizdate", ""))
    date_iso = _bizdate_to_iso(bizdate)
    snap = _base("kr", date_iso, now, is_holiday=False)
    snap["payload"] = {k: data.get(k) for k in _KR_PAYLOAD_KEYS}
    snap["sources"] = [
        {"label": label, "url": url.format(bizdate=bizdate)}
        for label, url in _KR_SOURCES_TMPL
    ]
    return snap


def build_us_snapshot(data: dict[str, Any], now: datetime) -> dict[str, Any]:
    """미국장 일일 스냅샷.

    Args:
        data: ``us_market.fetch_us_close()`` 반환 dict
            (indices/volatility/risk_onoff/macro/sectors/watch).
        now: 발행 기준 시각.
    """
    # US 거래일은 섹션 항목의 date 필드에서 추출 (모든 항목이 동일 거래일)
    date_iso = _us_trade_date(data)
    snap = _base("us", date_iso, now, is_holiday=False)
    snap["payload"] = {
        k: data.get(k)
        for k in ("indices", "volatility", "risk_onoff", "macro", "sectors", "watch")
    }
    snap["sources"] = [dict(s) for s in _US_SOURCES]
    return snap


def _us_trade_date(data: dict[str, Any]) -> Optional[str]:
    """US payload 의 임의 항목에서 거래일(date)을 뽑는다. 없으면 None."""
    for section in ("indices", "volatility", "macro", "sectors", "watch", "risk_onoff"):
        items = data.get(section) or {}
        for v in items.values():
            if isinstance(v, dict) and v.get("date"):
                return v["date"]
    return None


def build_weekly_snapshot(
    kospi_daily: list[dict[str, Any]],
    watch_5d: dict[str, float],
    now: datetime,
) -> dict[str, Any]:
    """주간 스냅샷.

    Args:
        kospi_daily: ``naver_kr.fetch_kospi_daily()`` 반환 (KR 일일과 동일 행 구조).
        watch_5d: {ticker: pct_5d} (``weekly._watch_5d_pct()`` 반환).
        now: 발행 기준 시각 (KST aware 권장, 주차/날짜 산출에 사용).
    """
    kst_now = now.astimezone(_KST)
    date_iso = kst_now.date().isoformat()
    bizdate = kst_now.strftime("%Y%m%d")
    snap = _base("weekly", date_iso, now, is_holiday=False)
    snap["week"] = _iso_week(kst_now)
    snap["payload"] = {
        "kospi_daily": kospi_daily,
        "watch_5d": [{"ticker": t, "pct_5d": pct} for t, pct in watch_5d.items()],
    }
    snap["sources"] = [
        {"label": label, "url": url.format(bizdate=bizdate)}
        for label, url in _WEEKLY_SOURCES_TMPL
    ]
    return snap


def build_calendar_snapshot(
    now: datetime,
    months_back: int = 6,
    months_fwd: int = 1,
) -> dict[str, Any]:
    """거래일/휴장 캘린더 스냅샷.

    거래일 판정은 calendar_utils(XKRX/NYSE)에 위임한다 — 웹은 이 결과만 표시하고
    휴장 로직을 재구현하지 않는다(불변성).

    범위: now(KST) 기준 [months_back 개월 전 1일, months_fwd 개월 후 말일].
    """
    import calendar as _cal
    import datetime as _dt

    from market_flow import calendar_utils as cu

    kst_now = now.astimezone(_KST)
    y, m = kst_now.year, kst_now.month
    # 시작: months_back 개월 전 1일
    sy, sm = y, m - months_back
    while sm <= 0:
        sm += 12
        sy -= 1
    start = _dt.date(sy, sm, 1)
    # 끝: months_fwd 개월 후 말일
    ey, em = y, m + months_fwd
    while em > 12:
        em -= 12
        ey += 1
    end = _dt.date(ey, em, _cal.monthrange(ey, em)[1])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(timespec="seconds"),
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "kr": cu.kr_trading_days(start, end),
        "us": cu.us_trading_days(start, end),
    }


def snapshot_path(snapshot: dict[str, Any]) -> str:
    """스냅샷이 발행될 저장소 내 상대 경로를 돌려준다.

    kr/us → snapshots/<market>/<date>.json
    weekly → snapshots/weekly/<week>.json
    calendar → snapshots/calendar.json
    """
    market = snapshot.get("market")
    if market is None and "range" in snapshot:
        return "snapshots/calendar.json"
    if market == "weekly":
        return f"snapshots/weekly/{snapshot['week']}.json"
    return f"snapshots/{market}/{snapshot['date']}.json"


def to_json(snapshot: dict[str, Any]) -> str:
    """스냅샷 dict → 안정적인(키 정렬, UTF-8) JSON 문자열."""
    import json

    return json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
