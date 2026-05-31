"""market_flow/screeners/money_flow.py 단위 테스트.

I2: percentile_score 가 이상치에 강건한 분위수 점수인지 검증한다(외부 호출 없음).
I3: fetch_universe 가 다축 랭킹을 합집합·dedupe·cap 하는지(KIS 호출은 mock).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from market_flow.screeners import money_flow as MF
from market_flow.screeners.money_flow import percentile_score


def test_rank_recovers_discrimination_under_outlier():
    # I2 핵심: 초대형 이상치(5000)에도 나머지가 0 근처로 붕괴하지 않고 서열을 유지.
    # 구(舊) value/max*max_score 였다면 [25,1.5,1.25,1.0,0.9] 로 변별 붕괴.
    out = percentile_score(pd.Series([5000, 300, 250, 200, 180]), 25)
    assert list(out) == [25.0, 20.0, 15.0, 10.0, 5.0]


def test_negatives_score_zero():
    out = percentile_score(pd.Series([-100, -5, -1]), 25)
    assert list(out) == [0.0, 0.0, 0.0]


def test_mixed_only_positives_ranked():
    # 양수 {100,200,50} 만 분위수, 음수/0 은 0
    out = percentile_score(pd.Series([100, -50, 200, 0, 50]), 25)
    assert out.iloc[1] == 0.0  # -50
    assert out.iloc[3] == 0.0  # 0
    assert out.iloc[2] == 25.0  # 200 최고
    assert out.iloc[0] == round(25 * 2 / 3, 1)  # 100 중간 = 16.7
    assert out.iloc[4] == round(25 / 3, 1)  # 50 최저 양수 = 8.3


def test_ties_use_average_percentile():
    # 동점은 평균 분위수(method='average') — 최상위 동점이라도 max(25)가 아니라 평균
    out = percentile_score(pd.Series([100, 100, 50]), 25)
    assert out.iloc[0] == out.iloc[1] == round(25 * 2.5 / 3, 1)  # 20.8
    assert out.iloc[2] == round(25 * 1 / 3, 1)  # 8.3


def test_all_equal_positive_same_mid_score():
    # 전원 동점 → 평균 분위수 (1+2+3)/3 / 3 = 0.667 → 16.7 (모두 같은 중간 점수)
    out = percentile_score(pd.Series([100, 100, 100]), 25)
    assert list(out) == [round(25 * 2 / 3, 1)] * 3


def test_all_nonpositive_all_zero():
    out = percentile_score(pd.Series([0, -1, 0]), 25)
    assert list(out) == [0.0, 0.0, 0.0]


def test_single_positive_gets_full():
    out = percentile_score(pd.Series([42]), 25)
    assert list(out) == [25.0]


def test_empty_returns_empty():
    out = percentile_score(pd.Series([], dtype=float), 25)
    assert len(out) == 0


def test_preserves_index():
    out = percentile_score(pd.Series([300, 100], index=["A", "B"]), 25)
    assert out["A"] == 25.0
    assert out["B"] == round(25 / 2, 1)  # rank pct [B=0.5, A=1.0] → 12.5


# ──────────────────────────────────────────────
#  I3: fetch_universe 다축 합집합 (KIS 호출 mock)
# ──────────────────────────────────────────────


def _vol_df(codes):
    # 거래량 순위 스키마 (코드 컬럼 = mksc_shrn_iscd, 거래대금 acml_tr_pbmn 보유)
    return pd.DataFrame(
        {
            "mksc_shrn_iscd": list(codes),
            "hts_kor_isnm": [f"종목{c}" for c in codes],
            "stck_prpr": [1000] * len(codes),
            "prdy_ctrt": [1.0] * len(codes),
            "acml_vol": list(range(len(codes), 0, -1)),
            "acml_tr_pbmn": [100 * (i + 1) for i in range(len(codes))],
        }
    )


def _fluc_df(codes):
    # 등락률 순위 스키마 — 코드 컬럼이 stck_shrn_iscd, 거래대금 컬럼 없음
    return pd.DataFrame(
        {
            "stck_shrn_iscd": list(codes),
            "hts_kor_isnm": [f"등락{c}" for c in codes],
            "stck_prpr": [2000] * len(codes),
            "prdy_ctrt": [5.0] * len(codes),
            "acml_vol": [10] * len(codes),
        }
    )


def _client(vol=(), rise=(), fall=()):
    c = MagicMock()
    c.volume_rank.return_value = _vol_df(vol)

    def _fluc(market="J", sort="0"):
        return _fluc_df(rise if sort == "0" else fall)

    c.fluctuation_rank.side_effect = _fluc
    return c


def test_universe_unions_and_dedupes_axes():
    c = _client(vol=["A", "B", "C"], rise=["C", "D"], fall=["E", "F"])
    uni = MF.fetch_universe(c, top=10)
    codes = list(uni["code"])
    assert set(codes) == {"A", "B", "C", "D", "E", "F"}  # 4축 합집합
    assert codes.count("C") == 1  # 거래량∩등락률 중복은 한 번만
    # 중복 C 는 거래량(거래대금 축은 거래량 재정렬) 우선 → 이름이 '종목C'
    assert uni[uni["code"] == "C"]["name"].iloc[0] == "종목C"


def test_universe_normalizes_fluctuation_code_column():
    # 거래량이 비어도 등락률 축(stck_shrn_iscd)이 code 로 정규화되어 들어온다
    c = _client(vol=[], rise=["X", "Y"], fall=[])
    uni = MF.fetch_universe(c, top=10)
    assert set(uni["code"]) == {"X", "Y"}


def test_universe_survives_one_axis_failure():
    c = MagicMock()
    c.volume_rank.return_value = _vol_df(["A", "B"])
    c.fluctuation_rank.side_effect = RuntimeError("KIS 429")
    uni = MF.fetch_universe(c, top=10)
    assert set(uni["code"]) == {"A", "B"}  # 등락률 실패해도 거래량 축으로 풀 구성


def test_universe_includes_decliners_for_sell_coverage():
    # 하락률 상위가 후보에 포함되어야 I1 순매도 블록 후보가 생긴다
    c = _client(vol=["A"], rise=["R"], fall=["F1", "F2"])
    codes = set(MF.fetch_universe(c, top=10)["code"])
    assert {"F1", "F2"} <= codes


def test_universe_caps_at_top():
    c = _client(vol=["A", "B", "C", "D", "E"], rise=[], fall=[])
    assert len(MF.fetch_universe(c, top=3)) == 3


def test_universe_empty_when_all_unavailable():
    c = MagicMock()
    c.volume_rank.return_value = pd.DataFrame()
    c.fluctuation_rank.return_value = pd.DataFrame()
    assert MF.fetch_universe(c, top=10).empty


def test_normalize_rank_df_without_code_returns_empty():
    df = pd.DataFrame({"hts_kor_isnm": ["X"], "stck_prpr": [1]})
    assert MF._normalize_rank_df(df).empty


def test_normalize_rank_df_rejects_null_and_bogus_codes():
    # None/NaN 가 'None'/'nan' 코드로 위장해 풀에 들어오지 않는다(top 슬롯 낭비 방지)
    df = pd.DataFrame(
        {
            "mksc_shrn_iscd": ["005930", None, float("nan")],
            "hts_kor_isnm": ["삼성전자", "X", "Y"],
        }
    )
    assert list(MF._normalize_rank_df(df)["code"]) == ["005930"]


def test_universe_dup_keeps_canonical_volume_record():
    # C 는 거래량 3위 + 거래대금 최저(value 축 끝)이지만 등락 1위 → round-robin 은 등락
    # 축에서 먼저 뽑지만, 저장 레코드는 거래량(canonical) 행이어야 한다(필드 손실 방지).
    c = MagicMock()
    c.volume_rank.return_value = pd.DataFrame(
        {
            "mksc_shrn_iscd": ["A", "B", "C"],
            "hts_kor_isnm": ["종목A", "종목B", "종목C"],
            "stck_prpr": [1000, 1000, 1000],
            "prdy_ctrt": [1.0, 1.0, 1.0],
            "acml_vol": [3, 2, 1],
            "acml_tr_pbmn": [300, 200, 50],  # C 최저 거래대금 → value 축 끝
        }
    )
    c.fluctuation_rank.side_effect = lambda market="J", sort="0": (
        _fluc_df(["C"]) if sort == "0" else _fluc_df([])
    )
    crow = MF.fetch_universe(c, top=10).set_index("code").loc["C"]
    assert crow["name"] == "종목C"  # 등락 행(등락C) 아닌 거래량 행
    assert crow["trade_value"] == 50  # 거래량 행의 trade_value 보존(등락 행은 NA)


# ──────────────────────────────────────────────
#  I5: 종가환산 정밀도 (대표가격 (고+저+종)/3)
# ──────────────────────────────────────────────


def _ohlcv_df(closes, highs=None, lows=None):
    n = len(closes)
    d = {
        "stck_bsop_date": [f"202605{10 + i:02d}" for i in range(n)],
        "stck_clpr": [str(c) for c in closes],
        "acml_vol": ["1000"] * n,
        "acml_tr_pbmn": ["100000000"] * n,
    }
    if highs is not None:
        d["stck_hgpr"] = [str(h) for h in highs]
    if lows is not None:
        d["stck_lwpr"] = [str(lo) for lo in lows]
    return pd.DataFrame(d)


def test_typical_price_uses_high_low_close_mean():
    # 마지막 거래일 대표가격 = (고+저+종)/3 — 종가와 명확히 다른 값으로 검증
    c = MagicMock()
    c.inquire_daily_price.return_value = _ohlcv_df(
        closes=[100, 100, 100, 100, 100, 120],
        highs=[100, 100, 100, 100, 100, 150],
        lows=[100, 100, 100, 100, 100, 99],
    )
    m = MF.calc_supply_metrics(c, "005930")
    assert m["typical_price"] == (150 + 99 + 120) / 3  # 123.0 ≠ 종가 120
    assert m["last_close"] == 120


def test_typical_price_falls_back_to_close_without_high_low():
    c = MagicMock()
    c.inquire_daily_price.return_value = _ohlcv_df([100, 101, 102, 103, 104, 105])
    m = MF.calc_supply_metrics(c, "005930")
    assert m["typical_price"] == 105.0  # 고/저가 없으면 종가 폴백


def test_typical_price_falls_back_when_low_missing():
    # 고가만 있고 저가 결측이면 종가로 폴백(둘 다 있어야 대표가 계산)
    c = MagicMock()
    c.inquire_daily_price.return_value = _ohlcv_df(
        [100, 101, 102, 103, 104, 120], highs=[130] * 6
    )
    m = MF.calc_supply_metrics(c, "005930")
    assert m["typical_price"] == 120.0


def test_investor_flow_converts_quantity_with_passed_price():
    # 순매수 '수량' × 전달 단가(price) 로 환산 (stck_clpr 미반환 경로)
    c = MagicMock()
    c.inquire_investor.return_value = pd.DataFrame(
        {
            "stck_bsop_date": ["20260525"],
            "frgn_ntby_qty": ["100"],
            "orgn_ntby_qty": ["50"],
        }
    )
    flow = MF.calc_investor_flow(c, "005930", window=1, price=1000.0)
    assert flow["foreign_value"] == 100 * 1000.0
    assert flow["orgn_value"] == 50 * 1000.0
    assert flow["both_buy"] is True


# ──────────────────────────────────────────────
#  is_etf / grade_from_ratios (#10 I-cleanup 회귀 가드 — 외부 호출 없음)
# ──────────────────────────────────────────────


def test_is_etf_recognizes_prefixes():
    assert MF.is_etf("KODEX 200") is True
    assert MF.is_etf("TIGER 미국S&P500") is True
    assert MF.is_etf("ACE 마이크로소프트") is True


def test_is_etf_rejects_non_etf_and_non_str():
    assert MF.is_etf("삼성전자") is False
    assert MF.is_etf(None) is False
    assert MF.is_etf(123) is False


def test_grade_from_ratios_tiers():
    assert MF.grade_from_ratios(1.6, 1.3) == "S"  # 5_20>1.5 & 5_60>1.2
    assert MF.grade_from_ratios(1.3, 1.1) == "A"  # 5_20>1.2 & 5_60>1.0
    assert MF.grade_from_ratios(1.0, 0.5) == "B"  # 0.8<=5_20<=1.2
    assert MF.grade_from_ratios(0.7, 0.5) == "C"  # 0.6<=5_20<0.8
    assert MF.grade_from_ratios(0.5, 0.5) == "D"  # 그 외


def test_grade_strong_short_but_weak_long_falls_to_d():
    # 5_20 강함(1.3>1.2)이나 5_60 약함(0.9<1.0) → A 불충족, B/C 범위도 벗어나 D
    assert MF.grade_from_ratios(1.3, 0.9) == "D"


def test_grade_from_ratios_boundaries():
    # strict(>) / inclusive(<=) 경계 고정
    assert MF.grade_from_ratios(1.5, 1.3) == "A"  # 1.5 는 >1.5 아님 → S 불충족
    assert MF.grade_from_ratios(1.2, 1.1) == "B"  # 1.2 는 >1.2 아님 → A 불충족
    assert MF.grade_from_ratios(0.8, 0.5) == "B"  # 0.8 inclusive → B
    assert MF.grade_from_ratios(0.6, 0.5) == "C"  # 0.6 inclusive → C


def test_flow_strength_neutral_labels():
    # #10 중립화: 권유성('강력매집'/별표) 제거 — 자금 유입 강도 사실 표기만
    assert MF.flow_strength(85) == "유입 매우강"
    assert MF.flow_strength(65) == "유입 강"
    assert MF.flow_strength(45) == "유입 보통"
    assert MF.flow_strength(30) == "유입 약/없음"
    for s in (85, 65, 45, 30):
        label = MF.flow_strength(s)
        assert "매집" not in label and "매수" not in label and "★" not in label
