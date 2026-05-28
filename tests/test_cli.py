from __future__ import annotations

import os

import main


def test_test_flag_after_subcommand_sets_env_temporarily(monkeypatch):
    seen = {}

    def fake_notify(args):
        seen["test_env"] = os.environ.get("MARKET_FLOW_TEST_SEND")

    monkeypatch.setattr(main, "_cmd_notify_test", fake_notify)

    assert main.main(["notify-test", "--test"]) == 0
    assert seen["test_env"] == "1"
    assert "MARKET_FLOW_TEST_SEND" not in os.environ


def test_test_flag_before_subcommand_sets_env_temporarily(monkeypatch):
    seen = {}

    def fake_notify(args):
        seen["test_env"] = os.environ.get("MARKET_FLOW_TEST_SEND")

    monkeypatch.setattr(main, "_cmd_notify_test", fake_notify)

    assert main.main(["--test", "notify-test"]) == 0
    assert seen["test_env"] == "1"
    assert "MARKET_FLOW_TEST_SEND" not in os.environ


def test_without_test_flag_does_not_set_test_env(monkeypatch):
    seen = {}

    def fake_notify(args):
        seen["test_env"] = os.environ.get("MARKET_FLOW_TEST_SEND")

    monkeypatch.setattr(main, "_cmd_notify_test", fake_notify)

    assert main.main(["notify-test"]) == 0
    assert seen["test_env"] is None
