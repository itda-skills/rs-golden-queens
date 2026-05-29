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
