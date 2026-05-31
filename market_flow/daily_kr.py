"""한국장 일간 매매동향 → 텔레그램 발송

Usage:
  python daily_kr.py            # 오늘
  python daily_kr.py 20260522   # 특정일

SPEC-MF-SCHED-001: 한국 휴장일에는 `[KR] YYYY-MM-DD (요일) 오늘은 휴장입니다`
한 줄 발송. 날짜는 KST 로컬 기준 (REQ-MF-HOL-004).

데이터 정합 (#10 P0-a):
  - E2/I8: KIS 섹터·수급 스크리너를 독립 처리해 하나가 실패해도 다른 하나는 살리고,
    전멸(섹터 0종 / 수급 0건 / 연결 실패)을 본문 경고로 노출한다(조용한 부분실패 차단).
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from market_flow.calendar_utils import format_holiday_message, is_kr_trading_day
from market_flow.fetchers.naver_kr import fetch_today
from market_flow.formatter import format_kr_daily, kr_weekday
from market_flow.publish_channel import maybe_publish, web_link_suffix
from market_flow.publisher import build_holiday_snapshot, build_kr_snapshot
from market_flow.telegram_push import send

_KST = ZoneInfo("Asia/Seoul")


def _warn_block(warnings: list[str]) -> str:
    """경고 목록을 본문 말미에 덧붙일 블록. 비면 빈 문자열."""
    return ("\n\n" + "\n".join(warnings)) if warnings else ""


def _norm_yyyymmdd(s: Optional[str], year_hint: Optional[str] = None) -> Optional[str]:
    """다양한 날짜 표기를 YYYYMMDD 로 정규화.

    '20260529'(YYYYMMDD) → '20260529', '26.05.29'(YY.MM.DD) → '20260529',
    '2026-05-29' → '20260529', '05.29'(MM.DD) → year_hint 의 연도를 붙여 해석.
    형식 불명이거나 MM.DD 인데 year_hint 가 없으면 None.

    Args:
        year_hint: MM.DD 해석에 쓸 기준 날짜(YYYYMMDD 8자리). 데스크탑 일별 추이가
            'MM.DD'로 오므로 요청 bizdate 연도를 붙인다(일별은 요청일 부근이라 안전).
    """
    if not s:
        return None
    digits = s.replace(".", "").replace("-", "").strip()
    if len(digits) == 8 and digits.isdigit():
        return digits
    if len(digits) == 6 and digits.isdigit():  # YY.MM.DD
        return "20" + digits
    if len(digits) == 4 and digits.isdigit() and year_hint and len(year_hint) >= 4:
        return year_hint[:4] + digits  # MM.DD → 요청 연도 + MMDD
    return None


def _build_kr_freshness_warnings(data: dict, req_bizdate: str) -> list[str]:
    """E7 + KIS 날짜 신선도: 데이터 실제 기준일이 요청일과 다르면 경고(사실 안내만).

    - E7: 모바일 당일 합산(kospi/kosdaq)은 날짜 파라미터가 없어 항상 최신값이다.
      과거일 재발송·마감 직후 미갱신 시 제목(요청일)과 어긋나므로 본문에 노출한다.
      코스피·코스닥 두 시장의 bizdate 를 모두 본다.
    - 데스크탑 일별 추이의 최신 행 날짜(MM.DD)도 요청일과 대조한다.
    - KIS 섹터 ETF 데이터의 기준일은 모든 항목을 검사한다(등락률 정렬이라
      첫 항목만으로는 mixed/stale 을 놓친다).
    """
    w: list[str] = []
    req = _norm_yyyymmdd(req_bizdate)
    if not req:
        return w

    # E7: 모바일 투자자별 당일 합산 기준일 (코스피·코스닥 둘 다)
    mobs = set()
    for mk in ("kospi", "kosdaq"):
        m = _norm_yyyymmdd((data.get(mk) or {}).get("bizdate"))
        if m:
            mobs.add(m)
    stale_mob = sorted(d for d in mobs if d != req)
    if stale_mob:
        w.append(
            f"⚠️ 투자자별 당일 합산은 {kr_weekday(stale_mob[0])} 기준 (요청 {kr_weekday(req)})"
        )

    # E7: 데스크탑 일별 추이 최신 행 (MM.DD → 요청 연도로 해석)
    daily = data.get("kospi_daily") or []
    desk = _norm_yyyymmdd(daily[0].get("date"), year_hint=req) if daily else None
    if desk and desk != req:
        w.append(f"⚠️ 일별 추이 최신일은 {kr_weekday(desk)} (요청 {kr_weekday(req)})")

    # KIS 섹터 ETF 기준일 — 모든 항목 검사 (P0-a 로 과거일 재발송은 KIS 스킵 → 오늘만 도달)
    sec_dates = {_norm_yyyymmdd(s.get("date")) for s in (data.get("sectors") or [])}
    stale_sec = sorted(d for d in sec_dates if d and d != req)
    if stale_sec:
        w.append(
            f"⚠️ 섹터 ETF는 {kr_weekday(stale_sec[0])} 기준 (오늘 {kr_weekday(req)})"
        )

    return w


# 한국 수급 항등식 — naver 데스크탑 일별 11컬럼은 파싱이 정상이면 정확히 성립한다:
#   ① 제로섬:   개인 + 외국인 + 기관계 + 기타법인 = 0
#   ② 기관 소계: 금융투자 + 보험 + 투신 + 은행 + 기타금융 + 연기금 = 기관계
# 모바일 당일 합산(kospi/kosdaq)은 기타법인을 파싱하지 않으므로 적용하지 않는다(거짓경고 방지).
# 억원 — 억 단위 반올림 여유. 파싱오류는 수천억대로 어긋나 충분히 탐지된다.
_KR_SUM_TOL = 10
_KR_INST_PARTS = ("finance", "insurance", "trust", "bank", "other_fin", "pension")
_KR_SUM_KEYS = ("personal", "foreign", "institutional", "other_corp", *_KR_INST_PARTS)


def _build_kr_integrity_warnings(data: dict) -> list[str]:
    """I-sum: 데스크탑 일별 행의 수급 항등식으로 파싱 무결성을 자동 점검한다.

    제로섬·기관소계가 허용오차를 크게 벗어나면 E3/E4 류 침묵 파싱오류(셀 정렬
    어긋남·결측 0강제로 인한 누적합 오염 포함)로 보고 본문에 '정합성 의심' 한 줄을
    띄운다(사실 안내만, 시그널 아님). 외부 호출·추가 소스 없음.

    필드가 하나라도 결측(None)인 행은 건너뛴다 — 거짓경고를 내지 않기 위함.
    """
    rows = data.get("kospi_daily") or []
    checked = bad = 0
    for r in rows:
        if any(r.get(k) is None for k in _KR_SUM_KEYS):
            continue
        checked += 1
        zerosum = r["personal"] + r["foreign"] + r["institutional"] + r["other_corp"]
        subsum = sum(r[k] for k in _KR_INST_PARTS)
        if abs(zerosum) > _KR_SUM_TOL or abs(subsum - r["institutional"]) > _KR_SUM_TOL:
            bad += 1
    if checked and bad:
        return [f"⚠️ 수급 데이터 정합성 의심 — 일별 {bad}/{checked}행 합계검증 실패"]
    return []


def _collect_kis_sections(client, data: dict, warnings: list[str]) -> None:
    """KIS 섹터 ETF·동적 수급을 독립적으로 수집해 data 에 채운다.

    섹터와 스크리너를 별도 try 로 감싸 하나가 실패해도 다른 하나는 살린다(E2).
    전멸(섹터 0종 / 수급 0건)은 warnings 에 사실 안내를 추가한다(I8).
    """
    try:
        from market_flow.fetchers.kr_etfs import fetch_kr_sectors

        print("📥 KIS 섹터 ETF 18종 수집 시작")
        sectors = fetch_kr_sectors(client)
        print(f"📊 섹터 ETF 수집 완료 — {len(sectors)}/18종")
        data["sectors"] = sectors
        if len(sectors) == 0:
            warnings.append("⚠️ 섹터 ETF 수집 실패")
        elif len(sectors) < 18:
            warnings.append(f"⚠️ 섹터 ETF {len(sectors)}/18종만 수집")
    except Exception as e:  # noqa: BLE001 — 발송 보호: 섹터 실패가 전체를 막지 않음
        print(f"⚠️  섹터 fetch 실패 (메시지에서 제외): {e}", file=sys.stderr)
        warnings.append("⚠️ 섹터 ETF 수집 실패")

    try:
        from market_flow.fetchers.kr_money_flow import fetch_money_flow_watch

        print("📥 KIS 동적 수급 워치 스크리닝 시작 (top=40)")
        money_flow = fetch_money_flow_watch(
            client, window=1, top=40, etf_show=5, stock_show=5
        )
        n_etf = len(money_flow.get("etfs", []))
        n_stock = len(money_flow.get("stocks", []))
        print(f"📊 동적 워치 완료 — ETF {n_etf}종 + 개별주 {n_stock}종")
        data["money_flow"] = money_flow
        if n_etf == 0 and n_stock == 0:
            warnings.append("⚠️ 수급 스크리닝 결과 없음")
    except Exception as e:  # noqa: BLE001 — 발송 보호: 수급 실패가 전체를 막지 않음
        print(f"⚠️  수급 스크리닝 실패 (메시지에서 제외): {e}", file=sys.stderr)
        warnings.append("⚠️ 수급 스크리닝 실패")

    try:
        from market_flow.fetchers.kr_foreign_inst import fetch_foreign_inst_tally

        print("📥 KIS 외국인·기관 가집계(장중 추정) 수집 시작")
        fi = fetch_foreign_inst_tally(client, show=5)
        n_buy = len(fi.get("buy", []))
        n_sell = len(fi.get("sell", []))
        print(f"📊 가집계 완료 — 순매수 {n_buy}종 + 순매도 {n_sell}종")
        data["foreign_inst"] = fi
        if n_buy == 0 and n_sell == 0:
            warnings.append("⚠️ 가집계 수집 결과 없음")
    except Exception as e:  # noqa: BLE001 — 발송 보호: 가집계 실패가 전체를 막지 않음
        print(f"⚠️  가집계 수집 실패 (메시지에서 제외): {e}", file=sys.stderr)
        warnings.append("⚠️ 가집계 수집 실패")


def main(argv: Optional[list[str]] = None, now: Optional[datetime] = None) -> None:
    if argv is None:
        argv = []
    if now is None:
        now = datetime.now(_KST)

    # argv 로 날짜(YYYYMMDD)가 지정되면 휴장 게이트도 그 날짜 기준으로 판정한다
    # (daily_us 와 동일 패턴). 그래야 휴장일(주말 등)에 과거 거래일을 재발송할 때
    # "오늘이 휴장"이라는 이유로 막히지 않는다.
    if argv:
        now = datetime.strptime(argv[0], "%Y%m%d").replace(tzinfo=_KST)

    # 휴장 게이트: fetcher를 호출하지 않고 한 줄 메시지만 발송
    if not is_kr_trading_day(now):
        date_str = now.astimezone(_KST).strftime("%Y-%m-%d %A")
        print(f"🏖️  한국 휴장일 — {date_str}: 휴장 안내 메시지만 발송")
        msg = format_holiday_message("KR", now)
        send(msg)
        maybe_publish(build_holiday_snapshot("kr", msg, now), now)
        return

    bizdate = argv[0] if argv else now.astimezone(_KST).strftime("%Y%m%d")
    print(f"📥 네이버 한국장 데이터 수집 시작 — bizdate={bizdate}")
    data = fetch_today(bizdate)
    print(
        f"📊 데이터 수집 완료 — keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
    )

    # KIS 기반 섹터 ETF 18종 + 동적 수급 워치 (실패해도 기존 메시지는 정상 발송).
    # KIS fetcher 는 datetime.now() 기준으로만 동작(과거 일자 조회 불가)하므로, argv 로
    # 날짜를 지정한 '과거일 재발송'에서는 제목·스냅샷 일자와 어긋나지 않도록 KIS 섹션을
    # 통째로 스킵한다.
    #   ※ 과거 버그: now 를 argv 날짜로 덮은 뒤 그 now 로 today_kst 를 계산하면
    #     bizdate == today_kst 가 되어 스킵이 무력화됐다. argv 존재로 직접 판정한다.
    data["sectors"] = None
    data["money_flow"] = None
    data["foreign_inst"] = None
    kis_warnings: list[str] = []
    if argv:
        print(
            f"⏭️  KIS 섹션 스킵 — 과거일 재발송(bizdate={bizdate}). "
            f"KIS 는 datetime.now() 기준이라 과거 일자 데이터를 줄 수 없음"
        )
    else:
        client = None
        try:
            from kis import KISClient

            client = KISClient(svr="prod")
        except Exception as e:  # noqa: BLE001 — 발송 보호: KIS 연결 실패가 전체를 막지 않음
            print(f"⚠️  KIS 클라이언트 생성 실패: {e}", file=sys.stderr)
            kis_warnings.append("⚠️ KIS 연결 실패 (섹터·수급·가집계 제외)")
        if client is not None:
            _collect_kis_sections(client, data, kis_warnings)
    if kis_warnings:
        print("⚠️  본문 경고: " + " | ".join(kis_warnings))

    # E7 + KIS 날짜 신선도: 데이터 실제 기준일 ↔ 요청일 경고 (기준일 정합)
    freshness_warnings = _build_kr_freshness_warnings(data, bizdate)
    if freshness_warnings:
        print("⚠️  기준일 경고: " + " | ".join(freshness_warnings))
    # I-sum: 수급 항등식(제로섬·기관소계)으로 파싱 무결성 점검
    integrity_warnings = _build_kr_integrity_warnings(data)
    if integrity_warnings:
        print("⚠️  정합성 경고: " + " | ".join(integrity_warnings), file=sys.stderr)
    # 기준일 → 정합성 → KIS 부분실패 순으로 본문 경고를 쌓는다
    all_warnings = freshness_warnings + integrity_warnings + kis_warnings

    iso_date = (
        f"{bizdate[:4]}-{bizdate[4:6]}-{bizdate[6:]}" if len(bizdate) == 8 else bizdate
    )
    sources = (
        "\n\n출처: "
        f"[네이버 일별](https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate})"
        f" · [모바일 통합](https://m.stock.naver.com/domestic/index/KOSPI/total)"
        f"{web_link_suffix('kr', iso_date)}"
    )

    text = format_kr_daily(data) + _warn_block(all_warnings) + sources
    print(f"📤 Telegram 발송 시작 (텍스트, {len(text)} chars)")
    resp = send(text)

    msg_id = (
        resp.get("result", {}).get("message_id", 0) if isinstance(resp, dict) else 0
    )
    results = resp.get("results", []) if isinstance(resp, dict) else []
    ok_n = sum(1 for r in results if r.get("ok"))
    suffix = f" — 발송 {ok_n}/{len(results)} 성공" if results else ""
    print(f"✅ 한국장 푸시: msg_id={msg_id}, bizdate={bizdate}{suffix}")

    # 발행 단계 (발송과 완전 분리 — 실패해도 위 발송에 영향 없음)
    maybe_publish(build_kr_snapshot(data, now), now)


if __name__ == "__main__":
    main(sys.argv[1:])
