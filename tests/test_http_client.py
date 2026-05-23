"""
M-1: http_client.py 단위 테스트
- UA 헤더 포함 여부
- 200 정상 응답 / EUC-KR 디코딩
- HTTP 404/500 오류 처리
- 네트워크 오류 처리
- 인코딩 실패 처리
- EUC-KR → UTF-8 round-trip
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import urllib.request
import socket

# scripts 디렉토리를 sys.path에 추가
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


class TestFetch(unittest.TestCase):
    """fetch() 함수 테스트"""

    def test_fetch_returns_bytes_on_200(self):
        """정상 200 응답 시 bytes 반환"""
        from naver_investor_flow.http_client import fetch
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html>test</html>"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.status = 200

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch("http://example.com")

        self.assertIsInstance(result, bytes)
        self.assertEqual(result, b"<html>test</html>")

    def _capture_request(self, fetch_kwargs: dict | None = None):
        """fetch 호출 후 captured Request 객체 반환 (헤더 검증용 헬퍼)."""
        from naver_investor_flow.http_client import fetch
        captured = []

        def mock_urlopen(req, timeout):
            captured.append(req)
            mock_response = MagicMock()
            mock_response.read.return_value = b"data"
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            fetch("http://example.com", **(fetch_kwargs or {}))
        return captured[0]

    def test_fetch_includes_referer_when_provided(self):
        """referer 인자가 Referer 헤더로 전달되는지 검증"""
        req = self._capture_request({"referer": "https://finance.naver.com/sise/sise_trans_style.naver"})
        # urllib Request는 헤더 키를 capitalize-first로 정규화함
        headers_lower = {k.lower(): v for k, v in req.headers.items()}
        self.assertEqual(
            headers_lower.get("referer"),
            "https://finance.naver.com/sise/sise_trans_style.naver",
        )

    def test_fetch_omits_referer_by_default(self):
        """referer 인자 미지정 시 Referer 헤더 부재"""
        req = self._capture_request()
        headers_lower = {k.lower(): v for k, v in req.headers.items()}
        self.assertNotIn("referer", headers_lower)

    def test_fetch_includes_browser_accept_headers(self):
        """실제 브라우저 흉내 — Accept·Accept-Language 헤더 기본 포함"""
        req = self._capture_request()
        headers_lower = {k.lower(): v for k, v in req.headers.items()}
        self.assertIn("accept", headers_lower)
        self.assertIn("accept-language", headers_lower)
        self.assertIn("ko", headers_lower["accept-language"].lower())

    def test_fetch_includes_user_agent(self):
        """요청에 Windows Chrome UA 헤더 포함 여부 검증"""
        from naver_investor_flow.http_client import fetch, UA
        captured_request = []

        def mock_urlopen(req, timeout):
            captured_request.append(req)
            mock_response = MagicMock()
            mock_response.read.return_value = b"data"
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            fetch("http://example.com")

        self.assertEqual(len(captured_request), 1)
        req = captured_request[0]
        actual_ua = req.get_header("User-agent")
        self.assertEqual(actual_ua, UA)

    def test_fetch_raises_http_error_on_404(self):
        """404 응답 시 HTTPError 전파"""
        from naver_investor_flow.http_client import fetch, HttpError
        http_err = urllib.error.HTTPError(
            url="http://example.com", code=404,
            msg="Not Found", hdrs=None, fp=None
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with self.assertRaises(HttpError) as ctx:
                fetch("http://example.com")
        self.assertEqual(ctx.exception.code, 404)

    def test_fetch_raises_http_error_on_500(self):
        """500 응답 시 HttpError 전파"""
        from naver_investor_flow.http_client import fetch, HttpError
        http_err = urllib.error.HTTPError(
            url="http://example.com", code=500,
            msg="Internal Server Error", hdrs=None, fp=None
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with self.assertRaises(HttpError) as ctx:
                fetch("http://example.com")
        self.assertEqual(ctx.exception.code, 500)

    def test_fetch_raises_network_error_on_urlerror(self):
        """네트워크 오류 시 NetworkError 전파"""
        from naver_investor_flow.http_client import fetch, NetworkError
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with self.assertRaises(NetworkError):
                fetch("http://example.com")

    def test_fetch_raises_network_error_on_timeout(self):
        """타임아웃 시 NetworkError 전파"""
        from naver_investor_flow.http_client import fetch, NetworkError
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timeout")):
            with self.assertRaises(NetworkError):
                fetch("http://example.com")


class TestDecodeResponse(unittest.TestCase):
    """decode_response() 함수 테스트"""

    def test_decode_euc_kr(self):
        """EUC-KR bytes → UTF-8 문자열 정상 변환"""
        from naver_investor_flow.http_client import decode_response
        # 삼성전자를 EUC-KR로 인코딩
        raw = "삼성전자".encode("euc-kr")
        result = decode_response(raw)
        self.assertEqual(result, "삼성전자")

    def test_decode_utf8_fallback(self):
        """EUC-KR 실패 시 UTF-8 fallback"""
        from naver_investor_flow.http_client import decode_response
        raw = "hello world".encode("utf-8")
        result = decode_response(raw)
        self.assertEqual(result, "hello world")

    def test_decode_euc_kr_korean_mixed(self):
        """한글+영문+숫자 혼합 EUC-KR round-trip"""
        from naver_investor_flow.http_client import decode_response
        text = "HD현대중공업 005380 buy 1,234 삼성전자"
        raw = text.encode("euc-kr")
        result = decode_response(raw)
        self.assertEqual(result, text)

    def test_decode_raises_encoding_error(self):
        """EUC-KR, UTF-8 모두 실패 시 EncodingError 발생"""
        from naver_investor_flow.http_client import decode_response, EncodingError
        # 유효하지 않은 바이트 시퀀스 (EUC-KR도 UTF-8도 아님)
        raw = bytes([0xFF, 0xFE, 0x80, 0x81])
        with self.assertRaises(EncodingError):
            decode_response(raw)

    def test_decode_preserves_unicode_symbols(self):
        """unicode 특수문자 포함 EUC-KR 디코딩"""
        from naver_investor_flow.http_client import decode_response
        # EUC-KR로 표현 가능한 한자 포함
        text = "기타법인 -1,234 +567"
        raw = text.encode("euc-kr")
        result = decode_response(raw)
        self.assertEqual(result, text)

    def test_no_mojibake_in_result(self):
        """결과에 깨진 문자(＊·?) 없음 검증"""
        from naver_investor_flow.http_client import decode_response
        text = "KODEX 200 SK하이닉스 카카오 NAVER"
        raw = text.encode("euc-kr")
        result = decode_response(raw)
        self.assertNotIn("?", result)
        self.assertNotIn("�", result)  # replacement character


class TestConstants(unittest.TestCase):
    """상수 정의 테스트"""

    def test_ua_contains_windows_chrome(self):
        """UA 상수에 Windows Chrome 포함"""
        from naver_investor_flow.http_client import UA
        self.assertIn("Windows NT 10.0", UA)
        self.assertIn("Chrome", UA)

    def test_ua_is_string(self):
        """UA는 문자열"""
        from naver_investor_flow.http_client import UA
        self.assertIsInstance(UA, str)


if __name__ == "__main__":
    unittest.main()
