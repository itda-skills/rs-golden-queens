"""네이버 금융 — 한국 매매동향 수집

- 모바일 API: 코스피/코스닥 당일 합산 + 프로그램매매
- 데스크탑 페이지: 시간별/일별 추세 (코스피 — 10거래일)
"""

import html
import json
import re
import sys
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


def _strip_tags(s: str) -> str:
    """셀 내부 태그 제거 + HTML 엔티티 복원 + 공백 정리.

    <td><span>1</span></td> → '1', '&#43;1,234' → '+1,234'(엔티티 복원).
    숫자 내부 공백/&nbsp; 정리는 _n 이 담당한다(날짜·시간 셀은 건드리지 않음).
    """
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _n(s):
    """추이 셀 → 정수. '-'·빈칸은 0(순매수 없음), 파싱 불가는 경고 후 0(크래시 가드).

    일별 표는 0순매수를 '-'로 표기하므로 '-'→0 은 의도된 동작이다(누적합 정합은
    daily_kr 의 I-sum 항등식 검증이 별도로 감시). 숫자가 아닌 예상 외 값에는 죽지
    않고 0 + stderr 경고로 처리해 KR 발송 전체가 중단되지 않게 한다(E4).
    """
    s = (s or "").strip()
    # 유니코드 마이너스류(−, –, —, －)를 ASCII '-' 로 정규화 (&minus; 등 엔티티 대응)
    for ch in ("−", "–", "—", "－"):
        if ch in s:
            s = s.replace(ch, "-")
    if s in ("", "-"):
        return 0
    try:
        # 천단위 콤마·선행 +·내부 공백/&nbsp(\xa0) 제거 후 정수화
        return int(
            s.replace(",", "").replace("+", "").replace("\xa0", "").replace(" ", "")
        )
    except ValueError:
        print(f"⚠️  추이 셀 파싱 실패: {s!r} → 0", file=sys.stderr)
        return 0


def _parse_trend_rows(body, time_col):
    """11컬럼 표 행 추출 — <tr>/<td> 속성·중첩 태그·빈 셀에 견고(E3).

    네이버 마크업 변경(속성 추가, 셀 내부 span 등)에도 깨지지 않도록 관대하게
    매칭하고 셀 내부 태그는 제거한다. 11컬럼 행을 하나도 못 뽑았는데 <tr> 자체는
    있으면 stderr 경고(조용한 0행 차단).
    """
    out = []
    # 일별은 YY.MM.DD, 시간별은 HH:MM — 첫 셀이 이 형식인 행만 데이터로 채택한다.
    # 네이버 페이지 하단 페이지네이션("1 2 3 … 10")이 11컬럼으로 잡혀 가짜 행으로
    # 들어오는 것을 차단한다(E8).
    key_re = re.compile(
        r"^\d{1,2}:\d{2}$" if time_col else r"^\d{2}\.\d{2}(?:\.\d{2})?$"
    )
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.DOTALL):
        cells = [
            _strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
        ]
        if len(cells) < 11:
            continue
        # 첫 셀이 날짜/시간 형식이 아니면(페이지네이션 등 비-데이터 행) 제외한다.
        if not key_re.match(cells[0].strip()):
            continue
        out.append(
            {
                ("time" if time_col else "date"): cells[0],
                "personal": _n(cells[1]),
                "foreign": _n(cells[2]),
                "institutional": _n(cells[3]),
                "finance": _n(cells[4]),
                "insurance": _n(cells[5]),
                "trust": _n(cells[6]),
                "bank": _n(cells[7]),
                "other_fin": _n(cells[8]),
                "pension": _n(cells[9]),
                "other_corp": _n(cells[10]),
            }
        )
    if not out and "<tr" in body.lower():
        print(
            "⚠️  추이 파싱 0행 — <tr> 는 있으나 11컬럼 행 없음 (네이버 마크업 변경 가능)",
            file=sys.stderr,
        )
    return out


def fetch_today(bizdate=None):
    """한 번에 — 코스피·코스닥 + 코스피 일별.

    시간별(intraday)은 분단위라 마감 발송·발행 어디에도 쓰이지 않아 수집하지 않는다
    (#10 I-cleanup — 순수 낭비 + 실패 표면적 축소). 필요 시 fetch_kospi_intraday 직접 호출.
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
