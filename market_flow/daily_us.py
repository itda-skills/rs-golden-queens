"""미국장 마감 요약 → 텔레그램 발송

Usage:
  python daily_us.py             # 최신 거래일
  python daily_us.py 2026-05-22  # 특정일

SPEC-MF-SCHED-001:
  - DST 게이트: 환경변수 MARKET_SCHEDULE(edt|est)와 실제 시즌이 불일치하면 즉시 종료
  - 미국 휴장일: `[US] YYYY-MM-DD (요일) 오늘은 휴장입니다` 한 줄 발송
    (날짜는 ET 로컬 기준, REQ-MF-HOL-004)

데이터 정합 (#10 P0-a):
  - E5: 전체 미수집이면 `None 미국장 마감` 빈 표 대신 명시적 실패 안내 + 발행 스킵
  - E1: target 모드(과거일 재발행)에서 데이터 거래일이 요청일과 다르면 경고 + 발행 스킵
        (latest 모드는 yfinance 최신 거래일을 신뢰 — 장중/지연 실행 false stale 방지)
  - I8: 일부 섹션 미수집을 본문에 노출 (조용한 부분실패 차단)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from market_flow.calendar_utils import (
    format_holiday_message,
    is_us_in_dst,
    is_us_trading_day,
    last_us_trading_day,
)
from market_flow.fetchers.us_market import fetch_us_close
from market_flow.formatter import format_us_daily
from market_flow.publish_channel import maybe_publish, web_link_suffix_for_snapshot
from market_flow.publisher import build_holiday_snapshot, build_us_snapshot
from market_flow.telegram_push import send

_ET = ZoneInfo("America/New_York")

_US_SECTION_KR = {
    "indices": "지수",
    "volatility": "변동성",
    "risk_onoff": "위험선호",
    "macro": "매크로",
    "sectors": "섹터",
    "watch": "워치ETF",
}


def _parse_target_date(raw: str) -> Optional[datetime]:
    """YYYY-MM-DD 또는 YYYYMMDD 문자열을 ET aware datetime 으로 파싱."""
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=_ET)
        except ValueError:
            continue
    return None


def _md_label(iso: Optional[str]) -> Optional[str]:
    """'2026-05-22' → '5/22(목)'. None/형식오류면 None."""
    if not iso:
        return None
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
    except ValueError:
        return None
    return f"{dt.month}/{dt.day}({'월화수목금토일'[dt.weekday()]})"


def _warn_block(warnings: list[str]) -> str:
    """경고 목록을 본문 말미에 덧붙일 블록. 비면 빈 문자열."""
    return ("\n\n" + "\n".join(warnings)) if warnings else ""


def _build_us_warnings(
    snapshot: dict,
    section_counts: dict,
    target: Optional[str],
) -> tuple[list[str], bool]:
    """E1 신선도(target 모드 한정) + I8 부분실패 경고를 만든다 (사실 안내만).

    Returns:
        (warnings, stale). stale=True 면 target 불일치 — 잘못된 날짜로 발행하지
        않도록 호출 측이 발행을 건너뛴다. latest 모드는 yfinance 최신 거래일을
        신뢰해 신선도 경고를 내지 않는다(장중/지연 실행 false stale 방지).
    """
    w: list[str] = []
    data_date = snapshot.get("date")
    stale = bool(target and data_date and data_date != target)
    if stale:
        w.append(
            f"⚠️ 데이터 기준일 {data_date} ≠ 요청일 {target} — yfinance에 해당일 데이터가 없습니다"
        )
    missing = [k for k, v in section_counts.items() if not v]
    if missing:
        names = ", ".join(_US_SECTION_KR.get(m, m) for m in missing)
        w.append(f"⚠️ 일부 섹션 미수집: {names}")
    return w, stale


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> None:
    if argv is None:
        argv = []
    if now is None:
        now = datetime.now(_ET)

    # argv 로 날짜가 지정되면 휴장 게이트도 그 날짜 기준으로 판정
    target: Optional[str] = None
    if argv:
        parsed = _parse_target_date(argv[0])
        if parsed is None:
            sys.exit(f"DATE 형식 오류: '{argv[0]}' (YYYY-MM-DD 또는 YYYYMMDD)")
        now = parsed
        target = parsed.strftime("%Y-%m-%d")

    schedule = os.environ.get("MARKET_SCHEDULE", "").strip().lower()
    if schedule in {"edt", "est"}:
        in_dst = is_us_in_dst(now)
        if (schedule == "edt" and not in_dst) or (schedule == "est" and in_dst):
            actual_season = "EDT" if in_dst else "EST"
            print(
                f"⏭️  스킵: MARKET_SCHEDULE={schedule} 인데 실제 시즌은 {actual_season} — 발송 안 함"
            )
            sys.exit(0)

    # 휴장 게이트
    if not is_us_trading_day(now):
        date_str = now.strftime("%Y-%m-%d %A")
        print(f"🏖️  미국 휴장일 — {date_str}: 휴장 안내 메시지만 발송")
        msg = format_holiday_message("US", now)
        send(msg)
        maybe_publish(build_holiday_snapshot("us", msg, now), now)
        return

    print(f"📥 yfinance 미국장 데이터 수집 시작 — target={target or 'latest'}")
    data = fetch_us_close(target)
    section_counts = (
        {k: sum(1 for v in (data.get(k) or {}).values() if v) for k in data}
        if isinstance(data, dict)
        else {}
    )
    print(f"📊 데이터 수집 완료 — sections={section_counts}")

    # E5: 전체 미수집이면 'None 미국장 마감' 빈 표 대신 명시적 실패 안내 + 발행 스킵
    if sum(section_counts.values()) == 0:
        date_label = (
            _md_label(target) or _md_label(last_us_trading_day(now)) or "최근 거래일"
        )
        print(
            f"⚠️  미국장 데이터 전체 미수집 — 실패 안내만 발송, 발행 스킵 ({date_label})"
        )
        send(
            f"🇺🇸 *미국장 데이터 수집 실패* ({date_label})\n"
            "데이터 출처(yfinance)에서 유효한 종가를 받지 못했습니다."
        )
        return

    # 스냅샷을 먼저 만들어 거래일(date)을 확정 — 웹 링크와 발행에 재사용
    snapshot = build_us_snapshot(data, now)

    # E1 신선도(target 한정) + I8 부분실패 경고
    warnings, stale = _build_us_warnings(snapshot, section_counts, target)
    if warnings:
        print("⚠️  본문 경고: " + " | ".join(warnings))

    # stale(잘못된 날짜)이면 발행을 건너뛰므로 웹 링크도 붙이지 않는다(#10 I9 — 404 방지).
    web_link = web_link_suffix_for_snapshot(snapshot) if not stale else ""
    sources = (
        "\n\n출처: "
        "[Yahoo Finance](https://finance.yahoo.com/markets/)"
        " · [S&P 섹터](https://finance.yahoo.com/sectors/)"
        f"{web_link}"
    )

    text = format_us_daily(data) + _warn_block(warnings) + sources
    print(f"📤 Telegram 발송 시작 (텍스트, {len(text)} chars)")
    resp = send(text)

    msg_id = (
        resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    )
    results = resp.get("results", []) if isinstance(resp, dict) else []
    ok_n = sum(1 for r in results if r.get("ok"))
    suffix = f" — 발송 {ok_n}/{len(results)} 성공" if results else ""
    print(f"✅ 미국장 푸시: msg_id={msg_id}{suffix}")

    # 발행 단계 (발송과 완전 분리). target 불일치(stale)면 잘못된 날짜로 발행하지 않는다.
    if stale:
        print(
            f"⚠️  target({target}) 불일치 — 발행 스킵 (stale 데이터의 잘못된 날짜 발행 방지)"
        )
    else:
        maybe_publish(snapshot, now)


if __name__ == "__main__":
    main(sys.argv[1:])
