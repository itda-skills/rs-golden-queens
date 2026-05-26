"""주간 리포트 → 텔레그램 발송 (그 주 마지막 한국 거래일)

- 코스피 5거래일 누적 (네이버 데스크탑 10일 페이지에서 최신 5일)
- 미국 워치 ETF 5거래일 누적 등락 (yfinance 일별 데이터)

SPEC-MF-SCHED-001: 평일 KST 18:30에 트리거되지만, "오늘이 그 주의 마지막
한국 거래일"일 때만 발송. 금요일 휴장이면 직전 거래일에 이월 발송.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from market_flow.calendar_utils import is_last_kr_trading_day_of_week
from market_flow.fetchers.naver_kr import fetch_kospi_daily
from market_flow.fetchers.us_market import WATCH
from market_flow.formatter import format_weekly, render_weekly_html
from market_flow.telegram_push import send, send_photo


def _is_image_mode() -> bool:
    return os.environ.get("MARKET_FLOW_RENDER", "").strip().lower() == "image"

_KST = ZoneInfo("Asia/Seoul")


def _watch_5d_pct():
    """워치 ETF 최근 5거래일 누적 등락률"""
    syms = " ".join(t for t, _ in WATCH)
    end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    df = yf.download(syms, start=start, end=end, progress=False, auto_adjust=False)
    out = {}
    for ticker, _ in WATCH:
        try:
            close = df["Close"][ticker].dropna()
            if len(close) >= 6:
                # 최근 5거래일 누적 등락 = (오늘 / 6일전) - 1
                pct = (float(close.iloc[-1]) / float(close.iloc[-6]) - 1) * 100
                out[ticker] = pct
        except Exception:
            pass
    return out


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> None:
    if argv is None:
        argv = []
    if now is None:
        now = datetime.now(_KST)

    # 마지막 거래일 게이트: 그 외 날에는 침묵 스킵
    if not is_last_kr_trading_day_of_week(now):
        return

    bizdate = now.astimezone(_KST).strftime("%Y%m%d")
    kospi_daily = fetch_kospi_daily(bizdate)
    watch_5d = _watch_5d_pct()

    sources = (
        "\n\n출처: "
        f"[네이버 일별](https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate})"
        " · [Yahoo Finance](https://finance.yahoo.com/markets/)"
    )

    if _is_image_mode():
        from market_flow.render.renderer import html_to_png

        html = render_weekly_html(kospi_daily, watch_5d)
        png = html_to_png(html)
        caption = f"📅 *주간 매매동향 리포트* ({datetime.now().strftime('%-m/%-d')} 기준){sources}"
        resp = send_photo(png, caption=caption)
    else:
        text = format_weekly(kospi_daily, watch_5d) + sources
        resp = send(text)

    msg_id = resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    print(f"✅ 주간 리포트 푸시: msg_id={msg_id}")


if __name__ == "__main__":
    main(sys.argv[1:])
