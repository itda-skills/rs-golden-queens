"""Money Flow Screener — 자금 흐름 스크리너

거래대금 상위 + 외인·기관 순매수(또는 합산) 종목을 자동 추출.
ETF/개별종목/혼합 모드, 당일/5일/20일 누적 모드 지원.

원본: AI프로젝트/.claude/skills/money-flow/scripts/money_flow_screener.py
이 리포에 포팅하면서 PROJECT_ROOT sys.path 하드코딩 제거.

Usage (CLI):
    # 기본 (전체 + 5일 누적)
    python -m market_flow.screeners.money_flow

    # ETF만, 당일
    python -m market_flow.screeners.money_flow --mode etf --window 1

    # JSON
    python -m market_flow.screeners.money_flow --json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

from kis import KISClient

ETF_PREFIXES = (
    "KODEX", "TIGER", "SOL", "ACE", "HANARO", "KOSEF",
    "KBSTAR", "ARIRANG", "KOACT", "KoAct", "RISE", "PLUS",
    "TIMEFOLIO", "마이다스", "히어로즈", "WOORI", "WON",
    "마이티", "FOCUS", "VITA", "ITF", "BNK",
)

GRADE_SCORE = {"S": 30, "A": 22, "B": 15, "C": 8, "D": 4}


def is_etf(name: str) -> bool:
    if not isinstance(name, str):
        return False
    return any(name.startswith(p) for p in ETF_PREFIXES)


def grade_from_ratios(ratio_5_20: float, ratio_5_60: float) -> str:
    if ratio_5_20 > 1.5 and ratio_5_60 > 1.2:
        return "S"
    if ratio_5_20 > 1.2 and ratio_5_60 > 1.0:
        return "A"
    if 0.8 <= ratio_5_20 <= 1.2:
        return "B"
    if 0.6 <= ratio_5_20 < 0.8:
        return "C"
    return "D"


def fetch_universe(client: KISClient, top: int) -> pd.DataFrame:
    """거래량 순위에서 상위 N개를 후보로 가져온다."""
    df = client.volume_rank()
    if df.empty:
        return df
    keep = ["mksc_shrn_iscd", "hts_kor_isnm", "stck_prpr",
            "prdy_ctrt", "acml_vol", "acml_tr_pbmn"]
    keep = [c for c in keep if c in df.columns]
    df = df[keep].copy()
    df = df.rename(columns={
        "mksc_shrn_iscd": "code",
        "hts_kor_isnm": "name",
        "stck_prpr": "price",
        "prdy_ctrt": "chg_pct",
        "acml_vol": "volume",
        "acml_tr_pbmn": "trade_value",
    })
    for col in ["price", "chg_pct", "volume", "trade_value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.head(top).reset_index(drop=True)


def calc_supply_metrics(client: KISClient, code: str) -> dict:
    """일봉 60일로 거래대금 MA + 가격 모멘텀 계산."""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
    try:
        ohlcv = client.inquire_daily_price(code, start, end, period="D")
    except Exception:
        return {}
    if ohlcv.empty:
        return {}

    df = ohlcv.copy()
    rename_map = {
        "stck_bsop_date": "date",
        "stck_clpr": "close",
        "acml_vol": "volume",
        "acml_tr_pbmn": "trade_value",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    for col in ["close", "volume", "trade_value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(df) < 5:
        return {}

    if "trade_value" not in df.columns or df["trade_value"].isna().all():
        df["trade_value"] = df["close"] * df["volume"]

    tv = df["trade_value"]
    ma5 = tv.tail(5).mean()
    ma20 = tv.tail(20).mean() if len(df) >= 20 else tv.mean()
    ma60 = tv.tail(60).mean() if len(df) >= 60 else tv.mean()
    r_5_20 = (ma5 / ma20) if ma20 else 0.0
    r_5_60 = (ma5 / ma60) if ma60 else 0.0
    grade = grade_from_ratios(r_5_20, r_5_60)

    last_close = df["close"].iloc[-1]
    ret_5 = ((last_close / df["close"].iloc[-6]) - 1) * 100 if len(df) >= 6 else 0.0
    ret_20 = ((last_close / df["close"].iloc[-21]) - 1) * 100 if len(df) >= 21 else 0.0

    return {
        "ma5": ma5,
        "ma20": ma20,
        "r_5_20": r_5_20,
        "r_5_60": r_5_60,
        "grade": grade,
        "last_close": last_close,
        "ret_5": ret_5,
        "ret_20": ret_20,
        "ohlcv": df,
    }


def calc_investor_flow(client: KISClient, code: str, window: int, last_close: float) -> dict:
    """외인·기관 윈도우 누적 순매수 (수량 → 금액 환산)."""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=window * 3 + 10)).strftime("%Y%m%d")
    try:
        df = client.inquire_investor(code, start, end)
    except Exception:
        return {"foreign_value": 0.0, "orgn_value": 0.0, "both_buy": False}
    if df.empty:
        return {"foreign_value": 0.0, "orgn_value": 0.0, "both_buy": False}

    for col in ["frgn_ntby_qty", "orgn_ntby_qty", "stck_clpr"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "stck_bsop_date" in df.columns:
        df = df.sort_values("stck_bsop_date")
    df = df.tail(window)

    if "stck_clpr" in df.columns and df["stck_clpr"].notna().any():
        df["frgn_value"] = df["frgn_ntby_qty"].fillna(0) * df["stck_clpr"].fillna(last_close)
        df["orgn_value"] = df["orgn_ntby_qty"].fillna(0) * df["stck_clpr"].fillna(last_close)
    else:
        df["frgn_value"] = df["frgn_ntby_qty"].fillna(0) * last_close
        df["orgn_value"] = df["orgn_ntby_qty"].fillna(0) * last_close

    foreign_value = df["frgn_value"].sum()
    orgn_value = df["orgn_value"].sum()
    both_buy = (foreign_value > 0) and (orgn_value > 0)
    return {
        "foreign_value": foreign_value,
        "orgn_value": orgn_value,
        "both_buy": bool(both_buy),
    }


def percentile_score(values: pd.Series, max_score: int) -> pd.Series:
    pos = values.clip(lower=0)
    if pos.max() == 0:
        return pd.Series([0] * len(values), index=values.index)
    return (pos / pos.max() * max_score).round(1)


def screen(client: KISClient, mode: str, window: int, top: int,
           min_foreign: float, min_orgn: float, sort: str) -> pd.DataFrame:
    universe = fetch_universe(client, top)
    if universe.empty:
        return universe

    if mode == "etf":
        universe = universe[universe["name"].apply(is_etf)].reset_index(drop=True)
    elif mode == "stock":
        universe = universe[~universe["name"].apply(is_etf)].reset_index(drop=True)

    rows = []
    for _, row in universe.iterrows():
        code = row["code"]
        name = row["name"]

        supply = calc_supply_metrics(client, code)
        time.sleep(0.12)
        if not supply:
            continue

        flow = calc_investor_flow(client, code, window, supply["last_close"])
        time.sleep(0.12)

        foreign_eok = flow["foreign_value"] / 1e8
        orgn_eok = flow["orgn_value"] / 1e8

        if foreign_eok < min_foreign:
            continue
        if orgn_eok < min_orgn:
            continue

        rows.append({
            "code": code,
            "name": name,
            "price": supply["last_close"],
            "ret_5": supply["ret_5"],
            "ret_20": supply["ret_20"],
            "trade_value_eok": row.get("trade_value", 0) / 1e8 if pd.notna(row.get("trade_value", 0)) else 0,
            "ma5_eok": supply["ma5"] / 1e8,
            "r_5_20": supply["r_5_20"],
            "r_5_60": supply["r_5_60"],
            "grade": supply["grade"],
            "foreign_eok": foreign_eok,
            "orgn_eok": orgn_eok,
            "combined_eok": foreign_eok + orgn_eok,
            "both_buy": flow["both_buy"],
            "is_etf": is_etf(name),
        })

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)

    df["score_grade"] = df["grade"].map(GRADE_SCORE).fillna(0)
    df["score_foreign"] = percentile_score(df["foreign_eok"], 25)
    df["score_orgn"] = percentile_score(df["orgn_eok"], 25)
    df["score_both"] = df["both_buy"].apply(lambda x: 10 if x else 0)
    df["score_mom"] = ((df["ret_5"] > 0).astype(int) * 5
                      + (df["ret_20"] > 0).astype(int) * 5)
    df["mf_score"] = (df["score_grade"] + df["score_foreign"]
                     + df["score_orgn"] + df["score_both"] + df["score_mom"]).round(1)

    # 정렬 키 — 모두 부호 있는 값의 내림차순.
    # combined: 자금 유입 Top (음수 종목은 하위로 밀림 — 매도 종목 강조엔 부적합).
    sort_keys = {
        "combined": "combined_eok",
        "foreign": "foreign_eok",
        "orgn": "orgn_eok",
        "value": "trade_value_eok",
        "score": "mf_score",
    }
    sort_col = sort_keys.get(sort, "mf_score")
    df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
    return df


def recommend(score: float) -> str:
    if score >= 80:
        return "★★★ 강력매집"
    if score >= 60:
        return "★★ 매집진행"
    if score >= 40:
        return "★ 부분유입"
    return "무신호"


def render_table(df: pd.DataFrame, show: int) -> str:
    if df.empty:
        return "(스크리닝 결과 없음)"
    df = df.head(show).copy()
    df["추천"] = df["mf_score"].apply(recommend)
    df["타입"] = df["is_etf"].apply(lambda x: "ETF" if x else "주식")

    cols = [
        ("code", "코드"),
        ("name", "종목명"),
        ("타입", "타입"),
        ("price", "종가"),
        ("ret_5", "5일%"),
        ("trade_value_eok", "거래대금(억)"),
        ("grade", "등급"),
        ("foreign_eok", "외인(억)"),
        ("orgn_eok", "기관(억)"),
        ("combined_eok", "합산(억)"),
        ("mf_score", "MF점수"),
        ("추천", "추천"),
    ]
    out = df[[c for c, _ in cols]].copy()
    out.columns = [k for _, k in cols]

    fmt = {
        "종가": "{:,.0f}",
        "5일%": "{:+.2f}",
        "거래대금(억)": "{:,.0f}",
        "외인(억)": "{:+,.1f}",
        "기관(억)": "{:+,.1f}",
        "합산(억)": "{:+,.1f}",
        "MF점수": "{:.1f}",
    }
    for c, f in fmt.items():
        if c in out.columns:
            out[c] = out[c].apply(lambda v, f=f: f.format(v) if pd.notna(v) else "-")
    return out.to_string(index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["etf", "stock", "all"], default="all")
    ap.add_argument("--window", type=int, choices=[1, 5, 20], default=5)
    ap.add_argument("--top", type=int, default=30, help="후보 풀 (max 60)")
    ap.add_argument("--show", type=int, default=15, help="표시 종목 수")
    ap.add_argument("--min-foreign", type=float, default=0.0, help="외인 최소 순매수 (억)")
    ap.add_argument("--min-orgn", type=float, default=0.0, help="기관 최소 순매수 (억)")
    ap.add_argument("--sort", choices=["combined", "foreign", "orgn", "value", "score"],
                    default="score")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    client = KISClient(svr="prod")
    print(f"[money-flow] mode={args.mode} window={args.window}일 top={args.top}", file=sys.stderr)

    df = screen(
        client,
        mode=args.mode,
        window=args.window,
        top=min(args.top, 60),
        min_foreign=args.min_foreign,
        min_orgn=args.min_orgn,
        sort=args.sort,
    )

    if args.json:
        out = df.head(args.show).to_dict(orient="records")
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return

    title = f"=== Money Flow Screener — {args.mode.upper()} / {args.window}일 누적 ==="
    print(title)
    print(render_table(df, args.show))
    print()
    print("[Score] 80+ ★★★ 강력매집 | 60+ ★★ 매집진행 | 40+ ★ 부분유입 | <40 무신호")
    print("[등급] 거래대금 5MA/20MA, 5MA/60MA — S/A/B/C/D")


if __name__ == "__main__":
    main()
