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
            parts.append(_padl(s, widths[i]) if aligns[i] == "r" else _padr(s, widths[i]))
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
            parts.append(_padl(s, widths[i]) if aligns[i] == "r" else _padr(s, widths[i]))
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
    if v is None: return "⚪"
    if v > 0: return "🔴"
    if v < 0: return "🔵"
    return "⚪"


def arrow(v):
    if v is None: return "–"
    if v > 0: return "▲"
    if v < 0: return "▼"
    return "–"


def mark(v):
    return f"{emoji(v)}{arrow(v)}"


def signed(v, fmt="+,d"):
    if v is None: return "-"
    return format(v, fmt)


def signed_pct(v):
    if v is None: return "-"
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
        ["외인", signed(side["foreign"]),       emoji(side["foreign"])],
        ["기관", signed(side["institutional"]), emoji(side["institutional"])],
        ["개인", signed(side["personal"]),      emoji(side["personal"])],
    ]


def _kr_detail_table(detail):
    """기관 세부 (코스피만)."""
    rows = []
    pairs = [
        ("금융투자", "finance"),
        ("보험",     "insurance"),
        ("투신",     "trust"),
        ("은행",     "bank"),
        ("기타금융", "other_fin"),
        ("연기금",   "pension"),
        ("기타법인", "other_corp"),
    ]
    for label, key in pairs:
        v = detail.get(key)
        rows.append([label, signed(v), emoji(v)])
    return rows


def _kr_program_table(side):
    return [
        ["차익",   signed(side["program_arb"]),    emoji(side["program_arb"])],
        ["비차익", signed(side["program_nonarb"]), emoji(side["program_nonarb"])],
        ["합계",   signed(side["program_total"]),  emoji(side["program_total"])],
    ]


def render_kr_daily_html(data):
    """한국장 일간 매매동향 → HTML 문자열 (이미지 렌더용)."""
    from market_flow.render.renderer import render_template

    bizdate = data["bizdate"]
    daily_rows = data.get("kospi_daily") or []
    detail = daily_rows[0] if daily_rows else None

    cum5 = None
    if len(daily_rows) >= 5:
        cum5 = {
            "foreign": sum(r["foreign"] for r in daily_rows[:5]),
            "institutional": sum(r["institutional"] for r in daily_rows[:5]),
            "personal": sum(r["personal"] for r in daily_rows[:5]),
        }

    return render_template(
        "kr_daily.html.j2",
        {
            "weekday": kr_weekday(bizdate),
            "kospi": data["kospi"],
            "kosdaq": data["kosdaq"],
            "detail": detail,
            "cum5": cum5,
        },
    )


def format_kr_daily(data):
    """한국장 일간 매매동향. data = fetchers.naver_kr.fetch_today() 결과"""
    bizdate = data["bizdate"]
    kospi = data["kospi"]
    kosdaq = data["kosdaq"]
    daily_rows = data.get("kospi_daily") or []
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

    if len(daily_rows) >= 5:
        f5 = sum(r["foreign"] for r in daily_rows[:5])
        i5 = sum(r["institutional"] for r in daily_rows[:5])
        p5 = sum(r["personal"] for r in daily_rows[:5])
        L.append("")
        L.append("🔁 *코스피 5거래일 누적*")
        rows = [
            ["외인", signed(f5), emoji(f5)],
            ["기관", signed(i5), emoji(i5)],
            ["개인", signed(p5), emoji(p5)],
        ]
        L.append(_card(rows, ALIGNS))

    return "\n".join(L)


# ───────────────────────────────────────────────
#  미국장
# ───────────────────────────────────────────────

INDICES = [("^GSPC", "S&P500"), ("^IXIC", "나스닥"),
           ("^DJI", "다우"), ("^RUT", "러셀2000")]
VOLATILITY = [("^VIX", "VIX"), ("^VVIX", "VVIX"), ("^SKEW", "SKEW")]
MACRO = [("^TNX", "10Y금리"), ("^TYX", "30Y금리"),
         ("DX-Y.NYB", "DXY"), ("KRW=X", "원달러"),
         ("CL=F", "WTI"), ("GC=F", "금")]
WATCH = [("QQQ", "나스닥100"), ("SMH", "반도체"), ("NLR", "원자력"),
         ("XLE", "에너지"), ("GLD", "금"), ("SLV", "은"),
         ("ITA", "방산"), ("XOVR", "SpaceX")]


def _us_price_table(catalog, source):
    """지수/변동성/매크로 — (라벨, 종가, 등락률, 마크) 4열."""
    rows = []
    for t, _ in catalog:
        d = source.get(t)
        if not d:
            continue
        rows.append([d["label"], f"{d['close']:,.2f}", signed_pct(d["pct"]), emoji(d["pct"])])
    return rows


def render_us_daily_html(data):
    """미국장 마감 요약 → HTML 문자열 (이미지 렌더용)."""
    from market_flow.render.renderer import render_template

    # target 날짜 라벨 추출 (기존 format_us_daily 와 동일 로직)
    target = None
    for cat in ("indices", "watch"):
        for d in (data.get(cat) or {}).values():
            if d and d.get("date"):
                dt = datetime.strptime(d["date"], "%Y-%m-%d")
                target = f"{dt.month}/{dt.day}({'월화수목금토일'[dt.weekday()]})"
                break
        if target:
            break

    def _flatten(catalog, source):
        out = []
        for t, _ in catalog:
            d = source.get(t)
            if not d:
                continue
            out.append({"label": d["label"], "close": d.get("close"), "pct": d.get("pct")})
        return out

    idx = data.get("indices") or {}
    vol = data.get("volatility") or {}
    risk = data.get("risk_onoff") or {}
    mac = data.get("macro") or {}
    sec = data.get("sectors") or {}
    watch_raw = data.get("watch") or {}

    # 위험선호 판정 (기존 로직과 동일)
    risk_label = risk_cls = None
    hyg_pct = ief_pct = 0.0
    hyg = risk.get("HYG")
    ief = risk.get("IEF")
    if hyg and ief:
        hyg_pct, ief_pct = hyg["pct"], ief["pct"]
        diff = hyg_pct - ief_pct
        if diff > 0.2:
            risk_label, risk_cls = "위험선호", "up"
        elif diff < -0.2:
            risk_label, risk_cls = "안전자산", "down"
        else:
            risk_label, risk_cls = "중립", "flat"

    sectors_sorted = sorted(
        [{"label": v["label"], "pct": v["pct"]} for v in sec.values() if v],
        key=lambda x: -(x["pct"] or 0),
    )

    watch_list = []
    for t, _ in WATCH:
        d = watch_raw.get(t)
        if not d:
            continue
        vr = d.get("vol_ratio")
        watch_list.append({
            "ticker": t,
            "label": d["label"],
            "close": d["close"],
            "pct": d["pct"],
            "vol_str": f"×{vr:.2f}" if vr else "-",
            "hot": bool(vr and vr >= 1.5),
        })

    return render_template(
        "us_daily.html.j2",
        {
            "target": target or "",
            "indices": _flatten(INDICES, idx),
            "volatility": _flatten(VOLATILITY, vol),
            "macro": _flatten(MACRO, mac),
            "sectors": sectors_sorted,
            "watch": watch_list,
            "risk_label": risk_label,
            "risk_cls": risk_cls,
            "hyg_pct": hyg_pct,
            "ief_pct": ief_pct,
        },
    )


def format_us_daily(data):
    """미국장 마감 요약. data = fetchers.us_market.fetch_us_close() 결과"""
    target = None
    for cat in ("indices", "watch"):
        for d in (data.get(cat) or {}).values():
            if d and d.get("date"):
                dt = datetime.strptime(d["date"], "%Y-%m-%d")
                target = f"{dt.month}/{dt.day}({'월화수목금토일'[dt.weekday()]})"
                break
        if target: break

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
    L.append("")

    hyg = risk.get("HYG"); ief = risk.get("IEF")
    if hyg and ief:
        diff = hyg["pct"] - ief["pct"]
        if diff > 0.2:
            label = f"🔴▲ *위험선호* (HYG {signed_pct(hyg['pct'])} > IEF {signed_pct(ief['pct'])}, 갭 +{diff:.2f}%p)"
        elif diff < -0.2:
            label = f"🔵▼ *안전자산* (HYG {signed_pct(hyg['pct'])} < IEF {signed_pct(ief['pct'])}, 갭 {diff:.2f}%p)"
        else:
            label = f"⚪– *중립* (HYG {signed_pct(hyg['pct'])} / IEF {signed_pct(ief['pct'])})"
        L.append("💵 *위험선호 (Risk On/Off)*")
        L.append(f"  {label}")
        L.append("")

    L.append("💹 *매크로* _(종가 / 등락)_")
    L.append(_card(_us_price_table(MACRO, mac), PRICE_ALIGNS))
    L.append("")

    L.append("💼 *섹터 (S&P 11)* _(등락 기준 정렬)_")
    sec_rows = [[v["label"], signed_pct(v["pct"]), emoji(v["pct"])]
                for _, v in sorted([(k, v) for k, v in sec.items() if v], key=lambda x: -x[1]["pct"])]
    L.append(_card(sec_rows, ["l", "r", "l"]))
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
        watch_rows.append([
            t,
            d["label"],
            f"${d['close']:,.2f}",
            signed_pct(d["pct"]),
            f"{vr_str}{hot}",
            emoji(d["pct"]),
        ])
    L.append(_card(watch_rows, ["l", "l", "r", "r", "r", "l"]))

    return "\n".join(L)


# ───────────────────────────────────────────────
#  주간
# ───────────────────────────────────────────────

def render_weekly_html(kospi_daily, watch_5d):
    """주간 리포트 → HTML 문자열 (이미지 렌더용)."""
    from market_flow.render.renderer import render_template

    cum = None
    days = 0
    daily_rows = []
    if kospi_daily:
        days = min(5, len(kospi_daily))
        sub = kospi_daily[:days]
        cum = {
            "foreign": sum(r["foreign"] for r in sub),
            "institutional": sum(r["institutional"] for r in sub),
            "personal": sum(r["personal"] for r in sub),
        }
        daily_rows = sub

    watch_sorted = sorted((watch_5d or {}).items(), key=lambda x: -x[1])
    return render_template(
        "weekly.html.j2",
        {
            "today_label": datetime.now().strftime("%m/%d"),
            "cum": cum,
            "days": days,
            "daily_rows": daily_rows,
            "watch_5d": watch_sorted,
        },
    )


def format_weekly(kospi_daily, watch_5d):
    """주간 리포트.
    kospi_daily: 네이버에서 받은 코스피 일별(최대 10개)
    watch_5d: 워치 ETF 최근 N거래일 종가/등락 (yfinance에서 별도 fetch)
    """
    L = [f"📅 *주간 매매동향 리포트* ({datetime.now().strftime('%m/%d')} 기준)", ""]

    if kospi_daily and len(kospi_daily) >= 1:
        days = min(5, len(kospi_daily))
        kospi_daily = kospi_daily[:days]
        f = sum(r["foreign"] for r in kospi_daily)
        i = sum(r["institutional"] for r in kospi_daily)
        p = sum(r["personal"] for r in kospi_daily)
        L.append(f"🇰🇷 *코스피 {days}거래일 누적* (억원)")
        cum_rows = [
            ["외인", signed(f), emoji(f)],
            ["기관", signed(i), emoji(i)],
            ["개인", signed(p), emoji(p)],
        ]
        L.append(_card(cum_rows, ["l", "r", "l"]))
        L.append("")

        L.append("일별 _(일자 · 외인 · 기관)_:")
        daily_rows_t = []
        for r in kospi_daily:
            daily_rows_t.append([
                r["date"],
                signed(r["foreign"]),
                emoji(r["foreign"]),
                signed(r["institutional"]),
                emoji(r["institutional"]),
            ])
        L.append(_card(daily_rows_t, ["l", "r", "l", "r", "l"]))
        L.append("")

    if watch_5d:
        L.append("🇺🇸 *워치 ETF 5거래일 누적 등락*")
        watch_rows = [[ticker, signed_pct(pct), emoji(pct)]
                      for ticker, pct in sorted(watch_5d.items(), key=lambda x: -x[1])]
        L.append(_card(watch_rows, ["l", "r", "l"]))

    return "\n".join(L)
