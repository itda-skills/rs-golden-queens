#!/bin/sh
# 컨테이너 진입점.
#
# 인자 없거나 "scheduler" → 상시 스케줄러 모드 (기본)
# 그 외 → main.py 일회성 호출 (예: notify-test, daily-kr)

set -e

if [ $# -eq 0 ] || [ "$1" = "scheduler" ]; then
    exec python /app/scheduler.py
else
    exec python /app/main.py "$@"
fi
