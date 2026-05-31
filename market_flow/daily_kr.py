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

import os
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from market_flow.calendar_utils import format_holiday_message, is_kr_trading_day
from market_flow.fetchers.naver_kr import fetch_today
from market_flow.formatter import format_kr_daily, render_kr_daily_html, kr_weekday
from market_flow.publish_channel import maybe_publish, web_link_suffix
from market_flow.publisher import build_holiday_snapshot, build_kr_snapshot
from market_flow.telegram_push import send, send_photo

_KST = ZoneInfo("Asia/Seoul")


def _is_image_mode() -> bool:
    return os.environ.get("MARKET_FLOW_RENDER", "").strip().lower() == "image"


def _warn_block(warnings: list[str]) -> str:
    """경고 목록을 본문 말미에 덧붙일 블록. 비면 빈 문자열."""
    return ("\n\n" + "\n".join(warnings)) if warnings else ""


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
            kis_warnings.append("⚠️ KIS 연결 실패 (섹터·수급 제외)")
        if client is not None:
            _collect_kis_sections(client, data, kis_warnings)
    if kis_warnings:
        print("⚠️  본문 경고: " + " | ".join(kis_warnings))

    iso_date = (
        f"{bizdate[:4]}-{bizdate[4:6]}-{bizdate[6:]}" if len(bizdate) == 8 else bizdate
    )
    sources = (
        "\n\n출처: "
        f"[네이버 일별](https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={bizdate})"
        f" · [모바일 통합](https://m.stock.naver.com/domestic/index/KOSPI/total)"
        f"{web_link_suffix('kr', iso_date)}"
    )

    if _is_image_mode():
        from market_flow.render.renderer import html_to_png

        print("🖼️  이미지 모드 — HTML→PNG 렌더")
        html = render_kr_daily_html(data)
        png = html_to_png(html)
        caption = (
            f"📊 *{kr_weekday(bizdate)} 마감 매매동향*"
            f"{_warn_block(kis_warnings)}{sources}"
        )
        print(f"📤 Telegram 발송 시작 (사진, {len(png)} bytes)")
        resp = send_photo(png, caption=caption)
    else:
        text = format_kr_daily(data) + _warn_block(kis_warnings) + sources
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
