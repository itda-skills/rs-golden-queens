"""주간 리포트 → 텔레그램 발송 (그 주 마지막 한국 거래일)

- 코스피 5거래일 누적 (네이버 데스크탑 10일 페이지에서 최신 5일)
- 미국 워치 ETF 5거래일 누적 등락 (yfinance 일별 데이터)

SPEC-MF-SCHED-001: 평일 KST 18:30에 트리거되지만, "오늘이 그 주의 마지막
한국 거래일"일 때만 발송. 금요일 휴장이면 직전 거래일에 이월 발송.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import yfinance as yf

from market_flow.calendar_utils import is_last_kr_trading_day_of_week
from market_flow.fetchers.naver_kr import fetch_kospi_daily
from market_flow.fetchers.us_market import WATCH
from market_flow.formatter import format_weekly
from market_flow.publish_channel import maybe_publish, web_link_suffix
from market_flow.publisher import build_weekly_snapshot
from market_flow.telegram_push import send

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
            else:
                print(
                    f"warn: watch_5d {ticker}: 거래일 부족 ({len(close)} < 6)",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"warn: watch_5d {ticker}: {type(e).__name__}: {e}", file=sys.stderr)
    return out


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> None:
    if argv is None:
        argv = []
    if now is None:
        now = datetime.now(_KST)

    # 마지막 거래일 게이트: 그 외 날에는 발송 없이 명시적으로 스킵 로그
    if not is_last_kr_trading_day_of_week(now):
        weekday = now.astimezone(_KST).strftime("%A (%Y-%m-%d)")
        print(f"⏭️  스킵: 이번 주 마지막 한국 거래일이 아님 — {weekday}")
        return

    bizdate = now.astimezone(_KST).strftime("%Y%m%d")
    print(f"📥 코스피 일별 데이터 수집 시작 — bizdate={bizdate}")
    kospi_daily = fetch_kospi_daily(bizdate)
    print(
        f"📊 코스피 일별 수집 완료 — rows={len(kospi_daily) if isinstance(kospi_daily, (list, dict)) else '?'}"
    )
    print("📥 워치 ETF 5거래일 누적 등락 수집 시작")
    watch_5d = _watch_5d_pct()
    print(f"📊 워치 ETF 수집 완료 — tickers={list(watch_5d.keys())}")

    snapshot = build_weekly_snapshot(kospi_daily, watch_5d, now)
    sources = (
        "\n\n출처: "
        f"[네이버 일별](https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate})"
        " · [Yahoo Finance](https://finance.yahoo.com/markets/)"
        f"{web_link_suffix('weekly', snapshot['week'])}"
    )

    text = format_weekly(kospi_daily, watch_5d) + sources
    print(f"📤 Telegram 발송 시작 (텍스트, {len(text)} chars)")
    resp = send(text)

    msg_id = (
        resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    )
    results = resp.get("results", []) if isinstance(resp, dict) else []
    ok_n = sum(1 for r in results if r.get("ok"))
    suffix = f" — 발송 {ok_n}/{len(results)} 성공" if results else ""
    print(f"✅ 주간 리포트 푸시: msg_id={msg_id}{suffix}")

    # 발행 단계 (발송과 완전 분리 — 실패해도 위 발송에 영향 없음)
    maybe_publish(snapshot, now)


if __name__ == "__main__":
    main(sys.argv[1:])
