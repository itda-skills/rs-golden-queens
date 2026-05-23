"""일일 수집 엔트리 — 9회 호출 후 텔레그램 알림.

CI(GitHub Actions)에서 cron으로 매일 KST 18:10에 호출된다.
- flow_day 1회 + deal_rank 8조합 (KOSPI/KOSDAQ × 외국인/기관 × 매수/매도) = 9회
- 결과를 사람이 읽는 마크다운 요약으로 변환 후 stdout + 텔레그램 전송
- 텔레그램 환경변수(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) 부재 시 stdout만

종속성: stdlib only. requirements.txt 없음.
"""

from __future__ import annotations

import datetime
import sys
import traceback
from typing import Any

from naver_investor_flow import http_client, parser_flow, parser_rank, notify_telegram

BASE_FLOW = "https://finance.naver.com/sise/investorDealTrendDay.naver"
BASE_RANK = "https://finance.naver.com/sise/sise_deal_rank_iframe.naver"
REFERER_FLOW = "https://finance.naver.com/sise/sise_trans_style.naver"
REFERER_RANK = "https://finance.naver.com/sise/sise_deal_rank.naver"

MARKET_MAP = {"kospi": "01", "kosdaq": "02"}
INVESTOR_MAP = {"foreign": "9000", "institution": "1000"}

# 8조합 순서 (보고서 표시 순)
DEAL_RANK_COMBOS = [
    ("kospi", "foreign", "buy"),
    ("kospi", "foreign", "sell"),
    ("kospi", "institution", "buy"),
    ("kospi", "institution", "sell"),
    ("kosdaq", "foreign", "buy"),
    ("kosdaq", "foreign", "sell"),
    ("kosdaq", "institution", "buy"),
    ("kosdaq", "institution", "sell"),
]

LABEL_MARKET = {"kospi": "KOSPI", "kosdaq": "KOSDAQ"}
LABEL_INVESTOR = {"foreign": "외국인", "institution": "기관"}
LABEL_SIDE = {"buy": "매수", "sell": "매도"}


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


def build_report(
    flow_rows: list[dict],
    rank_results: list[tuple[tuple[str, str, str], list[dict]]],
    *,
    bizdate: str,
    fetched_at: str,
) -> str:
    """수집 결과를 사람이 읽는 마크다운 요약으로 변환.

    Args:
        flow_rows: flow_day 행 (최근 영업일부터)
        rank_results: [((market, investor, side), rows), ...] 순서대로 8개
        bizdate: 호출 기준일 (KST YYYYMMDD)
        fetched_at: ISO 8601 (KST)
    """
    lines: list[str] = []
    lines.append(f"📊 네이버 투자자 매매동향 — 기준일 {bizdate} (KST)")
    lines.append(f"수집 시각: {fetched_at}")
    lines.append("")

    # ▎일별 시장 매매 (최대 5행, 단위 억원)
    lines.append("▎일별 시장 매매 (억원, 부호=순매수)")
    if not flow_rows:
        lines.append("  (데이터 없음)")
    else:
        for row in flow_rows[:5]:
            lines.append(
                f"  {row['date']}  "
                f"개인 {_fmt_eok(row['individual_eok'])} / "
                f"외국인 {_fmt_eok(row['foreign_eok'])} / "
                f"기관계 {_fmt_eok(row['institution_total_eok'])}"
            )
    lines.append("")

    # ▎8조합 종목 랭킹 (각 TOP3, 단위 백만원)
    for combo, rows in rank_results:
        market, investor, side = combo
        header = f"▎{LABEL_MARKET[market]} {LABEL_INVESTOR[investor]} {LABEL_SIDE[side]} TOP3 (백만원)"
        lines.append(header)
        if not rows:
            lines.append("  (데이터 없음)")
        else:
            for i, r in enumerate(rows[:3], start=1):
                code = r.get("code") or "------"
                lines.append(f"  {i}. {r['name']} ({code})  {_fmt_mn(r['amount_mn_krw'])}")
        lines.append("")

    lines.append("─────────")
    lines.append("출처: finance.naver.com (사실 데이터, 투자 권유 아님)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """수집 + 보고서 + 텔레그램 전송. exit code 반환.

    0: 정상
    1: 수집·보고서 작성 실패 (텔레그램 전송 실패는 0 — collect는 성공)
    """
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

    report = build_report(
        flow_rows, rank_results, bizdate=bizdate, fetched_at=fetched_at
    )
    print(report)

    # 텔레그램 전송 (설정 부재 시 no-op, 실패는 stderr만)
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
    sys.exit(main())
