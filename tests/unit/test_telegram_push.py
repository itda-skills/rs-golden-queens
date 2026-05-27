"""SPEC-MF-TEST-001: telegram_push 단위 테스트.

market_flow/telegram_push.py 의 dry-run 분기 / 실 HTTP 분기 / 환경변수
검증 / ANSI 색 처리 동작을 검증한다. 외부 호출은 모두 mock 으로 차단.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
from unittest.mock import MagicMock, patch

import pytest

from market_flow import telegram_push as tp  # noqa: E402


# ──────────────────────────────────────────────
#  _is_dry_run
# ──────────────────────────────────────────────

class TestIsDryRun:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "YES", " 1 ", "True"])
    def test_truthy_values(self, value, monkeypatch):
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", value)
        assert tp._is_dry_run() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "", "random"])
    def test_falsy_values(self, value, monkeypatch):
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", value)
        assert tp._is_dry_run() is False

    def test_unset_returns_false(self, monkeypatch):
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
        assert tp._is_dry_run() is False


# ──────────────────────────────────────────────
#  _env
# ──────────────────────────────────────────────

class TestEnv:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_BOT_TOKEN", "abc123")
        assert tp._env("GOLDENQUEENS_BOT_TOKEN") == "abc123"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_BOT_TOKEN", "  abc123  ")
        assert tp._env("GOLDENQUEENS_BOT_TOKEN") == "abc123"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("GOLDENQUEENS_BOT_TOKEN", raising=False)
        with pytest.raises(RuntimeError) as exc:
            tp._env("GOLDENQUEENS_BOT_TOKEN")
        assert "GOLDENQUEENS_BOT_TOKEN" in str(exc.value)

    def test_raises_when_empty(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_BOT_TOKEN", "")
        with pytest.raises(RuntimeError):
            tp._env("GOLDENQUEENS_BOT_TOKEN")


# ──────────────────────────────────────────────
#  send — dry-run 분기 (REQ-MF-TEST-004)
# ──────────────────────────────────────────────

class TestSendDryRun:
    def test_does_not_call_urlopen(self, monkeypatch):
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
        with patch("market_flow.telegram_push.urllib.request.urlopen") as mock_urlopen:
            tp.send("hello world")
            mock_urlopen.assert_not_called()

    def test_prints_message_to_stdout(self, monkeypatch, capsys):
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
        tp.send("hello world")
        out = capsys.readouterr().out
        assert "hello world" in out
        # 구분선 ─ × 60 라인이 3개 (헤더 위/아래 + 본문 아래)
        assert out.count("─" * 60) >= 3

    def test_returns_stub_response(self, monkeypatch):
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
        resp = tp.send("test")
        # 백워드 호환: ok / result / dry_run 유지
        assert resp["ok"] is True
        assert resp["dry_run"] is True
        assert resp["result"] == {"message_id": 0}
        # 신규: 다중 발송 상세
        assert isinstance(resp["results"], list)
        assert len(resp["results"]) == 1
        assert resp["results"][0]["dry_run"] is True

    def test_works_without_secrets(self, monkeypatch):
        """dry-run 시 토큰·chat_id 미설정이어도 RuntimeError 미발생."""
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
        monkeypatch.delenv("GOLDENQUEENS_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GOLDENQUEENS_CHAT_ID", raising=False)
        # RuntimeError 가 발생하지 않아야 함
        resp = tp.send("test")
        assert resp["ok"] is True

    def test_includes_parse_mode_and_silent_in_header(self, monkeypatch, capsys):
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
        tp.send("text", parse_mode="HTML", disable_notification=True)
        out = capsys.readouterr().out
        assert "parse_mode=HTML" in out
        assert "silent=True" in out


# ──────────────────────────────────────────────
#  send — 실제 HTTP 분기 (REQ-MF-TEST-005)
# ──────────────────────────────────────────────

class TestSendRealHttp:
    def _setup_env(self, monkeypatch):
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
        monkeypatch.setenv("GOLDENQUEENS_BOT_TOKEN", "TEST_TOKEN")
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "12345")

    def _make_mock_response(self, payload=None):
        if payload is None:
            payload = {"ok": True, "result": {"message_id": 42}}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode()
        # context manager 지원
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_calls_urlopen_exactly_once(self, monkeypatch):
        self._setup_env(monkeypatch)
        with patch("market_flow.telegram_push.urllib.request.urlopen", return_value=self._make_mock_response()) as mock_u:
            tp.send("test")
            assert mock_u.call_count == 1

    def test_url_contains_bot_token_and_sendmessage(self, monkeypatch):
        self._setup_env(monkeypatch)
        with patch("market_flow.telegram_push.urllib.request.urlopen", return_value=self._make_mock_response()) as mock_u:
            tp.send("test")
            request_arg = mock_u.call_args.args[0]
            assert request_arg.full_url == "https://api.telegram.org/botTEST_TOKEN/sendMessage"

    def test_payload_contains_required_keys(self, monkeypatch):
        self._setup_env(monkeypatch)
        with patch("market_flow.telegram_push.urllib.request.urlopen", return_value=self._make_mock_response()) as mock_u:
            tp.send("hello")
            request_arg = mock_u.call_args.args[0]
            data = request_arg.data.decode()
            parsed = urllib.parse.parse_qs(data)
            assert "chat_id" in parsed
            assert "text" in parsed
            assert "parse_mode" in parsed
            assert "disable_notification" in parsed
            assert "disable_web_page_preview" in parsed
            assert parsed["chat_id"] == ["12345"]
            assert parsed["text"] == ["hello"]

    def test_returns_parsed_response_json(self, monkeypatch):
        self._setup_env(monkeypatch)
        payload = {"ok": True, "result": {"message_id": 999}}
        with patch("market_flow.telegram_push.urllib.request.urlopen", return_value=self._make_mock_response(payload)):
            resp = tp.send("test")
            # 백워드 호환 핵심 필드만 검증 (results 키가 추가됨)
            assert resp["ok"] is True
            assert resp["result"] == {"message_id": 999}
            # 단일 chat_id 환경에서 results 는 1건
            assert len(resp["results"]) == 1
            assert resp["results"][0]["chat_id"] == "12345"
            assert resp["results"][0]["ok"] is True

    def test_raises_when_token_missing(self, monkeypatch):
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
        monkeypatch.delenv("GOLDENQUEENS_BOT_TOKEN", raising=False)
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "12345")
        with pytest.raises(RuntimeError) as exc:
            tp.send("test")
        assert "GOLDENQUEENS_BOT_TOKEN" in str(exc.value)

    def test_raises_when_chat_id_missing(self, monkeypatch):
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
        monkeypatch.setenv("GOLDENQUEENS_BOT_TOKEN", "tok")
        monkeypatch.delenv("GOLDENQUEENS_CHAT_ID", raising=False)
        with pytest.raises(RuntimeError) as exc:
            tp.send("test")
        assert "GOLDENQUEENS_CHAT_ID" in str(exc.value)

    def test_disable_notification_true_serialized(self, monkeypatch):
        self._setup_env(monkeypatch)
        with patch("market_flow.telegram_push.urllib.request.urlopen", return_value=self._make_mock_response()) as mock_u:
            tp.send("test", disable_notification=True)
            data = mock_u.call_args.args[0].data.decode()
            parsed = urllib.parse.parse_qs(data)
            assert parsed["disable_notification"] == ["true"]


# ──────────────────────────────────────────────
#  _colorize_for_stdout
# ──────────────────────────────────────────────

class TestColorize:
    def test_no_tty_returns_unchanged(self, monkeypatch):
        # capsys 환경에서 sys.stdout.isatty() 는 자연 False
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        text = "+123 / -456"
        assert tp._colorize_for_stdout(text) == text

    def test_tty_wraps_positive_with_red_ansi(self, monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        out = tp._colorize_for_stdout("+123")
        assert "\033[31m" in out
        assert "+123" in out
        assert "\033[0m" in out

    def test_tty_wraps_negative_with_blue_ansi(self, monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        out = tp._colorize_for_stdout("-123")
        assert "\033[34m" in out
        assert "-123" in out

    def test_tty_handles_percent_suffix(self, monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        out = tp._colorize_for_stdout("+1.5%")
        assert "\033[31m" in out
        assert "+1.5%" in out


# ──────────────────────────────────────────────
#  _chat_ids — 콤마 분리 파서 (SPEC-MF-MULTI-CHAT)
# ──────────────────────────────────────────────

class TestChatIds:
    def test_single_value(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "42478249")
        assert tp._chat_ids() == ["42478249"]

    def test_multiple_comma_separated(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "1,2,3")
        assert tp._chat_ids() == ["1", "2", "3"]

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "1, 2 ,  3")
        assert tp._chat_ids() == ["1", "2", "3"]

    def test_filters_empty_entries(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "1,,2,,,3")
        assert tp._chat_ids() == ["1", "2", "3"]

    def test_filters_leading_trailing_comma(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", ",1,")
        assert tp._chat_ids() == ["1"]

    def test_channel_username_supported(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "42, @channelname, -100123")
        assert tp._chat_ids() == ["42", "@channelname", "-100123"]

    def test_raises_when_only_commas(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", ",,,")
        with pytest.raises(RuntimeError) as exc:
            tp._chat_ids()
        assert "유효한 chat_id" in str(exc.value)

    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv("GOLDENQUEENS_CHAT_ID", raising=False)
        with pytest.raises(RuntimeError):
            tp._chat_ids()

    def test_raises_when_empty(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "")
        with pytest.raises(RuntimeError):
            tp._chat_ids()


# ──────────────────────────────────────────────
#  send — 다중 chat_id 발송 (SPEC-MF-MULTI-CHAT)
# ──────────────────────────────────────────────

class TestSendMultiChat:
    def _setup_env(self, monkeypatch, chat_ids):
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)
        monkeypatch.setenv("GOLDENQUEENS_BOT_TOKEN", "TEST_TOKEN")
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", chat_ids)

    def _make_mock_response(self, message_id=42):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"ok": True, "result": {"message_id": message_id}}
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_calls_urlopen_once_per_chat_id(self, monkeypatch):
        self._setup_env(monkeypatch, "111,222,333")
        with patch(
            "market_flow.telegram_push.urllib.request.urlopen",
            side_effect=[self._make_mock_response(m) for m in (10, 20, 30)],
        ) as mock_u:
            resp = tp.send("hello")
            assert mock_u.call_count == 3

    def test_each_call_uses_correct_chat_id(self, monkeypatch):
        self._setup_env(monkeypatch, "111,222,333")
        with patch(
            "market_flow.telegram_push.urllib.request.urlopen",
            side_effect=[self._make_mock_response(m) for m in (10, 20, 30)],
        ) as mock_u:
            tp.send("hello")
            chat_ids_used = []
            for call in mock_u.call_args_list:
                req = call.args[0]
                parsed = urllib.parse.parse_qs(req.data.decode())
                chat_ids_used.append(parsed["chat_id"][0])
            assert chat_ids_used == ["111", "222", "333"]

    def test_aggregate_response_format(self, monkeypatch):
        self._setup_env(monkeypatch, "111,222")
        with patch(
            "market_flow.telegram_push.urllib.request.urlopen",
            side_effect=[self._make_mock_response(10), self._make_mock_response(20)],
        ):
            resp = tp.send("hello")
            assert resp["ok"] is True
            # 첫 성공의 message_id 가 백워드 호환 result 에 노출
            assert resp["result"] == {"message_id": 10}
            assert len(resp["results"]) == 2
            assert resp["results"][0]["chat_id"] == "111"
            assert resp["results"][0]["result"]["message_id"] == 10
            assert resp["results"][1]["chat_id"] == "222"
            assert resp["results"][1]["result"]["message_id"] == 20

    def test_partial_failure_continues_remaining(self, monkeypatch):
        """첫 chat 실패해도 나머지 chat 으로 발송 진행."""
        self._setup_env(monkeypatch, "bad,good")

        def side_effect(*args, **kwargs):
            req = args[0]
            parsed = urllib.parse.parse_qs(req.data.decode())
            cid = parsed["chat_id"][0]
            if cid == "bad":
                raise urllib.error.HTTPError(
                    url=req.full_url, code=400, msg="Bad Request", hdrs=None, fp=None
                )
            return self._make_mock_response(99)

        with patch(
            "market_flow.telegram_push.urllib.request.urlopen", side_effect=side_effect
        ) as mock_u:
            resp = tp.send("hello")
            assert mock_u.call_count == 2  # 두 chat 모두 시도
            assert resp["ok"] is False  # 하나 실패했으니 False
            # 백워드 호환: 첫 성공의 message_id 가 result 에 노출
            assert resp["result"] == {"message_id": 99}
            assert resp["results"][0]["ok"] is False
            assert "HTTPError" in resp["results"][0]["error"]
            assert resp["results"][1]["ok"] is True

    def test_all_failures_yields_result_message_id_zero(self, monkeypatch):
        self._setup_env(monkeypatch, "x,y")
        with patch(
            "market_flow.telegram_push.urllib.request.urlopen",
            side_effect=RuntimeError("boom"),
        ):
            resp = tp.send("hello")
            assert resp["ok"] is False
            assert resp["result"] == {"message_id": 0}
            assert all(r["ok"] is False for r in resp["results"])

    def test_dry_run_shows_all_chat_ids(self, monkeypatch, capsys):
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
        monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "111,222,333")
        resp = tp.send("hello")
        out = capsys.readouterr().out
        # chat_ids 리스트가 dry-run 헤더에 표시되어야 함
        assert "111" in out and "222" in out and "333" in out
        # 응답 results 도 3건
        assert len(resp["results"]) == 3


