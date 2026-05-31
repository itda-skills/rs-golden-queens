"""SPEC-MF-TEST-001: kis/client 재시도·예산 단위 테스트 (#10 I8).

_get_json 의 5xx/네트워크/EGW00201 재시도, 4xx 조기반환, wall-clock 예산
(deadline) 차단과 get()/post() 의 degrade 동작을 검증한다. requests.get/post 는
모두 mock 으로 차단하고 sleep/random/monotonic 도 주입해 결정적으로 돌린다.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from kis.client import (
    KISClient,
    _is_rate_limited,
    _KISDeadlineExceeded,
    _KISRateLimited,
    _KISTransient,
)


def _client() -> KISClient:
    """auth 를 mock 해 네트워크·토큰 발급 없이 KISClient 생성."""
    auth = MagicMock()
    auth.base_url = "https://kis.example"
    auth.get_headers.return_value = {}
    return KISClient(auth=auth)


def _resp(status=200, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {} if json_data is None else json_data
    r.text = text
    r.headers = {}
    return r


# ──────────────────────────────────────────────
#  _is_rate_limited
# ──────────────────────────────────────────────


class TestIsRateLimited:
    def test_msg_cd(self):
        assert _is_rate_limited({"msg_cd": "EGW00201", "msg1": "x"}) is True

    def test_msg1_substring(self):
        assert _is_rate_limited({"msg1": "...EGW00201..."}) is True

    def test_normal(self):
        assert _is_rate_limited({"rt_cd": "0"}) is False

    def test_non_dict(self):
        assert _is_rate_limited(None) is False


# ──────────────────────────────────────────────
#  _get_json 재시도
# ──────────────────────────────────────────────


class TestGetJson:
    def test_success_200_single_call(self):
        c = _client()
        with patch(
            "kis.client.requests.get", return_value=_resp(200, {"rt_cd": "0"})
        ) as g:
            resp, data = c._get_json("u", {}, {})
        assert data == {"rt_cd": "0"}
        assert g.call_count == 1

    def test_5xx_then_success(self):
        c = _client()
        with (
            patch(
                "kis.client.requests.get",
                side_effect=[_resp(503, text="busy"), _resp(200, {"rt_cd": "0"})],
            ) as g,
            patch("kis.client.time.sleep") as s,
            patch("kis.client.random.random", return_value=0.0),
        ):
            resp, data = c._get_json("u", {}, {})
        assert data == {"rt_cd": "0"}
        assert g.call_count == 2
        assert s.call_count == 1

    def test_5xx_exhausts_raises_transient(self):
        c = _client()
        with (
            patch("kis.client.requests.get", return_value=_resp(500, text="err")),
            patch("kis.client.time.sleep"),
            patch("kis.client.random.random", return_value=0.0),
        ):
            with pytest.raises(_KISTransient):
                c._get_json("u", {}, {})

    def test_4xx_returns_none_no_retry(self):
        c = _client()
        with (
            patch("kis.client.requests.get", return_value=_resp(403)) as g,
            patch("kis.client.time.sleep") as s,
        ):
            resp, data = c._get_json("u", {}, {})
        assert data is None
        assert resp.status_code == 403
        assert g.call_count == 1
        assert s.call_count == 0

    def test_egw00201_then_success(self):
        c = _client()
        rate = _resp(200, {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당초과"})
        with (
            patch(
                "kis.client.requests.get",
                side_effect=[rate, _resp(200, {"rt_cd": "0"})],
            ) as g,
            patch("kis.client.time.sleep"),
            patch("kis.client.random.random", return_value=0.0),
        ):
            resp, data = c._get_json("u", {}, {})
        assert data == {"rt_cd": "0"}
        assert g.call_count == 2

    def test_egw00201_exhausts_raises_ratelimited(self):
        c = _client()
        rate = _resp(200, {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "x"})
        with (
            patch("kis.client.requests.get", return_value=rate),
            patch("kis.client.time.sleep"),
            patch("kis.client.random.random", return_value=0.0),
        ):
            with pytest.raises(_KISRateLimited):
                c._get_json("u", {}, {})

    def test_timeout_then_success(self):
        c = _client()
        with (
            patch(
                "kis.client.requests.get",
                side_effect=[
                    requests.exceptions.Timeout(),
                    _resp(200, {"rt_cd": "0"}),
                ],
            ) as g,
            patch("kis.client.time.sleep"),
            patch("kis.client.random.random", return_value=0.0),
        ):
            resp, data = c._get_json("u", {}, {})
        assert g.call_count == 2


# ──────────────────────────────────────────────
#  wall-clock 예산(deadline)
# ──────────────────────────────────────────────


class TestBudget:
    def test_deadline_exceeded_skips_network(self):
        c = _client()
        c._deadline = 100.0
        with (
            patch("kis.client.time.monotonic", return_value=200.0),
            patch("kis.client.requests.get") as g,
        ):
            with pytest.raises(_KISDeadlineExceeded):
                c._get_json("u", {}, {})
        assert g.call_count == 0  # 예산 초과 → 네트워크 호출 안 함

    def test_deadline_blocks_retry(self):
        # 진입 시엔 예산 여유, 5xx 후 재시도 직전엔 예산 소진 → 자지 않고 raise
        c = _client()
        with (
            # monotonic: set_budget(0.0) → 진입 _budget_left(0.05) → 재시도전(100.0)
            patch("kis.client.time.monotonic", side_effect=[0.0, 0.05, 100.0]),
            patch("kis.client.requests.get", return_value=_resp(500, text="e")) as g,
            patch("kis.client.time.sleep") as s,
            patch("kis.client.random.random", return_value=1.0),
        ):
            c.set_budget(10.0)
            with pytest.raises(_KISTransient):
                c._get_json("u", {}, {})
        assert g.call_count == 1  # 재시도 안 함
        assert s.call_count == 0  # 자지 않음

    def test_set_budget_none_clears(self):
        c = _client()
        c.set_budget(10.0)
        assert c._deadline is not None
        c.set_budget(None)
        assert c._deadline is None
        assert c._budget_left() is None

    def test_fetch_dataframe_partial_frame_on_deadline(self):
        # page0 성공(tr_cont=M 연속조회) 후 page1 진입 시 예산 소진 → 부분 프레임 반환.
        c = _client()
        page0 = _resp(200, {"rt_cd": "0", "output": [{"a": 1}]})
        page0.headers = {"tr_cont": "M"}
        with (
            # monotonic: set_budget(0.0) → page0 진입(0.05, 여유) → page1 진입(100.0, 소진)
            patch("kis.client.time.monotonic", side_effect=[0.0, 0.05, 100.0]),
            patch("kis.client.requests.get", side_effect=[page0]) as g,
        ):
            c.set_budget(10.0)
            df = c.fetch_dataframe("/api", "TR", {})
        assert len(df) == 1  # page0 부분 프레임만 살아남음
        assert g.call_count == 1  # page1 은 네트워크에 가지 않음


# ──────────────────────────────────────────────
#  get() / post() degrade
# ──────────────────────────────────────────────


class TestGetPost:
    def test_get_5xx_exhausts_returns_error_dict(self):
        c = _client()
        with (
            patch("kis.client.requests.get", return_value=_resp(500, text="e")),
            patch("kis.client.time.sleep"),
            patch("kis.client.random.random", return_value=0.0),
        ):
            out = c.get("/api", "TR", {})
        assert out["rt_cd"] == "-1"

    def test_get_4xx_returns_error_dict(self):
        c = _client()
        with patch("kis.client.requests.get", return_value=_resp(404)) as g:
            out = c.get("/api", "TR", {})
        assert out["rt_cd"] == "-1"
        assert g.call_count == 1

    def test_post_no_retry(self):
        c = _client()
        with patch("kis.client.requests.post", return_value=_resp(500, text="e")) as p:
            out = c.post("/api", "TR", {})
        assert out["rt_cd"] == "-1"
        assert p.call_count == 1  # POST(주문 등)는 비멱등 — 재시도 안 함
