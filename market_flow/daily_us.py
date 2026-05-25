"""미국장 마감 요약 → 텔레그램 발송

Usage:
  python daily_us.py             # 최신 거래일
  python daily_us.py 2026-05-22  # 특정일
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetchers.us_market import fetch_us_close
from formatter import format_us_daily
from telegram_push import send


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    data = fetch_us_close(target)
    text = format_us_daily(data)
    resp = send(text)
    print(f"✅ 미국장 푸시: msg_id={resp['result']['message_id']}")


if __name__ == "__main__":
    main()
