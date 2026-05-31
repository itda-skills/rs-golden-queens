"""한국장 동적 워치 — money-flow 스크리너 래퍼.

ETF Top N + 개별주 Top N을 각각 별도로 뽑아 반환.
"""

from __future__ import annotations

from kis import KISClient
from market_flow.screeners.money_flow import screen


def fetch_money_flow_watch(
    client: KISClient | None = None,
    window: int = 1,
    top: int = 40,
    etf_show: int = 5,
    stock_show: int = 5,
) -> dict:
    """오늘의 수급 Top — ETF·개별주 분리.

    Args:
        client: KISClient (없으면 신규 생성)
        window: 1=당일, 5=5일 누적, 20=20일 누적
        top: 후보 풀 (volume_rank 상위 N, 최대 60)
        etf_show: ETF 표시 개수
        stock_show: 개별주 표시 개수

    Returns:
        {"etfs": [...], "stocks": [...]} — 외인+기관 합산(부호 있는) 내림차순.
        즉 "오늘 자금이 가장 많이 유입된 Top N" 목록.
        합산이 음수인 종목도 결과 풀에는 들어오지만(min_*=-1e10),
        head() 가 양수/0 근처 종목을 먼저 잡아내므로 "큰 순매도 종목" 은
        이 정렬에서 상위에 오지 않음. 매도 시그널이 필요하면 sort 정책 변경 필요.
    """
    if client is None:
        client = KISClient(svr="prod")

    # 필터 해제 (-1e10) — 외인 매도장에서도 기관 단독 매집 종목이 결과 풀에
    # 살아남아야 head(5) 자리가 0 또는 양수로 채워지므로 (HANDOFF 3-3).
    # sort=combined: 부호 있는 합산 내림차순 → 자금 유입 Top.
    df = screen(
        client,
        mode="all",
        window=window,
        top=min(top, 60),
        min_foreign=-1e10,
        min_orgn=-1e10,
        sort="combined",
    )
    if df.empty:
        return {"etfs": [], "stocks": []}

    etfs_df = df[df["is_etf"]].copy()
    stocks_df = df[~df["is_etf"]].copy()

    etfs = etfs_df.head(etf_show).to_dict(orient="records")
    stocks = stocks_df.head(stock_show).to_dict(orient="records")
    return {"etfs": etfs, "stocks": stocks}


if __name__ == "__main__":
    import json

    out = fetch_money_flow_watch(window=1, etf_show=5, stock_show=5)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
