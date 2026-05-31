"""외부 호출 재시도 헬퍼 (#10 I8).

멱등 GET 등 부작용 없는 호출에만 쓴다. 지수 백오프 + full jitter 로 '소스
일시 장애'(네트워크 순단·5xx·레이트리밋)를 흡수하되, 총 대기 상한을 잡
타임아웃 안으로 묶는다(attempts·max_delay·deadline).

재시도는 **갱신지연(stale)을 메우지 못한다** — 같은 직전 거래일 데이터를 다시
받을 뿐이므로, 신선도 검증(daily_us E1·daily_kr E7)과 짝으로 둔다. 부분실패
노출(섹션 미수집 경고)도 retry 소진 후의 잔여 실패를 사용자에게 알리는 짝이다.

표준 라이브러리만 사용한다(tenacity 등 런타임 의존성 추가 없음).
"""

from __future__ import annotations

import random
import sys
import time
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
    deadline: Optional[float] = None,
    should_retry: Optional[Callable[[Exception], bool]] = None,
    label: str = "",
    sleep: Callable[[float], None] = time.sleep,
    rand: Callable[[], float] = random.random,
    clock: Callable[[], float] = time.monotonic,
) -> T:
    """``fn`` 을 최대 ``attempts`` 회 시도한다. **멱등 호출에만** 사용한다.

    Args:
        fn: 인자 없는 콜러블. 부작용이 재실행돼도 안전해야 한다(멱등 GET 등).
        attempts: 총 시도 횟수(최초 포함). 1 이면 재시도 없음, 2 면 1회 재시도.
        base_delay: 지수 백오프 기준(초). i 번째 재시도 전 대기 상한은
            ``min(max_delay, base_delay * 2**i)``.
        max_delay: 회당 대기 상한(초).
        deadline: ``clock()`` 기준 절대 마감 시각(초). 다음 대기가 이를 넘을
            것으로 예상되면 더 자지 않고 마지막 예외를 그대로 raise 한다.
        should_retry: 예외를 받아 재시도 여부를 판정. ``None`` 이면 모든 예외를
            재시도(호출부에서 명시 권장 — 로직 오류까지 재시도하지 않도록).
        label: 로그용 식별자(URL·티커 등). 빈 문자열이면 재시도 로그를 생략.
        sleep/rand/clock: 테스트 주입용(결정성 확보).

    Returns:
        ``fn()`` 의 성공 반환값.

    Raises:
        재시도가 모두 실패하면 **마지막 예외**를 그대로 전파한다.
    """
    if attempts < 1:
        raise ValueError(f"attempts 는 1 이상이어야 한다: {attempts}")

    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — should_retry 로 선별 후 재전파
            is_last = i == attempts - 1
            if is_last or (should_retry is not None and not should_retry(exc)):
                raise
            # full jitter: [0, min(max_delay, base_delay * 2**i))
            backoff = min(max_delay, base_delay * (2**i))
            delay = rand() * backoff
            if deadline is not None and clock() + delay >= deadline:
                # 남은 예산이 없으면 더 자지 않고 현재 실패를 그대로 낸다.
                raise
            if label:
                print(
                    f"⚠️  재시도 {i + 1}/{attempts - 1} ({label}): "
                    f"{type(exc).__name__}: {exc} — {delay:.2f}s 후",
                    file=sys.stderr,
                )
            sleep(delay)

    # 도달 불가: 루프는 항상 return 하거나 raise 한다.
    raise AssertionError("retry_call: unreachable")  # pragma: no cover


def retryable_urllib(exc: Exception, *, retry_429: bool = True) -> bool:
    """urllib 계열 호출의 '일시 장애' 판정 (네트워크 순단·서버 5xx·429).

    4xx(429 제외)는 요청 자체의 문제라 재시도하지 않는다. ``HTTPError`` 는
    ``URLError`` 의 서브클래스이므로 먼저 검사한다.

    Args:
        retry_429: 429(Too Many Requests)를 재시도 대상에 포함할지. 네이버 등
            멱등 GET 은 True, 비멱등 POST(telegram)는 retry_after 무시 위험이
            있어 False 로 둔다.
    """
    import urllib.error

    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or (retry_429 and exc.code == 429)
    if isinstance(exc, urllib.error.URLError):
        return True  # DNS/연결 실패 등 네트워크 순단
    # TimeoutError(=socket.timeout 별칭, py3.10+)·연결 리셋 등 저수준 OS 오류
    return isinstance(exc, (TimeoutError, ConnectionError))
