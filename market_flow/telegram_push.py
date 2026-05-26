"""골든퀸즈봇 텔레그램 발송

환경변수 우선 (GitHub Actions 호환):
  1. os.environ — GitHub Actions Secrets
  2. .env 파일 — 로컬 개발
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# .env 파일이 있으면 로드 (로컬 개발용)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass


def _env(key):
    val = os.environ.get(key, "").strip()
    if not val:
        raise RuntimeError(
            f"환경변수 {key} 가 비어있음. "
            f"로컬: .env 파일 / GitHub Actions: repo Secrets 에 등록 필요."
        )
    return val


def _is_dry_run():
    return os.environ.get("MARKET_FLOW_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}


# ANSI 색상 — dry-run stdout 가독성용 (텔레그램 발송 텍스트와 무관)
_ANSI_RED = "\033[31m"
_ANSI_BLUE = "\033[34m"
_ANSI_RESET = "\033[0m"
# +1,234 / -56.78 / +0.5% 등 부호 붙은 수치 매칭 (앞은 공백/문자열시작/`/괄호 등 비숫자)
_SIGNED_NUM_RE = re.compile(r"(?<![\d.])([+\-])([\d][\d,]*(?:\.\d+)?%?)")


def _colorize_for_stdout(text):
    """양수는 빨강, 음수는 파랑 ANSI 색으로 강조 (한국 증시 컨벤션)."""
    if not sys.stdout.isatty():
        return text

    def repl(m):
        sign, num = m.group(1), m.group(2)
        color = _ANSI_RED if sign == "+" else _ANSI_BLUE
        return f"{color}{sign}{num}{_ANSI_RESET}"

    return _SIGNED_NUM_RE.sub(repl, text)


def send(text, parse_mode="Markdown", disable_notification=False):
    """텔레그램 채널/그룹/개인으로 메시지 발송

    MARKET_FLOW_DRY_RUN=1 환경변수가 설정된 경우 실제 발송 없이 stdout 출력.
    """
    if _is_dry_run():
        print("─" * 60)
        print(f"[DRY-RUN] parse_mode={parse_mode} silent={disable_notification}")
        print("─" * 60)
        print(_colorize_for_stdout(text))
        print("─" * 60)
        return {"ok": True, "dry_run": True, "result": {"message_id": 0}}

    token = _env("GOLDENQUEENS_BOT_TOKEN")
    chat_id = _env("GOLDENQUEENS_CHAT_ID")

    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": "true" if disable_notification else "false",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=payload
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def send_photo(image_bytes, caption=None, parse_mode="Markdown", disable_notification=False):
    """텔레그램으로 이미지(PNG bytes) 발송.

    MARKET_FLOW_DRY_RUN=1 환경변수가 설정된 경우 ./out/ 디렉터리에 저장 후 종료.
    """
    if _is_dry_run():
        out_dir = Path.cwd() / "out"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "telegram-preview.png"
        out_path.write_bytes(image_bytes)
        print("─" * 60)
        print(f"[DRY-RUN] sendPhoto → 저장 위치: {out_path}")
        if caption:
            print(f"[DRY-RUN] caption: {caption}")
        print("─" * 60)
        return {"ok": True, "dry_run": True, "result": {"message_id": 0}}

    token = _env("GOLDENQUEENS_BOT_TOKEN")
    chat_id = _env("GOLDENQUEENS_CHAT_ID")

    # multipart/form-data 직접 구성 (urllib 표준 라이브러리만 사용)
    boundary = "----rsgq" + os.urandom(8).hex()
    parts = []

    def add_field(name, value):
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(str(value).encode())
        parts.append(b"\r\n")

    add_field("chat_id", chat_id)
    if caption:
        add_field("caption", caption)
        add_field("parse_mode", parse_mode)
    add_field("disable_notification", "true" if disable_notification else "false")

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="photo"; filename="report.png"\r\n')
    parts.append(b"Content-Type: image/png\r\n\r\n")
    parts.append(image_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(parts)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "🤖 골든퀸즈 알리미 점검 메시지"
    resp = send(text)
    print(f"✅ msg_id={resp['result']['message_id']}")
