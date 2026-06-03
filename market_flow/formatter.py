"""텔레그램 메시지 포맷터 — 한국 증시 색 컨벤션 + 구분선형 테이블

🔴▲ = 상승 (양수)
🔵▼ = 하락 (음수)
⚪–  = 보합 / None

각 데이터 섹션은 triple-backtick(pre) 블록으로 감싸서
인라인 코드의 클라이언트별 강조 색(빨강)을 회피하고
등폭 폰트로 정렬되도록 한다.
"""

import unicodedata
from datetime import datetime

# ───────────────────────────────────────────────
#  시각 폭 헬퍼 — CJK/이모지 2칸, ASCII 1칸
# ───────────────────────────────────────────────

# 자주 쓰는 이모지 폭 매핑 (unicodedata만으로는 'N' 분류되어 폭 1로 잘못 잡힘)
_WIDE_EMOJI = set("🔴🔵⚪🔥🇰🇷🇺🇸📊📈📉📅⭐💵💹💼🌡️🔁")
# 카드 컬럼 정렬용 ASCII 별표(⭐ 대비 폭 1)는 그대로 1칸 처리


def _vw(s):
    """문자열의 시각 폭. 등폭 폰트 기준 칸 수."""
    n = 0
    for c in s:
        if c in _WIDE_EMOJI:
            n += 2
        elif unicodedata.east_asian_width(c) in ("W", "F"):
            n += 2
        elif ord(c) >= 0x1F000:  # 기타 이모지 영역
            n += 2
        else:
            n += 1
    return n


def _padr(s, w):
    """우측 공백 패딩 (왼쪽 정렬)."""
    return s + " " * max(0, w - _vw(s))


def _padl(s, w):
    """좌측 공백 패딩 (오른쪽 정렬)."""
    return " " * max(0, w - _vw(s)) + s


def _card(rows, aligns, sep="  "):
    """카드 스타일 블록. 헤더·구분선 없이 행만 출력.

    텔레그램 모노스페이스 폰트는 이모지/한글/숫자가 정확히 등폭이 아니어서
    헤더-데이터 매칭이 어긋난다. 카드 스타일은 헤더를 포기하는 대신
    각 컬럼을 최대폭으로 정렬해 행 내부 일관성만 유지한다.

    rows: [[cell, cell, ...], ...]
    aligns: ['l', 'l', 'r', ...] — l=좌측 정렬, r=우측 정렬
    sep: 컬럼 구분 문자열 (기본 두 칸)
    """
    if not rows:
        return "```\n```"
    cols = len(aligns)
    widths = [0] * cols
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], _vw(str(cell)))
    out = ["```"]
    for r in rows:
        parts = []
        for i, cell in enumerate(r):
            s = str(cell)
            parts.append(
                _padl(s, widths[i]) if aligns[i] == "r" else _padr(s, widths[i])
            )
        out.append(sep.join(parts).rstrip())
    out.append("```")
    return "\n".join(out)


def _table(rows, aligns, header=None, sep_char="─"):
    """등폭 테이블 문자열 생성. triple-backtick 블록까지 포함.

    rows: [[cell, cell, ...], ...]
    aligns: ['l', 'l', 'r', ...] — l=좌측 정렬, r=우측 정렬
    header: [cell, cell, ...] (옵션)
    """
    all_rows = ([header] if header else []) + rows
    cols = len(aligns)
    widths = [0] * cols
    for r in all_rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], _vw(str(cell)))

    def fmt_row(r):
        parts = []
        for i, cell in enumerate(r):
            s = str(cell)
            parts.append(
                _padl(s, widths[i]) if aligns[i] == "r" else _padr(s, widths[i])
            )
        return "  ".join(parts).rstrip()

    out = ["```"]
    if header:
        out.append(fmt_row(header))
        out.append(sep_char * (sum(widths) + 2 * (cols - 1)))
    for r in rows:
        out.append(fmt_row(r))
    out.append("```")
    return "\n".join(out)


# ───────────────────────────────────────────────
#  부호/색 헬퍼
# ───────────────────────────────────────────────


def emoji(v):
    if v is None:
        return "⚪"
    if v > 0:
        return "🔴"
    if v < 0:
        return "🔵"
    return "⚪"


def arrow(v):
    if v is None:
        return "–"
    if v > 0:
        return "▲"
    if v < 0:
        return "▼"
    return "–"


def mark(v):
    return f"{emoji(v)}{arrow(v)}"


def signed(v, fmt="+,d"):
    if v is None:
        return "-"
    return format(v, fmt)


def signed_pct(v):
    if v is None:
        return "-"
    return f"{v:+.2f}%"


def kr_weekday(bizdate):
    """20260522 → 5/22(금)"""
    d = datetime.strptime(bizdate, "%Y%m%d")
    return f"{d.month}/{d.day}({'월화수목금토일'[d.weekday()]})"


# ───────────────────────────────────────────────
#  한국장
# ───────────────────────────────────────────────


def _kr_main_table(side):
    """코스피/코스닥 외인·기관·개인 행. 컬럼: 라벨, 숫자(우측), 마크."""
    return [
        ["외인", signed(side["foreign"]), emoji(side["foreign"])],
        ["기관", signed(side["institutional"]), emoji(side["institutional"])],
        ["개인", signed(side["personal"]), emoji(side["personal"])],
    ]


def _kr_detail_table(detail):
    """기관 세부 (코스피만)."""
    rows = []
    pairs = [
        ("금융투자", "finance"),
        ("보험", "insurance"),
        ("투신", "trust"),
        ("은행", "bank"),
        ("기타금융", "other_fin"),
        ("연기금", "pension"),
        ("기타법인", "other_corp"),
    ]
    for label, key in pairs:
        v = detail.get(key)
        rows.append([label, signed(v), emoji(v)])
    return rows


def _kr_program_table(side):
    return [
        ["차익", signed(side["program_arb"]), emoji(side["program_arb"])],
        ["비차익", signed(side["program_nonarb"]), emoji(side["program_nonarb"])],
        ["합계", signed(side["program_total"]), emoji(side["program_total"])],
    ]


def format_kr_daily(data):
    """한국장 일간 매매동향. data = fetchers.naver_kr.fetch_today() 결과"""
    bizdate = data["bizdate"]
    kospi = data["kospi"]
    kosdaq = data["kosdaq"]
    daily_rows = data.get("kospi_daily") or []
    kosdaq_daily_rows = data.get("kosdaq_daily") or []
    detail = daily_rows[0] if daily_rows else None

    L = []
    L.append(f"📊 *{kr_weekday(bizdate)} 마감 매매동향*")
    L.append("_단위: 억원 (순매수)_")
    L.append("")

    ALIGNS = ["l", "r", "l"]

    L.append("🇰🇷 *코스피*")
    L.append(_card(_kr_main_table(kospi), ALIGNS))
    if detail:
        L.append("기관 세부:")
        L.append(_card(_kr_detail_table(detail), ALIGNS))
    L.append("")

    L.append("🇰🇷 *코스닥*")
    L.append(_card(_kr_main_table(kosdaq), ALIGNS))
    L.append("")

    L.append("📈 *프로그램매매 (코스피)*")
    L.append(_card(_kr_program_table(kospi), ALIGNS))
    L.append("")
    L.append("📈 *프로그램매매 (코스닥)*")
    L.append(_card(_kr_program_table(kosdaq), ALIGNS))

    def _append_daily_block(title, rows):
        if not rows:
            return
        days = min(5, len(rows))
        recent = rows[:days]
        f5 = sum(r["foreign"] for r in recent)
        i5 = sum(r["institutional"] for r in recent)
        p5 = sum(r["personal"] for r in recent)
        L.append("")
        L.append(f"🔁 *{title} {days}거래일 누적*")
        cum_rows = [
            ["외인", signed(f5), emoji(f5)],
            ["기관", signed(i5), emoji(i5)],
            ["개인", signed(p5), emoji(p5)],
        ]
        L.append(_card(cum_rows, ALIGNS))
        L.append(f"{title} 일별 _(일자 · 외인 · 기관)_:")
        trend_rows = [
            [
                r["date"],
                signed(r["foreign"]),
                emoji(r["foreign"]),
                signed(r["institutional"]),
                emoji(r["institutional"]),
            ]
            for r in recent
        ]
        L.append(_card(trend_rows, ["l", "r", "l", "r", "l"]))

    _append_daily_block("코스피", daily_rows)
    _append_daily_block("코스닥", kosdaq_daily_rows)

    # 섹터 ETF (18종)
    sectors = data.get("sectors") or []
    if sectors:
        L.append("")
        L.append("💼 *섹터 ETF (18종)* _(등락 기준 정렬)_")
        rows = []
        for s in sectors:
            vr = s.get("vol_ratio")
            vr_str = f"×{vr:.2f}" if vr else "-"
            hot = "🔥" if vr and vr >= 1.5 else ""
            rows.append(
                [s["label"], signed_pct(s["pct"]), f"{vr_str}{hot}", emoji(s["pct"])]
            )
        L.append(_card(rows, ["l", "r", "l", "l"]))

    # 텔레그램은 수급 상위 5개만 보여준다(웹은 스냅샷의 나머지를 '더보기'로 펼침).
    # 스냅샷엔 fetcher 가 담은 전체(최대 10)가 그대로 들어간다(publisher 별도 경로).
    TG_SHOW = 5
    # 동적 수급 워치 (오늘의 수급 Top)
    money_flow = data.get("money_flow") or {}
    etfs = (money_flow.get("etfs") or [])[:TG_SHOW]
    stocks = (money_flow.get("stocks") or [])[:TG_SHOW]
    if etfs or stocks:
        L.append("")
        L.append("🔥 *오늘의 수급 Top (자동 스크리닝)*")
        L.append(
            "_거래량·거래대금·등락률 상위 후보 · 외인·기관 합산 "
            "(당일/억원, 수량×대표가 환산 추정)_"
        )

    if etfs:
        L.append("")
        L.append("⭐ *ETF Top*")
        L.append(_card(_money_flow_rows(etfs), ["l", "l", "l", "r", "r", "l"]))

    if stocks:
        L.append("")
        L.append("📈 *개별주 Top*")
        L.append(_card(_money_flow_rows(stocks), ["l", "l", "l", "r", "r", "l"]))

    # 외인·기관 순매도 상위 (I1) — 매수 라벨(🔥·grade·Top) 미사용, 금액 사실값만.
    etfs_sell = (money_flow.get("etfs_sell") or [])[:TG_SHOW]
    stocks_sell = (money_flow.get("stocks_sell") or [])[:TG_SHOW]
    if etfs_sell or stocks_sell:
        L.append("")
        L.append("📉 *외인·기관 순매도 상위 (자동 스크리닝)*")
        L.append("_외인·기관 합산이 음수인 종목 (당일/억원, 수량×대표가 환산 추정)_")

    if etfs_sell:
        L.append("")
        L.append("*ETF*")
        L.append(_card(_money_flow_sell_rows(etfs_sell), ["l", "l", "r", "r"]))

    if stocks_sell:
        L.append("")
        L.append("*개별주*")
        L.append(_card(_money_flow_sell_rows(stocks_sell), ["l", "l", "r", "r"]))

    # 외국인·기관 가집계 (장중 추정, KIS FHPTJ04400000) — 확정 아님, 금액 사실값만(I4)
    fi = data.get("foreign_inst") or {}
    fi_buy = (fi.get("buy") or [])[:TG_SHOW]
    fi_sell = (fi.get("sell") or [])[:TG_SHOW]
    if fi_buy or fi_sell:
        L.append("")
        L.append("🏛 *외국인·기관 가집계 (장중 추정)*")
        L.append("_증권사 장중 입력 누계(최종 ~14:30) · 확정 아님 / 단위: 억원_")

    if fi_buy:
        L.append("")
        L.append("*순매수 상위*")
        L.append(_card(_foreign_inst_rows(fi_buy), ["l", "l", "r", "r"]))

    if fi_sell:
        L.append("")
        L.append("*순매도 상위*")
        L.append(_card(_foreign_inst_rows(fi_sell), ["l", "l", "r", "r"]))

    return "\n".join(L)


def _money_flow_rows(items):
    """동적 워치 행: [코드, 종목명(14자), 등급, 외인(억), 기관(억), 🔥]."""
    rows = []
    for r in items:
        name = (r.get("name") or "")[:14]
        grade = r.get("grade") or "-"
        f_eok = r.get("foreign_eok") or 0
        o_eok = r.get("orgn_eok") or 0
        both = "🔥" if r.get("both_buy") else ""
        rows.append(
            [
                r.get("code", "-"),
                name,
                grade,
                f"외{f_eok:+.0f}",
                f"기{o_eok:+.0f}",
                both,
            ]
        )
    return rows


def _money_flow_sell_rows(items):
    """순매도 행: [코드, 종목명(14자), 외인(억), 기관(억)].

    I1 순매도 블록 — 매수 편향 라벨(🔥·grade·Top)을 재사용하지 않는다(codex 주의).
    음수 부호가 그대로 순매도를 나타낸다(시그널 단어 없이 사실값만).
    """
    rows = []
    for r in items:
        name = (r.get("name") or "")[:14]
        f_eok = r.get("foreign_eok") or 0
        o_eok = r.get("orgn_eok") or 0
        rows.append([r.get("code", "-"), name, f"외{f_eok:+.0f}", f"기{o_eok:+.0f}"])
    return rows


def _foreign_inst_rows(items):
    """가집계 행: [코드, 종목명(14자), 외인(억), 기관(억)] — 금액 사실값만(시그널 없이).

    결측(None)은 0 이 아니라 '-' 로 표기한다(가짜 0 방지).
    """
    rows = []
    for r in items:
        name = (r.get("name") or "")[:14]
        f = r.get("foreign_eok")
        o = r.get("orgn_eok")
        f_str = "외-" if f is None else f"외{f:+.0f}"
        o_str = "기-" if o is None else f"기{o:+.0f}"
        rows.append([r.get("code", "-"), name, f_str, o_str])
    return rows


# ───────────────────────────────────────────────
#  미국장
# ───────────────────────────────────────────────

INDICES = [
    ("^GSPC", "S&P500"),
    ("^IXIC", "나스닥"),
    ("^DJI", "다우"),
    ("^RUT", "러셀2000"),
]
# us_market.VOLATILITY 와 동일 순서·라벨 유지 — 텔레그램 렌더 catalog.
# (웹도 발행값의 order(catalog 순서)로 렌더해 텔레그램과 정합한다 — #10.)
VOLATILITY = [
    ("^VIX9D", "VIX 9일"),
    ("^VIX", "VIX 30일"),
    ("^VVIX", "VVIX"),
    ("^SKEW", "SKEW"),
    ("^GVZ", "금변동성"),
    ("^OVX", "유가변동성"),
]
MACRO = [
    ("^TNX", "10Y금리"),
    ("^TYX", "30Y금리"),
    ("DX-Y.NYB", "DXY"),
    ("KRW=X", "원달러"),
    ("CL=F", "WTI"),
    ("GC=F", "금"),
]
WATCH = [
    ("QQQ", "나스닥100"),
    ("SMH", "반도체"),
    ("NLR", "원자력"),
    ("XLE", "에너지"),
    ("GLD", "금"),
    ("SLV", "은"),
    ("ITA", "방산"),
    ("XOVR", "SpaceX"),
]


def _us_price_table(catalog, source):
    """지수/변동성/매크로 — (라벨, 종가, 등락률, 마크) 4열."""
    rows = []
    for t, _ in catalog:
        d = source.get(t)
        if not d:
            continue
        rows.append(
            [d["label"], f"{d['close']:,.2f}", signed_pct(d["pct"]), emoji(d["pct"])]
        )
    return rows


def _risk_lean(value, inverse, tol=0.05):
    """등락(또는 갭)이 정의상 가리키는 위험선호 쪽. 종합 점수·예측이 아니다.

    inverse=True 면 '하락이 위험선호'(VIX·달러·금 같은 공포·안전자산 지표).
    |value| < tol 이면 중립. 결측은 '—'.
    """
    if value is None:
        return "—"
    if abs(value) < tol:
        return "중립"
    riskon_when_up = not inverse
    return "위험선호" if (value > 0) == riskon_when_up else "안전자산"


def _oas_date_label(iso):
    """OAS 관측일 라벨. '2026-05-28' → ' (5/28 기준)'.

    하이일드 OAS 는 T+1 지연으로 미국장 종가일과 다를 수 있어 관측일을 명시한다
    (stale 을 당일 값으로 위장하지 않기 위함). 형식 오류·None 이면 ''.
    """
    if not iso:
        return ""
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
    except (ValueError, TypeError):
        return ""
    return f" ({dt.month}/{dt.day} 기준)"


def _risk_axes(vol, mac):
    """리스크 보조 축(VIX·달러·금) 사실 나열 — [라벨, 등락, 정의상 방향]. 결측은 건너뜀.

    VIX·달러·금은 모두 하락이 위험선호(inverse). 발행된 등락값에서 파생만 한다.
    """
    rows = []
    for label, src, key in (
        ("VIX", vol, "^VIX"),
        ("달러(DXY)", mac, "DX-Y.NYB"),
        ("금", mac, "GC=F"),
    ):
        q = src.get(key)
        pct = q.get("pct") if q else None
        if pct is not None:
            rows.append([label, signed_pct(pct), _risk_lean(pct, inverse=True)])
    return rows


def _vix_term_structure(vol, tol=0.3):
    """VIX 기간구조(9일 vs 30일) — 곡선 형태 사실. 종합 판단·예측이 아니다.

    spread = 30일 − 9일. 30일>9일(spread>tol)=콘탱고(우상향, 평상시),
    9일>30일(spread<-tol)=백워데이션(우하향), |spread|≤tol=평탄.
    9일·30일 종가 중 하나라도 결측이면 None(섹션 자체를 생략).
    """
    short = (vol.get("^VIX9D") or {}).get("close")
    long_ = (vol.get("^VIX") or {}).get("close")
    if short is None or long_ is None:
        return None
    spread = long_ - short
    # 표시 단위(소수 2자리)로 반올림해 분류 — 부동소수로 +0.30p 가 콘탱고로 새지 않게.
    # 웹(VixTermStructure)도 동일하게 round(2) 후 비교(SoT 정합).
    s = round(spread, 2)
    if s > tol:
        shape = "콘탱고"
    elif s < -tol:
        shape = "백워데이션"
    else:
        shape = "평탄"
    return {"short": short, "long": long_, "spread": spread, "shape": shape}


def format_us_daily(data):
    """미국장 마감 요약. data = fetchers.us_market.fetch_us_close() 결과"""
    target = None
    for cat in ("indices", "volatility", "macro", "sectors", "watch", "risk_onoff"):
        for d in (data.get(cat) or {}).values():
            if d and d.get("date"):
                dt = datetime.strptime(d["date"], "%Y-%m-%d")
                target = f"{dt.month}/{dt.day}({'월화수목금토일'[dt.weekday()]})"
                break
        if target:
            break

    idx = data.get("indices") or {}
    vol = data.get("volatility") or {}
    risk = data.get("risk_onoff") or {}
    mac = data.get("macro") or {}
    sec = data.get("sectors") or {}
    watch = data.get("watch") or {}

    L = [f"🇺🇸 *{target} 미국장 마감*", ""]

    PRICE_ALIGNS = ["l", "r", "r", "l"]

    L.append("📊 *주요 지수* _(종가 / 등락)_")
    L.append(_card(_us_price_table(INDICES, idx), PRICE_ALIGNS))
    L.append("")

    L.append("🌡️ *변동성·꼬리위험* _(종가 / 등락)_")
    L.append(_card(_us_price_table(VOLATILITY, vol), PRICE_ALIGNS))
    # VIX 기간구조(I7): 9일 vs 30일 곡선 형태 — 콘탱고/백워데이션 사실. 예측 아님.
    ts = _vix_term_structure(vol)
    if ts:
        L.append(
            f"  _VIX 기간구조: 9일 {ts['short']:,.2f} / 30일 {ts['long']:,.2f} "
            f"→ {ts['shape']} ({ts['spread']:+.2f}p)_"
        )
    L.append("")

    hyg = risk.get("HYG")
    ief = risk.get("IEF")
    oas = data.get("high_yield_oas")
    # 다축 병기(I6): VIX·달러·금이 정의상 가리키는 쪽 — 사실 나열(종합 판단 아님).
    # primary(HYG-IEF) 가 결측이어도 보조축만으로 섹션을 띄운다(웹과 SoT 정합).
    axis_rows = _risk_axes(vol, mac)
    if (hyg and ief) or axis_rows or oas:
        L.append("💵 *위험선호 (Risk On/Off)*")
        if hyg and ief:
            diff = hyg["pct"] - ief["pct"]
            if diff > 0.2:
                label = f"🔴▲ *위험선호* (HYG {signed_pct(hyg['pct'])} > IEF {signed_pct(ief['pct'])}, 갭 +{diff:.2f}%p)"
            elif diff < -0.2:
                label = f"🔵▼ *안전자산* (HYG {signed_pct(hyg['pct'])} < IEF {signed_pct(ief['pct'])}, 갭 {diff:.2f}%p)"
            else:
                label = f"⚪– *중립* (HYG {signed_pct(hyg['pct'])} / IEF {signed_pct(ief['pct'])})"
            L.append(f"  {label}")
        if axis_rows:
            L.append("_리스크 축 (지표 방향이 가리키는 쪽 · 종합 판단·예측 아님)_:")
            L.append(_card(axis_rows, ["l", "r", "l"]))
        # 하이일드 OAS(I6 2nd, FRED): 신용 스프레드 사실값 + 정의상 방향(OAS 상승=
        # 스프레드 확대=안전자산). 종합 판단·예측이 아니다.
        if oas and oas.get("value") is not None:
            val = oas["value"]
            ch = oas.get("change")
            d = _oas_date_label(oas.get("date"))
            if ch is not None:
                # change 는 fetcher 가 소수 2자리로 확정한 발행값 — 여기선 표시만 한다
                # (웹도 동일 값으로 분류 — round 방식 차이로 SoT 가 깨지지 않게).
                lean = _risk_lean(ch, inverse=True, tol=0.01)
                L.append(
                    f"  _하이일드 OAS(신용 스프레드){d}: {val:.2f}%p "
                    f"(전일比 {ch:+.2f}p) → {lean} 쪽_"
                )
            else:
                L.append(f"  _하이일드 OAS(신용 스프레드){d}: {val:.2f}%p_")
        L.append("")

    L.append("💹 *매크로* _(종가 / 등락)_")
    L.append(_card(_us_price_table(MACRO, mac), PRICE_ALIGNS))
    L.append("")

    L.append("💼 *섹터 (S&P 11)* _(등락 정렬 · vs S&P500 · 거래량강도)_")
    sp500_pct = (idx.get("^GSPC") or {}).get("pct")
    sec_rows = []
    for _, v in sorted(
        [(k, v) for k, v in sec.items() if v], key=lambda x: -(x[1]["pct"] or 0)
    ):
        pct = v["pct"]
        # ^GSPC 대비 상대강도(%p) — 같은 날 시장 대비 초과/미달. 둘 다 있을 때만.
        rel = (pct - sp500_pct) if (sp500_pct is not None and pct is not None) else None
        rel_str = f"vs{rel:+.2f}" if rel is not None else "vs-"
        vr = v.get("vol_ratio")
        # vol_ratio=0(유효값)을 결측처럼 '-' 로 떨구지 않는다(웹 ×0.00 과 정합).
        vr_str = f"×{vr:.2f}{'🔥' if vr >= 1.5 else ''}" if vr is not None else "-"
        sec_rows.append([v["label"], signed_pct(pct), emoji(pct), rel_str, vr_str])
    L.append(_card(sec_rows, ["l", "r", "l", "r", "l"]))
    L.append("")

    L.append("⭐ *워치 ETF* _(티커 · 테마 · 종가 · 등락 · 거래량강도)_")
    L.append("_거래량강도 = 당일/5일평균, 1.5↑ = 자금 쏠림 🔥_")
    watch_rows = []
    for t, _ in WATCH:
        d = watch.get(t)
        if not d:
            continue
        vr = d.get("vol_ratio")
        vr_str = f"×{vr:.2f}" if vr else "-"
        hot = "🔥" if vr and vr >= 1.5 else ""
        watch_rows.append(
            [
                t,
                d["label"],
                f"${d['close']:,.2f}",
                signed_pct(d["pct"]),
                f"{vr_str}{hot}",
                emoji(d["pct"]),
            ]
        )
    L.append(_card(watch_rows, ["l", "l", "r", "r", "r", "l"]))

    return "\n".join(L)


# ───────────────────────────────────────────────
#  주간
# ───────────────────────────────────────────────


def format_weekly(kospi_daily, kosdaq_daily, watch_5d):
    """주간 리포트.
    kospi_daily: 네이버에서 받은 코스피 일별(최대 10개)
    kosdaq_daily: KIS에서 받은 코스닥 일별(최대 10개)
    watch_5d: 워치 ETF 최근 N거래일 종가/등락 (yfinance에서 별도 fetch)
    """
    L = [f"📅 *주간 매매동향 리포트* ({datetime.now().strftime('%m/%d')} 기준)", ""]

    def _kr_block(title, daily):
        if not (daily and len(daily) >= 1):
            return
        days = min(5, len(daily))
        rows = daily[:days]
        f = sum(r["foreign"] for r in rows)
        i = sum(r["institutional"] for r in rows)
        p = sum(r["personal"] for r in rows)
        L.append(f"🇰🇷 *{title} {days}거래일 누적* (억원)")
        cum_rows = [
            ["외인", signed(f), emoji(f)],
            ["기관", signed(i), emoji(i)],
            ["개인", signed(p), emoji(p)],
        ]
        L.append(_card(cum_rows, ["l", "r", "l"]))
        L.append("")

        L.append("일별 _(일자 · 외인 · 기관)_:")
        daily_rows_t = []
        for r in rows:
            daily_rows_t.append(
                [
                    r["date"],
                    signed(r["foreign"]),
                    emoji(r["foreign"]),
                    signed(r["institutional"]),
                    emoji(r["institutional"]),
                ]
            )
        L.append(_card(daily_rows_t, ["l", "r", "l", "r", "l"]))
        L.append("")

    _kr_block("코스피", kospi_daily)
    _kr_block("코스닥", kosdaq_daily)

    if watch_5d:
        L.append("🇺🇸 *워치 ETF 5거래일 누적 등락*")
        watch_rows = [
            [ticker, signed_pct(pct), emoji(pct)]
            for ticker, pct in sorted(watch_5d.items(), key=lambda x: -x[1])
        ]
        L.append(_card(watch_rows, ["l", "r", "l"]))

    return "\n".join(L)
