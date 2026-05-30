"""미국장 마감 요약 → 텔레그램 발송

Usage:
  python daily_us.py             # 최신 거래일
  python daily_us.py 2026-05-22  # 특정일

SPEC-MF-SCHED-001:
  - DST 게이트: 환경변수 MARKET_SCHEDULE(edt|est)와 실제 시즌이 불일치하면 즉시 종료
  - 미국 휴장일: `[US] YYYY-MM-DD (요일) 오늘은 휴장입니다` 한 줄 발송
    (날짜는 ET 로컬 기준, REQ-MF-HOL-004)
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
)
from market_flow.fetchers.us_market import fetch_us_close
from market_flow.formatter import format_us_daily, render_us_daily_html
from market_flow.publish_channel import maybe_publish, web_link_suffix
from market_flow.publisher import build_holiday_snapshot, build_us_snapshot
from market_flow.telegram_push import send, send_photo

_ET = ZoneInfo("America/New_York")


def _is_image_mode() -> bool:
    return os.environ.get("MARKET_FLOW_RENDER", "").strip().lower() == "image"


def _parse_target_date(raw: str) -> Optional[datetime]:
    """YYYY-MM-DD 또는 YYYYMMDD 문자열을 ET aware datetime 으로 파싱."""
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=_ET)
        except ValueError:
            continue
    return None


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

    # 스냅샷을 먼저 만들어 거래일(date)을 확정 — 웹 링크와 발행에 재사용
    snapshot = build_us_snapshot(data, now)
    web_link = web_link_suffix("us", snapshot["date"]) if snapshot.get("date") else ""
    sources = (
        "\n\n출처: "
        "[Yahoo Finance](https://finance.yahoo.com/markets/)"
        " · [S&P 섹터](https://finance.yahoo.com/sectors/)"
        f"{web_link}"
    )

    if _is_image_mode():
        from market_flow.render.renderer import html_to_png

        print("🖼️  이미지 모드 — HTML→PNG 렌더")
        html = render_us_daily_html(data)
        png = html_to_png(html)
        caption = f"🇺🇸 *{now.strftime('%-m/%-d')} 미국장 마감*{sources}"
        print(f"📤 Telegram 발송 시작 (사진, {len(png)} bytes)")
        resp = send_photo(png, caption=caption)
    else:
        text = format_us_daily(data) + sources
        print(f"📤 Telegram 발송 시작 (텍스트, {len(text)} chars)")
        resp = send(text)

    msg_id = (
        resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    )
    results = resp.get("results", []) if isinstance(resp, dict) else []
    ok_n = sum(1 for r in results if r.get("ok"))
    suffix = f" — 발송 {ok_n}/{len(results)} 성공" if results else ""
    print(f"✅ 미국장 푸시: msg_id={msg_id}{suffix}")

    # 발행 단계 (발송과 완전 분리 — 실패해도 위 발송에 영향 없음)
    maybe_publish(snapshot, now)


if __name__ == "__main__":
    main(sys.argv[1:])
