"""pytest 공통 설정 (SPEC-MF-TEST-001 + SPEC-MF-SCHED-001 공용).

역할:
- ``market_flow/`` 디렉터리를 ``sys.path`` 에 추가하여 ``import formatter``,
  ``import daily_kr``, ``from fetchers.naver_kr import ...`` 형태로 접근 가능하게 한다.
- ``@pytest.mark.live`` 마커 등록 + 기본 실행 시 자동 deselect 훅
  (REQ-MF-TEST-002).
- 환경변수 누수 차단 autouse 픽스처 — ``MARKET_FLOW_DRY_RUN`` /
  ``GOLDENQUEENS_BOT_TOKEN`` / ``GOLDENQUEENS_CHAT_ID`` / ``MARKET_SCHEDULE``
  을 매 테스트 시작 시 초기화 (REQ-MF-TEST-NEG-001).
- 합성 fixture 로더 — 네이버/yfinance 응답을 ``tests/fixtures/`` 에서 로드.

NOTE: 기존 SPEC-MF-SCHED-001 테스트(``tests/test_calendar_utils.py`` 등)는
``market_flow/`` 가 sys.path 에 추가되어야 ``import daily_kr`` 가 동작한다.
본 SPEC 추가 시 이 패턴을 보존한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ──────────────────────────────────────────────────────────────────
#  sys.path 설정 — market_flow 패키지를 평탄(flat) import 가능하게
# ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_MARKET_FLOW = _ROOT / "market_flow"
if str(_MARKET_FLOW) not in sys.path:
    sys.path.insert(0, str(_MARKET_FLOW))

# fixture 파일 경로
_FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ──────────────────────────────────────────────────────────────────
#  live 마커 등록 + 자동 deselect (REQ-MF-TEST-002)
# ──────────────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    """``live`` 마커를 pytest 에 등록한다."""
    config.addinivalue_line(
        "markers",
        "live: 실제 네트워크 호출 테스트 (기본 실행에서 자동 deselect)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """기본 실행에서 ``@pytest.mark.live`` 부착 테스트를 자동 skip.

    - ``pytest`` (마커 없음): live 자동 skip
    - ``pytest -m live``: live 만 실행 (deselect 훅이 미동작)
    - ``pytest -m "not live"``: live 자동 skip (이미 -m 으로 필터됨)
    """
    marker_expr = config.getoption("-m") or ""
    # 사용자가 ``-m`` 으로 live 를 명시했으면 그대로 진행
    if "live" in marker_expr and "not live" not in marker_expr:
        return
    skip_live = pytest.mark.skip(
        reason="기본 실행에서 live 테스트는 자동 제외 (-m live 로 명시)"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


# ──────────────────────────────────────────────────────────────────
#  환경변수 누수 차단 autouse 픽스처 (REQ-MF-TEST-NEG-001)
# ──────────────────────────────────────────────────────────────────

_ISOLATED_ENV_KEYS = (
    "MARKET_FLOW_DRY_RUN",
    "GOLDENQUEENS_BOT_TOKEN",
    "GOLDENQUEENS_CHAT_ID",
    "MARKET_SCHEDULE",
)


@pytest.fixture(autouse=True)
def _isolate_market_flow_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """매 테스트 시작 시 market_flow 관련 환경변수를 제거한다.

    monkeypatch 가 테스트 종료 시 자동으로 원복하므로, 테스트가
    setenv 로 설정한 값이 다음 테스트에 누수되지 않는다.
    """
    for key in _ISOLATED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


# ──────────────────────────────────────────────────────────────────
#  합성 fixture 로더 (REQ-MF-TEST-010)
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fixtures_dir() -> Path:
    """``tests/fixtures/`` 절대 경로."""
    return _FIXTURES


@pytest.fixture
def naver_mobile_kospi_json(fixtures_dir: Path) -> str:
    """네이버 모바일 KOSPI 응답 (raw JSON 문자열)."""
    return (fixtures_dir / "naver_kr" / "mobile_kospi.json").read_text(
        encoding="utf-8"
    )


@pytest.fixture
def naver_mobile_kosdaq_json(fixtures_dir: Path) -> str:
    """네이버 모바일 KOSDAQ 응답 (raw JSON 문자열)."""
    return (fixtures_dir / "naver_kr" / "mobile_kosdaq.json").read_text(
        encoding="utf-8"
    )


@pytest.fixture
def naver_intraday_html(fixtures_dir: Path) -> str:
    """네이버 데스크탑 시간별 추세 HTML (utf-8 디코딩된 문자열)."""
    return (fixtures_dir / "naver_kr" / "intraday.html").read_text(
        encoding="utf-8"
    )


@pytest.fixture
def naver_daily_html(fixtures_dir: Path) -> str:
    """네이버 데스크탑 일별 추세 HTML (utf-8 디코딩된 문자열)."""
    return (fixtures_dir / "naver_kr" / "daily.html").read_text(
        encoding="utf-8"
    )


@pytest.fixture
def naver_mobile_kospi_dict(naver_mobile_kospi_json: str) -> dict:
    """KOSPI 모바일 응답을 dict 로 파싱."""
    return json.loads(naver_mobile_kospi_json)
