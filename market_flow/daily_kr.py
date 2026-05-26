"""한국장 일간 매매동향 → 텔레그램 발송

Usage:
  python daily_kr.py            # 오늘
  python daily_kr.py 20260522   # 특정일

SPEC-MF-SCHED-001: 한국 휴장일에는 `[KR] YYYY-MM-DD (요일) 오늘은 휴장입니다`
한 줄 발송. 날짜는 KST 로컬 기준 (REQ-MF-HOL-004).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from market_flow.calendar_utils import format_holiday_message, is_kr_trading_day
from market_flow.fetchers.naver_kr import fetch_today
from market_flow.formatter import format_kr_daily, render_kr_daily_html, kr_weekday
from market_flow.telegram_push import send, send_photo

_KST = ZoneInfo("Asia/Seoul")


def _is_image_mode() -> bool:
    return os.environ.get("MARKET_FLOW_RENDER", "").strip().lower() == "image"


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> None:
    if argv is None:
        argv = []
    if now is None:
        now = datetime.now(_KST)

    # 휴장 게이트: fetcher를 호출하지 않고 한 줄 메시지만 발송
    if not is_kr_trading_day(now):
        send(format_holiday_message("KR", now))
        return

    bizdate = argv[0] if argv else now.astimezone(_KST).strftime("%Y%m%d")
    data = fetch_today(bizdate)

    sources = (
        "\n\n출처: "
        f"[네이버 일별](https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate})"
        f" · [모바일 통합](https://m.stock.naver.com/domestic/index/KOSPI/total)"
    )

    if _is_image_mode():
        from market_flow.render.renderer import html_to_png

        html = render_kr_daily_html(data)
        png = html_to_png(html, width=720, height=3200)
        caption = f"📊 *{kr_weekday(bizdate)} 마감 매매동향*{sources}"
        resp = send_photo(png, caption=caption)
    else:
        text = format_kr_daily(data) + sources
        resp = send(text)

    msg_id = resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    print(f"✅ 한국장 푸시: msg_id={msg_id}, bizdate={bizdate}")


if __name__ == "__main__":
    main(sys.argv[1:])
