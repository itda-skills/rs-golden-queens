"""pytest 설정 — 패키지 root를 sys.path에 추가하여 `naver_investor_flow` import 가능하게."""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
