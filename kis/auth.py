# -*- coding: utf-8 -*-
"""
KIS Open API 인증 모듈
- .env 파일에서 자격증명 로드 (YAML 불필요)
- OAuth 토큰 자동 발급/캐시/갱신
- 실전/모의투자 환경 전환
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

# 토큰 캐시 경로
_TOKEN_DIR = Path.home() / "KIS" / "config"
_TOKEN_DIR.mkdir(parents=True, exist_ok=True)

# 네트워크 timeout (초). KIS 무응답 시 운영 푸시가 잡 타임아웃까지 차단되는 것을 방지.
HTTP_TIMEOUT = 10


class KISAuth:
    """한국투자증권 API 인증 관리자"""

    # 도메인 설정
    URLS = {
        "prod": "https://openapi.koreainvestment.com:9443",
        "vps": "https://openapivts.koreainvestment.com:29443",
        "ws_prod": "ws://ops.koreainvestment.com:21000",
        "ws_vps": "ws://ops.koreainvestment.com:31000",
    }

    def __init__(self, env_path: str = None, svr: str = "prod"):
        """
        Args:
            env_path: .env 파일 경로 (기본: 프로젝트 루트의 .env)
            svr: "prod" (실전) 또는 "vps" (모의투자)
        """
        self.svr = svr
        self._load_env(env_path)

        self.base_url = self.URLS[svr]
        self.ws_url = self.URLS[f"ws_{svr}"]

        self.app_key = os.environ.get("KIS_APP_KEY", "")
        self.app_secret = os.environ.get("KIS_APP_SECRET", "")
        acct = os.environ.get("KIS_ACCOUNT", "00000000-01")
        parts = acct.split("-")
        self.account_no = parts[0]  # 8자리
        self.product_cd = parts[1] if len(parts) > 1 else "01"  # 2자리

        self.token: str = ""
        self.token_expires: datetime | None = None
        self._ws_approval_key: str = ""
        self._rate_sleep = 0.1 if svr == "prod" else 0.5

    def _load_env(self, env_path: str = None):
        """간단한 .env 파일 로더 (python-dotenv 없이 동작).

        env_path 미지정 시 repo root `.env` 와 `market_flow/.env` 둘 다 시도.
        `os.environ.setdefault` 라서 먼저 잡힌 값이 우선, 환경변수 주입(GitHub
        Actions secrets 등)이 있으면 그게 가장 우선.
        """
        if env_path is not None:
            self._load_env_file(Path(env_path))
            return
        project_root = Path(__file__).resolve().parent.parent
        for candidate in (project_root / ".env",
                          project_root / "market_flow" / ".env"):
            self._load_env_file(candidate)

    @staticmethod
    def _load_env_file(env_file: Path) -> None:
        if not env_file.exists():
            return
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

    # ── OAuth 토큰 ──────────────────────────────────────────────

    def _token_file(self) -> Path:
        return _TOKEN_DIR / f"KIS{datetime.today().strftime('%Y%m%d')}"

    def _read_cached_token(self) -> str | None:
        """로컬 캐시된 토큰 읽기 (YAML 의존성 없이)"""
        tf = self._token_file()
        if not tf.exists():
            return None
        try:
            lines = tf.read_text(encoding="utf-8").strip().splitlines()
            cache = {}
            for line in lines:
                if ": " in line:
                    k, v = line.split(": ", 1)
                    cache[k.strip()] = v.strip()

            token = cache.get("token")
            exp_str = cache.get("valid-date")
            if token and exp_str:
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d %H:%M:%S")
                if exp_dt > datetime.now():
                    return token
        except Exception:
            pass
        return None

    def _save_token(self, token: str, expires: str):
        tf = self._token_file()
        tf.write_text(
            f"token: {token}\nvalid-date: {expires}\n",
            encoding="utf-8",
        )

    def authenticate(self) -> str:
        """OAuth 접근 토큰 발급 (캐시 우선)"""
        cached = self._read_cached_token()
        if cached:
            self.token = cached
            self._update_headers()
            return cached

        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "charset": "UTF-8",
        }
        resp = requests.post(url, json=body, headers=headers, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        self.token = data["access_token"]
        expires = data.get("access_token_token_expired", "")
        if expires:
            self._save_token(self.token, expires)
            self.token_expires = datetime.strptime(expires, "%Y-%m-%d %H:%M:%S")

        self._update_headers()
        return self.token

    def _update_headers(self):
        """인증 후 공통 헤더 갱신"""
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "charset": "UTF-8",
            "authorization": f"Bearer {self.token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "custtype": "P",
        }

    def get_headers(self, tr_id: str, tr_cont: str = "") -> dict:
        """API 호출용 헤더 생성"""
        if not self.token:
            self.authenticate()
        h = dict(self._headers)
        # 모의투자 TR ID 변환
        if self.svr == "vps" and tr_id[0] in ("T", "J", "C"):
            tr_id = "V" + tr_id[1:]
        h["tr_id"] = tr_id
        h["tr_cont"] = tr_cont
        return h

    # ── WebSocket 인증 ───────────────────────────────────────────

    def get_ws_approval_key(self) -> str:
        """WebSocket 접속키 발급"""
        if self._ws_approval_key:
            return self._ws_approval_key

        url = f"{self.base_url}/oauth2/Approval"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret,
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(url, json=body, headers=headers, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        self._ws_approval_key = resp.json()["approval_key"]
        return self._ws_approval_key

    # ── 유틸 ─────────────────────────────────────────────────────

    def smart_sleep(self):
        """Rate limit 대응 슬립"""
        time.sleep(self._rate_sleep)

    def is_paper(self) -> bool:
        return self.svr == "vps"

    def __repr__(self):
        mode = "모의투자" if self.is_paper() else "실전투자"
        return f"KISAuth({mode}, acct={self.account_no}-{self.product_cd})"
