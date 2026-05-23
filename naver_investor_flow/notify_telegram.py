"""Telegram 전송 모듈 — stdlib only.

환경변수:
- TELEGRAM_BOT_TOKEN: BotFather 발급 토큰
- TELEGRAM_CHAT_ID: 수신 chat ID (개인·그룹·채널 모두 가능)

둘 다 있어야 전송. 하나라도 비면 no-op (stdout 출력은 collect.py 책임).
이 분리로 로컬 호출(키 없음)·CI 호출(키 있음) 모두 동일 코드 경로 사용.

Telegram sendMessage API: https://core.telegram.org/bots/api#sendmessage
- 메시지 최대 4096자
- parse_mode 선택: None(plain text·안전), Markdown, MarkdownV2, HTML
- 본 모듈은 plain text 사용 — 종목명 특수문자(예: `KODEX 200선물인버스2X`) 이스케이프 부담 회피
"""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.telegram.org"
MAX_MESSAGE_CHARS = 4096
DEFAULT_TIMEOUT = 10.0


class TelegramConfig:
    """환경변수 기반 텔레그램 설정."""

    def __init__(self, token: str | None, chat_id: str | None) -> None:
        self.token = token
        self.chat_id = chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.token) and bool(self.chat_id)

    @classmethod
    def from_env(cls, env: dict | None = None) -> "TelegramConfig":
        env = env if env is not None else os.environ
        return cls(
            token=env.get("TELEGRAM_BOT_TOKEN") or None,
            chat_id=env.get("TELEGRAM_CHAT_ID") or None,
        )


def truncate_for_telegram(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    """Telegram 메시지 길이 제한에 맞게 자른다. 끝에 잘렸음 표시 추가."""
    if len(text) <= limit:
        return text
    marker = "\n…(잘림)"
    return text[: limit - len(marker)] + marker


def send_message(
    text: str,
    config: TelegramConfig | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """텔레그램으로 메시지 전송.

    Args:
        text: 보낼 본문
        config: TelegramConfig (None이면 환경변수 기반 자동 생성)
        timeout: HTTP 타임아웃 (초)

    Returns:
        True: 전송 성공
        False: 설정 비활성 또는 전송 실패 (실패 시 stderr에 사유 출력)
    """
    cfg = config if config is not None else TelegramConfig.from_env()
    if not cfg.enabled:
        return False

    payload = urllib.parse.urlencode({
        "chat_id": cfg.chat_id,
        "text": truncate_for_telegram(text),
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    url = f"{API_BASE}/bot{cfg.token}/sendMessage"
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else {}
            if not parsed.get("ok", False):
                print(
                    f"[notify_telegram] API ok=false: {parsed.get('description', body)}",
                    file=sys.stderr,
                )
                return False
            return True
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        print(
            f"[notify_telegram] HTTP {exc.code}: {body[:200]}",
            file=sys.stderr,
        )
        return False
    except (urllib.error.URLError, socket.timeout) as exc:
        print(f"[notify_telegram] 네트워크 오류: {exc}", file=sys.stderr)
        return False
