"""market_flow/fetchers/kr_foreign_inst.py 단위 테스트 (I4 가집계).

KIS foreign_institution_total 을 mock 해 외부 호출 없이 금액 환산·순매수/순매도·
스키마 미인식 graceful degrade 만 검증한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from market_flow.fetchers import kr_foreign_inst as FI


def _tally_df(codes, frgn, orgn):
    return pd.DataFrame(
        {
            "mksc_shrn_iscd": list(codes),
            "hts_kor_isnm": [f"종목{c}" for c in codes],
            "frgn_ntby_tr_pbmn": list(frgn),  # 외국인 순매수 거래대금(원)
            "orgn_ntby_tr_pbmn": list(orgn),  # 기관계 순매수 거래대금(원)
        }
    )


def _client(buy_df, sell_df):
    c = MagicMock()

    def _fit(div="1", sort="0", **k):
        return buy_df if sort == "0" else sell_df

    c.foreign_institution_total.side_effect = _fit
    return c


def test_to_eok_converts_won_and_guards_garbage():
    assert FI._to_eok("70,000,000,000") == 700.0  # 700억
    assert FI._to_eok(30_000_000_000) == 300.0
    assert FI._to_eok("N/A") is None
    assert FI._to_eok(None) is None


def test_tally_buy_sell_amounts_and_combined():
    c = _client(
        _tally_df(["005930"], [70_000_000_000], [30_000_000_000]),  # +700 / +300
        _tally_df(["000660"], [-50_000_000_000], [-10_000_000_000]),  # -500 / -100
    )
    out = FI.fetch_foreign_inst_tally(c, show=5)
    buy = out["buy"][0]
    assert buy["code"] == "005930"
    assert buy["foreign_eok"] == 700.0
    assert buy["orgn_eok"] == 300.0
    assert buy["combined_eok"] == 1000.0
    sell = out["sell"][0]
    assert sell["foreign_eok"] == -500.0  # 순매도는 음수 그대로
    assert sell["combined_eok"] == -600.0


def test_tally_schema_miss_returns_empty():
    c = MagicMock()
    c.foreign_institution_total.return_value = pd.DataFrame({"unknown": [1, 2]})
    assert FI.fetch_foreign_inst_tally(c) == {"buy": [], "sell": []}


def test_tally_empty_df_returns_empty():
    c = MagicMock()
    c.foreign_institution_total.return_value = pd.DataFrame()
    assert FI.fetch_foreign_inst_tally(c) == {"buy": [], "sell": []}


def test_tally_filters_bogus_code():
    df = _tally_df(["", "005930"], [100_000_000, 200_000_000], [0, 0])
    c = _client(df, pd.DataFrame())
    codes = [r["code"] for r in FI.fetch_foreign_inst_tally(c)["buy"]]
    assert "" not in codes and "005930" in codes


def test_to_eok_rejects_nan_inf():
    assert FI._to_eok(float("nan")) is None
    assert FI._to_eok(float("inf")) is None


def test_combined_none_when_component_missing():
    # 한 컬럼만 결측(NaN)이면 combined 는 None(가짜 0 아님)
    df = _tally_df(["005930"], [float("nan")], [30_000_000_000])
    item = FI.fetch_foreign_inst_tally(_client(df, pd.DataFrame()))["buy"][0]
    assert item["foreign_eok"] is None
    assert item["orgn_eok"] == 300.0
    assert item["combined_eok"] is None


def test_tally_filters_bogus_codes_before_head():
    # ""/"<NA>" 가짜 코드는 head 전에 걸러져 top 슬롯을 먹지 않는다
    df = _tally_df(["", "<NA>", "005930", "000660"], [1e8] * 4, [0] * 4)
    codes = [
        r["code"]
        for r in FI.fetch_foreign_inst_tally(_client(df, pd.DataFrame()), show=2)["buy"]
    ]
    assert codes == ["005930", "000660"]
