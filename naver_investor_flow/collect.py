"""일일 수집 엔트리 — 9회 호출 후 텔레그램 알림.

CI(GitHub Actions)에서 cron으로 매일 KST 18:10에 호출된다.
- flow_day 1회 + deal_rank 8조합 (KOSPI/KOSDAQ × 외국인/기관 × 매수/매도) = 9회
- 결과를 사람이 읽는 마크다운 요약으로 변환 후 stdout + 텔레그램 전송
- 텔레그램 환경변수(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) 부재 시 stdout만

종속성: stdlib only. requirements.txt 없음.
"""

from __future__ import annotations

import argparse
import datetime
import sys
import traceback

from naver_investor_flow import http_client, parser_flow, parser_rank, notify_telegram, report_engine

# SPEC-REPORT-001: 라벨/조합 정본은 report_engine 으로 이전됨.
# 하위 호환을 위해 collect 에서도 재-export (다른 모듈/테스트가 collect.LABEL_* 를 참조할 수 있음).
DEAL_RANK_COMBOS = report_engine.DEAL_RANK_COMBOS
LABEL_MARKET = report_engine.LABEL_MARKET
LABEL_INVESTOR = report_engine.LABEL_INVESTOR
LABEL_SIDE = report_engine.LABEL_SIDE

BASE_FLOW = "https://finance.naver.com/sise/investorDealTrendDay.naver"
BASE_RANK = "https://finance.naver.com/sise/sise_deal_rank_iframe.naver"
REFERER_FLOW = "https://finance.naver.com/sise/sise_trans_style.naver"
REFERER_RANK = "https://finance.naver.com/sise/sise_deal_rank.naver"

MARKET_MAP = {"kospi": "01", "kosdaq": "02"}
INVESTOR_MAP = {"foreign": "9000", "institution": "1000"}

def _kst_today() -> str:
    """KST 기준 오늘 날짜 YYYYMMDD."""
    kst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(kst).strftime("%Y%m%d")


def fetch_flow_day(bizdate: str | None = None) -> list[dict]:
    bd = bizdate or _kst_today()
    url = f"{BASE_FLOW}?bizdate={bd}&sosok="
    html = http_client.fetch_html(url, referer=REFERER_FLOW)
    return parser_flow.parse_flow_day(html)


def fetch_deal_rank(market: str, investor: str, side: str) -> list[dict]:
    sosok = MARKET_MAP[market]
    gubun = INVESTOR_MAP[investor]
    url = f"{BASE_RANK}?sosok={sosok}&investor_gubun={gubun}&type={side}"
    html = http_client.fetch_html(url, referer=REFERER_RANK)
    return parser_rank.parse_deal_rank(html)


def _fmt_eok(v: int) -> str:
    """억원 부호 포함 천단위 콤마."""
    return f"{v:+,}"


def _fmt_mn(v: int) -> str:
    """백만원 부호 포함."""
    return f"{v:+,}"


# @MX:NOTE: SPEC-REPORT-001 — 보고서 합성은 report_engine 으로 위임.
# 기존 build_report 호출자(테스트 포함)와의 하위 호환을 위해 동일 시그니처를 유지한다.
def build_report(
    flow_rows: list[dict],
    rank_results: list[tuple[tuple[str, str, str], list[dict]]],
    *,
    bizdate: str,
    fetched_at: str,
) -> str:
    """수집 결과를 사람이 읽는 마크다운 요약으로 변환.

    SPEC-REPORT-001 이후 본 함수는 `report_engine.build_context` + `render_report`
    의 얇은 래퍼이다. 출력은 SPEC-REPORT-001 도입 전과 byte-for-byte 동등하다.
    """
    ctx = report_engine.build_context(
        flow_rows, rank_results, bizdate=bizdate, fetched_at=fetched_at
    )
    return render_report(ctx)


# @MX:NOTE: SPEC-REPORT-001 의 신규 공개 API. 컨텍스트 dict 를 받아 템플릿 렌더링 결과 반환.
# @MX:ANCHOR: collect.main 및 tests/test_collect_render.py 가 호출하는 경계
# @MX:REASON: 템플릿 외부화의 entry point — 변경 시 cron 출력에 직접 영향
def render_report(context: dict) -> str:
    """report_engine.render 위임. 실패 시 엔진 내부에서 fallback 처리."""
    return report_engine.render(context)


def _build_arg_parser() -> argparse.ArgumentParser:
    """collect 진입점 argparse 정의. dry-run 옵션 노출."""
    parser = argparse.ArgumentParser(
        prog="python -m naver_investor_flow.collect",
        description="네이버 투자자 매매동향 9콜 통합 수집 + 보고서 + Telegram 전송",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Telegram 전송을 명시적으로 skip (env가 설정되어 있어도). 수집·보고서·stdout 출력은 그대로.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """수집 + 보고서 + 텔레그램 전송. exit code 반환.

    0: 정상
    1: 수집·보고서 작성 실패 (텔레그램 전송 실패는 0 — collect는 성공)
    """
    # argv=None 이면 빈 리스트로 처리 (sys.argv 누설 방지 — 테스트·라이브러리 호출 안전).
    # __main__ 가드는 명시적으로 sys.argv[1:] 를 전달한다.
    args = _build_arg_parser().parse_args(argv if argv is not None else [])

    kst = datetime.timezone(datetime.timedelta(hours=9))
    fetched_at = datetime.datetime.now(kst).isoformat(timespec="seconds")
    bizdate = _kst_today()

    try:
        flow_rows = fetch_flow_day(bizdate=bizdate)
    except Exception:
        flow_rows = []
        print("[collect] flow_day 실패:", file=sys.stderr)
        traceback.print_exc()

    rank_results: list[tuple[tuple[str, str, str], list[dict]]] = []
    for combo in DEAL_RANK_COMBOS:
        try:
            rows = fetch_deal_rank(*combo)
        except Exception:
            rows = []
            print(f"[collect] deal_rank {combo} 실패:", file=sys.stderr)
            traceback.print_exc()
        rank_results.append((combo, rows))

    # SPEC-REPORT-001: 신규 경로 — context 빌드 후 render_report 위임.
    # render_report 자체가 fallback 을 내장하지만, 컨텍스트 빌드/외부 예외에 대한
    # 추가 방어선으로 try 로 감싸 직접 _build_report_fallback 으로 fallback.
    ctx = report_engine.build_context(
        flow_rows, rank_results, bizdate=bizdate, fetched_at=fetched_at
    )
    try:
        report = render_report(ctx)
    except Exception as e:
        print(f"[collect] render_report 실패 ({type(e).__name__}: {e}) — fallback", file=sys.stderr)
        report = report_engine._build_report_fallback(ctx)
    print(report)

    # 텔레그램 전송 (--no-telegram dry-run 우선, 그 다음 env 부재 시 no-op)
    if args.no_telegram:
        print("[collect] --no-telegram 플래그 — Telegram 전송 skip (stdout만)", file=sys.stderr)
    else:
        cfg = notify_telegram.TelegramConfig.from_env()
        if cfg.enabled:
            ok = notify_telegram.send_message(report, config=cfg)
            if ok:
                print("[collect] telegram 전송 성공", file=sys.stderr)
            else:
                print("[collect] telegram 전송 실패", file=sys.stderr)
        else:
            print("[collect] TELEGRAM_BOT_TOKEN/CHAT_ID 미설정 — stdout만", file=sys.stderr)

    # 수집 자체가 전부 실패한 경우만 비정상 종료
    if not flow_rows and all(not rows for _, rows in rank_results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
