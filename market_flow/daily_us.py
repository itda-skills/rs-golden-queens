"""미국장 마감 요약 → 텔레그램 발송

Usage:
  python daily_us.py             # 최신 거래일
  python daily_us.py 2026-05-22  # 특정일

SPEC-MF-SCHED-001:
  - DST 게이트: 환경변수 MARKET_SCHEDULE(edt|est)와 실제 시즌이 불일치하면 즉시 종료
  - 미국 휴장일: "[US] 오늘은 휴장입니다" 한 줄 발송
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

from calendar_utils import is_us_in_dst, is_us_trading_day
from fetchers.us_market import fetch_us_close
from formatter import format_us_daily
from telegram_push import send

_ET = ZoneInfo("America/New_York")
_US_HOLIDAY_MSG = "[US] 오늘은 휴장입니다"


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    if now is None:
        now = datetime.now(_ET)

    schedule = os.environ.get("MARKET_SCHEDULE", "").strip().lower()
    # @MX:WARN: [AUTO] 이중 발송 방지 게이트
    # @MX:REASON: dual-cron 구조에서 두 잡 중 하나만 진행해야 함
    if schedule in {"edt", "est"}:
        in_dst = is_us_in_dst(now)
        if (schedule == "edt" and not in_dst) or (schedule == "est" and in_dst):
            sys.exit(0)

    # 휴장 게이트
    if not is_us_trading_day(now):
        send(_US_HOLIDAY_MSG)
        return

    target = argv[0] if argv else None
    data = fetch_us_close(target)
    text = format_us_daily(data)
    resp = send(text)
    msg_id = resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    print(f"✅ 미국장 푸시: msg_id={msg_id}")


if __name__ == "__main__":
    main()
