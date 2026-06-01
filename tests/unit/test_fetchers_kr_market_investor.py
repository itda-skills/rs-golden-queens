"""KIS 시장별 투자자 일별 fetcher 단위 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from market_flow.fetchers.kr_market_investor import fetch_kosdaq_daily


def test_fetch_kosdaq_daily_normalizes_kis_rows_to_display_shape():
    client = MagicMock()
    client.inquire_investor_daily_by_market.return_value = pd.DataFrame(
        [
            {
                "stck_bsop_date": "20260529",
                "prsn_ntby_tr_pbmn": "-879299",
                "frgn_ntby_tr_pbmn": "597493",
                "orgn_ntby_tr_pbmn": "300980",
            }
        ]
    )

    out = fetch_kosdaq_daily("20260529", client=client)

    client.inquire_investor_daily_by_market.assert_called_once_with("KSQ", "20260529")
    assert out == [
        {
            "date": "26.05.29",
            "personal": -8793,
            "foreign": 5975,
            "institutional": 3010,
        }
    ]


def test_fetch_kosdaq_daily_limits_to_10_latest_rows():
    client = MagicMock()
    client.inquire_investor_daily_by_market.return_value = pd.DataFrame(
        [
            {
                "stck_bsop_date": f"202605{29 - i:02d}",
                "prsn_ntby_tr_pbmn": "100",
                "frgn_ntby_tr_pbmn": "200",
                "orgn_ntby_tr_pbmn": "300",
            }
            for i in range(12)
        ]
    )

    out = fetch_kosdaq_daily("20260529", client=client)

    assert len(out) == 10
    assert out[0]["date"] == "26.05.29"
    assert out[-1]["date"] == "26.05.20"


def test_fetch_kosdaq_daily_empty_frame_returns_empty_list(capsys):
    client = MagicMock()
    client.inquire_investor_daily_by_market.return_value = pd.DataFrame()

    out = fetch_kosdaq_daily("20260529", client=client)

    assert out == []
    assert "코스닥 일별 0행" in capsys.readouterr().err
