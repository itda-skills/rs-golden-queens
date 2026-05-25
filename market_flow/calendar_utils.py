"""SPEC-MF-SCHED-001: 거래일·DST 판정 유틸리티.

세 텔레그램 봇(`daily_kr.py`, `daily_us.py`, `weekly.py`)이 공통으로
사용하는 거래소 캘린더 판정 함수 모음. 모든 공개 함수는 시각 주입
파라미터(`now: datetime | None = None`)를 받아 결정론적 테스트가
가능하도록 설계되었다.

- NYSE 휴장 판정: `pandas_market_calendars` (NYSE 캘린더)
- XKRX 휴장 판정: `exchange_calendars` (XKRX 캘린더)
- DST 판정: 표준 `zoneinfo`의 `dst()` 반환값으로 판단
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import exchange_calendars as _ec
import pandas_market_calendars as _mcal

_KST = ZoneInfo("Asia/Seoul")
_ET = ZoneInfo("America/New_York")

# 캘린더 객체는 모듈 로드 시 1회 초기화 (오프라인 동작)
_NYSE = _mcal.get_calendar("NYSE")
_XKRX = _ec.get_calendar("XKRX")


def _now_in(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


# @MX:NOTE: [AUTO] DST 시즌 판정 (America/New_York 기준)
def is_us_in_dst(now: Optional[datetime] = None) -> bool:
    """현재 미국 동부 시각이 DST(EDT) 시즌인지 판정.

    Args:
        now: 판정 기준 시각. None이면 `datetime.now(America/New_York)`.
             tzinfo가 없으면 ET로 가정. UTC 등 다른 tz는 ET로 변환 후 판정.

    Returns:
        EDT 시즌이면 True, EST 시즌이면 False.
    """
    if now is None:
        now = _now_in(_ET)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    else:
        now = now.astimezone(_ET)
    return now.dst() != timedelta(0)


# @MX:ANCHOR: [AUTO] 미국 거래일 판정 진입점
# @MX:REASON: fan_in >= 3 (daily_us, calendar_utils 내부 다른 함수에서 호출 가능)
def is_us_trading_day(now: Optional[datetime] = None) -> bool:
    """NYSE 거래일 여부 판정 (반장일도 거래일로 간주).

    Args:
        now: 판정 기준 시각. None이면 `datetime.now(America/New_York)`.

    Returns:
        해당 일자가 NYSE 거래일이면 True, 아니면 False.
    """
    if now is None:
        now = _now_in(_ET)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    target = now.astimezone(_ET).date()
    return _is_nyse_session(target)


def _is_nyse_session(d: date) -> bool:
    iso = d.isoformat()
    schedule = _NYSE.schedule(start_date=iso, end_date=iso)
    return not schedule.empty


# @MX:ANCHOR: [AUTO] 한국 거래일 판정 진입점
# @MX:REASON: fan_in >= 3 (daily_kr, weekly, calendar_utils 내부 호출)
def is_kr_trading_day(now: Optional[datetime] = None) -> bool:
    """XKRX 거래일 여부 판정.

    Args:
        now: 판정 기준 시각. None이면 `datetime.now(Asia/Seoul)`.

    Returns:
        해당 일자가 한국 거래소 거래일이면 True, 아니면 False.
    """
    if now is None:
        now = _now_in(_KST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_KST)
    target = now.astimezone(_KST).date()
    return _is_xkrx_session(target)


def _is_xkrx_session(d: date) -> bool:
    return bool(_XKRX.is_session(d.isoformat()))


# @MX:ANCHOR: [AUTO] 주간 리포트 발송 게이트
# @MX:REASON: fan_in >= 1 (weekly), 마지막 거래일 이월 발송 핵심 분기
def is_last_kr_trading_day_of_week(now: Optional[datetime] = None) -> bool:
    """오늘이 이번 주 (월~금)의 마지막 한국 거래일인지 판정.

    "마지막 거래일"의 정의: 오늘이 KR 거래일이면서, 오늘+1 ~ 같은 주
    금요일까지 모두 비거래일.

    Args:
        now: 판정 기준 시각. None이면 `datetime.now(Asia/Seoul)`.

    Returns:
        오늘이 그 주의 마지막 거래일이면 True.
    """
    if now is None:
        now = _now_in(_KST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_KST)
    today = now.astimezone(_KST).date()

    # 오늘 자체가 비거래일이면 False
    if not _is_xkrx_session(today):
        return False

    # 오늘+1 ~ 이번 주 금요일까지 모두 비거래일이어야 True
    # weekday(): 월=0, 금=4
    weekday = today.weekday()
    if weekday >= 4:  # 금/토/일 — 오늘이 금요일이면 그 주 마지막 평일
        return True

    for offset in range(1, 5 - weekday):  # 다음날 ~ 금요일
        candidate = today + timedelta(days=offset)
        if _is_xkrx_session(candidate):
            return False
    return True
