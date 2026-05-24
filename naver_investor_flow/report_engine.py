"""Telegram 일일 보고서 렌더링 엔진 (SPEC-REPORT-001).

stdlib-only slot-fill 렌더러. 외부 마크다운 템플릿(`templates/daily_report.md`)을
읽어 컨텍스트 dict 의 슬롯을 `str.format(**ctx)` 으로 채운다.

설계 결정:
- 외부 템플릿 엔진(Jinja2/Mako 등) 일체 사용 금지 [HARD]
- 단위 비대칭(flow_day=억원, deal_rank=백만원) 보존 [HARD]
- 실패 시 (`FileNotFoundError`, `OSError`, `UnicodeDecodeError`, `KeyError`)
  `_build_report_fallback(context)` 로 폴백하며 stderr 1줄 경고 (REQ-004)
- 디스크 영속화 금지: 결과는 호출자에게 반환만, 파일 쓰기 없음

@MX:NOTE: SPEC-REPORT-001 슬롯 채우기 템플릿 렌더러 모듈
@MX:ANCHOR: collect.main 및 tests/test_collect_render.py, tests/test_report_engine.py 가 호출하는 공개 API 경계
@MX:REASON: 보고서 양식의 단일 진실 공급원이며, 변경 시 byte-for-byte 동등성이 깨질 위험 존재
"""

from __future__ import annotations

import json
import os
import sys
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

# -----------------------------------------------------------------------------
# 라벨/조합 — collect.py 에서 이전 (포맷팅 계층 관심사)
# -----------------------------------------------------------------------------

# 8조합 순서 (보고서 표시 순)
DEAL_RANK_COMBOS: list[tuple[str, str, str]] = [
    ("kospi", "foreign", "buy"),
    ("kospi", "foreign", "sell"),
    ("kospi", "institution", "buy"),
    ("kospi", "institution", "sell"),
    ("kosdaq", "foreign", "buy"),
    ("kosdaq", "foreign", "sell"),
    ("kosdaq", "institution", "buy"),
    ("kosdaq", "institution", "sell"),
]

LABEL_MARKET = {"kospi": "KOSPI", "kosdaq": "KOSDAQ"}
LABEL_INVESTOR = {"foreign": "외국인", "institution": "기관"}
LABEL_SIDE = {"buy": "매수", "sell": "매도"}

# 안전 기본값 (REQ-003, Edge Case 8)
_DEFAULT_CONFIG = {"flow_day_rows": 5, "rank_top_n": 3}

_TEMPLATES_PKG = "naver_investor_flow.templates"
_DEFAULT_TEMPLATE_NAME = "daily_report.md"
_CONFIG_NAME = "context-config.json"


# -----------------------------------------------------------------------------
# 숫자 포맷터 (단위 비대칭은 호출 위치에서 보장)
# -----------------------------------------------------------------------------

def _fmt_eok(v: int) -> str:
    """억원 부호 포함 천단위 콤마."""
    return f"{v:+,}"


def _fmt_mn(v: int) -> str:
    """백만원 부호 포함."""
    return f"{v:+,}"


# -----------------------------------------------------------------------------
# 템플릿/설정 로드 (REQ-001, REQ-003)
# -----------------------------------------------------------------------------

def _resolve_template_path() -> Path | None:
    """템플릿 경로 결정. ENV 우선, 그다음 패키지 기본값.

    @MX:NOTE: NIF_TEMPLATE_PATH 는 운영자가 신뢰하는 절대 경로로 가정한다.
    개인용 cron 단일 사용자 모델이므로 traversal 검증은 수행하지 않는다.
    """
    env_path = os.environ.get("NIF_TEMPLATE_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    # 패키지 기본값 — importlib.resources 로 접근
    try:
        ref = resources.files(_TEMPLATES_PKG) / _DEFAULT_TEMPLATE_NAME
        # ref.read_text 가능 여부로 존재 확인 — 경로 객체로 반환
        return Path(str(ref))
    except (ModuleNotFoundError, FileNotFoundError):
        return None


def _load_template(path: Path) -> str:
    """템플릿 파일을 UTF-8 로 읽는다. 실패 시 예외 전파(REQ-004 가 catch)."""
    return path.read_text(encoding="utf-8")


def _load_config() -> dict[str, int]:
    """context-config.json 로드. 실패 시 안전 기본값 반환 + stderr 경고 (Edge Case 8)."""
    try:
        ref = resources.files(_TEMPLATES_PKG) / _CONFIG_NAME
        raw = ref.read_text(encoding="utf-8")
        data = json.loads(raw)
        # 누락 키는 기본값으로 보충
        out = dict(_DEFAULT_CONFIG)
        for key in _DEFAULT_CONFIG:
            if key in data and isinstance(data[key], int):
                out[key] = data[key]
        return out
    except (FileNotFoundError, OSError, json.JSONDecodeError, ModuleNotFoundError) as e:
        print(f"[report_engine] context-config.json 로드 실패 ({type(e).__name__}): 기본값 사용", file=sys.stderr)
        return dict(_DEFAULT_CONFIG)


# -----------------------------------------------------------------------------
# 슬롯 빌더 — flow_day / deal_rank 마크다운 블록 생성
# -----------------------------------------------------------------------------

def _build_flow_day_table(flow_rows: list[dict], limit: int) -> str:
    """일별 시장 매매 마크다운 블록. 단위 억원. 헤더 1줄 + 본문 N줄.

    @MX:NOTE: 단위 '억원' 은 본 함수 내부에서만 사용한다 — deal_rank 와 단위 비대칭 유지.
    """
    lines: list[str] = ["▎일별 시장 매매 (억원, 부호=순매수)"]
    if not flow_rows:
        lines.append("  (데이터 없음)")
    else:
        for row in flow_rows[:limit]:
            lines.append(
                f"  {row['date']}  "
                f"개인 {_fmt_eok(row['individual_eok'])} / "
                f"외국인 {_fmt_eok(row['foreign_eok'])} / "
                f"기관계 {_fmt_eok(row['institution_total_eok'])}"
            )
    return "\n".join(lines)


def _build_rank_section(market: str, investor: str, side: str, rows: list[dict], top_n: int) -> str:
    """단일 조합 랭킹 섹션. 단위 백만원. 헤더 1줄 + 본문 N줄.

    @MX:NOTE: 단위 '백만원' 은 본 함수 내부에서만 사용한다 — flow_day 와 단위 비대칭 유지.
    """
    header = f"▎{LABEL_MARKET[market]} {LABEL_INVESTOR[investor]} {LABEL_SIDE[side]} TOP3 (백만원)"
    lines: list[str] = [header]
    if not rows:
        lines.append("  (데이터 없음)")
    else:
        for i, r in enumerate(rows[:top_n], start=1):
            code = r.get("code") or "------"
            lines.append(f"  {i}. {r['name']} ({code})  {_fmt_mn(r['amount_mn_krw'])}")
    return "\n".join(lines)


def _build_rank_sections_block(
    rank_results: Iterable[tuple[tuple[str, str, str], list[dict]]],
    top_n: int,
) -> str:
    """8개 조합 섹션을 DEAL_RANK_COMBOS 순서로 조합. 각 섹션 사이에 빈 줄."""
    sections: list[str] = []
    for combo, rows in rank_results:
        market, investor, side = combo
        sections.append(_build_rank_section(market, investor, side, rows, top_n))
    # 레거시 build_report 는 각 섹션 뒤에 빈 줄 1개를 둔다 — 마지막 섹션 뒤에도 빈 줄
    return "\n\n".join(sections) + "\n"


# -----------------------------------------------------------------------------
# 컨텍스트 구성 / 렌더링
# -----------------------------------------------------------------------------

def build_context(
    flow_rows: list[dict],
    rank_results: list[tuple[tuple[str, str, str], list[dict]]],
    *,
    bizdate: str,
    fetched_at: str,
) -> dict[str, Any]:
    """렌더 컨텍스트 dict 조립. 모든 슬롯을 채워서 반환.

    조합 검증: rank_results 가 8개 미만이면 누락된 조합은 빈 리스트로 채운다.
    """
    cfg = _load_config()
    flow_limit = cfg["flow_day_rows"]
    rank_top_n = cfg["rank_top_n"]

    # rank_results 를 dict 로 인덱싱 (누락 조합은 빈 리스트)
    rank_map: dict[tuple[str, str, str], list[dict]] = {combo: rows for combo, rows in rank_results}
    normalized = [(combo, rank_map.get(combo, [])) for combo in DEAL_RANK_COMBOS]

    ctx: dict[str, Any] = {
        # Header
        "title_emoji": "📊",
        "bizdate": bizdate,
        "fetched_at": fetched_at,
        # Flow day
        "flow_day_table": _build_flow_day_table(flow_rows, flow_limit),
        "flow_day_rows_limit": flow_limit,
        # Rank — composite (default 템플릿이 사용)
        "rank_sections_block": _build_rank_sections_block(normalized, rank_top_n),
        "rank_top_n": rank_top_n,
        # Footer
        "divider": "─────────",
        "disclaimer": "출처: finance.naver.com (사실 데이터, 투자 권유 아님)",
    }

    # Per-section 슬롯 — 사용자 커스텀 템플릿이 선택적으로 사용 (Option B)
    for combo, rows in normalized:
        market, investor, side = combo
        key = f"rank_{market}_{investor}_{side}_top"
        ctx[key] = _build_rank_section(market, investor, side, rows, rank_top_n)

    return ctx


def render(context: dict[str, Any]) -> str:
    """템플릿을 로드해 슬롯을 채워 반환. 실패 시 fallback.

    REQ-001/REQ-004 준수:
    - ENV 또는 패키지 기본 템플릿 로드
    - str.format(**context) 로 슬롯 채움
    - 임의의 (FileNotFoundError, OSError, UnicodeDecodeError, KeyError) 시
      stderr 에 1줄 경고 출력 후 `_build_report_fallback(context)` 반환
    """
    path = _resolve_template_path()
    try:
        if path is None or not path.exists():
            raise FileNotFoundError(str(path) if path else "<unresolved>")
        template = _load_template(path)
        return template.format(**context)
    except FileNotFoundError as e:
        print(f"[report_engine] 템플릿 파일 없음: {e} — fallback 사용", file=sys.stderr)
    except UnicodeDecodeError as e:
        print(f"[report_engine] 템플릿 디코드 실패 ({path}): {e} — fallback 사용", file=sys.stderr)
    except KeyError as e:
        # str.format 이 발생시키는 KeyError — e.args[0] 가 누락 슬롯명
        missing = e.args[0] if e.args else "<unknown>"
        print(f"[report_engine] 템플릿에 슬롯 누락: '{missing}' — fallback 사용", file=sys.stderr)
    except OSError as e:
        print(f"[report_engine] 템플릿 I/O 오류 ({path}): {e} — fallback 사용", file=sys.stderr)
    return _build_report_fallback(context)


# -----------------------------------------------------------------------------
# 레거시 fallback — collect.build_report 본문을 verbatim 으로 이전
# (REQ-004 가 보존을 요구하므로 삭제 금지)
# -----------------------------------------------------------------------------

# @MX:LEGACY: 기존 collect.build_report 의 본문을 그대로 보존
# @MX:REASON: SPEC-REPORT-001 REQ-004 의 fallback 계약 — 템플릿 실패 시 단일 진실
# @MX:NOTE: 컨텍스트 dict 만 받도록 시그니처 변경. 내부 합성 로직은 변경 없음.
def _build_report_fallback(context: dict[str, Any]) -> str:
    """레거시 inline-build 경로. 컨텍스트 dict 로부터 마크다운을 직접 합성.

    REQ-004: 템플릿 로드/렌더 실패 시 호출되며, 출력은 SPEC-REPORT-001 도입 전
    `collect.build_report` 의 출력과 byte-for-byte 동등하다.
    """
    bizdate = context["bizdate"]
    fetched_at = context["fetched_at"]
    flow_day_table = context["flow_day_table"]
    rank_sections_block = context["rank_sections_block"]
    divider = context["divider"]
    disclaimer = context["disclaimer"]

    lines: list[str] = []
    lines.append(f"📊 네이버 투자자 매매동향 — 기준일 {bizdate} (KST)")
    lines.append(f"수집 시각: {fetched_at}")
    lines.append("")
    # flow_day_table 은 헤더 + 본문 (개행 포함된 단일 블록)
    lines.append(flow_day_table)
    lines.append("")
    # rank_sections_block 은 8개 섹션이 빈 줄로 구분되고 끝에 \n 1개가 붙은 단일 블록.
    # 레거시 build_report 는 각 섹션 + 빈 줄 패턴이었으므로, 통째로 한 줄로 join 한 뒤
    # 마지막에 divider/disclaimer 가 붙는다.
    # 레거시는 마지막 섹션 뒤에 빈 줄("")이 lines 에 들어간 뒤 divider 가 추가됨.
    # rank_sections_block 끝의 "\n" 이 마지막 빈 줄 역할을 하도록 구성.
    lines.append(rank_sections_block.rstrip("\n"))
    lines.append("")
    lines.append(divider)
    lines.append(disclaimer)
    return "\n".join(lines)
