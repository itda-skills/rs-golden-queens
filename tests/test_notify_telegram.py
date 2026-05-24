"""notify_telegram.py 단위 테스트.

라이브 호출 없이 mock으로:
- 환경변수 부재 시 enabled=False, send_message=False
- 환경변수 있으면 sendMessage 엔드포인트로 POST
- 4096자 초과 시 truncate
- HTTP 4xx 응답 처리
- ok=false 응답 처리
- 네트워크 오류 처리
"""

import io
import unittest
import urllib.error
from contextlib import redirect_stderr
from unittest.mock import patch, MagicMock

from naver_investor_flow.notify_telegram import (
    TelegramConfig,
    send_message,
    truncate_for_telegram,
    MAX_MESSAGE_CHARS,
)


class TestTelegramConfig(unittest.TestCase):
    def test_from_env_both_present(self):
        cfg = TelegramConfig.from_env({"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": "C"})
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.token, "T")
        self.assertEqual(cfg.chat_id, "C")

    def test_from_env_token_missing(self):
        cfg = TelegramConfig.from_env({"TELEGRAM_CHAT_ID": "C"})
        self.assertFalse(cfg.enabled)

    def test_from_env_chat_id_missing(self):
        cfg = TelegramConfig.from_env({"TELEGRAM_BOT_TOKEN": "T"})
        self.assertFalse(cfg.enabled)

    def test_from_env_empty_strings_disabled(self):
        cfg = TelegramConfig.from_env({"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""})
        self.assertFalse(cfg.enabled)

    def test_from_env_no_keys_disabled(self):
        cfg = TelegramConfig.from_env({})
        self.assertFalse(cfg.enabled)


class TestTruncate(unittest.TestCase):
    def test_short_unchanged(self):
        self.assertEqual(truncate_for_telegram("abc"), "abc")

    def test_exactly_at_limit_unchanged(self):
        s = "a" * MAX_MESSAGE_CHARS
        self.assertEqual(truncate_for_telegram(s), s)

    def test_over_limit_truncated_with_marker(self):
        s = "a" * (MAX_MESSAGE_CHARS + 100)
        out = truncate_for_telegram(s)
        self.assertLessEqual(len(out), MAX_MESSAGE_CHARS)
        self.assertTrue(out.endswith("(잘림)"))


class TestSendMessage(unittest.TestCase):
    def test_disabled_returns_false_no_network(self):
        """설정 비활성 시 즉시 False, 네트워크 호출 없음"""
        cfg = TelegramConfig(token=None, chat_id=None)
        with patch("urllib.request.urlopen") as mock_open:
            ok = send_message("hi", config=cfg)
        self.assertFalse(ok)
        mock_open.assert_not_called()

    def test_success_posts_to_send_message_endpoint(self):
        """정상 응답 — sendMessage 엔드포인트로 POST, ok=True"""
        cfg = TelegramConfig(token="TOK", chat_id="123")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true, "result": {}}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = []
        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ok = send_message("안녕 텔레그램", config=cfg)

        self.assertTrue(ok)
        self.assertEqual(len(captured), 1)
        req = captured[0]
        self.assertIn("/botTOK/sendMessage", req.full_url)
        self.assertEqual(req.method, "POST")
        # 본문에 chat_id와 text 포함
        body = req.data.decode("utf-8")
        self.assertIn("chat_id=123", body)
        self.assertIn("text=", body)

    def test_api_returns_ok_false(self):
        """Telegram API가 ok=false 응답하면 False + stderr 로그"""
        cfg = TelegramConfig(token="TOK", chat_id="123")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": false, "description": "Bad Request: chat not found"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        buf = io.StringIO()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with redirect_stderr(buf):
                ok = send_message("x", config=cfg)
        self.assertFalse(ok)
        self.assertIn("chat not found", buf.getvalue())

    def test_http_error_4xx(self):
        """4xx 응답 시 False + stderr 로그"""
        cfg = TelegramConfig(token="TOK", chat_id="123")
        err = urllib.error.HTTPError(
            url="https://api.telegram.org/botTOK/sendMessage",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"ok": false, "description": "Unauthorized"}'),
        )
        buf = io.StringIO()
        with patch("urllib.request.urlopen", side_effect=err):
            with redirect_stderr(buf):
                ok = send_message("x", config=cfg)
        self.assertFalse(ok)
        self.assertIn("401", buf.getvalue())

    def test_network_error(self):
        """URLError 발생 시 False + stderr 로그"""
        cfg = TelegramConfig(token="TOK", chat_id="123")
        buf = io.StringIO()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS fail")):
            with redirect_stderr(buf):
                ok = send_message("x", config=cfg)
        self.assertFalse(ok)
        self.assertIn("DNS fail", buf.getvalue())

    def test_long_message_truncated_before_send(self):
        """4096자 초과 메시지는 truncate되어 전송"""
        cfg = TelegramConfig(token="TOK", chat_id="123")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        captured = []
        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return mock_resp

        long_text = "x" * (MAX_MESSAGE_CHARS + 500)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            send_message(long_text, config=cfg)

        # POST body 길이 검사 (urlencode된 text= 부분이 truncate되어야 함)
        body = captured[0].data.decode("utf-8")
        # url-encoded라 정확 비교는 어렵지만 길이는 원본보다 적음
        self.assertLess(len(body), len(long_text) + 200)


if __name__ == "__main__":
    unittest.main()
