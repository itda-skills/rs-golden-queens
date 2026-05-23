"""
http_client.py — urllib 기반 HTTP GET + EUC-KR 디코딩 + UA 헤더

REQ-002: urllib 자체수행 (requests/WebFetch 금지)
REQ-003: EUC-KR → UTF-8 변환
REQ-004: Windows Chrome UA 헤더
EXC-3: 네트워크 오류 처리
EXC-4: 인코딩 실패 처리
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

# Windows Chrome UA (REQ-004)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 10.0


class HttpError(Exception):
    """HTTP 응답 코드 비정상 (4xx/5xx) — exit code 2"""

    def __init__(self, code: int, url: str) -> None:
        super().__init__(f"HTTP {code}: {url}")
        self.code = code
        self.url = url


class NetworkError(Exception):
    """네트워크 연결 실패 / 타임아웃 — exit code 4"""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class EncodingError(Exception):
    """EUC-KR, UTF-8 모두 디코딩 실패 — exit code 5"""
    pass


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT, referer: str | None = None) -> bytes:
    """URL에 GET 요청하여 raw bytes 반환.

    실제 브라우저 요청을 흉내내기 위해 UA 외에 Accept·Accept-Language 기본 헤더를
    함께 보낸다. iframe 호출 시 부모 페이지 URL을 Referer로 전달하면 차단 회피
    안전책이 된다 (네이버 금융은 현재 Referer 없어도 200을 주지만, 변경 가능성 대비).

    Args:
        url: 요청 URL
        timeout: 요청 타임아웃 (초)
        referer: Referer 헤더 (iframe 부모 페이지 URL)

    Returns:
        응답 raw bytes (디코딩은 caller 책임)

    Raises:
        HttpError: HTTP 4xx/5xx 응답
        NetworkError: 연결 실패, 타임아웃
    """
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise HttpError(code=exc.code, url=url) from exc
    except urllib.error.URLError as exc:
        raise NetworkError(detail=str(exc.reason)) from exc
    except socket.timeout as exc:
        raise NetworkError(detail=str(exc)) from exc


def decode_response(raw: bytes) -> str:
    """raw bytes를 UTF-8 문자열로 변환.

    EUC-KR 우선 시도, 실패 시 UTF-8 fallback.
    둘 다 실패하면 EncodingError 발생.

    Args:
        raw: 응답 raw bytes

    Returns:
        UTF-8 문자열

    Raises:
        EncodingError: 두 인코딩 모두 실패
    """
    # 네이버 금융 표준 인코딩
    try:
        return raw.decode("euc-kr")
    except (UnicodeDecodeError, LookupError):
        pass
    # fallback
    try:
        return raw.decode("utf-8")
    except (UnicodeDecodeError, LookupError) as exc:
        raise EncodingError(f"인코딩 실패 (EUC-KR, UTF-8 모두 불가): {exc}") from exc


def fetch_html(url: str, timeout: float = DEFAULT_TIMEOUT, referer: str | None = None) -> str:
    """URL 페치 후 문자열 반환 (fetch + decode_response 합성).

    Args:
        url: 요청 URL
        timeout: 타임아웃 (초)
        referer: Referer 헤더 (iframe 부모 페이지 URL)

    Returns:
        디코딩된 HTML 문자열

    Raises:
        HttpError, NetworkError, EncodingError
    """
    raw = fetch(url, timeout=timeout, referer=referer)
    return decode_response(raw)
