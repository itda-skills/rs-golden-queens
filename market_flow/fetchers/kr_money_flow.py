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
        {"etfs", "stocks", "etfs_sell", "stocks_sell"} — 모두 외인+기관 합산 기준.
        - etfs/stocks: 합산 내림차순 Top("오늘 자금이 가장 많이 유입된" 순매수 상위).
        - etfs_sell/stocks_sell: 합산이 음수(실제 순매도)인 종목 중 가장 큰 순매도
          상위(I1). head/내림차순만으로는 절대 선택되지 않던 '외인·기관 대량 순매도'를
          별도 블록으로 노출한다(순매수 편향 보완). 금액 사실값만, 시그널 단어 없이.
    """
    if client is None:
        client = KISClient(svr="prod")

    # 필터 해제 (-1e10) — 음수(순매도) 종목도 풀에 살아남아야 순매도 블록(I1)의
    # 후보가 되고, 외인 매도장에서도 기관 단독 매집 종목이 순매수 블록을 채운다.
    # sort=combined: 부호 있는 합산 내림차순.
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
        return {"etfs": [], "stocks": [], "etfs_sell": [], "stocks_sell": []}

    etfs_df = df[df["is_etf"]].copy()
    stocks_df = df[~df["is_etf"]].copy()

    # 순매수 Top: 합산이 양수(실제 순매수)인 종목만 내림차순 상단.
    # 양수 필터로 순매도 블록과 disjoint — 양수가 N개 미만이어도 음수가 섞이지 않는다.
    etfs = etfs_df[etfs_df["combined_eok"] > 0].head(etf_show).to_dict(orient="records")
    stocks = (
        stocks_df[stocks_df["combined_eok"] > 0]
        .head(stock_show)
        .to_dict(orient="records")
    )
    # 순매도 Top: 합산이 음수(실제 순매도)인 종목 중 가장 큰 순매도부터(I1).
    # 내림차순 head 만으로는 절대 잡히지 않던 외인·기관 대량 순매도를 별도 블록으로.
    etfs_sell = (
        etfs_df[etfs_df["combined_eok"] < 0]
        .nsmallest(etf_show, "combined_eok")
        .to_dict(orient="records")
    )
    stocks_sell = (
        stocks_df[stocks_df["combined_eok"] < 0]
        .nsmallest(stock_show, "combined_eok")
        .to_dict(orient="records")
    )
    return {
        "etfs": etfs,
        "stocks": stocks,
        "etfs_sell": etfs_sell,
        "stocks_sell": stocks_sell,
    }


if __name__ == "__main__":
    import json

    out = fetch_money_flow_watch(window=1, etf_show=5, stock_show=5)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
