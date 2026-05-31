"""골든퀸즈봇 텔레그램 발송

환경변수 우선 (GitHub Actions / 로컬 실행 호환):
  1. os.environ — GitHub Actions Secrets / 셸 환경변수
  2. .env 파일 — 로컬 개발

기본 발송은 GOLDENQUEENS_BOT_TOKEN / GOLDENQUEENS_CHAT_ID 를 사용합니다.
MARKET_FLOW_TEST_SEND=1 이면 TEST_GOLDENQUEENS_BOT_TOKEN /
TEST_GOLDENQUEENS_CHAT_ID 를 사용합니다.

GOLDENQUEENS_CHAT_ID 와 TEST_GOLDENQUEENS_CHAT_ID 는 **콤마로 구분된 여러 chat_id** 를 지원합니다.
  예: "42478249"                 → 1곳
      "42478249,-1001234567890"  → 2곳
      "42478249, @channel, 123"  → 3곳 (공백 트림)

부분 실패 정책:
  - 한 chat_id 발송이 실패해도 나머지 chat_id 에 대한 발송은 계속됨
  - 모든 발송 결과는 results 리스트에 기록되며 stderr 에 경고 출력
  - ok 필드는 "전부 성공" 일 때만 True
  - 호출자는 종료 코드를 받지 않음 (best-effort)
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from market_flow._retry import retry_call, retryable_urllib

# .env 파일이 있으면 로드 (로컬 개발용)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass


def _log(msg):
    """telegram_push 내부 진행 로그 (stdout)."""
    print(f"[telegram] {msg}", flush=True)


def _warn(msg):
    """경고 로그 (stderr)."""
    print(f"[telegram] WARN {msg}", file=sys.stderr, flush=True)


def _is_test_send():
    return os.environ.get("MARKET_FLOW_TEST_SEND", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _env_names_for(base_key):
    if not _is_test_send():
        return (base_key,)
    if base_key == "GOLDENQUEENS_BOT_TOKEN":
        return ("TEST_GOLDENQUEENS_BOT_TOKEN",)
    if base_key == "GOLDENQUEENS_CHAT_ID":
        return ("TEST_GOLDENQUEENS_CHAT_ID",)
    return (f"TEST_{base_key}",)


def _env(key):
    val, _ = _env_first((key,))
    return val


def _env_first(keys):
    for key in keys:
        val = os.environ.get(key, "").strip()
        if val:
            return val, key
    label = " 또는 ".join(keys)
    if len(keys) == 1:
        label = keys[0]
    raise RuntimeError(
        f"환경변수 {label} 가 비어있음. "
        f"로컬: .env 파일 / GitHub Actions: repo Secrets 에 등록 필요."
    )


def _bot_token():
    val, _ = _bot_token_with_source()
    return val


def _bot_token_with_source():
    return _env_first(_env_names_for("GOLDENQUEENS_BOT_TOKEN"))


def _chat_id_env_label():
    keys = _env_names_for("GOLDENQUEENS_CHAT_ID")
    return " 또는 ".join(keys) if len(keys) > 1 else keys[0]


def _chat_id_raw():
    val, _ = _chat_id_raw_with_source()
    return val


def _chat_id_raw_with_source():
    return _env_first(_env_names_for("GOLDENQUEENS_CHAT_ID"))


def _chat_ids():
    """GOLDENQUEENS_CHAT_ID 를 콤마로 분리한 리스트 반환.

    빈 값/공백은 제외. 환경변수 자체가 비었거나 유효한 항목이 0개면 RuntimeError.

    예시:
        "42478249"               → ["42478249"]
        "1,2,3"                  → ["1", "2", "3"]
        "1, 2 , 3"               → ["1", "2", "3"]
        "1,,2"                   → ["1", "2"]
        ",1,"                    → ["1"]
        ","                      → RuntimeError
    """
    ids, _ = _chat_ids_with_source()
    return ids


def _chat_ids_with_source():
    raw, source = _chat_id_raw_with_source()
    ids = [s.strip() for s in raw.split(",") if s.strip()]
    if not ids:
        raise RuntimeError(
            f"{_chat_id_env_label()} 에 유효한 chat_id 가 하나도 없음 (콤마만 있거나 빈 항목)"
        )
    return ids, source


def _mask_chat_id(chat_id):
    return _mask_env_value(chat_id)


def _mask_env_value(value, keep=4):
    """로그용 환경변수 값 마스킹. 전체 값은 노출하지 않는다."""
    s = str(value)
    if s == "<unset>":
        return s
    if len(s) <= keep * 2:
        return "*" * len(s)
    return f"{s[:keep]}...{s[-keep:]}"


def _mask_env_values(values):
    return "[" + ", ".join(_mask_env_value(v) for v in values) + "]"


def _is_dry_run():
    return os.environ.get("MARKET_FLOW_DRY_RUN", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


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


def _post_message(token, chat_id, text, parse_mode, disable_notification):
    """단일 chat_id 에 sendMessage 호출. 실패 시 예외 그대로 전파.

    sendMessage 는 비멱등(재전송 시 중복 발송 위험)이라 5xx·네트워크 순단에만
    1회 재시도한다(#10 I8). 4xx·429 는 재시도하지 않는다 — 잘못된 요청은
    재전송해도 같고, 429 는 retry_after 를 무시하면 더 악화된다. 연결 자체가
    실패한 네트워크 오류는 서버 미수신 가능성이 높아 1회 재전송이 안전하다.
    """
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": "true" if disable_notification else "false",
            "disable_web_page_preview": "true",
        }
    ).encode()

    def _once():
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=payload
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())

    return retry_call(
        _once,
        attempts=2,
        should_retry=lambda e: retryable_urllib(e, retry_429=False),
        label=f"telegram:{_mask_chat_id(chat_id)}",
    )


def _aggregate(results):
    """다중 chat_id 발송 결과를 백워드 호환 응답 dict 로 합친다.

    - ok: 전부 성공이면 True, 하나라도 실패면 False
    - result.message_id: 첫 성공의 message_id (기존 호출자 호환)
    - results: per-chat 상세
    """
    all_ok = all(r["ok"] for r in results)
    first_ok = next((r for r in results if r["ok"]), None)
    first_result = first_ok.get("result", {}) if first_ok else {"message_id": 0}
    return {
        "ok": all_ok,
        "result": first_result,
        "results": results,
    }


def send(text, parse_mode="Markdown", disable_notification=False):
    """텔레그램 채널/그룹/개인으로 메시지 발송. 다중 chat_id 지원.

    MARKET_FLOW_DRY_RUN=1 환경변수가 설정된 경우 실제 발송 없이 stdout 출력.

    Returns:
        {"ok": bool, "result": {"message_id": int}, "results": [per-chat ...]}
    """
    if _is_dry_run():
        # dry-run 에서는 chat_id 가 설정되어 있으면 리스트로 표시, 없으면 placeholder
        try:
            ids, chat_id_env = _chat_ids_with_source()
        except RuntimeError:
            ids = ["<unset>"]
            chat_id_env = _chat_id_env_label()
        print("─" * 60)
        print(
            f"[DRY-RUN] chat_id_env={chat_id_env} chat_count={len(ids)} parse_mode={parse_mode} "
            f"silent={disable_notification} text_len={len(text)} chat_ids={_mask_env_values(ids)}"
        )
        print("─" * 60)
        print(_colorize_for_stdout(text))
        print("─" * 60)
        results = [
            {"chat_id": c, "ok": True, "result": {"message_id": 0}, "dry_run": True}
            for c in ids
        ]
        return {
            "ok": True,
            "dry_run": True,
            "result": {"message_id": 0},
            "results": results,
        }

    token, token_env = _bot_token_with_source()
    ids, chat_id_env = _chat_ids_with_source()

    _log(
        f"send() 시작 — token_env={token_env} chat_id_env={chat_id_env} "
        f"token={_mask_env_value(token)} chat_count={len(ids)} "
        f"chat_ids={_mask_env_values(ids)} text_len={len(text)} parse_mode={parse_mode}"
    )

    results = []
    for cid in ids:
        try:
            resp = _post_message(token, cid, text, parse_mode, disable_notification)
            msg_id = (resp.get("result") or {}).get("message_id", 0)
            _log(f"  → chat={_mask_chat_id(cid)} ok=True msg_id={msg_id}")
            results.append(
                {
                    "chat_id": cid,
                    "ok": True,
                    "result": resp.get("result", {"message_id": msg_id}),
                }
            )
        except Exception as e:
            _warn(f"  → chat={_mask_chat_id(cid)} 발송 실패: {type(e).__name__}: {e}")
            results.append(
                {"chat_id": cid, "ok": False, "error": f"{type(e).__name__}: {e}"}
            )

    ok_n = sum(1 for r in results if r["ok"])
    _log(f"send() 완료 — 성공 {ok_n}/{len(results)}")
    return _aggregate(results)


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "🤖 골든퀸즈 알리미 점검 메시지"
    resp = send(text)
    print(
        f"✅ ok={resp['ok']} msg_id={resp['result']['message_id']} results={len(resp['results'])}"
    )
