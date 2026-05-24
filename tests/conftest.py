"""pytest 설정 — 패키지 root를 sys.path에 추가하여 `naver_investor_flow` import 가능하게."""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_configure(config):
    """커스텀 마커 등록 — PytestUnknownMarkWarning 방지."""
    config.addinivalue_line(
        "markers",
        "live: 실제 네이버 금융 서버에 네트워크 호출을 수행하는 라이브 스모크 테스트",
    )
