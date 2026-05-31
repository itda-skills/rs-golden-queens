"""한국 섹터 ETF 18종 — 마감가·등락률·거래량강도(vol_ratio) 수집.

미국장 us_market 워치 ETF 의 한국판. KIS API 사용.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd

from kis import KISClient

SECTORS = [
    ("091160", "반도체"),
    ("091180", "자동차"),
    ("091170", "은행"),
    ("117700", "건설"),
    ("266420", "헬스케어"),
    ("244580", "바이오"),
    ("305720", "2차전지"),
    ("266360", "미디어"),
    ("157490", "소프트웨어"),
    ("117460", "에너지화학"),
    ("102970", "증권"),
    ("140710", "운송"),
    ("228790", "화장품"),
    ("463250", "방산우주"),
    ("466920", "조선"),
    ("487240", "AI전력"),
    ("132030", "금"),
    ("144600", "은"),
]


def _fetch_one(client: KISClient, code: str, label: str) -> dict | None:
    """단일 ETF의 종가·등락률·vol_ratio (5일 평균 대비) 계산."""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")

    try:
        df = client.inquire_daily_price(code, start, end, period="D")
    except Exception:
        return None
    if df.empty or len(df) < 2:
        return None

    rename = {
        "stck_bsop_date": "date",
        "stck_clpr": "close",
        "acml_vol": "volume",
        "acml_tr_pbmn": "trade_value",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["close", "volume", "trade_value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(df) < 2:
        return None

    today_close = float(df["close"].iloc[-1])
    prev_close = float(df["close"].iloc[-2])
    pct = (today_close - prev_close) / prev_close * 100 if prev_close else 0.0

    vol_ratio = None
    if "volume" in df.columns and len(df) >= 6:
        v_today = float(df["volume"].iloc[-1])
        v_avg5 = float(df["volume"].iloc[-6:-1].mean())
        if v_avg5 > 0:
            vol_ratio = v_today / v_avg5

    trade_value_eok = None
    if "trade_value" in df.columns and pd.notna(df["trade_value"].iloc[-1]):
        trade_value_eok = float(df["trade_value"].iloc[-1]) / 1e8

    return {
        "code": code,
        "label": label,
        "close": today_close,
        "pct": pct,
        "vol_ratio": vol_ratio,
        "trade_value_eok": trade_value_eok,
        "date": str(df["date"].iloc[-1]),
    }


def fetch_kr_sectors(client: KISClient | None = None) -> list[dict]:
    """섹터 ETF 18종 일괄 조회. pct 내림차순 정렬."""
    if client is None:
        client = KISClient(svr="prod")

    out: list[dict] = []
    for code, label in SECTORS:
        d = _fetch_one(client, code, label)
        if d:
            out.append(d)
        time.sleep(0.12)  # KIS prod rate limit
    out.sort(key=lambda x: -(x["pct"] or 0))
    return out


if __name__ == "__main__":
    import json

    rows = fetch_kr_sectors()
    print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
