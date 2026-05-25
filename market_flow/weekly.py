"""주간 리포트 → 텔레그램 발송 (매주 금요일)

- 코스피 5거래일 누적 (네이버 데스크탑 10일 페이지에서 최신 5일)
- 미국 워치 ETF 5거래일 누적 등락 (yfinance 일별 데이터)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yfinance as yf

from fetchers.naver_kr import fetch_kospi_daily
from fetchers.us_market import WATCH
from formatter import format_weekly
from telegram_push import send


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


def main():
    bizdate = datetime.now().strftime("%Y%m%d")
    kospi_daily = fetch_kospi_daily(bizdate)
    watch_5d = _watch_5d_pct()
    text = format_weekly(kospi_daily, watch_5d)
    resp = send(text)
    print(f"✅ 주간 리포트 푸시: msg_id={resp['result']['message_id']}")


if __name__ == "__main__":
    main()
