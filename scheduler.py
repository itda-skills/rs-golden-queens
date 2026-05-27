"""APScheduler 기반 cron 진입점.

상시 실행되며 /app/schedule.toml 의 정의에 따라 KST 기준으로 작업을 트리거한다.

스케줄 변경: schedule.toml 만 수정하면 됨. 코드 수정 불요.

환경변수:
    GOLDENQUEENS_BOT_TOKEN  Telegram bot token (필수)
    GOLDENQUEENS_CHAT_ID    Telegram chat id (필수)
    MARKET_FLOW_RENDER      "text" 권장
    TZ                      기본 Asia/Seoul (Dockerfile에서 설정)
    SCHEDULE_FILE           기본 /app/schedule.toml (검증용 오버라이드)

NAS 재부팅 등으로 누락 시 misfire_grace_time(30분) 이내 자동 보충.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any
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
DEFAULT_SCHEDULE_FILE = "/app/schedule.toml"
SUBPROCESS_TIMEOUT = 300  # 5분
MISFIRE_GRACE = 1800  # 30분

REQUIRED_JOB_FIELDS = ("id", "command", "day_of_week", "hour", "minute")
ALLOWED_COMMANDS = {"daily-kr", "daily-us", "weekly", "notify-test", "smoke-kr", "smoke-us"}


def run_command(command: str, env_overrides: dict[str, str] | None = None) -> None:
    """main.py 를 subprocess 로 호출. 표준 출력/에러를 컨테이너 stdout 으로 중계."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    label = command
    if env_overrides:
        kv = ",".join(f"{k}={v}" for k, v in env_overrides.items())
        label = f"{command} [{kv}]"
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


def _validate_job(job: dict[str, Any], index: int) -> None:
    """단일 job 정의를 검증한다. 부적합 시 ValueError."""
    for f in REQUIRED_JOB_FIELDS:
        if f not in job:
            raise ValueError(f"job[{index}]: 필수 필드 '{f}' 누락")
    if not isinstance(job["id"], str) or not job["id"]:
        raise ValueError(f"job[{index}]: id 는 비어있지 않은 문자열이어야 함")
    if job["command"] not in ALLOWED_COMMANDS:
        raise ValueError(
            f"job[{index}] id={job['id']}: command '{job['command']}' 허용 안 됨. "
            f"허용: {sorted(ALLOWED_COMMANDS)}"
        )
    hour = job["hour"]
    minute = job["minute"]
    if not (isinstance(hour, int) and 0 <= hour <= 23):
        raise ValueError(f"job[{index}] id={job['id']}: hour 는 0~23 정수")
    if not (isinstance(minute, int) and 0 <= minute <= 59):
        raise ValueError(f"job[{index}] id={job['id']}: minute 는 0~59 정수")
    env = job.get("env")
    if env is not None and not isinstance(env, dict):
        raise ValueError(f"job[{index}] id={job['id']}: env 는 테이블이어야 함")


def load_schedule(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """schedule.toml 을 읽고 검증된 job 리스트를 반환한다."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"스케줄 파일을 찾을 수 없음: {p}")
    with p.open("rb") as f:
        data = tomllib.load(f)
    jobs = data.get("job")
    if not jobs:
        raise ValueError(f"{p}: [[job]] 항목이 하나도 없음")
    if not isinstance(jobs, list):
        raise ValueError(f"{p}: job 은 [[job]] 배열이어야 함")
    ids: set[str] = set()
    for i, job in enumerate(jobs):
        _validate_job(job, i)
        if job["id"] in ids:
            raise ValueError(f"job[{i}]: 중복된 id '{job['id']}'")
        ids.add(job["id"])
    return jobs


def main() -> int:
    if not _required_env_present():
        return 2

    schedule_file = os.environ.get("SCHEDULE_FILE", DEFAULT_SCHEDULE_FILE)
    try:
        jobs = load_schedule(schedule_file)
    except (FileNotFoundError, ValueError) as e:
        log.error("스케줄 로드 실패: %s", e)
        return 3
    log.info("schedule.toml 로드: %s (%d 개 작업)", schedule_file, len(jobs))

    sched = BlockingScheduler(timezone=KST)

    for job in jobs:
        trigger = CronTrigger(
            day_of_week=job["day_of_week"],
            hour=job["hour"],
            minute=job["minute"],
            timezone=KST,
        )
        env_overrides = job.get("env") or None
        sched.add_job(
            run_command,
            trigger,
            args=(job["command"],),
            kwargs={"env_overrides": env_overrides} if env_overrides else {},
            id=job["id"],
            misfire_grace_time=MISFIRE_GRACE,
            coalesce=True,
        )

    log.info("scheduler started (TZ=Asia/Seoul, misfire_grace=%ds)", MISFIRE_GRACE)
    for job in sched.get_jobs():
        log.info("  job=%s trigger=%s", job.id, job.trigger)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
