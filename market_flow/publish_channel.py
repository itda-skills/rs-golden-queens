"""발행 채널 어댑터 — 스냅샷을 데이터 저장소에 push.

스냅샷 JSON을 별도 데이터 저장소(``itda-skills/rs-golden-queens-data``)에
git CLI로 commit + push 한다. index.json / latest.json 도 함께 갱신한다.

설계:
  - ``Publisher`` 인터페이스 + git CLI 구현체(``GitPublisher``).
  - 인증은 SSH deploy key (환경변수로 주입, 코드/로그 노출 금지).
  - ``MARKET_FLOW_DRY_RUN=1`` 이면 실제 push 없이 미리보기만.
  - 실패는 침묵하지 않고 ``[publish]`` 마커로 로그 남김 (발송과 분리는 호출 측 #4 책임).

환경변수:
  GOLDENQUEENS_DATA_REPO    데이터 저장소 (기본 git@github.com:itda-skills/rs-golden-queens-data.git)
  GOLDENQUEENS_DATA_BRANCH  대상 브랜치 (기본 main)
  GIT_SSH_COMMAND           deploy key 사용 시 ``ssh -i <key>`` (호출 환경이 설정)
  MARKET_FLOW_DRY_RUN       1이면 실제 push 안 함
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Protocol
from zoneinfo import ZoneInfo

from market_flow import publisher as P

_KST = ZoneInfo("Asia/Seoul")

_DEFAULT_REPO = "git@github.com:itda-skills/rs-golden-queens-data.git"
_DEFAULT_BRANCH = "main"


def _log(msg: str) -> None:
    print(f"[publish] {msg}", flush=True)


def _warn(msg: str) -> None:
    print(f"[publish] WARN {msg}", file=sys.stderr, flush=True)


def _is_dry_run() -> bool:
    return os.environ.get("MARKET_FLOW_DRY_RUN", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def is_publish_enabled() -> bool:
    """발행 단계 활성화 여부. ``MARKET_FLOW_PUBLISH`` 가 참일 때만 발행한다.

    기본은 비활성 — 기존 발송 동작에 영향을 주지 않는다(opt-in).
    """
    return os.environ.get("MARKET_FLOW_PUBLISH", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def maybe_publish(snapshot: dict[str, Any], now: Optional[datetime] = None) -> bool:
    """발행이 활성화된 경우에만 스냅샷을 발행한다.

    발행 단계는 텔레그램 발송과 완전히 분리된다 — 어떤 예외도 호출 측으로
    전파하지 않고 ``[publish]`` 마커 로그만 남긴다(발송 성공을 막지 않음).

    Returns:
        실제 발행 시도 성공 시 True, 비활성/실패 시 False.
    """
    if not is_publish_enabled():
        return False
    try:
        return publish_snapshot(snapshot, now)
    except Exception as e:  # noqa: BLE001 — 발송 흐름 보호: 어떤 경우에도 전파 금지
        _warn(
            f"발행 단계 예외 무시 ({snapshot.get('market')}): {type(e).__name__}: {e}"
        )
        return False


def _trigger_revalidate(snapshot: dict[str, Any]) -> None:
    """발행 직후 웹 on-demand revalidate 호출 (선택적, 실패 무시).

    환경변수가 모두 설정된 경우에만 동작한다:
      MARKET_FLOW_REVALIDATE_URL    예) https://rs-golden-queens.vercel.app/api/revalidate
      MARKET_FLOW_REVALIDATE_SECRET 웹의 REVALIDATE_SECRET 과 동일
    """
    import json as _json
    import urllib.error
    import urllib.request

    url = os.environ.get("MARKET_FLOW_REVALIDATE_URL", "").strip()
    secret = os.environ.get("MARKET_FLOW_REVALIDATE_SECRET", "").strip()
    if not url or not secret:
        return

    market = snapshot["market"]
    entry = snapshot["week"] if market == "weekly" else snapshot["date"]
    payload = _json.dumps({"secret": secret, "market": market, "id": entry}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            _log(f"revalidate 호출 — {market} {entry} (HTTP {resp.status})")
    except (urllib.error.URLError, OSError) as e:  # noqa: BLE001 — 발행 성공에 영향 없음
        _warn(f"revalidate 실패 (무시): {type(e).__name__}: {e}")


def _data_repo() -> str:
    return os.environ.get("GOLDENQUEENS_DATA_REPO", "").strip() or _DEFAULT_REPO


def _data_branch() -> str:
    return os.environ.get("GOLDENQUEENS_DATA_BRANCH", "").strip() or _DEFAULT_BRANCH


# ──────────────────────────────────────────────
#  index.json / latest.json 갱신 (순수 함수)
# ──────────────────────────────────────────────


def _market_key(snapshot: dict[str, Any]) -> str:
    """index/latest 에서 쓰는 시장 키."""
    return snapshot["market"]


def _entry_id(snapshot: dict[str, Any]) -> str:
    """index 목록에 들어갈 식별자 (kr/us=date, weekly=week)."""
    return snapshot["week"] if snapshot["market"] == "weekly" else snapshot["date"]


def update_index(
    index: dict[str, Any], snapshot: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """index.json 내용을 갱신한 새 dict 반환. 같은 식별자는 중복 없이 최신순 정렬."""
    out = dict(index)
    out.setdefault("schema_version", P.SCHEMA_VERSION)
    out["updated_at"] = now.isoformat(timespec="seconds")
    key = _market_key(snapshot)
    ids = set(out.get(key) or [])
    ids.add(_entry_id(snapshot))
    out[key] = sorted(ids, reverse=True)
    return out


def update_latest(
    latest: dict[str, Any], snapshot: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """latest.json 내용을 갱신한 새 dict 반환."""
    out = dict(latest)
    out.setdefault("schema_version", P.SCHEMA_VERSION)
    out["updated_at"] = now.isoformat(timespec="seconds")
    key = _market_key(snapshot)
    entry = {"path": P.snapshot_path(snapshot)}
    if snapshot["market"] == "weekly":
        entry["week"] = snapshot["week"]
    entry["date"] = snapshot["date"]
    out[key] = entry
    return out


# ──────────────────────────────────────────────
#  Publisher 인터페이스
# ──────────────────────────────────────────────


class Publisher(Protocol):
    def publish(self, snapshot: dict[str, Any], now: Optional[datetime] = None) -> bool:
        """스냅샷 1건 + index/latest 갱신을 발행. 성공 시 True."""
        ...


class GitPublisher:
    """데이터 저장소를 임시 디렉토리에 clone → 파일 쓰기 → commit + push."""

    def __init__(self, repo: Optional[str] = None, branch: Optional[str] = None):
        self.repo = repo or _data_repo()
        self.branch = branch or _data_branch()

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

    def publish(self, snapshot: dict[str, Any], now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.now(_KST)
        rel_path = P.snapshot_path(snapshot)
        entry = _entry_id(snapshot)

        if _is_dry_run():
            _log(f"[DRY-RUN] {snapshot['market']} {entry} → {rel_path} (push 안 함)")
            _log(f"[DRY-RUN] 미리보기 {len(P.to_json(snapshot))} chars")
            return True

        try:
            with tempfile.TemporaryDirectory(prefix="gq-data-") as tmp:
                root = Path(tmp)
                _log(f"clone {self.repo} (branch={self.branch})")
                self._git(
                    root,
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    self.branch,
                    self.repo,
                    "repo",
                )
                repo_dir = root / "repo"

                # 1) 스냅샷 파일
                self._write_json(repo_dir / rel_path, snapshot)

                # 2) index.json / latest.json 갱신
                index = self._read_json(repo_dir / "snapshots/index.json", default={})
                latest = self._read_json(repo_dir / "snapshots/latest.json", default={})
                self._write_json(
                    repo_dir / "snapshots/index.json",
                    update_index(index, snapshot, now),
                )
                self._write_json(
                    repo_dir / "snapshots/latest.json",
                    update_latest(latest, snapshot, now),
                )

                # 3) commit + push (변경 없으면 skip)
                self._git(repo_dir, "add", "-A")
                status = self._git(repo_dir, "status", "--porcelain").stdout.strip()
                if not status:
                    _log(f"변경 없음 — {snapshot['market']} {entry} 이미 최신")
                    return True
                msg = f"publish: {snapshot['market']} {entry}"
                self._git(
                    repo_dir,
                    "-c",
                    "user.name=golden-queens-bot",
                    "-c",
                    "user.email=bot@itda.work",
                    "commit",
                    "-m",
                    msg,
                )
                self._git(repo_dir, "push", "origin", self.branch)
                _log(f"발행 완료 — {rel_path} (+index/latest)")
                _trigger_revalidate(snapshot)
                return True
        except subprocess.CalledProcessError as e:
            # git stderr 에 토큰/키가 섞이지 않도록 메시지만 축약 출력
            _warn(
                f"발행 실패 ({snapshot['market']} {entry}): git {e.cmd[1] if len(e.cmd) > 1 else '?'} rc={e.returncode}"
            )
            if e.stderr:
                _warn(f"git stderr: {e.stderr.strip().splitlines()[-1][:200]}")
            return False
        except Exception as e:  # noqa: BLE001
            _warn(f"발행 실패 ({snapshot['market']} {entry}): {type(e).__name__}: {e}")
            return False

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default


def publish_snapshot(snapshot: dict[str, Any], now: Optional[datetime] = None) -> bool:
    """기본 GitPublisher 로 스냅샷 1건 발행. 호출 편의 함수."""
    return GitPublisher().publish(snapshot, now)
