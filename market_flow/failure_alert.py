"""운영 워크플로우 실패 알림 — 테스트(운영자) 채널로 실패 사실을 알린다.

GitHub Actions 의 ``if: failure()`` 단계에서 ``main.py --test notify-failure`` 로
호출된다. 본 단계 로그에서 main.py 의 ``[FAIL]`` 마커 줄을 원인으로 뽑고, 워크플로우
이름과 run 링크를 붙인다. 구독자 채널에는 보내지 않는다.

tee 로 남긴 로그는 GitHub 의 시크릿 마스킹을 거치지 않으므로, 텔레그램 봇 토큰
패턴과 환경변수의 시크릿 값을 지운 뒤에만 메시지에 담는다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_MAX_CAUSE = 400
_BOT_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")
_SECRET_ENV_RE = re.compile(r"(TOKEN|SECRET|KEY|ACCOUNT|CHAT_ID)")


def _redact(text: str, env: dict[str, str]) -> str:
    text = _BOT_TOKEN_RE.sub("bot***", text)
    for name, value in env.items():
        value = (value or "").strip()
        if len(value) >= 6 and _SECRET_ENV_RE.search(name):
            text = text.replace(value, "***")
    return text


def extract_cause(log_text: str) -> str | None:
    """로그의 마지막 ``[FAIL]`` 마커 줄 → 장식(━)을 걷은 원인 한 줄."""
    fails = [ln for ln in log_text.splitlines() if "[FAIL]" in ln]
    if not fails:
        return None
    cause = fails[-1].replace("━", "").strip()
    return cause[:_MAX_CAUSE]


def build_message(log_text: str | None, env: dict[str, str]) -> str:
    workflow = env.get("GITHUB_WORKFLOW") or "(알 수 없는 워크플로우)"
    cause = extract_cause(log_text) if log_text else None
    if cause is None:
        cause = "로그에 [FAIL] 마커 없음 — 설치·체크아웃 등 실행 전 단계 실패 또는 타임아웃·취소 가능"
    lines = [
        "🚨 [rs-golden-queens] 워크플로우 실패",
        f"워크플로우: {workflow}",
        f"원인: {cause}",
    ]
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    repo, run_id = env.get("GITHUB_REPOSITORY"), env.get("GITHUB_RUN_ID")
    if repo and run_id:
        lines.append(f"로그: {server}/{repo}/actions/runs/{run_id}")
    return _redact("\n".join(lines), env)


def main(log_path: str | None) -> int:
    from market_flow.telegram_push import send

    log_text = None
    if log_path:
        try:
            log_text = Path(log_path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"⚠️  실패 로그 읽기 실패: {log_path} — {e}")
    text = build_message(log_text, dict(os.environ))
    print(text)
    # 원인 줄에 _ * [ 등이 섞여 Markdown 파싱이 깨지지 않도록 평문으로 보낸다.
    resp = send(text, parse_mode=None)
    return 0 if resp.get("ok") else 1
