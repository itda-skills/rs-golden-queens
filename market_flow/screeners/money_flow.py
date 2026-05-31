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
    "KODEX",
    "TIGER",
    "SOL",
    "ACE",
    "HANARO",
    "KOSEF",
    "KBSTAR",
    "ARIRANG",
    "KOACT",
    "KoAct",
    "RISE",
    "PLUS",
    "TIMEFOLIO",
    "마이다스",
    "히어로즈",
    "WOORI",
    "WON",
    "마이티",
    "FOCUS",
    "VITA",
    "ITF",
    "BNK",
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


# 랭킹 API 마다 코드 컬럼명이 다르다(거래량=mksc_shrn_iscd, 등락률=stck_shrn_iscd 등).
# 공통 스키마(code,name,price,chg_pct,volume,trade_value)로 정규화한다.
_RANK_CODE_COLS = ("mksc_shrn_iscd", "stck_shrn_iscd", "stck_iscd")
_RANK_NUM_COLS = {
    "price": "stck_prpr",
    "chg_pct": "prdy_ctrt",
    "volume": "acml_vol",
    "trade_value": "acml_tr_pbmn",
}


_BOGUS_CODES = {"", "nan", "none", "<na>", "null"}


def _normalize_rank_df(df: pd.DataFrame) -> pd.DataFrame:
    """랭킹 응답을 공통 스키마로. 코드 컬럼을 못 찾으면 빈 DF(해당 축 무시)."""
    if df is None or getattr(df, "empty", True):
        return pd.DataFrame()
    code_col = next((c for c in _RANK_CODE_COLS if c in df.columns), None)
    if code_col is None:
        return pd.DataFrame()
    d = df[df[code_col].notna()].reset_index(drop=True)  # None/NaN 코드 먼저 제거
    out = pd.DataFrame()
    out["code"] = d[code_col].astype(str).str.strip()
    out["name"] = d["hts_kor_isnm"].astype(str) if "hts_kor_isnm" in d.columns else ""
    for std, raw in _RANK_NUM_COLS.items():
        out[std] = pd.to_numeric(d[raw], errors="coerce") if raw in d.columns else pd.NA
    out = out[
        ~out["code"].str.lower().isin(_BOGUS_CODES)
    ]  # 'None'/'nan' 등 가짜 코드 제거
    return out.reset_index(drop=True)


def _safe_rank(label: str, fn) -> pd.DataFrame:
    """랭킹 호출 1건 보호 — 한 축 실패가 후보 풀 전체를 막지 않는다(침묵 종료 금지).

    응답은 있는데 코드 컬럼/값을 못 알아본 경우(스키마 변경 의심)도 경고로 드러낸다.
    """
    try:
        raw = fn()
    except Exception as e:  # noqa: BLE001 — 발송 보호: 한 축 실패 허용
        print(f"⚠️  {label} 순위 조회 실패: {e}", file=sys.stderr)
        return pd.DataFrame()
    norm = _normalize_rank_df(raw)
    if norm.empty and raw is not None and not getattr(raw, "empty", True):
        print(
            f"⚠️  {label} 순위 응답에서 유효 코드 인식 실패 (KIS 스키마 변경?)",
            file=sys.stderr,
        )
    return norm


def _interleave_dedupe(frames: list[pd.DataFrame], top: int) -> pd.DataFrame:
    """여러 축의 상위를 round-robin 으로 뽑아 code 중복 제거, top 개까지.

    한 축(거래량)이 후보를 독식하지 않도록 축을 번갈아 채우되, 저장 레코드는 축
    우선순위(frames 순서: 거래량→거래대금→상승→하락)의 정규 레코드를 쓴다. 그래야
    같은 종목이 등락률 축에서 먼저 선택돼도 거래량 행의 풍부한 필드(거래대금 등)를
    잃지 않는다. 종목당 후속 호출 비용은 top 으로 고정(풀만 다양화)된다.
    """
    record_lists = [f.to_dict("records") for f in frames if not f.empty]
    if not record_lists:
        return pd.DataFrame()
    # 코드별 정규 레코드 — frames 우선순위로 setdefault(앞 축이 이김)
    canonical: dict[str, dict] = {}
    for rl in record_lists:
        for rec in rl:
            canonical.setdefault(rec["code"], rec)
    picked: list[dict] = []
    seen: set[str] = set()
    i = 0
    while len(picked) < top and any(i < len(rl) for rl in record_lists):
        for rl in record_lists:
            if i < len(rl):
                code = rl[i]["code"]
                if code and code not in seen:
                    seen.add(code)
                    picked.append(canonical[code])
                    if len(picked) >= top:
                        break
        i += 1
    return pd.DataFrame(picked)


def fetch_universe(client: KISClient, top: int) -> pd.DataFrame:
    """다축 랭킹 합집합으로 후보 풀을 넓힌다(I3).

    단일 거래량 순위(~30행)만으로는 조용한 매집·저회전 대형주·약세 종목을 놓친다.
    거래량·거래대금·등락률(상승/하락) 상위를 round-robin 합집합해 top 개로 캡한다.
    하락률 상위는 I1 순매도 보완에도 기여. code 중복은 거래량 축 우선으로 dedupe.
    추가 비용은 랭킹 호출 2건뿐(종목당 2콜 비용은 top 으로 고정).
    """
    vol = _safe_rank("거래량", client.volume_rank)
    rise = _safe_rank("등락률 상승", lambda: client.fluctuation_rank(sort="0"))
    fall = _safe_rank("등락률 하락", lambda: client.fluctuation_rank(sort="1"))
    # 거래대금 축 — 추가 호출 없이 거래량 응답을 재정렬(저회전 대형주 보강)
    if (
        not vol.empty
        and "trade_value" in vol.columns
        and vol["trade_value"].notna().any()
    ):
        value = vol.sort_values("trade_value", ascending=False).reset_index(drop=True)
    else:
        value = pd.DataFrame()
    return _interleave_dedupe([vol, value, rise, fall], top)


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
        "stck_hgpr": "high",
        "stck_lwpr": "low",
        "acml_vol": "volume",
        "acml_tr_pbmn": "trade_value",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    for col in ["close", "high", "low", "volume", "trade_value"]:
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

    # 종가환산 정밀도(I5): 마지막 거래일 대표가격 (고+저+종)/3 — 종가보다 체결 평균가에
    # 가깝다. 고/저가 결측 시 종가로 폴백(ohlcv 는 이미 받았으므로 추가 호출 0).
    _last = df.iloc[-1]
    _hi = _last["high"] if "high" in df.columns else None
    _lo = _last["low"] if "low" in df.columns else None
    if pd.notna(_hi) and pd.notna(_lo):
        typical_price = (float(_hi) + float(_lo) + float(last_close)) / 3
    else:
        typical_price = float(last_close)

    return {
        "ma5": ma5,
        "ma20": ma20,
        "r_5_20": r_5_20,
        "r_5_60": r_5_60,
        "grade": grade,
        "last_close": last_close,
        "typical_price": typical_price,
        "ret_5": ret_5,
        "ret_20": ret_20,
        "ohlcv": df,
    }


def calc_investor_flow(client: KISClient, code: str, window: int, price: float) -> dict:
    """외인·기관 윈도우 누적 순매수 (수량 → 금액 환산, 종가환산 추정치).

    inquire_investor 는 순매수 '수량'만 주므로(금액·종가 미반환) 금액은 단가 환산
    추정치다(I5). 환산 단가 price 는 calc_supply_metrics 의 대표가격 (고+저+종)/3 —
    종가보다 체결 평균가에 가깝다.
    """
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=window * 3 + 10)).strftime("%Y%m%d")
    try:
        df = client.inquire_investor(code, start, end)
    except Exception:
        return {"foreign_value": 0.0, "orgn_value": 0.0, "both_buy": False}
    if df.empty:
        return {"foreign_value": 0.0, "orgn_value": 0.0, "both_buy": False}

    for col in ["frgn_ntby_qty", "orgn_ntby_qty"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "stck_bsop_date" in df.columns:
        df = df.sort_values("stck_bsop_date")
    df = df.tail(window)

    # 금액·종가 미반환 → 수량 × 대표가격(price) 으로 환산(I5). 종가 대신 (고+저+종)/3.
    df["frgn_value"] = df["frgn_ntby_qty"].fillna(0) * price
    df["orgn_value"] = df["orgn_ntby_qty"].fillna(0) * price

    foreign_value = df["frgn_value"].sum()
    orgn_value = df["orgn_value"].sum()
    both_buy = (foreign_value > 0) and (orgn_value > 0)
    return {
        "foreign_value": foreign_value,
        "orgn_value": orgn_value,
        "both_buy": bool(both_buy),
    }


def percentile_score(values: pd.Series, max_score: int) -> pd.Series:
    """양수(순매수) 값의 분위수 점수 [0, max_score]. 음수·0(비매수)은 0점.

    이전 구현(value / max * max_score)은 한 종목의 초대형 순매수가 나머지를 0 근처로
    깔아뭉개 변별력을 잃었다(예: [5000,300,250,200,180] → [25,1.5,1.25,1.0,0.9]).
    분위수(rank)는 이상치에 강건해 상대 서열을 보존한다
    ([5000,300,250,200,180] → [25,20,15,10,5]). 음수(순매도)는 매수 점수 0 으로 둔다.
    """
    pos = values.clip(lower=0)
    mask = pos > 0
    out = pd.Series(0.0, index=values.index)
    if mask.any():
        out.loc[mask] = (pos[mask].rank(pct=True) * max_score).round(1)
    return out


def screen(
    client: KISClient,
    mode: str,
    window: int,
    top: int,
    min_foreign: float,
    min_orgn: float,
    sort: str,
) -> pd.DataFrame:
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

        flow = calc_investor_flow(
            client, code, window, supply.get("typical_price", supply["last_close"])
        )
        time.sleep(0.12)

        foreign_eok = flow["foreign_value"] / 1e8
        orgn_eok = flow["orgn_value"] / 1e8

        if foreign_eok < min_foreign:
            continue
        if orgn_eok < min_orgn:
            continue

        rows.append(
            {
                "code": code,
                "name": name,
                "price": supply["last_close"],
                "ret_5": supply["ret_5"],
                "ret_20": supply["ret_20"],
                "trade_value_eok": row.get("trade_value", 0) / 1e8
                if pd.notna(row.get("trade_value", 0))
                else 0,
                "ma5_eok": supply["ma5"] / 1e8,
                "r_5_20": supply["r_5_20"],
                "r_5_60": supply["r_5_60"],
                "grade": supply["grade"],
                "foreign_eok": foreign_eok,
                "orgn_eok": orgn_eok,
                "combined_eok": foreign_eok + orgn_eok,
                "both_buy": flow["both_buy"],
                "is_etf": is_etf(name),
            }
        )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)

    df["score_grade"] = df["grade"].map(GRADE_SCORE).fillna(0)
    df["score_foreign"] = percentile_score(df["foreign_eok"], 25)
    df["score_orgn"] = percentile_score(df["orgn_eok"], 25)
    df["score_both"] = df["both_buy"].apply(lambda x: 10 if x else 0)
    df["score_mom"] = (df["ret_5"] > 0).astype(int) * 5 + (df["ret_20"] > 0).astype(
        int
    ) * 5
    df["mf_score"] = (
        df["score_grade"]
        + df["score_foreign"]
        + df["score_orgn"]
        + df["score_both"]
        + df["score_mom"]
    ).round(1)

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


def flow_strength(score: float) -> str:
    """순매수 자금 유입 강도 구간(사실 표현). 투자 권유·매매 시점 판단이 아니다(#10).

    '강력매집' 같은 매수 권유 톤을 쓰지 않고 자금 유입 강도만 사실로 표기한다.
    """
    if score >= 80:
        return "유입 매우강"
    if score >= 60:
        return "유입 강"
    if score >= 40:
        return "유입 보통"
    return "유입 약/없음"


def render_table(df: pd.DataFrame, show: int) -> str:
    if df.empty:
        return "(스크리닝 결과 없음)"
    df = df.head(show).copy()
    df["유입강도"] = df["mf_score"].apply(flow_strength)
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
        ("유입강도", "유입강도"),
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
    ap.add_argument(
        "--min-foreign", type=float, default=0.0, help="외인 최소 순매수 (억)"
    )
    ap.add_argument("--min-orgn", type=float, default=0.0, help="기관 최소 순매수 (억)")
    ap.add_argument(
        "--sort",
        choices=["combined", "foreign", "orgn", "value", "score"],
        default="score",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    client = KISClient(svr="prod")
    print(
        f"[money-flow] mode={args.mode} window={args.window}일 top={args.top}",
        file=sys.stderr,
    )

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
    print("[Score] 80+ 유입 매우강 | 60+ 유입 강 | 40+ 유입 보통 | <40 유입 약/없음")
    print("[등급] 거래대금 5MA/20MA, 5MA/60MA — S/A/B/C/D")


if __name__ == "__main__":
    main()
