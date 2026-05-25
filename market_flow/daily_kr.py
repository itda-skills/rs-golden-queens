"""한국장 일간 매매동향 → 텔레그램 발송

Usage:
  python daily_kr.py            # 오늘
  python daily_kr.py 20260522   # 특정일
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetchers.naver_kr import fetch_today
from formatter import format_kr_daily
from telegram_push import send


def main():
    bizdate = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    data = fetch_today(bizdate)
    text = format_kr_daily(data)
    resp = send(text)
    print(f"✅ 한국장 푸시: msg_id={resp['result']['message_id']}, bizdate={bizdate}")


if __name__ == "__main__":
    main()
