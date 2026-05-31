"""market_flow/screeners/money_flow.py 단위 테스트.

I2: percentile_score 가 이상치에 강건한 분위수 점수인지 검증한다(외부 호출 없음).
"""

from __future__ import annotations

import pandas as pd

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
