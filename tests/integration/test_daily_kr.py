"""SPEC-MF-TEST-001: daily_kr.main() 통합 스모크.

dry-run 환경에서 fetch_today 모킹으로 main() 호출 시 SystemExit 없이
텔레그램 본문이 stdout 으로 출력되는지 검증.

SPEC-MF-SCHED-001 의 ``tests/test_daily_kr.py`` 는 휴장/거래일 게이트 분기에
집중. 본 파일은 "거래일 정상 흐름 + dry-run 출력 토큰" 검증에 집중.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import daily_kr  # noqa: E402

KST = ZoneInfo("Asia/Seoul")


def _fake_kr_data():
    """fetch_today() 가 반환하는 dict 합성."""
    return {
        "bizdate": "20260525",
        "kospi": {
            "foreign": 12345, "institutional": -6789, "personal": -5556,
            "program_arb": 100, "program_nonarb": 200, "program_total": 300,
        },
        "kosdaq": {
            "foreign": 1000, "institutional": 2000, "personal": -3000,
            "program_arb": 50, "program_nonarb": 60, "program_total": 110,
        },
        "kospi_daily": [
            {"date": "05.25", "personal": -100, "foreign": 50, "institutional": 50,
             "finance": 10, "insurance": 5, "trust": 5, "bank": 5,
             "other_fin": 5, "pension": 10, "other_corp": 10},
            {"date": "05.22", "personal": -200, "foreign": 150, "institutional": 50,
             "finance": 10, "insurance": 5, "trust": 5, "bank": 5,
             "other_fin": 5, "pension": 10, "other_corp": 10},
            {"date": "05.21", "personal": -150, "foreign": 100, "institutional": 50,
             "finance": 10, "insurance": 5, "trust": 5, "bank": 5,
             "other_fin": 5, "pension": 10, "other_corp": 10},
            {"date": "05.20", "personal": 50, "foreign": -100, "institutional": 50,
             "finance": 10, "insurance": 5, "trust": 5, "bank": 5,
             "other_fin": 5, "pension": 10, "other_corp": 10},
            {"date": "05.19", "personal": -50, "foreign": 80, "institutional": -30,
             "finance": 10, "insurance": 5, "trust": 5, "bank": 5,
             "other_fin": 5, "pension": 10, "other_corp": 10},
        ],
        "kospi_intraday": [],
    }


def test_daily_kr_main_dry_run_outputs_report(monkeypatch, capsys):
    """거래일 + dry-run → SystemExit 없이 stdout 에 한국장 본문 토큰 출력."""
    # 2026-05-25 월요일 정상 거래일 가정
    now = datetime(2026, 5, 25, 18, 10, tzinfo=KST)
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    with patch("daily_kr.fetch_today", return_value=_fake_kr_data()) as mock_fetch, \
         patch("telegram_push.urllib.request.urlopen") as mock_urlopen, \
         patch("daily_kr.is_kr_trading_day", return_value=True):
        # SystemExit 미발생 확인
        daily_kr.main(now=now)

    # 실제 텔레그램 호출 0회 (dry-run)
    mock_urlopen.assert_not_called()
    # fetch_today 정확히 1회 호출
    mock_fetch.assert_called_once()

    out = capsys.readouterr().out
    # 텔레그램 본문 구조 토큰
    assert "📊" in out
    assert "코스피" in out
    assert "마감 매매동향" in out
    # main() 의 완료 메시지
    assert "✅ 한국장 푸시" in out


def test_daily_kr_main_uses_argv_bizdate(monkeypatch, capsys):
    """argv[0] 의 bizdate 가 fetch_today 에 그대로 전달된다."""
    now = datetime(2026, 5, 25, 18, 10, tzinfo=KST)
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    with patch("daily_kr.fetch_today", return_value=_fake_kr_data()) as mock_fetch, \
         patch("telegram_push.urllib.request.urlopen"), \
         patch("daily_kr.is_kr_trading_day", return_value=True):
        daily_kr.main(argv=["20260520"], now=now)
    mock_fetch.assert_called_once_with("20260520")
