"""SPEC-MF-TEST-001: market_flow/_retry 단위 테스트 (#10 I8).

retry_call 의 성공/재시도/소진/deadline/should_retry 분기와 백오프 시퀀스,
그리고 retryable_urllib 의 일시 장애 판정을 검증한다. sleep/rand/clock 은 모두
주입해 결정적으로(실 대기 없이) 돌린다.
"""

from __future__ import annotations

import urllib.error

import pytest

from market_flow._retry import retry_call, retryable_urllib


class _Boom(Exception):
    """재시도 대상 합성 예외."""


# ──────────────────────────────────────────────
#  retry_call
# ──────────────────────────────────────────────


class TestRetryCall:
    def test_success_first_try_no_sleep(self):
        sleeps: list[float] = []
        assert retry_call(lambda: 42, sleep=sleeps.append) == 42
        assert sleeps == []

    def test_retries_then_succeeds(self):
        calls = {"n": 0}
        sleeps: list[float] = []

        def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                raise _Boom("transient")
            return "ok"

        result = retry_call(fn, attempts=3, sleep=sleeps.append, rand=lambda: 1.0)
        assert result == "ok"
        assert calls["n"] == 3
        assert len(sleeps) == 2  # 2회 재시도

    def test_exhausts_and_raises_last(self):
        sleeps: list[float] = []

        def fn():
            raise _Boom("always")

        with pytest.raises(_Boom, match="always"):
            retry_call(fn, attempts=3, sleep=sleeps.append, rand=lambda: 0.5)
        assert len(sleeps) == 2

    def test_should_retry_false_raises_immediately(self):
        sleeps: list[float] = []
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise ValueError("nope")

        with pytest.raises(ValueError):
            retry_call(
                fn, attempts=3, should_retry=lambda e: False, sleep=sleeps.append
            )
        assert calls["n"] == 1
        assert sleeps == []

    def test_attempts_one_no_retry(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise _Boom()

        with pytest.raises(_Boom):
            retry_call(fn, attempts=1, sleep=lambda d: None)
        assert calls["n"] == 1

    def test_full_jitter_backoff_sequence(self):
        # rand=1.0 → delay == min(max_delay, base_delay * 2**i)
        sleeps: list[float] = []

        def fn():
            raise _Boom()

        with pytest.raises(_Boom):
            retry_call(
                fn,
                attempts=4,
                base_delay=0.5,
                max_delay=4.0,
                sleep=sleeps.append,
                rand=lambda: 1.0,
            )
        assert sleeps == [0.5, 1.0, 2.0]  # i=0,1,2 (i=3 은 마지막 시도 → raise)

    def test_max_delay_caps_backoff(self):
        sleeps: list[float] = []

        def fn():
            raise _Boom()

        with pytest.raises(_Boom):
            retry_call(
                fn,
                attempts=5,
                base_delay=1.0,
                max_delay=2.0,
                sleep=sleeps.append,
                rand=lambda: 1.0,
            )
        assert sleeps == [1.0, 2.0, 2.0, 2.0]

    def test_jitter_scales_delay(self):
        # rand=0.25 → delay == 0.25 * backoff
        sleeps: list[float] = []

        def fn():
            raise _Boom()

        with pytest.raises(_Boom):
            retry_call(
                fn,
                attempts=3,
                base_delay=1.0,
                max_delay=10.0,
                sleep=sleeps.append,
                rand=lambda: 0.25,
            )
        assert sleeps == [0.25, 0.5]  # 0.25*1.0, 0.25*2.0

    def test_deadline_stops_before_sleep(self):
        sleeps: list[float] = []

        def fn():
            raise _Boom()

        with pytest.raises(_Boom):
            retry_call(
                fn,
                attempts=5,
                base_delay=1.0,
                deadline=0.5,
                sleep=sleeps.append,
                rand=lambda: 1.0,
                clock=lambda: 0.0,
            )
        # 첫 재시도 delay=1.0, clock()+1.0=1.0 >= 0.5 → 자지 않고 즉시 raise
        assert sleeps == []

    def test_invalid_attempts(self):
        with pytest.raises(ValueError):
            retry_call(lambda: 1, attempts=0)


# ──────────────────────────────────────────────
#  retryable_urllib
# ──────────────────────────────────────────────


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://x", code, "msg", {}, None)


class TestRetryableUrllib:
    def test_http_5xx_retryable(self):
        assert retryable_urllib(_http_error(500)) is True
        assert retryable_urllib(_http_error(503)) is True

    def test_http_4xx_not_retryable(self):
        assert retryable_urllib(_http_error(404)) is False
        assert retryable_urllib(_http_error(400)) is False

    def test_http_429_default_true(self):
        assert retryable_urllib(_http_error(429)) is True

    def test_http_429_opt_out(self):
        assert retryable_urllib(_http_error(429), retry_429=False) is False

    def test_urlerror_retryable(self):
        assert retryable_urllib(urllib.error.URLError("down")) is True

    def test_timeout_retryable(self):
        assert retryable_urllib(TimeoutError()) is True

    def test_connection_error_retryable(self):
        assert retryable_urllib(ConnectionError()) is True

    def test_unrelated_not_retryable(self):
        assert retryable_urllib(ValueError()) is False
        assert retryable_urllib(KeyError()) is False
