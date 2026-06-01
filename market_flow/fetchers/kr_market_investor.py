"""코스닥 시장 일별 투자자 순매수 — KIS FHPTJ04040000 래퍼.

네이버 코스피 일별(kospi_daily)과 동일한 표시 행 구조(date/personal/foreign/
institutional, 억원 정수, 최신순)로 정규화한다. 기관 세부는 코스피(네이버)와
항목 체계가 달라 담지 않는다.
"""

from __future__ import annotations

import sys
from datetime import datetime

from kis import KISClient


def _to_eok(v) -> int:
    """백만원 문자열 → 억원 정수. 파싱 불가는 0(크래시 가드)."""
    try:
        return round(float(str(v).replace(",", "").strip()) / 100)
    except (ValueError, TypeError):
        return 0


def _fmt_date(yyyymmdd) -> str:
    """'20260529' → '26.05.29' (네이버 일별 date 형식 정합)."""
    s = str(yyyymmdd).strip()
    return f"{s[2:4]}.{s[4:6]}.{s[6:8]}" if len(s) == 8 and s.isdigit() else s


def fetch_kosdaq_daily(
    bizdate: str, client: KISClient | None = None, days: int = 10
) -> list[dict]:
    """코스닥 일별 투자자 순매수(외인/기관/개인, 억원) — 최신순 최대 days행."""
    if client is None:
        client = KISClient(svr="prod")
    df = client.inquire_investor_daily_by_market("KSQ", bizdate)
    if df is None or getattr(df, "empty", True):
        print("⚠️  코스닥 일별 0행 — KIS 빈 응답", file=sys.stderr)
        return []
    out = []
    for _, r in df.head(days).iterrows():
        out.append(
            {
                "date": _fmt_date(r.get("stck_bsop_date")),
                "personal": _to_eok(r.get("prsn_ntby_tr_pbmn")),
                "foreign": _to_eok(r.get("frgn_ntby_tr_pbmn")),
                "institutional": _to_eok(r.get("orgn_ntby_tr_pbmn")),
            }
        )
    return out


if __name__ == "__main__":
    import json

    bd = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    print(json.dumps(fetch_kosdaq_daily(bd), ensure_ascii=False, indent=2))
