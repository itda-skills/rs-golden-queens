"""네이버 금융 — 한국 매매동향 수집

- 모바일 API: 코스피/코스닥 당일 합산 + 프로그램매매
- 데스크탑 페이지: 시간별/일별 추세 (코스피 — 10거래일)
"""

import json
import re
import urllib.request
from datetime import datetime

UA = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.naver.com/",
}


def _get(url, decode="utf-8"):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode(decode, errors="replace")


def fetch_daily_summary(market):
    """코스피/코스닥 당일 매매동향 + 프로그램매매 (모바일 API)

    Returns:
        {bizdate, personal, foreign, institutional,
         program_arb, program_nonarb, program_total}
    """
    assert market in ("KOSPI", "KOSDAQ")
    raw = _get(f"https://m.stock.naver.com/api/index/{market}/integration")
    data = json.loads(raw)
    deal = data.get("dealTrendInfo", {})
    prog = data.get("programTrendInfo", {})

    def to_int(v):
        if v is None or v == "":
            return None
        return int(str(v).replace(",", "").replace("+", ""))

    return {
        "bizdate": deal.get("bizdate"),
        "personal": to_int(deal.get("personalValue")),
        "foreign": to_int(deal.get("foreignValue")),
        "institutional": to_int(deal.get("institutionalValue")),
        "program_arb": to_int(prog.get("indexDifferenceReal")),
        "program_nonarb": to_int(prog.get("indexBiDifferenceReal")),
        "program_total": to_int(prog.get("indexTotalReal")),
    }


def fetch_kospi_intraday(bizdate):
    """코스피 시간별 누적 순매수 (데스크탑 페이지)"""
    body = _get(
        f"https://finance.naver.com/sise/investorDealTrendTime.naver?bizdate={bizdate}",
        decode="euc-kr",
    )
    return _parse_trend_rows(body, time_col=True)


def fetch_kospi_daily(bizdate):
    """코스피 일별 (기준일 포함 10거래일) 순매수 (데스크탑 페이지)"""
    body = _get(
        f"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate}",
        decode="euc-kr",
    )
    return _parse_trend_rows(body, time_col=False)


def _parse_trend_rows(body, time_col):
    """11컬럼 표 행 추출"""
    out = []
    for tr in re.findall(r"<tr>\s*((?:<td[^>]*>[^<]*</td>\s*)+)</tr>", body):
        cells = re.findall(r"<td[^>]*>([^<]+)</td>", tr)
        if len(cells) < 11:
            continue

        def n(s):
            return int(s.replace(",", "").replace("+", "")) if s and s != "-" else 0

        out.append(
            {
                ("time" if time_col else "date"): cells[0],
                "personal": n(cells[1]),
                "foreign": n(cells[2]),
                "institutional": n(cells[3]),
                "finance": n(cells[4]),
                "insurance": n(cells[5]),
                "trust": n(cells[6]),
                "bank": n(cells[7]),
                "other_fin": n(cells[8]),
                "pension": n(cells[9]),
                "other_corp": n(cells[10]),
            }
        )
    return out


def fetch_today(bizdate=None):
    """한 번에 — 코스피·코스닥 + 코스피 시간별/일별"""
    if bizdate is None:
        bizdate = datetime.now().strftime("%Y%m%d")
    return {
        "bizdate": bizdate,
        "kospi": fetch_daily_summary("KOSPI"),
        "kosdaq": fetch_daily_summary("KOSDAQ"),
        "kospi_intraday": fetch_kospi_intraday(bizdate),
        "kospi_daily": fetch_kospi_daily(bizdate),
    }


if __name__ == "__main__":
    import sys

    bizdate = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(fetch_today(bizdate), ensure_ascii=False, indent=2))
