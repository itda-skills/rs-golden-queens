"""APScheduler 기반 cron 진입점.

상시 실행되며 KST 기준으로 4개 작업을 트리거한다.

| 시각 (KST)       | 명령             | 비고                                 |
|------------------|------------------|--------------------------------------|
| 월-금 18:10      | daily-kr         | 한국장 매매동향                       |
| 월-금 18:30      | weekly           | 주간 리포트 (스크립트 내부에서 게이트) |
| 화-토 05:30      | daily-us (edt)   | 미국장 EDT 시즌 (스크립트 DST 게이트) |
| 화-토 06:30      | daily-us (est)   | 미국장 EST 시즌                       |

환경변수:
    GOLDENQUEENS_BOT_TOKEN  Telegram bot token (필수)
    GOLDENQUEENS_CHAT_ID    Telegram chat id (필수)
    MARKET_FLOW_RENDER      "text" 권장
    TZ                      기본 Asia/Seoul (Dockerfile에서 설정)

NAS 재부팅 등으로 누락 시 misfire_grace_time(30분) 이내 자동 보충.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    level=logging.INFO,
    stream=sys.stdout,
)
log = logging.getLogger("scheduler")

KST = ZoneInfo("Asia/Seoul")
MAIN_PY = "/app/main.py"
SUBPROCESS_TIMEOUT = 300  # 5분
MISFIRE_GRACE = 1800  # 30분


def run_command(command: str, market_schedule: str = "") -> None:
    """main.py를 subprocess로 호출. 표준 출력/에러를 컨테이너 stdout으로 중계."""
    env = os.environ.copy()
    if market_schedule:
        env["MARKET_SCHEDULE"] = market_schedule

    label = command + (f" [MARKET_SCHEDULE={market_schedule}]" if market_schedule else "")
    log.info("RUN  %s", label)

    try:
        result = subprocess.run(
            [sys.executable, MAIN_PY, command],
            env=env,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log.error("TIMEOUT %s (%ds 초과)", label, SUBPROCESS_TIMEOUT)
        return
    except Exception:
        log.exception("FAIL %s", label)
        return

    if result.stdout.strip():
        for line in result.stdout.rstrip().splitlines():
            log.info("  stdout | %s", line)
    if result.stderr.strip():
        for line in result.stderr.rstrip().splitlines():
            log.warning("  stderr | %s", line)

    if result.returncode == 0:
        log.info("DONE %s (exit=0)", label)
    else:
        log.error("FAIL %s (exit=%d)", label, result.returncode)


def _required_env_present() -> bool:
    missing = [k for k in ("GOLDENQUEENS_BOT_TOKEN", "GOLDENQUEENS_CHAT_ID") if not os.environ.get(k)]
    if missing:
        log.error("필수 환경변수 누락: %s", ", ".join(missing))
        return False
    return True


def main() -> int:
    if not _required_env_present():
        return 2

    sched = BlockingScheduler(timezone=KST)

    sched.add_job(
        run_command,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=10, timezone=KST),
        args=("daily-kr",),
        id="daily-kr",
        misfire_grace_time=MISFIRE_GRACE,
        coalesce=True,
    )
    sched.add_job(
        run_command,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=30, timezone=KST),
        args=("weekly",),
        id="weekly",
        misfire_grace_time=MISFIRE_GRACE,
        coalesce=True,
    )
    sched.add_job(
        run_command,
        CronTrigger(day_of_week="tue-sat", hour=5, minute=30, timezone=KST),
        args=("daily-us", "edt"),
        id="daily-us-edt",
        misfire_grace_time=MISFIRE_GRACE,
        coalesce=True,
    )
    sched.add_job(
        run_command,
        CronTrigger(day_of_week="tue-sat", hour=6, minute=30, timezone=KST),
        args=("daily-us", "est"),
        id="daily-us-est",
        misfire_grace_time=MISFIRE_GRACE,
        coalesce=True,
    )

    log.info("scheduler started (TZ=Asia/Seoul, misfire_grace=%ds)", MISFIRE_GRACE)
    for job in sched.get_jobs():
        trigger = job.trigger
        log.info("  job=%s trigger=%s", job.id, trigger)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
