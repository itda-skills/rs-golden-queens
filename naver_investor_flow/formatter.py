"""
formatter.py — json/table/csv 출력 + 디스클레이머

REQ-005: 디스클레이머 고정 문자열
REQ-030: json/table/csv 포맷
REQ-020.3: 단위 명시 (flow_day=억원, deal_rank=백만원+주)
NFR-4: 단위 혼용 금지
NFR-7: 모든 포맷 말미 디스클레이머
AC-6: 단위 스키마 mutually exclusive
AC-7: 세 포맷 모두 disclaimer
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone, timedelta

# SPEC-GOV-STOCK-001 P-1 동형 디스클레이머 (plan.md §3.4 정본)
DISCLAIMER = (
    "본 데이터는 네이버 금융에서 수집한 사실 자료이며, 투자 권유나 추천이 아닙니다. "
    "데이터 정확성·완전성·시의성을 보장하지 않습니다. 투자 결정 전 공식 출처를 확인하세요."
)


def _now_kst() -> str:
    """현재 시각 KST ISO 8601 문자열."""
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def _build_flow_day_envelope(data: list[dict], meta: dict) -> dict:
    """flow_day JSON 구조 생성."""
    merged_meta = {
        "bizdate_requested": meta.get("bizdate_requested"),
        "bizdate_returned": meta.get("bizdate_returned"),
        "source_url": meta.get("source_url", ""),
        "fetched_at": meta.get("fetched_at", _now_kst()),
        "disclaimer": DISCLAIMER,
    }
    return {
        "mode": "flow_day",
        "unit": "억원",
        "meta": merged_meta,
        "data": data,
    }


def _build_deal_rank_envelope(data: list[dict], meta: dict) -> dict:
    """deal_rank JSON 구조 생성."""
    merged_meta = {
        "market": meta.get("market", ""),
        "investor": meta.get("investor", ""),
        "side": meta.get("side", ""),
        "source_url": meta.get("source_url", ""),
        "fetched_at": meta.get("fetched_at", _now_kst()),
        "disclaimer": DISCLAIMER,
    }
    return {
        "mode": "deal_rank",
        "unit_amount": "백만원",
        "unit_quantity": "주",
        "meta": merged_meta,
        "data": data,
    }


def _format_json(mode: str, data: list[dict], meta: dict) -> str:
    """JSON 포맷 출력."""
    if not data:
        return json.dumps(
            {"status": "empty", "data": [], "reason": "데이터 없음"},
            ensure_ascii=False,
            indent=2,
        )
    if mode == "flow_day":
        envelope = _build_flow_day_envelope(data, meta)
    else:
        envelope = _build_deal_rank_envelope(data, meta)
    return json.dumps(envelope, ensure_ascii=False, indent=2)


def _format_table_flow(data: list[dict], meta: dict) -> str:
    """flow_day table 포맷."""
    lines = []
    # 헤더
    header = (
        f"{'날짜':<12} {'개인':>8} {'외국인':>8} {'기관계':>8} "
        f"{'금융투자':>8} {'보험':>6} {'투신':>8} {'은행':>6} "
        f"{'기타금융':>8} {'연기금':>8} {'기타법인':>8}"
    )
    sep = "-" * len(header)
    lines.append(sep)
    lines.append(header)
    lines.append(sep)
    for row in data:
        bd = row["institution_breakdown"]
        line = (
            f"{row['date']:<12} "
            f"{row['individual_eok']:>8,} "
            f"{row['foreign_eok']:>8,} "
            f"{row['institution_total_eok']:>8,} "
            f"{bd['financial_inv']:>8,} "
            f"{bd['insurance']:>6,} "
            f"{bd['trust']:>8,} "
            f"{bd['bank']:>6,} "
            f"{bd['other_finance']:>8,} "
            f"{bd['pension']:>8,} "
            f"{row['foreign_etc_eok']:>8,}"
        )
        lines.append(line)
    lines.append(sep)
    lines.append("단위: 억원")
    lines.append("")
    lines.append(f"disclaimer: {DISCLAIMER}")
    return "\n".join(lines)


def _format_table_rank(data: list[dict], meta: dict) -> str:
    """deal_rank table 포맷."""
    lines = []
    header = f"{'순위':>4} {'종목명':<16} {'코드':>8} {'수량(주)':>12} {'금액(백만원)':>14} {'거래량(주)':>14}"
    sep = "-" * len(header)
    lines.append(sep)
    lines.append(header)
    lines.append(sep)
    for row in data:
        code = row["code"] or "N/A   "
        line = (
            f"{row['rank']:>4} "
            f"{row['name']:<16} "
            f"{code:>8} "
            f"{row['quantity']:>12,} "
            f"{row['amount_mn_krw']:>14,} "
            f"{row['volume']:>14,}"
        )
        lines.append(line)
    lines.append(sep)
    lines.append("단위: 금액=백만원, 수량=주")
    lines.append("")
    lines.append(f"disclaimer: {DISCLAIMER}")
    return "\n".join(lines)


def _format_csv_flow(data: list[dict], meta: dict) -> str:
    """flow_day CSV 포맷 (RFC 4180)."""
    out = io.StringIO()
    writer = csv.writer(out)
    # 헤더
    writer.writerow([
        "date", "individual_eok", "foreign_eok", "institution_total_eok",
        "financial_inv", "insurance", "trust", "bank",
        "other_finance", "pension", "foreign_etc_eok"
    ])
    for row in data:
        bd = row["institution_breakdown"]
        writer.writerow([
            row["date"],
            row["individual_eok"],
            row["foreign_eok"],
            row["institution_total_eok"],
            bd["financial_inv"],
            bd["insurance"],
            bd["trust"],
            bd["bank"],
            bd["other_finance"],
            bd["pension"],
            row["foreign_etc_eok"],
        ])
    # 디스클레이머 행
    writer.writerow(["disclaimer", DISCLAIMER])
    return out.getvalue()


def _format_csv_rank(data: list[dict], meta: dict) -> str:
    """deal_rank CSV 포맷 (RFC 4180)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["rank", "name", "code", "quantity", "amount_mn_krw", "volume"])
    for row in data:
        writer.writerow([
            row["rank"],
            row["name"],
            row["code"] or "",
            row["quantity"],
            row["amount_mn_krw"],
            row["volume"],
        ])
    writer.writerow(["disclaimer", DISCLAIMER])
    return out.getvalue()


def format_output(
    mode: str,
    data: list[dict],
    meta: dict,
    fmt: str = "json",
    limit: int | None = None,
) -> str:
    """통합 출력 포맷터.

    Args:
        mode: "flow_day" 또는 "deal_rank"
        data: 파싱된 dict 리스트
        meta: 메타데이터 dict
        fmt: "json" | "table" | "csv"
        limit: 출력 행 수 제한 (None=전부)

    Returns:
        포맷된 문자열
    """
    if limit is not None and limit > 0:
        data = data[:limit]

    if fmt == "json":
        return _format_json(mode, data, meta)
    elif fmt == "table":
        if not data:
            return f"데이터 없음\n\ndisclaimer: {DISCLAIMER}"
        if mode == "flow_day":
            return _format_table_flow(data, meta)
        else:
            return _format_table_rank(data, meta)
    elif fmt == "csv":
        if not data:
            return f"disclaimer,{DISCLAIMER}\n"
        if mode == "flow_day":
            return _format_csv_flow(data, meta)
        else:
            return _format_csv_rank(data, meta)
    else:
        raise ValueError(f"지원하지 않는 포맷: {fmt}")
