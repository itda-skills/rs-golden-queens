"""SPEC-MF-TEST-001: 네이버 실 네트워크 스모크 (live 마커).

REQ-MF-TEST-009. 기본 ``pytest`` 실행에서는 conftest.py 의 자동 deselect
훅으로 skip 된다. 실 호출은 ``pytest -m live`` 로만 트리거.

값 검증은 하지 않음 — 외부 데이터는 매일 변동하므로 스키마와 키 존재 여부만 확인.
"""
from __future__ import annotations

import pytest

from fetchers import naver_kr  # noqa: E402


@pytest.mark.live
def test_fetch_daily_summary_kospi_smoke():
    """실제 네이버 모바일 API 호출 → dict 반환 + bizdate 키 존재."""
    result = naver_kr.fetch_daily_summary("KOSPI")
    assert isinstance(result, dict)
    assert "bizdate" in result
    # 7-key 스키마 회귀 차단
    assert set(result.keys()) == {
        "bizdate", "personal", "foreign", "institutional",
        "program_arb", "program_nonarb", "program_total",
    }


@pytest.mark.live
def test_fetch_kospi_daily_smoke():
    """실제 네이버 데스크탑 페이지 → 10거래일 row 반환."""
    # bizdate 는 현재 시각 기준
    from datetime import datetime
    bizdate = datetime.now().strftime("%Y%m%d")
    rows = naver_kr.fetch_kospi_daily(bizdate)
    assert isinstance(rows, list)
    # 데스크탑 페이지가 최대 10거래일을 반환하지만, 평일·휴장에 따라 변동.
    # 적어도 1개 이상이고 각 행에 date 키가 있는지만 검증.
    assert len(rows) >= 1
    for row in rows:
        assert "date" in row
        assert isinstance(row["personal"], int)
