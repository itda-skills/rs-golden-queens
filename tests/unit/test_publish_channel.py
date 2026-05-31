"""market_flow/publish_channel.py 단위 테스트.

index/latest 갱신(순수 함수)과 GitPublisher의 DRY-RUN/실패 격리 동작을 검증한다.
실제 네트워크 push는 하지 않는다 (DRY-RUN + git 명령 mock).
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from market_flow import publish_channel as C

_KST = ZoneInfo("Asia/Seoul")
_NOW = datetime(2026, 5, 29, 18, 10, 0, tzinfo=_KST)


@pytest.fixture
def kr_snap():
    return {
        "schema_version": 1,
        "market": "kr",
        "date": "2026-05-29",
        "generated_at": _NOW.isoformat(),
        "is_holiday": False,
        "payload": {"bizdate": "20260529", "kospi": {"foreign": -17314}},
        "sources": [],
    }


@pytest.fixture
def weekly_snap():
    return {
        "schema_version": 1,
        "market": "weekly",
        "date": "2026-05-29",
        "week": "2026-W22",
        "generated_at": _NOW.isoformat(),
        "is_holiday": False,
        "payload": {},
        "sources": [],
    }


# ──────────────────────────────────────────────
#  index.json 갱신
# ──────────────────────────────────────────────


class TestUpdateIndex:
    def test_adds_date_to_market_list(self, kr_snap):
        out = C.update_index({}, kr_snap, _NOW)
        assert out["kr"] == ["2026-05-29"]
        assert out["updated_at"] == "2026-05-29T18:10:00+09:00"

    def test_dedup_and_sorted_desc(self, kr_snap):
        idx = {"kr": ["2026-05-28", "2026-05-29"]}
        out = C.update_index(idx, kr_snap, _NOW)
        assert out["kr"] == ["2026-05-29", "2026-05-28"]  # 중복 없이 최신순

    def test_weekly_uses_week_id(self, weekly_snap):
        out = C.update_index({}, weekly_snap, _NOW)
        assert out["weekly"] == ["2026-W22"]

    def test_other_markets_untouched(self, kr_snap):
        out = C.update_index({"us": ["2026-05-28"]}, kr_snap, _NOW)
        assert out["us"] == ["2026-05-28"]


# ──────────────────────────────────────────────
#  latest.json 갱신
# ──────────────────────────────────────────────


class TestUpdateLatest:
    def test_kr_entry(self, kr_snap):
        out = C.update_latest({}, kr_snap, _NOW)
        assert out["kr"]["date"] == "2026-05-29"
        assert out["kr"]["path"] == "snapshots/kr/2026-05-29.json"

    def test_weekly_entry_has_week(self, weekly_snap):
        out = C.update_latest({}, weekly_snap, _NOW)
        assert out["weekly"]["week"] == "2026-W22"
        assert out["weekly"]["path"] == "snapshots/weekly/2026-W22.json"


# ──────────────────────────────────────────────
#  DRY-RUN
# ──────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_no_git_calls(self, kr_snap, monkeypatch):
        monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")
        called = []
        monkeypatch.setattr(
            C.GitPublisher, "_git", lambda self, cwd, *a: called.append(a)
        )
        ok = C.GitPublisher().publish(kr_snap, _NOW)
        assert ok is True
        assert called == []  # git 호출 없음


# ──────────────────────────────────────────────
#  실패 격리 (push 실패해도 예외 전파 안 함)
# ──────────────────────────────────────────────


class TestFailureIsolation:
    def test_clone_failure_returns_false(self, kr_snap, monkeypatch):
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)

        def boom(self, cwd, *args):
            raise subprocess.CalledProcessError(
                128, ["git", *args], stderr="fatal: auth failed"
            )

        monkeypatch.setattr(C.GitPublisher, "_git", boom)
        ok = C.GitPublisher().publish(kr_snap, _NOW)
        assert ok is False  # 예외 전파 없이 False

    def test_secret_not_leaked_on_failure(self, kr_snap, monkeypatch, capsys):
        monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)

        def boom(self, cwd, *args):
            raise subprocess.CalledProcessError(
                128, ["git", *args], stderr="error\nsecret-token-xyz"
            )

        monkeypatch.setattr(C.GitPublisher, "_git", boom)
        C.GitPublisher().publish(kr_snap, _NOW)
        err = capsys.readouterr().err
        # 마지막 한 줄만(축약) 출력 — 토큰이 들어와도 첫 줄 'error'는 노출 안 됨을 확인
        assert "[publish] WARN" in err


# ──────────────────────────────────────────────
#  config (환경변수)
# ──────────────────────────────────────────────


class TestConfig:
    def test_default_repo(self, monkeypatch):
        monkeypatch.delenv("GOLDENQUEENS_DATA_REPO", raising=False)
        assert "rs-golden-queens-data" in C.GitPublisher().repo

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("GOLDENQUEENS_DATA_REPO", "git@host:foo/bar.git")
        monkeypatch.setenv("GOLDENQUEENS_DATA_BRANCH", "dev")
        pub = C.GitPublisher()
        assert pub.repo == "git@host:foo/bar.git"
        assert pub.branch == "dev"


# ──────────────────────────────────────────────
#  웹 링크 (텔레그램 메시지 suffix)
# ──────────────────────────────────────────────


class TestWebLink:
    def test_detail_url_kr(self, monkeypatch):
        monkeypatch.delenv("MARKET_FLOW_WEB_URL", raising=False)
        assert (
            C.web_detail_url("kr", "2026-05-29")
            == "https://rs-golden-queens.vercel.app/kr/2026-05-29"
        )

    def test_detail_url_env_override(self, monkeypatch):
        monkeypatch.setenv("MARKET_FLOW_WEB_URL", "https://x.example/")
        assert C.web_detail_url("us", "2026-05-28") == "https://x.example/us/2026-05-28"


# ──────────────────────────────────────────────
#  발행 무결성 게이트 (#10 I9)
# ──────────────────────────────────────────────


class TestPublishGate:
    def test_invalid_snapshot_not_published(self, monkeypatch):
        monkeypatch.setenv("MARKET_FLOW_PUBLISH", "1")
        called = []
        monkeypatch.setattr(
            C, "publish_snapshot", lambda s, n=None: called.append(s) or True
        )
        bad = {
            "market": "us",
            "date": None,
            "is_holiday": False,
            "payload": {"indices": {}},
        }
        assert C.maybe_publish(bad) is False  # 게이트가 보류
        assert called == []  # 발행 시도 자체를 안 함

    def test_valid_snapshot_published(self, monkeypatch, kr_snap):
        monkeypatch.setenv("MARKET_FLOW_PUBLISH", "1")
        called = []
        monkeypatch.setattr(
            C, "publish_snapshot", lambda s, n=None: called.append(s) or True
        )
        assert C.maybe_publish(kr_snap) is True
        assert len(called) == 1

    def test_disabled_skips_before_validation(self, monkeypatch):
        # 발행 비활성이면 검증 이전에 False (게이트는 활성 경로에서만)
        monkeypatch.delenv("MARKET_FLOW_PUBLISH", raising=False)
        assert C.maybe_publish({"market": "us", "date": None}) is False


class TestWebLinkForSnapshot:
    """web_link_suffix_for_snapshot — 발행될 스냅샷에만 링크(#10 I9 P1-2)."""

    def test_off_when_publish_disabled(self, monkeypatch, kr_snap):
        monkeypatch.delenv("MARKET_FLOW_PUBLISH", raising=False)
        assert C.web_link_suffix_for_snapshot(kr_snap) == ""

    def test_link_when_valid_and_enabled(self, monkeypatch, kr_snap):
        monkeypatch.setenv("MARKET_FLOW_PUBLISH", "1")
        assert "kr/2026-05-29" in C.web_link_suffix_for_snapshot(kr_snap)

    def test_no_link_when_gate_holds(self, monkeypatch):
        # 발행 활성이어도 보류될 스냅샷(weekly 빈 payload)엔 링크 없음 — 404 방지
        monkeypatch.setenv("MARKET_FLOW_PUBLISH", "1")
        empty_weekly = {
            "market": "weekly",
            "date": "2026-05-29",
            "week": "2026-W22",
            "is_holiday": False,
            "payload": {"kospi_daily": [], "watch_5d": []},
        }
        assert C.web_link_suffix_for_snapshot(empty_weekly) == ""
