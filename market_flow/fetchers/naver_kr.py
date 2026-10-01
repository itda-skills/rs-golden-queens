"""네이버 금융 — 한국 매매동향 수집

- 모바일 API: 코스피/코스닥 당일 합산 + 프로그램매매
- Npay 증권 API: 코스피 일별 투자자 순매수 (10거래일)
"""

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from market_flow._retry import retry_call, retryable_urllib

UA = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.naver.com/",
}


def _get(url, decode="utf-8"):
    """멱등 GET — 네트워크 순단·5xx·429 를 지수 백오프로 재시도(#10 I8).

    재시도는 일시 장애만 흡수한다. 마감 직후 당일 데이터 미갱신(stale)은
    재시도해도 같은 값이라 daily_kr 의 기준일 경고(E7)가 별도로 노출한다.
    """

    def _once():
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode(decode, errors="replace")

    # attempts=2(1회 재시도): 안정적인 네이버의 일시 순단 흡수엔 충분하고, 4콜
    # 직렬이 잡 타임아웃 안에 머물도록 총 상한을 짧게 둔다(#10 I8).
    return retry_call(_once, attempts=2, should_retry=retryable_urllib, label=url)


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
        try:
            return int(str(v).replace(",", "").replace("+", "").strip())
        except (ValueError, TypeError):  # 예상 외 값에 죽지 않는다(E4 크래시 가드)
            print(f"⚠️  모바일 값 파싱 실패: {v!r} → None", file=sys.stderr)
            return None

    return {
        "bizdate": deal.get("bizdate"),
        "personal": to_int(deal.get("personalValue")),
        "foreign": to_int(deal.get("foreignValue")),
        "institutional": to_int(deal.get("institutionalValue")),
        "program_arb": to_int(prog.get("indexDifferenceReal")),
        "program_nonarb": to_int(prog.get("indexBiDifferenceReal")),
        "program_total": to_int(prog.get("indexTotalReal")),
    }


# Npay 증권 투자자별 매매동향 API — 옛 데스크탑 investorDealTrendDay.naver 는
# 2026-10 에 410 Gone 으로 폐기됐다. 응답의 investorGubun 코드를 기존 데스크탑 표
# 11컬럼 행 구조로 묶는다. 기관계(9999) 행은 응답에 없어 세부 합으로 계산한다.
_TREND_DAILY_URL = "https://stock.naver.com/api/domestic/market/trend/daily"
_TREND_GROUPS = {
    "personal": ("8000",),
    "foreign": ("9000", "9001"),  # 외국인 + 기타외국인
    "finance": ("1000",),
    "insurance": ("2000",),
    "trust": ("3000", "3100"),  # 투신 + 사모 = 옛 "투신(사모)" 열
    "bank": ("4000",),
    "other_fin": ("5000",),
    "pension": ("6000", "7000"),  # 연기금 + 국가·지자체 = 옛 "연기금등" 열
    "other_corp": ("7100",),
}
_TREND_INST_KEYS = (
    "finance",
    "insurance",
    "trust",
    "bank",
    "other_fin",
    "pension",
)
_TREND_ROWS = 10  # 옛 데스크탑 일별 표와 같은 10거래일
_TREND_PAGE_SIZE = 50
_TREND_MAX_PAGES = 4  # 과거일 재발송 시 최대 200거래일까지 거슬러 찾는다


def fetch_kospi_daily(bizdate):
    """코스피 일별 (기준일 포함 10거래일) 순매수, 억원 — Npay 증권 API.

    API 는 bizdate 파라미터와 무관하게 항상 최신일부터 내려주므로, 기준일 이하
    행만 골라 과거일 재발송과 daily_kr 의 기준일 경고(E7)가 옛 동작대로 유지되게 한다.
    """
    out = []
    for page in range(_TREND_MAX_PAGES):
        query = urllib.parse.urlencode(
            {
                "tradeType": "KRX",
                "marketType": "KOSPI",
                "bizdate": bizdate,
                "startIdx": page * _TREND_PAGE_SIZE,
                "pageSize": _TREND_PAGE_SIZE,
            }
        )
        data = json.loads(_get(f"{_TREND_DAILY_URL}?{query}"))
        content = data.get("content") or []
        for item in content:
            if str(item.get("bizdate", "")) <= str(bizdate):
                out.append(_trend_row(item))
                if len(out) >= _TREND_ROWS:
                    return out
        if not content or data.get("last") in (True, "true"):
            break
    if not out:
        print(f"⚠️  코스피 일별 0행 — bizdate={bizdate} 이하 행 없음", file=sys.stderr)
    return out


def _won_to_eok(v):
    """원 문자열 → 억원 정수. 파싱 불가는 경고 후 0(E4 크래시 가드)."""
    try:
        return round(int(str(v).replace(",", "").strip()) / 100_000_000)
    except (ValueError, TypeError):
        print(f"⚠️  추이 값 파싱 실패: {v!r} → 0", file=sys.stderr)
        return 0


def _trend_row(item):
    """API 일별 항목 → 옛 데스크탑 표와 같은 행(date YY.MM.DD, 억원 정수).

    억 단위 반올림은 그룹 합산 후 한 번만 한다(묶음별 반올림 오차 누적 방지).
    코드 누락은 0 으로 본다 — 합계 이상은 daily_kr 의 I-sum 검증이 감시한다.
    """
    won = {}
    for n in item.get("netAmounts") or []:
        try:
            won[str(n.get("investorGubun"))] = int(str(n.get("diffValue")).strip())
        except (ValueError, TypeError):
            print(f"⚠️  추이 값 파싱 실패: {n!r} → 0", file=sys.stderr)
    grouped = {
        k: sum(won.get(c, 0) for c in codes) for k, codes in _TREND_GROUPS.items()
    }
    inst = sum(grouped[k] for k in _TREND_INST_KEYS)
    d = str(item.get("bizdate", ""))
    row = {"date": f"{d[2:4]}.{d[4:6]}.{d[6:8]}" if len(d) == 8 else d}
    row["personal"] = _won_to_eok(grouped["personal"])
    row["foreign"] = _won_to_eok(grouped["foreign"])
    row["institutional"] = _won_to_eok(inst)
    for k in (*_TREND_INST_KEYS, "other_corp"):
        row[k] = _won_to_eok(grouped[k])
    return row


def fetch_today(bizdate=None):
    """한 번에 — 코스피·코스닥 + 코스피 일별.

    시간별(intraday)은 분단위라 마감 발송·발행 어디에도 쓰이지 않아 수집하지 않는다
    (#10 I-cleanup — 순수 낭비 + 실패 표면적 축소).
    """
    if bizdate is None:
        bizdate = datetime.now().strftime("%Y%m%d")
    return {
        "bizdate": bizdate,
        "kospi": fetch_daily_summary("KOSPI"),
        "kosdaq": fetch_daily_summary("KOSDAQ"),
        "kospi_daily": fetch_kospi_daily(bizdate),
    }


if __name__ == "__main__":
    import sys

    bizdate = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(fetch_today(bizdate), ensure_ascii=False, indent=2))
