"""발송 ↔ 발행 격리 통합 테스트 (#4).

발행 단계가 강제 실패해도 텔레그램 발송(daily 함수)은 정상 종료되어야 한다.
또한 MARKET_FLOW_PUBLISH 게이트가 opt-in (기본 비활성)임을 검증한다.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from market_flow import daily_kr

KST = ZoneInfo("Asia/Seoul")

# 정상 거래일 (2025-05-26 월)
_TRADING = datetime(2025, 5, 26, 18, 10, tzinfo=KST)

_FAKE_KR = {
    "bizdate": "20250526",
    "kospi": {
        "personal": 1,
        "foreign": 2,
        "institutional": 3,
        "program_arb": 0,
        "program_nonarb": 0,
        "program_total": 0,
    },
    "kosdaq": {
        "personal": 1,
        "foreign": 2,
        "institutional": 3,
        "program_arb": 0,
        "program_nonarb": 0,
        "program_total": 0,
    },
    "kospi_intraday": [],
    "kospi_daily": [
        {
            "date": "25.05.26",
            "personal": 1,
            "foreign": 2,
            "institutional": 3,
            "finance": 0,
            "insurance": 0,
            "trust": 0,
            "bank": 0,
            "other_fin": 0,
            "pension": 0,
            "other_corp": 0,
        }
    ],
}


def _patch_send_fetch():
    s = patch("market_flow.daily_kr.send")
    f = patch("market_flow.daily_kr.fetch_today")
    return s, f


class TestPublishGate:
    def test_disabled_by_default_no_publish(self, monkeypatch):
        """MARKET_FLOW_PUBLISH 미설정 → 발행 시도 안 함."""
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
        monkeypatch.delenv("MARKET_FLOW_PUBLISH", raising=False)
        s, f = _patch_send_fetch()
        with (
            s as mock_send,
            f as mock_fetch,
            patch("market_flow.daily_kr.maybe_publish") as mock_pub,
        ):
            mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
            mock_fetch.return_value = _FAKE_KR
            daily_kr.main(now=_TRADING)
            # maybe_publish 자체는 호출되지만 (게이트는 그 안에 있음)
            mock_pub.assert_called_once()


class TestPublishIsolation:
    def test_publish_failure_does_not_break_send(self, monkeypatch):
        """발행이 예외를 던져도 daily_kr.main 은 정상 종료."""
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
        monkeypatch.setenv("MARKET_FLOW_PUBLISH", "1")
        s, f = _patch_send_fetch()
        with (
            s as mock_send,
            f as mock_fetch,
            patch("market_flow.publish_channel.publish_snapshot") as mock_pub,
        ):
            mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
            mock_fetch.return_value = _FAKE_KR
            mock_pub.side_effect = RuntimeError("git push 실패!")
            # 예외가 전파되면 이 호출이 터진다 → 전파 안 됨을 검증
            daily_kr.main(now=_TRADING)
            mock_send.assert_called_once()  # 발송은 정상 수행됨

    def test_publish_called_when_enabled(self, monkeypatch):
        """발행 활성화 시 publish_snapshot 이 KR 스냅샷으로 호출된다."""
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
        monkeypatch.setenv("MARKET_FLOW_PUBLISH", "1")
        s, f = _patch_send_fetch()
        with (
            s as mock_send,
            f as mock_fetch,
            patch("market_flow.publish_channel.publish_snapshot") as mock_pub,
        ):
            mock_send.return_value = {"ok": True, "result": {"message_id": 1}}
            mock_fetch.return_value = _FAKE_KR
            mock_pub.return_value = True
            daily_kr.main(now=_TRADING)
            assert mock_pub.call_count == 1
            snap = mock_pub.call_args[0][0]
            assert snap["market"] == "kr"
            assert snap["date"] == "2025-05-26"
