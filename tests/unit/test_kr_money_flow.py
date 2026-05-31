"""market_flow/fetchers/kr_money_flow.py 단위 테스트 (I1 양방향 스크리너).

screen() 을 mock 해 외부 KIS 호출 없이 순매수 Top / 순매도 Bottom 선택 로직만 검증한다.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from market_flow.fetchers import kr_money_flow


def _row(code, name, is_etf, combined):
    return {
        "code": code,
        "name": name,
        "is_etf": is_etf,
        "foreign_eok": combined / 2,
        "orgn_eok": combined / 2,
        "combined_eok": combined,
        "grade": "B",
        "both_buy": combined > 0,
        "price": 1000,
        "ret_5": 0.0,
        "trade_value_eok": 100,
    }


def _pool():
    # screen() 출력 형태 — combined 내림차순 정렬된 풀
    # ETF/개별주 각각 양수 2 + 음수 2 — 정확한 집합·순서·disjoint 를 검증할 수 있게.
    rows = [
        _row("E1", "ETF+500", True, 500),
        _row("E2", "ETF+150", True, 150),
        _row("S1", "S+300", False, 300),
        _row("S2", "S+50", False, 50),
        _row("E3", "ETF-300", True, -300),
        _row("E4", "ETF-900", True, -900),
        _row("S3", "S-200", False, -200),
        _row("S4", "S-700", False, -700),
    ]
    return (
        pd.DataFrame(rows)
        .sort_values("combined_eok", ascending=False)
        .reset_index(drop=True)
    )


def test_bidirectional_buy_and_sell_selection():
    with patch("market_flow.fetchers.kr_money_flow.screen", return_value=_pool()):
        out = kr_money_flow.fetch_money_flow_watch(
            client=object(), etf_show=5, stock_show=5
        )
    buy_etf = [e["code"] for e in out["etfs"]]
    buy_stk = [s["code"] for s in out["stocks"]]
    sell_etf = [e["code"] for e in out["etfs_sell"]]
    sell_stk = [s["code"] for s in out["stocks_sell"]]
    # 순매수: 양수만, 내림차순
    assert buy_etf == ["E1", "E2"]
    assert buy_stk == ["S1", "S2"]
    # 순매도: 음수만, 가장 음수부터
    assert sell_etf == ["E4", "E3"]  # -900, -300
    assert sell_stk == ["S4", "S3"]  # -700, -200
    # disjoint — 한 종목이 매수·매도 양쪽에 들어가지 않는다
    assert set(buy_etf) & set(sell_etf) == set()
    assert set(buy_stk) & set(sell_stk) == set()


def test_few_positives_does_not_leak_negatives_into_buy():
    # 양수 ETF 1개뿐이고 etf_show=5 여도 buy 에 음수가 섞이지 않는다(disjoint 회귀가드)
    rows = [
        _row("E1", "ETF+100", True, 100),
        _row("E2", "ETF-100", True, -100),
        _row("E3", "ETF-900", True, -900),
    ]
    with patch(
        "market_flow.fetchers.kr_money_flow.screen",
        return_value=pd.DataFrame(rows),
    ):
        out = kr_money_flow.fetch_money_flow_watch(client=object(), etf_show=5)
    assert [e["code"] for e in out["etfs"]] == ["E1"]  # 양수만
    assert [e["code"] for e in out["etfs_sell"]] == ["E3", "E2"]  # 가장 음수부터
    assert {c["code"] for c in out["etfs"]} & {
        c["code"] for c in out["etfs_sell"]
    } == set()


def test_sell_excludes_zero_and_positive():
    # 음수 combined 가 없으면 순매도 블록은 비어야 한다(0/양수는 순매도 아님)
    rows = [_row("E1", "ETF+500", True, 500), _row("E2", "ETF0", True, 0)]
    with patch(
        "market_flow.fetchers.kr_money_flow.screen",
        return_value=pd.DataFrame(rows),
    ):
        out = kr_money_flow.fetch_money_flow_watch(client=object())
    assert out["etfs_sell"] == []
    assert out["stocks_sell"] == []


def test_empty_pool_all_blocks_empty():
    with patch(
        "market_flow.fetchers.kr_money_flow.screen",
        return_value=pd.DataFrame(),
    ):
        out = kr_money_flow.fetch_money_flow_watch(client=object())
    assert out == {"etfs": [], "stocks": [], "etfs_sell": [], "stocks_sell": []}
