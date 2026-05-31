"""FRED (St. Louis Fed) keyless CSV fetcher (#10 I6).

위험선호를 직접 사실값으로 보강한다 — API 키 불필요·공식·일별 실측. yfinance 와
별개 소스라 별도 모듈로 격리하고, 실패는 None 으로 degrade 한다(다른 US 섹션 무관).
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import sys
import urllib.request

from market_flow._retry import retry_call, retryable_urllib

_FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"


def fetch_fred_latest(series_id: str) -> dict | None:
    """FRED 시리즈 CSV 에서 최신 유효 관측 2개로 값+전일대비를 만든다.

    Returns:
        {series, date, value, prev, change} 또는 None(결측/실패).
        결측치('.')·헤더 행은 건너뛴다. 멱등 GET 이라 재시도한다(#10 I8).
    """
    # 최근 ~90일만 받아 전송량·파싱을 줄인다(전일대비엔 충분, 휴일 여유 포함).
    # cosd 는 대략적 시작일 필터라 로컬 날짜·1일 오차가 결과에 영향을 주지 않는다.
    cosd = (_dt.date.today() - _dt.timedelta(days=90)).isoformat()
    url = _FRED_CSV.format(series=series_id) + f"&cosd={cosd}"

    def _once():
        # FRED 앞단 봇방어는 브라우저 위장 UA(Mozilla/5.0 등)를 위장 스크래퍼로 보고
        # 응답을 hang(tarpit)시킨다(검증). 헤더를 비워 urllib 기본 UA 로 보내면
        # 정상 응답(~0.1s)한다 — 정직한 자동화 클라이언트는 통과한다.
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", errors="replace")

    try:
        body = retry_call(_once, attempts=2, should_retry=retryable_urllib, label=url)
    except Exception as e:  # noqa: BLE001 — FRED 실패는 None 으로 degrade
        print(
            f"warn: FRED {series_id} 수집 실패: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return None

    rows: list[tuple[str, float]] = []
    for row in csv.reader(io.StringIO(body)):
        if len(row) != 2:
            continue
        date, raw = row[0].strip(), row[1].strip()
        # FRED 결측치는 '.', 헤더는 observation_date/DATE(스키마 변형 대비 둘 다)
        if not raw or raw == "." or date in ("observation_date", "DATE"):
            continue
        try:
            rows.append((date, float(raw)))
        except ValueError:
            continue
    if not rows:
        print(f"warn: FRED {series_id} 유효 관측 없음", file=sys.stderr)
        return None

    date, value = rows[-1]
    prev = rows[-2][1] if len(rows) >= 2 else None
    # 발행 시점에 소수 2자리로 확정한다(SoT: 텔레그램·웹이 재반올림 없이 같은 값을
    # 표시·분류). `or 0.0` 로 -0.0 을 +0.0 으로 정규화해 양쪽 부호를 일치시킨다.
    change = (round(value - prev, 2) or 0.0) if prev is not None else None
    return {
        "series": series_id,
        "date": date,
        "value": value,
        "prev": prev,
        "change": change,
    }


def fetch_high_yield_oas() -> dict | None:
    """ICE BofA US High Yield Index OAS (BAMLH0A0HYM2) — 신용 스프레드 %p.

    상승=스프레드 확대(위험회피/안전자산), 하락=축소(위험선호). 사실값만 반환한다.
    """
    return fetch_fred_latest("BAMLH0A0HYM2")


if __name__ == "__main__":
    import json

    print(json.dumps(fetch_high_yield_oas(), ensure_ascii=False, indent=2))
