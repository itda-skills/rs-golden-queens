"""발행 스냅샷 빌더 (web 아카이브용)

텔레그램 발송과 분리된, 웹 표시용 구조화 JSON 스냅샷을 만든다.
fetcher 반환 dict를 거의 그대로 ``payload`` 로 담되, 색·이모지 문자열은
저장하지 않는다 (소비 측이 값/부호로 색 컨벤션을 재현).

스키마 상세는 itda-skills/rs-golden-queens-data/SCHEMA.md (schema_version 1) 참조.

이 모듈은 순수 함수만 둔다 (네트워크/파일 IO 없음). 실제 발행(업로드)은
채널 어댑터(별도 모듈)가 담당한다.
"""

from __future__ import annotations

import math
import re
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


# money_flow 발행 시 웹 표시에 쓰는 필드만 추린다 (내부 점수 score_*·is_etf 등 제외).
_KR_MF_FIELDS = (
    "code",
    "name",
    "grade",
    "price",
    "ret_5",
    "trade_value_eok",
    "foreign_eok",
    "orgn_eok",
    "combined_eok",
    "both_buy",
)
# 순매도 블록(I1)은 매수 개념 필드(grade·both_buy)를 담지 않는다 — 매수 라벨 재사용 금지.
_KR_MF_SELL_FIELDS = (
    "code",
    "name",
    "price",
    "ret_5",
    "trade_value_eok",
    "foreign_eok",
    "orgn_eok",
    "combined_eok",
)


def _kr_money_flow_payload(mf: Any) -> Optional[dict[str, Any]]:
    """동적 수급 워치(fetch_money_flow_watch 반환)를 발행용으로 정제. None 이면 None.

    텔레그램에 보내는 섹션을 웹도 동일하게 보여주기 위한 SoT 정합 — 색/이모지·
    내부 점수는 담지 않고 값만 담는다(웹이 값에서 색을 재현). 순매도 블록(I1)은
    매수 개념(grade·both_buy)을 제외한 사실 금액만 담는다.
    """
    if not mf:
        return None

    def pick(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        return {k: item.get(k) for k in fields}

    return {
        "etfs": [pick(x, _KR_MF_FIELDS) for x in (mf.get("etfs") or [])],
        "stocks": [pick(x, _KR_MF_FIELDS) for x in (mf.get("stocks") or [])],
        "etfs_sell": [pick(x, _KR_MF_SELL_FIELDS) for x in (mf.get("etfs_sell") or [])],
        "stocks_sell": [
            pick(x, _KR_MF_SELL_FIELDS) for x in (mf.get("stocks_sell") or [])
        ],
    }


# 외국인·기관 가집계(I4) 발행 필드 — 사실 금액만(가집계 = 장중 추정치).
_KR_FI_FIELDS = ("code", "name", "foreign_eok", "orgn_eok", "combined_eok")


def _kr_foreign_inst_payload(fi: Any) -> Optional[dict[str, Any]]:
    """외국인·기관 가집계(fetch_foreign_inst_tally 반환)를 발행용으로 정제. None 이면 None.

    가집계는 증권사 장중 입력 누계(추정)다 — 웹도 '장중 추정' 맥락에서 동일하게
    보여주기 위해 사실 금액만 담는다(시그널·라벨 문자열 미저장).
    """
    if not fi:
        return None

    def pick(item: dict[str, Any]) -> dict[str, Any]:
        return {k: item.get(k) for k in _KR_FI_FIELDS}

    return {
        "buy": [pick(x) for x in (fi.get("buy") or [])],
        "sell": [pick(x) for x in (fi.get("sell") or [])],
    }


def build_kr_snapshot(data: dict[str, Any], now: datetime) -> dict[str, Any]:
    """한국장 일일 스냅샷.

    Args:
        data: ``naver_kr.fetch_today()`` + KIS 섹터/수급(daily_kr 가 채움) dict.
        now: 발행 기준 시각 (KST aware 권장).
    """
    bizdate = str(data.get("bizdate", ""))
    date_iso = _bizdate_to_iso(bizdate)
    snap = _base("kr", date_iso, now, is_holiday=False)
    payload = {k: data.get(k) for k in _KR_PAYLOAD_KEYS}
    # SoT(#10 P0-c): 텔레그램이 보내는 섹터 ETF·동적 수급을 웹도 동일하게 보이도록 발행한다.
    # 추가 키이므로 schema_version 은 유지 — 구버전 웹 reader 는 누락 시 무시/폴백한다.
    # 섹터는 색/이모지 없는 값만(kr_etfs 반환 그대로), 수급은 표시 필드만 정제해 담는다.
    payload["sectors"] = data.get("sectors")
    payload["money_flow"] = _kr_money_flow_payload(data.get("money_flow"))
    payload["foreign_inst"] = _kr_foreign_inst_payload(data.get("foreign_inst"))
    snap["payload"] = payload
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
    # 결측 티커(_fetch_yf → None)는 발행 전 제거 — 웹(UsSectionTable)이 q.label 을
    # 바로 역참조하므로 null 티커가 스냅샷에 들어가면 카드가 런타임 에러난다.
    # 텔레그램(`if not d: continue`)과 동일하게 None 을 거른다(값 정합).
    snap["payload"] = {
        k: {t: v for t, v in (data.get(k) or {}).items() if v is not None}
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


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_iso_date(s: Any) -> bool:
    """엄격한 YYYY-MM-DD 날짜인지. strptime 은 '2026-5-9' 도 허용하므로 자릿수를 고정한다."""
    if not isinstance(s, str) or not _ISO_DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _payload_all_empty(snapshot: dict[str, Any]) -> bool:
    """핵심 payload 가 전부 결측인지(빈 페이지 판정).

    정상 데이터를 발행 보류로 막지 않도록 보수적으로 — '확실히 빈' 경우만 True.
    """
    payload = snapshot.get("payload")
    if not payload:
        return True
    market = snapshot.get("market")
    if market == "us":
        # {section: {ticker: {...}}} — 모든 섹션이 빈 dict 면 결측
        return all(not v for v in payload.values())
    if market == "weekly":
        return not (payload.get("kospi_daily") or payload.get("watch_5d"))
    if market == "kr":
        # bizdate 만으로는 유효가 아니다 — 빈 네이버 응답도 field=None dict 를 만든다.
        # 당일 합산(kospi/kosdaq)에 실제 수치가 하나라도 있거나 일별 추이가 있어야
        # 유효로 본다(KIS 섹터/수급은 부가라 그것만으론 KR 페이지를 만들지 않는다).
        def _has_vals(d: Any) -> bool:
            return isinstance(d, dict) and any(
                v is not None for k, v in d.items() if k != "bizdate"
            )

        return not (
            _has_vals(payload.get("kospi"))
            or _has_vals(payload.get("kosdaq"))
            or payload.get("kospi_daily")
        )
    return False


def validate_snapshot(snapshot: dict[str, Any]) -> Optional[str]:
    """발행을 보류해야 하는 이유(str) 또는 None(정상). publisher 레벨 최후 방어선(#10 I9).

    경로/인덱스 오염(``snapshots/<market>/None.json``)과 빈 페이지 발행을 막는다.
    호출부(daily_*)의 신선도 가드와 독립적으로 동작하는 이중 방어이며, 텔레그램
    발송과 무관하다(발송이 끝난 뒤 발행 단계에서만 본다).
    """
    market = snapshot.get("market")
    # 캘린더는 date 없이 range 로 식별 — 별도 경로
    if market is None and "range" in snapshot:
        return None
    if market not in ("kr", "us", "weekly"):
        return f"알 수 없는 market: {market!r}"
    # date 무결성 — snapshot_path/_entry_id 가 date 로 경로·식별자를 만든다
    if not _is_iso_date(snapshot.get("date")):
        return f"date 형식 오류: {snapshot.get('date')!r}"
    if market == "weekly" and not snapshot.get("week"):
        return f"weekly week 누락: {snapshot.get('week')!r}"
    # 휴장은 payload=None 이 정상(메시지만 발행)
    if snapshot.get("is_holiday"):
        return None
    # is_holiday=False 인데 핵심 payload 가 전부 결측이면 빈 페이지 — 발행 보류(degraded)
    if _payload_all_empty(snapshot):
        return "payload 전부 결측"
    return None


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


def _json_safe(obj: Any) -> Any:
    """발행 직전 JSON 안전 정규화.

    payload 에는 pandas ``to_dict(records)`` 유래 값이 섞일 수 있다. ``json.dumps``
    의 기본 ``allow_nan=True`` 는 NaN/Inf 를 ``NaN``/``Infinity`` 로 내보내는데 이는
    표준 JSON 이 아니어서 웹의 ``res.json()`` 이 거부한다. NaN/Inf 는 None 으로,
    numpy 스칼라는 파이썬 native 로 바꿔 '유효하지 않은 스냅샷'이 나가지 않게 한다.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if not isinstance(obj, (str, bytes, int)):
        # datetime/date/pandas.Timestamp → ISO 문자열 (json 비직렬 타입 방어)
        iso = getattr(obj, "isoformat", None)
        if callable(iso):
            try:
                return obj.isoformat()
            except Exception:  # noqa: BLE001 — 알 수 없는 타입은 원본 유지
                pass
        # numpy 스칼라 등 .item() 보유 객체 → native 로 (그 뒤 재귀로 NaN 처리)
        item = getattr(obj, "item", None)
        if callable(item):
            try:
                return _json_safe(obj.item())
            except Exception:  # noqa: BLE001 — 알 수 없는 타입은 원본 유지
                return obj
    return obj


def to_json(snapshot: dict[str, Any]) -> str:
    """스냅샷 dict → 안정적인(키 정렬, UTF-8) JSON 문자열.

    ``allow_nan=False`` 로 둬, NaN/Inf 가 남으면 조용히 유효하지 않은 JSON 을 웹으로
    내보내는 대신 발행 단계에서 ValueError 로 드러나게 한다. ``_json_safe`` 가 사전에
    None 으로 치환하므로 정상 경로에선 발생하지 않는다.
    """
    import json

    return json.dumps(
        _json_safe(snapshot),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
