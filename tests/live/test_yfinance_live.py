"""SPEC-MF-TEST-001: yfinance 실 네트워크 스모크 (live 마커).

REQ-MF-TEST-009. 기본 ``pytest`` 실행에서는 conftest.py 의 자동 deselect
훅으로 skip 된다. 실 호출은 ``pytest -m live`` 로만 트리거.

값 검증은 하지 않음 — Yahoo Finance 데이터는 변동/지연이 있으므로
카테고리 키 구조와 ^GSPC 의 None 여부만 검증.
"""
from __future__ import annotations

import pytest

from fetchers import us_market  # noqa: E402


@pytest.mark.live
def test_fetch_us_close_smoke():
    """실제 yfinance 호출 → 6 카테고리 키 dict 반환."""
    result = us_market.fetch_us_close()
    assert set(result.keys()) == {
        "indices", "volatility", "risk_onoff", "macro", "sectors", "watch",
    }
    # ^GSPC 는 가장 안정적인 ticker — None 이 아니어야 함
    assert result["indices"]["^GSPC"] is not None
    # ^GSPC 출력 스키마 회귀 차단
    assert set(result["indices"]["^GSPC"].keys()) == {
        "label", "close", "pct", "vol_ratio", "date",
    }
