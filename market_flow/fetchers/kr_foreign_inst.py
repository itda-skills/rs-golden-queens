"""한국 외국인·기관 매매종목 가집계 — KIS FHPTJ04400000 래퍼.

증권사가 장중 집계·입력한 단순 누계(가집계=장중 추정치, 확정 아님). 네이티브 순매수
거래대금(억원)을 반환해 동적 워치의 '수량×종가' 근사를 피하고 1콜로 끝낸다.
순매수/순매도 상위를 각각 뽑되, 금액 사실값만 담는다(시그널 단어 없이).
"""

from __future__ import annotations

import math

from kis import KISClient

# KIS 가집계 응답 컬럼 (FHPTJ04400000 output)
_CODE = "mksc_shrn_iscd"
_NAME = "hts_kor_isnm"
_FRGN = "frgn_ntby_tr_pbmn"  # 외국인 순매수 거래대금(원)
_ORGN = "orgn_ntby_tr_pbmn"  # 기관계 순매수 거래대금(원)
_BOGUS_CODES = {"", "nan", "none", "<na>", "null"}


def _to_eok(v):
    """원 단위 문자열/숫자 → 억원(소수1). 파싱 불가·NaN·Inf 는 None."""
    try:
        x = float(str(v).replace(",", "").strip()) / 1e8
    except (ValueError, TypeError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, 1)


def _rows(df, show):
    """가집계 응답 DataFrame → 표시용 레코드 리스트. 스키마 미인식이면 빈 리스트.

    가짜 코드 행을 먼저 거른 뒤 show 개를 채운다(무효 행이 top 슬롯을 먹지 않게).
    순매수/순매도 부호는 KIS '순매수 거래대금(ntby)' 의미상 부호 있는 값을 그대로
    쓴다(순매도상위면 음수). ※ 실 API 부호 관례는 첫 실발송 로그로 확인 권장.
    """
    if df is None or getattr(df, "empty", True):
        return []
    if _CODE not in df.columns or (_FRGN not in df.columns and _ORGN not in df.columns):
        return []
    out = []
    for _, r in df.iterrows():
        code = str(r.get(_CODE, "")).strip()
        if code.lower() in _BOGUS_CODES:
            continue
        frgn = _to_eok(r.get(_FRGN))
        orgn = _to_eok(r.get(_ORGN))
        combined = None if (frgn is None or orgn is None) else round(frgn + orgn, 1)
        out.append(
            {
                "code": code,
                "name": str(r.get(_NAME, "")).strip(),
                "foreign_eok": frgn,
                "orgn_eok": orgn,
                "combined_eok": combined,
            }
        )
        if len(out) >= show:
            break
    return out


def fetch_foreign_inst_tally(client: KISClient | None = None, show: int = 5) -> dict:
    """외국인·기관 매매종목 가집계(장중 추정) — 순매수/순매도 Top.

    Returns:
        {"buy": [...], "sell": [...]} — 각 항목은 code·name·외인/기관/합산(억원).
        가집계 = 증권사 장중 입력 누계(최종 ~14:30, 확정 아님). 사실 금액만.
    """
    if client is None:
        client = KISClient(svr="prod")
    # div=1 금액정렬, sort 0:순매수상위 / 1:순매도상위, etc=0 전체(외인+기관)
    buy = _rows(client.foreign_institution_total(div="1", sort="0"), show)
    sell = _rows(client.foreign_institution_total(div="1", sort="1"), show)
    return {"buy": buy, "sell": sell}
