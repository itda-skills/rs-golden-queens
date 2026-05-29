"""rs-golden-queens — 최상위 CLI 엔트리.

사용:
    python main.py [--test] daily-kr [DATE]   # DATE: YYYYMMDD
    python main.py [--test] daily-us [DATE]   # DATE: YYYY-MM-DD
    python main.py [--test] weekly
    python main.py [--test] notify-test
    python main.py smoke-kr
    python main.py smoke-us

향후 다른 패키지(xxx_flow)가 추가되면 본 파일에 subcommand 만 등록한다.
각 subcommand 의 실제 로직은 해당 패키지의 ``main(argv)`` 함수에 위임한다.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

_TEST_SEND_ENV = "MARKET_FLOW_TEST_SEND"


def _cmd_daily_kr(args: argparse.Namespace) -> None:
    from market_flow import daily_kr

    argv = [args.date] if args.date else []
    daily_kr.main(argv)


def _cmd_daily_us(args: argparse.Namespace) -> None:
    from market_flow import daily_us

    argv = [args.date] if args.date else []
    daily_us.main(argv)


def _cmd_weekly(args: argparse.Namespace) -> None:
    from market_flow import weekly

    weekly.main([])


def _cmd_notify_test(args: argparse.Namespace) -> None:
    import datetime as dt

    from market_flow.telegram_push import send

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(
        timespec="seconds"
    )
    mode = "test" if os.environ.get(_TEST_SEND_ENV) else "prod"
    resp = send(f"[rs-golden-queens] notify-test ({mode}) ping at {now} (KST)")
    print("OK" if resp.get("ok") else resp)


def _add_test_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--test",
        dest="use_test_env",
        action="store_true",
        default=argparse.SUPPRESS,
        help="TEST_GOLDENQUEENS_* 환경변수로 텔레그램 발송",
    )


def _cmd_smoke_kr(args: argparse.Namespace) -> None:
    from datetime import datetime

    from market_flow.fetchers.naver_kr import fetch_today

    data = fetch_today(datetime.now().strftime("%Y%m%d"))
    keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
    print("naver_kr OK:", keys)


def _cmd_smoke_us(args: argparse.Namespace) -> None:
    from market_flow.fetchers.us_market import fetch_us_close

    data = fetch_us_close()
    keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
    print("us_market OK:", keys)


def _cmd_publish_calendar(args: argparse.Namespace) -> None:
    """거래일/휴장 캘린더 스냅샷 발행 (텔레그램 발송 없음).

    MARKET_FLOW_PUBLISH 가 활성일 때만 실제 발행한다.
    """
    import datetime as _dt
    from zoneinfo import ZoneInfo

    from market_flow.publish_channel import maybe_publish
    from market_flow.publisher import build_calendar_snapshot

    now = _dt.datetime.now(ZoneInfo("Asia/Seoul"))
    snap = build_calendar_snapshot(now)
    print(
        f"📅 캘린더 스냅샷 — range={snap['range']['start']}~{snap['range']['end']} "
        f"KR={len(snap['kr'])} US={len(snap['us'])}"
    )
    maybe_publish(snap, now)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="rs-golden-queens 시장 알림 CLI",
    )
    parser.add_argument(
        "--test",
        dest="use_test_env",
        action="store_true",
        default=False,
        help="TEST_GOLDENQUEENS_* 환경변수로 텔레그램 발송",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p_kr = sub.add_parser("daily-kr", help="한국장 매매동향 발송")
    p_kr.add_argument("date", nargs="?", help="YYYYMMDD (기본: 오늘)")
    _add_test_arg(p_kr)
    p_kr.set_defaults(func=_cmd_daily_kr)

    p_us = sub.add_parser("daily-us", help="미국장 마감 요약 발송")
    p_us.add_argument("date", nargs="?", help="YYYY-MM-DD (기본: 최신 거래일)")
    _add_test_arg(p_us)
    p_us.set_defaults(func=_cmd_daily_us)

    p_weekly = sub.add_parser("weekly", help="주간 리포트 발송")
    _add_test_arg(p_weekly)
    p_weekly.set_defaults(func=_cmd_weekly)

    p_ping = sub.add_parser("notify-test", help="텔레그램 핑 (환경변수 검증)")
    _add_test_arg(p_ping)
    p_ping.set_defaults(func=_cmd_notify_test)

    p_skr = sub.add_parser("smoke-kr", help="네이버 fetch 단독 점검")
    p_skr.set_defaults(func=_cmd_smoke_kr)

    p_sus = sub.add_parser("smoke-us", help="yfinance fetch 단독 점검")
    p_sus.set_defaults(func=_cmd_smoke_us)

    p_cal = sub.add_parser("publish-calendar", help="거래일/휴장 캘린더 스냅샷 발행")
    p_cal.set_defaults(func=_cmd_publish_calendar)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    import datetime as _dt
    import traceback as _tb

    parser = build_parser()
    args = parser.parse_args(argv)

    _kst = _dt.timezone(_dt.timedelta(hours=9))
    started = _dt.datetime.now(_kst)
    started_iso = started.isoformat(timespec="seconds")
    cmd = args.command
    use_test_env = bool(getattr(args, "use_test_env", False))

    mode = "test" if use_test_env else "prod"
    print(
        f"━━━ [START] command={cmd} mode={mode} at={started_iso} (KST) ━━━", flush=True
    )

    had_previous_test_env = _TEST_SEND_ENV in os.environ
    previous_test_env = os.environ.get(_TEST_SEND_ENV)
    if use_test_env:
        os.environ[_TEST_SEND_ENV] = "1"
    try:
        try:
            args.func(args)
        except SystemExit as e:
            # 명시적 sys.exit(N) 은 그대로 전파하되 종료 로그를 남김
            ended = _dt.datetime.now(_kst)
            duration = (ended - started).total_seconds()
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
            marker = "DONE" if code == 0 else "FAIL"
            print(
                f"━━━ [{marker}] command={cmd} exit={code} duration={duration:.1f}s ━━━",
                flush=True,
            )
            raise
        except BaseException as e:
            ended = _dt.datetime.now(_kst)
            duration = (ended - started).total_seconds()
            print(
                f"━━━ [FAIL] command={cmd} duration={duration:.1f}s — {type(e).__name__}: {e} ━━━",
                file=sys.stderr,
                flush=True,
            )
            _tb.print_exc(file=sys.stderr)
            return 1
    finally:
        if use_test_env:
            if had_previous_test_env:
                os.environ[_TEST_SEND_ENV] = previous_test_env or ""
            else:
                os.environ.pop(_TEST_SEND_ENV, None)

    ended = _dt.datetime.now(_kst)
    duration = (ended - started).total_seconds()
    print(
        f"━━━ [DONE] command={cmd} exit=0 duration={duration:.1f}s ━━━",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
