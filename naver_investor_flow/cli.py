"""
main.py — CLI 진입점 (argparse + MODE 디스패치)

REQ-001: flow_day / deal_rank 두 MODE
REQ-030: --format {json,table,csv}
REQ-060: --limit N
REQ-010.1: --bizdate
REQ-020.1: --market, --investor, --side

exit code:
  0: 정상, empty
  2: http_error
  3: parse_error
  4: network_error
  5: encoding_error
  64: usage error
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys

from naver_investor_flow import http_client, parser_flow, parser_rank, formatter
from naver_investor_flow.http_client import HttpError, NetworkError, EncodingError


class ParseError(Exception):
    """HTML 파싱 오류 — exit code 3"""
    pass


# parser_flow에서도 사용할 수 있도록 export
parser_flow.ParseError = ParseError  # type: ignore


# ──────────────────────────────────────────────
# URL 빌더
# ──────────────────────────────────────────────

BASE_FLOW = "https://finance.naver.com/sise/investorDealTrendDay.naver"
BASE_RANK = "https://finance.naver.com/sise/sise_deal_rank_iframe.naver"

# iframe 부모 페이지 — Referer 헤더에 사용 (실제 브라우저 흉내)
REFERER_FLOW = "https://finance.naver.com/sise/sise_trans_style.naver"
REFERER_RANK = "https://finance.naver.com/sise/sise_deal_rank.naver"

MARKET_MAP = {"kospi": "01", "kosdaq": "02"}
INVESTOR_MAP = {"foreign": "9000", "institution": "1000"}


def _build_flow_url(bizdate: str | None) -> str:
    # 네이버는 bizdate 파라미터가 없으면 빈 페이지(1.6KB)를 반환한다.
    # bizdate 미지정 시 오늘 날짜를 주입하면 네이버가 그 이전 10영업일을 반환한다
    # (비영업일 입력에도 직전 영업일 데이터를 그대로 반환).
    effective_bizdate = bizdate or datetime.date.today().strftime("%Y%m%d")
    return f"{BASE_FLOW}?bizdate={effective_bizdate}&sosok="


def _build_rank_url(market: str, investor: str, side: str) -> str:
    sosok = MARKET_MAP[market]
    investor_gubun = INVESTOR_MAP[investor]
    return f"{BASE_RANK}?sosok={sosok}&investor_gubun={investor_gubun}&type={side}"


# ──────────────────────────────────────────────
# MODE 핸들러
# ──────────────────────────────────────────────

def _handle_flow_day(args: argparse.Namespace) -> None:
    bizdate = getattr(args, "bizdate", None)
    url = _build_flow_url(bizdate)

    html = http_client.fetch_html(url, referer=REFERER_FLOW)

    try:
        rows = parser_flow.parse_flow_day(html)
    except Exception as exc:
        _print_error({"status": "parse_error", "stage": "flow_day", "url": url, "detail": str(exc)})
        sys.exit(3)

    meta = {
        "bizdate_requested": bizdate,
        "bizdate_returned": rows[0]["date"].replace("-", "") if rows else None,
        "source_url": url,
    }

    limit = getattr(args, "limit", None)
    output = formatter.format_output(
        mode="flow_day",
        data=rows,
        meta=meta,
        fmt=args.format,
        limit=limit,
    )
    print(output)
    sys.exit(0)


def _handle_deal_rank(args: argparse.Namespace) -> None:
    url = _build_rank_url(args.market, args.investor, args.side)

    html = http_client.fetch_html(url, referer=REFERER_RANK)

    try:
        rows = parser_rank.parse_deal_rank(html)
    except Exception as exc:
        _print_error({"status": "parse_error", "stage": "deal_rank", "url": url, "detail": str(exc)})
        sys.exit(3)

    meta = {
        "market": args.market,
        "investor": args.investor,
        "side": args.side,
        "source_url": url,
    }

    limit = getattr(args, "limit", None)
    output = formatter.format_output(
        mode="deal_rank",
        data=rows,
        meta=meta,
        fmt=args.format,
        limit=limit,
    )
    print(output)
    sys.exit(0)


def _print_error(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


# ──────────────────────────────────────────────
# argparse 설정
# ──────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="네이버 금융 투자자 매매동향 조회",
    )
    subparsers = parser.add_subparsers(dest="mode")

    # ── flow_day ──
    flow = subparsers.add_parser("flow_day", help="일별 시장 매매동향")
    flow.add_argument(
        "--bizdate", metavar="YYYYMMDD",
        help="조회 영업일 (생략 시 최신)",
    )
    flow.add_argument(
        "--format", choices=["json", "table", "csv"], default="json",
        help="출력 포맷 (기본: json)",
    )
    flow.add_argument(
        "--limit", type=int, metavar="N",
        help="출력 행 수 제한 (1~10)",
    )

    # ── deal_rank ──
    rank = subparsers.add_parser("deal_rank", help="종목별 외국인·기관 매매 랭킹")
    rank.add_argument(
        "--market", required=True, choices=["kospi", "kosdaq"],
        help="시장 구분 (kospi|kosdaq)",
    )
    rank.add_argument(
        "--investor", required=True, choices=["foreign", "institution"],
        help="투자자 구분 (foreign|institution)",
    )
    rank.add_argument(
        "--side", required=True, choices=["buy", "sell"],
        help="매매 방향 (buy|sell)",
    )
    rank.add_argument(
        "--format", choices=["json", "table", "csv"], default="json",
        help="출력 포맷 (기본: json)",
    )
    rank.add_argument(
        "--limit", type=int, metavar="N",
        help="출력 행 수 제한 (1~30)",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI 진입점.

    Args:
        argv: 인자 리스트 (None이면 sys.argv[1:] 사용)
    """
    p = _build_parser()

    try:
        args = p.parse_args(argv)
    except SystemExit:
        # argparse 기본 에러는 exit 2, 우리는 64로 변환
        sys.exit(64)

    if args.mode is None:
        p.print_help(sys.stderr)
        sys.exit(64)

    try:
        if args.mode == "flow_day":
            _handle_flow_day(args)
        elif args.mode == "deal_rank":
            _handle_deal_rank(args)
    except HttpError as exc:
        _print_error({"status": "http_error", "code": exc.code, "url": exc.url})
        sys.exit(2)
    except NetworkError as exc:
        _print_error({"status": "network_error", "detail": exc.detail})
        sys.exit(4)
    except EncodingError as exc:
        _print_error({"status": "encoding_error", "detail": str(exc)})
        sys.exit(5)


if __name__ == "__main__":
    main()
