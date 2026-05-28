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
        date_str = now.astimezone(_KST).strftime("%Y-%m-%d %A")
        print(f"🏖️  한국 휴장일 — {date_str}: 휴장 안내 메시지만 발송")
        send(format_holiday_message("KR", now))
        return

    bizdate = argv[0] if argv else now.astimezone(_KST).strftime("%Y%m%d")
    print(f"📥 네이버 한국장 데이터 수집 시작 — bizdate={bizdate}")
    data = fetch_today(bizdate)
    print(f"📊 데이터 수집 완료 — keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}")

    # KIS 기반 섹터 ETF 18종 + 동적 수급 워치 (실패해도 기존 메시지는 정상 발송).
    # KIS fetcher 는 datetime.now() 기준으로만 동작하므로, 과거일 재발송 시에는
    # 제목과 데이터 일자가 어긋나는 것을 막기 위해 KIS 섹션을 통째로 스킵한다.
    data["sectors"] = None
    data["money_flow"] = None
    today_kst = now.astimezone(_KST).strftime("%Y%m%d")
    if bizdate != today_kst:
        print(
            f"⏭️  KIS 섹션 스킵 — bizdate={bizdate} != today={today_kst} "
            f"(과거일 재발송 모드: KIS 는 datetime.now() 기준이라 데이터 일자 불일치 위험)"
        )
    else:
        try:
            from kis import KISClient

            from market_flow.fetchers.kr_etfs import fetch_kr_sectors
            from market_flow.fetchers.kr_money_flow import fetch_money_flow_watch

            print("📥 KIS 섹터 ETF 18종 수집 시작")
            client = KISClient(svr="prod")
            sectors = fetch_kr_sectors(client)
            print(f"📊 섹터 ETF 수집 완료 — {len(sectors)}/18종")

            print("📥 KIS 동적 수급 워치 스크리닝 시작 (top=40)")
            money_flow = fetch_money_flow_watch(
                client, window=1, top=40, etf_show=5, stock_show=5
            )
            n_etf = len(money_flow.get("etfs", []))
            n_stock = len(money_flow.get("stocks", []))
            print(f"📊 동적 워치 완료 — ETF {n_etf}종 + 개별주 {n_stock}종")

            data["sectors"] = sectors
            data["money_flow"] = money_flow
        except Exception as e:
            print(f"⚠️  섹터/수급 fetch 실패 (메시지에서 제외): {e}", file=sys.stderr)

    sources = (
        "\n\n출처: "
        f"[네이버 일별](https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate})"
        f" · [모바일 통합](https://m.stock.naver.com/domestic/index/KOSPI/total)"
    )

    if _is_image_mode():
        from market_flow.render.renderer import html_to_png

        print("🖼️  이미지 모드 — HTML→PNG 렌더")
        html = render_kr_daily_html(data)
        png = html_to_png(html)
        caption = f"📊 *{kr_weekday(bizdate)} 마감 매매동향*{sources}"
        print(f"📤 Telegram 발송 시작 (사진, {len(png)} bytes)")
        resp = send_photo(png, caption=caption)
    else:
        text = format_kr_daily(data) + sources
        print(f"📤 Telegram 발송 시작 (텍스트, {len(text)} chars)")
        resp = send(text)

    msg_id = resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    results = resp.get("results", []) if isinstance(resp, dict) else []
    ok_n = sum(1 for r in results if r.get("ok"))
    suffix = f" — 발송 {ok_n}/{len(results)} 성공" if results else ""
    print(f"✅ 한국장 푸시: msg_id={msg_id}, bizdate={bizdate}{suffix}")


if __name__ == "__main__":
    main(sys.argv[1:])
