"""market_flow/failure_alert 단위 테스트 — 워크플로우 실패 알림 메시지."""

from __future__ import annotations

from unittest.mock import patch

from market_flow import failure_alert as fa

_ENV = {
    "GITHUB_WORKFLOW": "한국장 매매동향 푸시",
    "GITHUB_SERVER_URL": "https://github.com",
    "GITHUB_REPOSITORY": "itda-skills/rs-golden-queens",
    "GITHUB_RUN_ID": "36841003264",
}

_LOG = """━━━ [START] command=daily-kr mode=prod at=2026-10-01T18:10:58+09:00 (KST) ━━━
━━━ [FAIL] command=daily-kr duration=5.7s — HTTPError: HTTP Error 410: 410 ━━━
Traceback (most recent call last):
urllib.error.HTTPError: HTTP Error 410: 410
"""


class TestBuildMessage:
    def test_includes_workflow_cause_and_run_link(self):
        msg = fa.build_message(_LOG, _ENV)
        assert "워크플로우: 한국장 매매동향 푸시" in msg
        assert (
            "원인: [FAIL] command=daily-kr duration=5.7s — HTTPError: HTTP Error 410: 410"
            in msg
        )
        assert "━" not in msg
        assert (
            "로그: https://github.com/itda-skills/rs-golden-queens/actions/runs/36841003264"
            in msg
        )

    def test_uses_last_fail_line(self):
        log = "[FAIL] first\n...\n[FAIL] second\n"
        assert "원인: [FAIL] second" in fa.build_message(log, _ENV)

    def test_no_fail_marker_explains_pre_run_failure(self):
        msg = fa.build_message("pip install 실패\n", _ENV)
        assert "[FAIL] 마커 없음" in msg

    def test_missing_log_still_builds_message(self):
        msg = fa.build_message(None, _ENV)
        assert "[FAIL] 마커 없음" in msg
        assert "actions/runs/36841003264" in msg

    def test_cause_is_truncated(self):
        msg = fa.build_message("[FAIL] " + "x" * 2000, _ENV)
        assert len(msg) < 1000

    def test_redacts_bot_token_pattern(self):
        log = "[FAIL] url=https://api.telegram.org/bot123456:AAH-abc_def/sendMessage"
        msg = fa.build_message(log, _ENV)
        assert "AAH-abc_def" not in msg
        assert "bot***" in msg

    def test_redacts_secret_env_values(self):
        env = {**_ENV, "KIS_APP_SECRET": "supersecretvalue"}
        msg = fa.build_message("[FAIL] leaked supersecretvalue here", env)
        assert "supersecretvalue" not in msg
        assert "***" in msg


class TestMain:
    def test_sends_plain_text_and_returns_zero(self, tmp_path, monkeypatch):
        log = tmp_path / "flow.log"
        log.write_text(_LOG, encoding="utf-8")
        for k, v in _ENV.items():
            monkeypatch.setenv(k, v)
        with patch("market_flow.telegram_push.send", return_value={"ok": True}) as send:
            assert fa.main(str(log)) == 0
        text = send.call_args.args[0]
        assert "HTTP Error 410" in text
        assert send.call_args.kwargs["parse_mode"] is None

    def test_missing_log_file_does_not_crash(self, tmp_path):
        with patch("market_flow.telegram_push.send", return_value={"ok": False}):
            assert fa.main(str(tmp_path / "nope.log")) == 1
