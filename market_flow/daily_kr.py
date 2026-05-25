"""한국장 일간 매매동향 → 텔레그램 발송

Usage:
  python daily_kr.py            # 오늘
  python daily_kr.py 20260522   # 특정일

SPEC-MF-SCHED-001: 한국 휴장일에는 "[KR] 오늘은 휴장입니다" 한 줄 발송.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

from calendar_utils import is_kr_trading_day
from fetchers.naver_kr import fetch_today
from formatter import format_kr_daily
from telegram_push import send

_KST = ZoneInfo("Asia/Seoul")
_KR_HOLIDAY_MSG = "[KR] 오늘은 휴장입니다"


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    if now is None:
        now = datetime.now(_KST)

    # 휴장 게이트: fetcher를 호출하지 않고 한 줄 메시지만 발송
    if not is_kr_trading_day(now):
        send(_KR_HOLIDAY_MSG)
        return

    bizdate = argv[0] if argv else now.astimezone(_KST).strftime("%Y%m%d")
    data = fetch_today(bizdate)
    text = format_kr_daily(data)
    resp = send(text)
    msg_id = resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    print(f"✅ 한국장 푸시: msg_id={msg_id}, bizdate={bizdate}")


if __name__ == "__main__":
    main()
