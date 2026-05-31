"""미국장 마감 요약 — yfinance"""

import sys
from datetime import datetime, timedelta

import requests
import yfinance as yf

from market_flow._retry import retry_call
from market_flow.fetchers.fred import fetch_high_yield_oas


class _EmptyDownload(RuntimeError):
    """yf.download 가 빈 프레임을 반환 — 일시 장애로 보고 재시도하기 위한 신호."""


def _yf_retryable(exc: Exception) -> bool:
    """yfinance 다운로드의 '일시 장애' 판정(#10 I8).

    빈 프레임(_EmptyDownload)과 네트워크/타임아웃 계열만 재시도한다. yfinance 는
    내부적으로 requests 를 쓰므로 RequestException 도 포함한다.
    """
    return isinstance(
        exc,
        (
            _EmptyDownload,
            requests.exceptions.RequestException,
            TimeoutError,
            ConnectionError,
        ),
    )


def _download(syms, start, end):
    """yf.download 1회 — 빈 프레임이면 _EmptyDownload 로 재시도를 유도(#10 I8)."""
    df = yf.download(syms, start=start, end=end, progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise _EmptyDownload(syms)
    return df


INDICES = [
    ("^GSPC", "S&P500"),
    ("^IXIC", "나스닥"),
    ("^DJI", "다우"),
    ("^RUT", "러셀2000"),
]
# 변동성 (I7, #10): VIX 기간구조(9일/30일) + 꼬리위험(VVIX/SKEW) + 자산별 변동성.
# ^RVX(러셀)/^VXEEM(신흥국)은 yfinance EMPTY(상폐) — 스모크 확인 후 제외.
VOLATILITY = [
    ("^VIX9D", "VIX 9일"),
    ("^VIX", "VIX 30일"),
    ("^VVIX", "VVIX"),
    ("^SKEW", "SKEW"),
    ("^GVZ", "금변동성"),
    ("^OVX", "유가변동성"),
]
RISK_ONOFF = [("HYG", "고수익채권"), ("IEF", "7-10Y국채")]
MACRO = [
    ("^TNX", "10Y금리"),
    ("^TYX", "30Y금리"),
    ("DX-Y.NYB", "DXY"),
    ("KRW=X", "원달러"),
    ("CL=F", "WTI"),
    ("GC=F", "금"),
]
SECTORS = [
    ("XLK", "기술"),
    ("XLF", "금융"),
    ("XLV", "헬스케어"),
    ("XLY", "임의소비"),
    ("XLC", "통신"),
    ("XLI", "산업"),
    ("XLP", "필수소비"),
    ("XLE", "에너지"),
    ("XLU", "유틸"),
    ("XLB", "소재"),
    ("XLRE", "리츠"),
]
WATCH = [
    ("QQQ", "나스닥100"),
    ("SMH", "반도체"),
    ("NLR", "원자력"),
    ("XLE", "에너지"),
    ("GLD", "금"),
    ("SLV", "은"),
    ("ITA", "방산"),
    ("XOVR", "SpaceX"),
]


def _fetch_yf(tickers, target_date=None):
    """tickers → ticker별 {label, close, pct, vol_ratio, date}

    vol_ratio = 당일 거래량 / 직전 5거래일 평균
    target_date 가 None이면 가장 최근 거래일
    """
    syms = " ".join(t for t, _ in tickers)
    if target_date:
        end = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        start = (
            datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=45)
        ).strftime("%Y-%m-%d")
    else:
        end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")

    try:
        # attempts=2(1회 재시도): 6개 그룹이 독립 degrade 하므로 그룹당 상한을 짧게
        # 둬 flow-us 잡 타임아웃 안에 머물게 한다(#10 I8).
        df = retry_call(
            lambda: _download(syms, start, end),
            attempts=2,
            should_retry=_yf_retryable,
            label=f"yf[{syms}]",
        )
    except Exception as e:  # noqa: BLE001 — 그룹 전체를 결측으로 degrade
        # 재시도 소진. 빈 표·크래시 대신 그룹을 통째 None 으로 두면 daily_us 의
        # section_counts 가 0 으로 잡혀 '일부 섹션 미수집' 경고(E5/I8)가 작동한다.
        print(
            f"warn: fetch_yf 다운로드 실패 [{syms}]: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return {ticker: None for ticker, _ in tickers}
    out = {}
    for ticker, label in tickers:
        try:
            if len(tickers) > 1:
                close = df["Close"][ticker].dropna()
                vol = (
                    df["Volume"][ticker].dropna()
                    if "Volume" in df.columns.get_level_values(0)
                    else None
                )
            else:
                close = df["Close"].dropna()
                vol = df["Volume"].dropna() if "Volume" in df.columns else None
            if len(close) < 2:
                out[ticker] = None
                continue
            today, prev = float(close.iloc[-1]), float(close.iloc[-2])
            pct = (today - prev) / prev * 100
            vol_ratio = None
            if vol is not None and len(vol) >= 6:
                v_today = float(vol.iloc[-1])
                v_avg5 = float(vol.iloc[-6:-1].mean())
                if v_avg5 > 0:
                    vol_ratio = v_today / v_avg5
            out[ticker] = {
                "label": label,
                "close": today,
                "pct": pct,
                "vol_ratio": vol_ratio,
                "date": str(close.index[-1].date()),
            }
        except Exception as e:
            print(f"warn: fetch_yf {ticker}: {type(e).__name__}: {e}", file=sys.stderr)
            out[ticker] = None
    return out


def fetch_us_close(target_date=None):
    """미국장 마감 풀세트"""
    data = {
        "indices": _fetch_yf(INDICES, target_date),
        "volatility": _fetch_yf(VOLATILITY, target_date),
        "risk_onoff": _fetch_yf(RISK_ONOFF, target_date),
        "macro": _fetch_yf(MACRO, target_date),
        "sectors": _fetch_yf(SECTORS, target_date),
        "watch": _fetch_yf(WATCH, target_date),
    }
    # 하이일드 OAS(FRED, #10 I6): 최신 영업일 신용 스프레드 사실값. 과거일 재발송
    # (target 지정)에는 FRED 최신값이 그 날짜와 어긋나 stale 혼란이라 붙이지 않는다.
    data["high_yield_oas"] = fetch_high_yield_oas() if target_date is None else None
    return data


def fetch_watch_history(days=5):
    """워치 ETF 최근 N거래일 등락 (주간 리포트용)"""
    return _fetch_yf(
        WATCH
    )  # 단순화 — 최근 1일치만 우선. 주간은 weekly.py에서 N일 합산.


if __name__ == "__main__":
    import json

    target = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(fetch_us_close(target), ensure_ascii=False, indent=2, default=str))
