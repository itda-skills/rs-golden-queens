"""SPEC-MF-SCHED-001: daily_kr 분기 테스트.

acceptance.md Section 2 (KR 휴장 인지) + Section 6 (dry-run) 커버.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# daily_kr는 market_flow/ 내부 모듈 — conftest.py에서 sys.path에 추가됨
from market_flow import daily_kr  # noqa: E402

# 정상 KIS 응답 mock — bizdate==today 인 거래일 테스트가 실제 네트워크(KIS DNS/인증)를
# 타지 않도록 결정적으로 차단한다. 섹터 18종 + 수급 1건 → 경고 없는 완전 정상 경로.
_KR_SECTORS_OK = [{"label": f"S{i}", "pct": 0.1, "vol_ratio": None} for i in range(18)]
_KR_MF_OK = {
    "etfs": [
        {
            "code": "1",
            "name": "E",
            "grade": "A",
            "foreign_eok": 1.0,
            "orgn_eok": 1.0,
            "both_buy": True,
        }
    ],
    "stocks": [],
}


def _kr_holiday_msg(now: datetime) -> str:
    weekday = "월화수목금토일"[now.astimezone(KST).weekday()]
    return (
        f"[KR] {now.astimezone(KST).date().isoformat()} ({weekday}) 오늘은 휴장입니다"
    )


def test_kr_holiday_sends_one_liner_childrens_day(monkeypatch):
    # 2025-05-05 어린이날 (월요일)
    now = datetime(2025, 5, 5, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today") as mock_fetch,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        mock_send.assert_called_once_with(_kr_holiday_msg(now))
        mock_fetch.assert_not_called()


def test_kr_holiday_sends_one_liner_liberation_day(monkeypatch):
    # 2025-08-15 광복절 (금요일)
    now = datetime(2025, 8, 15, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today") as mock_fetch,
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        mock_send.assert_called_once_with(_kr_holiday_msg(now))
        mock_fetch.assert_not_called()


def test_kr_trading_day_sends_report(monkeypatch):
    # 2025-05-26 월요일 정상 거래일
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {
        "bizdate": "20250526",
        "kospi": {
            "foreign": 100,
            "institutional": 200,
            "personal": -300,
            "program_arb": 10,
            "program_nonarb": 20,
            "program_total": 30,
        },
        "kosdaq": {
            "foreign": 50,
            "institutional": 60,
            "personal": -110,
            "program_arb": 5,
            "program_nonarb": 10,
            "program_total": 15,
        },
        "kospi_daily": [],
    }
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=fake_data) as mock_fetch,
        patch("kis.KISClient"),
        patch(
            "market_flow.fetchers.kr_etfs.fetch_kr_sectors", return_value=_KR_SECTORS_OK
        ),
        patch(
            "market_flow.fetchers.kr_money_flow.fetch_money_flow_watch",
            return_value=_KR_MF_OK,
        ),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        mock_fetch.assert_called_once()
        # 휴장 메시지가 아닌 정상 보고서가 발송되어야 함
        assert mock_send.call_count == 1
        sent_text = mock_send.call_args.args[0]
        assert "오늘은 휴장입니다" not in sent_text
        assert "코스피" in sent_text or "마감" in sent_text


def test_kr_holiday_dry_run_via_env(monkeypatch, capsys):
    # 휴장 + MARKET_FLOW_DRY_RUN=1 → telegram_push.send는 실제로 호출되지만
    # 내부에서 stdout 분기. 본 테스트는 telegram_push.send를 mock하지 않고
    # urllib.request.urlopen을 mock하여 실제 텔레그램 API 미접촉을 검증한다.
    now = datetime(2025, 5, 5, 18, 10, tzinfo=KST)
    monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
    with (
        patch("market_flow.telegram_push.urllib.request.urlopen") as mock_urlopen,
        patch("market_flow.daily_kr.fetch_today") as mock_fetch,
    ):
        daily_kr.main(now=now)
        mock_urlopen.assert_not_called()
        mock_fetch.assert_not_called()
        captured = capsys.readouterr()
        assert _kr_holiday_msg(now) in captured.out


def test_kr_preserves_positional_date_argv(monkeypatch):
    """argv 위치 인자(YYYYMMDD)가 기존 동작을 유지해야 한다."""
    # 인자로 받은 날짜는 fetch_today에 전달되지만 휴장 판정은 'now'에 의존.
    # 위치 인자가 있을 때도 main()이 정상 작동하는지 확인.
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    fake_data = {
        "bizdate": "20250526",
        "kospi": {
            "foreign": 0,
            "institutional": 0,
            "personal": 0,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
        },
        "kosdaq": {
            "foreign": 0,
            "institutional": 0,
            "personal": 0,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
        },
        "kospi_daily": [],
    }
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=fake_data) as mock_fetch,
        patch("kis.KISClient"),
        patch(
            "market_flow.fetchers.kr_etfs.fetch_kr_sectors", return_value=_KR_SECTORS_OK
        ),
        patch(
            "market_flow.fetchers.kr_money_flow.fetch_money_flow_watch",
            return_value=_KR_MF_OK,
        ),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(argv=["20250526"], now=now)
        # fetch_today가 위치 인자 "20250526"으로 호출되어야 한다
        mock_fetch.assert_called_once_with("20250526")


# ──────────────────────────────────────────────
#  KIS 부분실패 노출 (#10 P0-a)
# ──────────────────────────────────────────────

_KR_FAKE = {
    "bizdate": "20250526",
    "kospi": {
        "foreign": 100,
        "institutional": 200,
        "personal": -300,
        "program_arb": 10,
        "program_nonarb": 20,
        "program_total": 30,
    },
    "kosdaq": {
        "foreign": 50,
        "institutional": 60,
        "personal": -110,
        "program_arb": 5,
        "program_nonarb": 10,
        "program_total": 15,
    },
    "kospi_daily": [],
}


def test_kr_kis_partial_failure_independent(monkeypatch):
    """E2/I8: 섹터 실패 + 수급 성공 → 섹터만 경고, 수급은 살린다(독립 처리)."""
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)  # bizdate == today → KIS 시도
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=dict(_KR_FAKE)),
        patch("kis.KISClient"),
        patch(
            "market_flow.fetchers.kr_etfs.fetch_kr_sectors",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "market_flow.fetchers.kr_money_flow.fetch_money_flow_watch",
            return_value={
                "etfs": [{"code": "069500", "name": "KODEX200"}],
                "stocks": [],
            },
        ),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        sent = mock_send.call_args.args[0]
        assert "섹터 ETF 수집 실패" in sent
        assert "수급 스크리닝 실패" not in sent  # 수급은 성공 → 경고 없음


def test_kr_kis_connection_failure_warning(monkeypatch):
    """E2/I8: KIS 연결 실패 → 경고, 본문(코스피/코스닥)은 정상 발송."""
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=dict(_KR_FAKE)),
        patch("kis.KISClient", side_effect=RuntimeError("auth fail")),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        sent = mock_send.call_args.args[0]
        assert "KIS 연결 실패" in sent
        assert "오늘은 휴장입니다" not in sent


def test_kr_kis_sector_partial_count_warning(monkeypatch):
    """E2/I8/#6: 섹터 18종 중 일부만 수집되면 'n/18종만 수집' 경고."""
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=dict(_KR_FAKE)),
        patch("kis.KISClient"),
        patch(
            "market_flow.fetchers.kr_etfs.fetch_kr_sectors",
            return_value=_KR_SECTORS_OK[:17],  # 17/18종만 수집
        ),
        patch(
            "market_flow.fetchers.kr_money_flow.fetch_money_flow_watch",
            return_value=_KR_MF_OK,
        ),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        sent = mock_send.call_args.args[0]
        assert "17/18종만 수집" in sent


# ──────────────────────────────────────────────
#  기준일 정합 (#10 P0-b) — E7 + KIS 날짜 신선도
# ──────────────────────────────────────────────


def test_kr_e7_mobile_bizdate_mismatch(monkeypatch):
    """E7: 과거일 재발송 시 모바일 당일 합산(날짜 파라미터 없어 최신값)이 요청일과 달라 경고."""
    now = datetime(2026, 5, 22, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    data = {
        "bizdate": "20260522",
        "kospi": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20260529",  # 모바일은 최신(20260529) — 요청 20260522 ≠
        },
        "kosdaq": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20260529",
        },
        "kospi_daily": [
            {"date": "26.05.22", "foreign": 1, "institutional": 1, "personal": -2}
        ],
    }
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=data),
        patch("market_flow.daily_kr.is_kr_trading_day", return_value=True),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        # argv 과거일 → KIS 스킵(P0-a), 모바일 기준일 불일치 경고만 노출
        daily_kr.main(argv=["20260522"], now=now)
        sent = mock_send.call_args.args[0]
        assert "투자자별 당일 합산은" in sent
        assert "5/29" in sent  # 모바일 기준일
        assert "요청 5/22" in sent


def test_kr_kis_sector_stale_date_warning(monkeypatch):
    """KIS 섹터 ETF 기준일이 오늘과 다르면(직전 거래일 데이터) 경고."""
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)  # argv 없음 → KIS 시도
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    data = {
        "bizdate": "20250526",
        "kospi": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20250526",  # 모바일 일치 → E7 경고 없음
        },
        "kosdaq": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20250526",
        },
        "kospi_daily": [
            {"date": "25.05.26", "foreign": 1, "institutional": 1, "personal": -2}
        ],
    }
    # 18종(부분 경고 없음)이지만 기준일이 직전 거래일(20250523)
    sectors_stale = [
        {"label": f"S{i}", "pct": 0.1, "vol_ratio": None, "date": "20250523"}
        for i in range(18)
    ]
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=data),
        patch("market_flow.daily_kr.is_kr_trading_day", return_value=True),
        patch("kis.KISClient"),
        patch(
            "market_flow.fetchers.kr_etfs.fetch_kr_sectors",
            return_value=sectors_stale,
        ),
        patch(
            "market_flow.fetchers.kr_money_flow.fetch_money_flow_watch",
            return_value=_KR_MF_OK,
        ),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        sent = mock_send.call_args.args[0]
        assert "섹터 ETF는" in sent
        assert "5/23" in sent
        assert "투자자별 당일 합산" not in sent  # 모바일 일치 → E7 경고 없음


def test_kr_e7_desktop_mmdd_stale(monkeypatch):
    """E7/#1: 데스크탑 일별 최신행이 실제 형식 'MM.DD' 여도 요청일과 다르면 경고."""
    now = datetime(2026, 5, 20, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    # 마감 직후 미갱신: 모바일·데스크탑 모두 직전 거래일(05.19), 요청 20260520
    data = {
        "bizdate": "20260520",
        "kospi": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20260519",
        },
        "kosdaq": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20260519",
        },
        "kospi_daily": [
            {"date": "05.19", "foreign": 1, "institutional": 1, "personal": -2}
        ],
    }
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=data),
        patch("market_flow.daily_kr.is_kr_trading_day", return_value=True),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(argv=["20260520"], now=now)  # argv → KIS 스킵
        sent = mock_send.call_args.args[0]
        assert "일별 추이 최신일은 5/19" in sent  # MM.DD 정규화로 stale 포착
        assert "투자자별 당일 합산은 5/19" in sent  # 모바일도 stale


def test_kr_e7_kosdaq_only_mismatch(monkeypatch):
    """E7/#2: KOSPI 는 요청일이고 KOSDAQ 만 다른 날이어도 경고."""
    now = datetime(2026, 5, 22, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    data = {
        "bizdate": "20260522",
        "kospi": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20260522",  # 일치
        },
        "kosdaq": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20260529",  # 불일치
        },
        "kospi_daily": [
            {"date": "05.22", "foreign": 1, "institutional": 1, "personal": -2}
        ],
    }
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=data),
        patch("market_flow.daily_kr.is_kr_trading_day", return_value=True),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(argv=["20260522"], now=now)
        sent = mock_send.call_args.args[0]
        assert "투자자별 당일 합산은 5/29" in sent  # KOSDAQ stale 포착


def test_kr_kis_sector_mixed_date(monkeypatch):
    """KIS #4: 첫 항목은 오늘이어도 일부 섹터가 직전일이면 (전체 집합 검사) 경고."""
    now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)
    monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
    data = {
        "bizdate": "20250526",
        "kospi": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20250526",
        },
        "kosdaq": {
            "foreign": 1,
            "institutional": 1,
            "personal": -2,
            "program_arb": 0,
            "program_nonarb": 0,
            "program_total": 0,
            "bizdate": "20250526",
        },
        "kospi_daily": [
            {"date": "05.26", "foreign": 1, "institutional": 1, "personal": -2}
        ],
    }
    # 첫 항목은 오늘(20250526), 나머지 17종은 직전(20250523)
    sectors_mixed = [
        {"label": "S0", "pct": 0.1, "vol_ratio": None, "date": "20250526"}
    ] + [
        {"label": f"S{i}", "pct": 0.1, "vol_ratio": None, "date": "20250523"}
        for i in range(1, 18)
    ]
    with (
        patch("market_flow.daily_kr.send") as mock_send,
        patch("market_flow.daily_kr.fetch_today", return_value=data),
        patch("market_flow.daily_kr.is_kr_trading_day", return_value=True),
        patch("kis.KISClient"),
        patch(
            "market_flow.fetchers.kr_etfs.fetch_kr_sectors",
            return_value=sectors_mixed,
        ),
        patch(
            "market_flow.fetchers.kr_money_flow.fetch_money_flow_watch",
            return_value=_KR_MF_OK,
        ),
        patch("market_flow.daily_kr.maybe_publish"),
    ):
        mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
        daily_kr.main(now=now)
        sent = mock_send.call_args.args[0]
        assert "섹터 ETF는 5/23" in sent  # 첫 항목(오늘) 아닌 직전일을 집합으로 포착
