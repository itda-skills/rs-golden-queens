"""SPEC-MF-TEST-001: formatter 단위 테스트.

market_flow/formatter.py 의 시각 폭 헬퍼 / 색·부호 헬퍼 / 테이블 렌더 /
요일 표시 / 한국·미국·주간 포맷터의 결정론적 출력 동작을 검증한다.
외부 의존성 없음 — 순수 함수.
"""

from __future__ import annotations

import pytest

from market_flow import formatter as F  # noqa: E402

# ──────────────────────────────────────────────
#  시각 폭 헬퍼 (_vw / _padr / _padl)
# ──────────────────────────────────────────────


class TestVw:
    def test_ascii_single_char_is_width_1(self):
        assert F._vw("a") == 1

    def test_ascii_string_is_sum_of_chars(self):
        assert F._vw("hello") == 5

    def test_cjk_char_is_width_2(self):
        assert F._vw("한") == 2

    def test_cjk_string_is_sum(self):
        assert F._vw("한국어") == 6

    @pytest.mark.parametrize("emoji", list("🔴🔵⚪🔥📊📈📉📅⭐💵💹💼🔁"))
    def test_known_wide_emoji_is_width_2(self, emoji):
        assert F._vw(emoji) == 2

    def test_high_codepoint_emoji_is_width_2(self):
        # \U0001F680 (rocket) — _WIDE_EMOJI 에 없지만 ord >= 0x1F000
        assert F._vw("\U0001f680") == 2

    def test_mixed_string_combines_widths(self):
        # "📊 외인" = 이모지(2) + 공백(1) + 한글 2자(4) = 7
        assert F._vw("📊 외인") == 7

    def test_empty_string_is_zero(self):
        assert F._vw("") == 0


class TestPadding:
    def test_padr_pads_with_spaces_on_right(self):
        assert F._padr("ab", 5) == "ab   "

    def test_padl_pads_with_spaces_on_left(self):
        assert F._padl("ab", 5) == "   ab"

    def test_padr_with_cjk_uses_visual_width(self):
        # 한글 폭 2 → 4칸 폭이 되려면 공백 2개
        assert F._padr("한", 4) == "한  "

    def test_padl_with_cjk_uses_visual_width(self):
        assert F._padl("한", 4) == "  한"

    def test_padr_no_padding_when_already_wider(self):
        assert F._padr("hello", 3) == "hello"

    def test_padl_no_padding_when_already_wider(self):
        assert F._padl("hello", 3) == "hello"


# ──────────────────────────────────────────────
#  부호·색 헬퍼 (emoji / arrow / mark / signed / signed_pct)
# ──────────────────────────────────────────────


class TestEmojiArrowMark:
    @pytest.mark.parametrize(
        "v,expected",
        [
            (100, "🔴"),
            (1, "🔴"),
            (-1, "🔵"),
            (-1000, "🔵"),
            (0, "⚪"),
            (None, "⚪"),
        ],
    )
    def test_emoji_by_sign(self, v, expected):
        assert F.emoji(v) == expected

    @pytest.mark.parametrize(
        "v,expected",
        [
            (100, "▲"),
            (-1, "▼"),
            (0, "–"),
            (None, "–"),
        ],
    )
    def test_arrow_by_sign(self, v, expected):
        assert F.arrow(v) == expected

    def test_mark_combines_emoji_and_arrow(self):
        assert F.mark(100) == "🔴▲"
        assert F.mark(-1) == "🔵▼"
        assert F.mark(0) == "⚪–"
        assert F.mark(None) == "⚪–"


class TestSigned:
    def test_signed_positive_uses_plus_prefix_and_comma(self):
        assert F.signed(1234) == "+1,234"

    def test_signed_negative_keeps_minus(self):
        assert F.signed(-1234) == "-1,234"

    def test_signed_zero_uses_plus_zero(self):
        assert F.signed(0) == "+0"

    def test_signed_none_returns_dash(self):
        assert F.signed(None) == "-"


class TestSignedPct:
    def test_signed_pct_positive(self):
        assert F.signed_pct(1.5) == "+1.50%"

    def test_signed_pct_negative(self):
        assert F.signed_pct(-2.345) == "-2.35%"

    def test_signed_pct_zero(self):
        assert F.signed_pct(0) == "+0.00%"

    def test_signed_pct_none(self):
        assert F.signed_pct(None) == "-"


# ──────────────────────────────────────────────
#  요일 (kr_weekday)
# ──────────────────────────────────────────────


class TestKrWeekday:
    def test_monday(self):
        # 2026-05-25 은 월요일
        assert F.kr_weekday("20260525") == "5/25(월)"

    def test_friday(self):
        # 2026-05-29 은 금요일
        assert F.kr_weekday("20260529") == "5/29(금)"

    def test_sunday(self):
        # 2026-05-31 은 일요일
        assert F.kr_weekday("20260531") == "5/31(일)"


# ──────────────────────────────────────────────
#  _table — triple-backtick 블록 렌더
# ──────────────────────────────────────────────


class TestTable:
    def test_starts_and_ends_with_triple_backticks(self):
        out = F._table([["a", "b"]], ["l", "l"], header=["H1", "H2"])
        lines = out.split("\n")
        assert lines[0] == "```"
        assert lines[-1] == "```"

    def test_with_header_includes_separator_line(self):
        out = F._table([["a", "b"]], ["l", "l"], header=["H1", "H2"])
        lines = out.split("\n")
        # ``` / 헤더 / sep / 행 / ```
        assert len(lines) == 5
        assert lines[1].startswith("H1")
        # separator 는 ─ 문자만
        assert set(lines[2]) == {"─"}

    def test_without_header_has_no_separator(self):
        out = F._table([["a", "b"]], ["l", "l"])
        lines = out.split("\n")
        # ``` / 행 / ```
        assert len(lines) == 3
        # separator 라인 없음
        assert "─" not in out

    def test_right_align_pads_on_left(self):
        out = F._table([["12345", "1"]], ["l", "r"])
        # 두 번째 셀이 우측 정렬 — 첫 행의 두 번째 셀 폭과 동일하게 패딩
        lines = out.split("\n")
        # rstrip 으로 우측 공백이 제거되어 셀 1 그대로
        assert lines[1].rstrip().endswith("1")

    def test_custom_sep_char(self):
        out = F._table([["a"]], ["l"], header=["H"], sep_char="=")
        lines = out.split("\n")
        assert set(lines[2]) == {"="}


# ──────────────────────────────────────────────
#  format_kr_daily
# ──────────────────────────────────────────────


def _make_kr_side(prefix=1):
    """코스피/코스닥 한 쪽(side) 데이터 빌더."""
    return {
        "foreign": 100 * prefix,
        "institutional": 200 * prefix,
        "personal": -300 * prefix,
        "program_arb": 10 * prefix,
        "program_nonarb": 20 * prefix,
        "program_total": 30 * prefix,
    }


def _make_daily_row(date, scale=1):
    return {
        "date": date,
        "personal": -100 * scale,
        "foreign": 50 * scale,
        "institutional": 50 * scale,
        "finance": 10 * scale,
        "insurance": 5 * scale,
        "trust": 5 * scale,
        "bank": 5 * scale,
        "other_fin": 5 * scale,
        "pension": 10 * scale,
        "other_corp": 10 * scale,
    }


class TestFormatKrDaily:
    def test_contains_required_structure_tokens(self):
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(1),
            "kosdaq": _make_kr_side(2),
            "kospi_daily": [],
        }
        out = F.format_kr_daily(data)
        # 구조 토큰
        assert "📊" in out
        assert "마감 매매동향" in out
        assert "단위: 억원" in out
        assert "🇰🇷" in out
        assert "코스피" in out
        assert "코스닥" in out
        assert "📈" in out
        assert "프로그램매매" in out
        # triple-backtick 블록 4개 이상 (코스피/기관세부X/코스닥/프로그램2)
        assert out.count("```") >= 8  # 시작·끝 짝수

    def test_5day_section_when_at_least_5_rows(self):
        rows = [_make_daily_row(f"05.{20 + i:02d}", scale=i + 1) for i in range(5)]
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": rows,
        }
        out = F.format_kr_daily(data)
        assert "5거래일 누적" in out
        assert "🔁" in out

    def test_no_5day_section_when_fewer_than_5_rows(self):
        rows = [_make_daily_row("05.25") for _ in range(3)]
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": rows,
        }
        out = F.format_kr_daily(data)
        assert "5거래일 누적" not in out

    def test_includes_detail_table_when_daily_rows_present(self):
        # daily_rows 가 1개라도 있으면 detail = daily_rows[0] → 기관 세부 표 출력
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [_make_daily_row("05.25")],
        }
        out = F.format_kr_daily(data)
        assert "기관 세부" in out
        assert "금융투자" in out

    # ── 섹터 ETF 18종 ──
    def test_no_sector_section_when_missing(self):
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
        }
        out = F.format_kr_daily(data)
        assert "섹터 ETF" not in out

    def test_sector_section_when_present(self):
        sectors = [
            {
                "code": "091160",
                "label": "반도체",
                "close": 35000.0,
                "pct": 2.5,
                "vol_ratio": 1.6,
                "trade_value_eok": 500.0,
                "date": "20260525",
            },
            {
                "code": "132030",
                "label": "금",
                "close": 13000.0,
                "pct": -1.2,
                "vol_ratio": 0.9,
                "trade_value_eok": 200.0,
                "date": "20260525",
            },
        ]
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "sectors": sectors,
        }
        out = F.format_kr_daily(data)
        assert "💼" in out
        assert "섹터 ETF (18종)" in out
        assert "반도체" in out
        assert "+2.50%" in out
        assert "🔥" in out  # vol_ratio 1.6 → 🔥 표시
        assert "-1.20%" in out

    def test_sector_section_handles_none_vol_ratio(self):
        sectors = [
            {
                "code": "091160",
                "label": "반도체",
                "close": 35000.0,
                "pct": 1.0,
                "vol_ratio": None,
                "trade_value_eok": None,
                "date": "20260525",
            },
        ]
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "sectors": sectors,
        }
        # vol_ratio None 이어도 예외 없이 렌더되어야 함
        out = F.format_kr_daily(data)
        assert "섹터 ETF" in out

    # ── 동적 수급 워치 ──
    def test_no_money_flow_section_when_empty(self):
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "money_flow": {"etfs": [], "stocks": []},
        }
        out = F.format_kr_daily(data)
        assert "오늘의 수급 Top" not in out
        assert "ETF Top" not in out
        assert "개별주 Top" not in out

    def test_money_flow_etf_only(self):
        mf = {
            "etfs": [
                {
                    "code": "396500",
                    "name": "TIGER 반도체TOP10",
                    "grade": "B",
                    "foreign_eok": -19.0,
                    "orgn_eok": 688.0,
                    "both_buy": False,
                },
            ],
            "stocks": [],
        }
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "money_flow": mf,
        }
        out = F.format_kr_daily(data)
        assert "오늘의 수급 Top" in out
        assert "ETF Top" in out
        assert "개별주 Top" not in out
        assert "396500" in out
        assert "TIGER 반도체TOP10" in out

    def test_money_flow_both_sections_and_fire_marker(self):
        mf = {
            "etfs": [
                {
                    "code": "462330",
                    "name": "KODEX 2차전지",
                    "grade": "B",
                    "foreign_eok": 23.0,
                    "orgn_eok": 334.0,
                    "both_buy": True,
                },
            ],
            "stocks": [
                {
                    "code": "417010",
                    "name": "나노팀",
                    "grade": "S",
                    "foreign_eok": 54.0,
                    "orgn_eok": 0.0,
                    "both_buy": False,
                },
            ],
        }
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "money_flow": mf,
        }
        out = F.format_kr_daily(data)
        assert "ETF Top" in out
        assert "개별주 Top" in out
        assert "🔥" in out  # both_buy True → 🔥
        assert "나노팀" in out

    def test_money_flow_handles_missing_keys(self):
        # KIS 응답 일부 키 누락에도 예외 없이 렌더
        mf = {
            "etfs": [
                {"code": "000000", "name": "X"},  # grade·foreign_eok·orgn_eok 없음
            ],
            "stocks": [],
        }
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "money_flow": mf,
        }
        out = F.format_kr_daily(data)
        assert "ETF Top" in out

    def test_money_flow_sell_block_no_buy_labels(self):
        # I1: 순매도 블록은 매수 라벨(🔥·grade·"Top")을 재사용하지 않고 금액만 노출
        mf = {
            "etfs": [],
            "stocks": [],
            "etfs_sell": [
                {
                    "code": "069500",
                    "name": "KODEX 200",
                    "foreign_eok": -700.0,
                    "orgn_eok": -200.0,
                    "combined_eok": -900.0,
                },
            ],
            "stocks_sell": [
                {
                    "code": "005930",
                    "name": "삼성전자",
                    "foreign_eok": -500.0,
                    "orgn_eok": -150.0,
                    "combined_eok": -650.0,
                    "grade": "GRADEX",  # 순매도 렌더에서 무시되어야 할 매수 개념(sentinel)
                    "both_buy": True,
                },
            ],
        }
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "money_flow": mf,
        }
        out = F.format_kr_daily(data)
        assert "순매도 상위" in out
        assert "삼성전자" in out and "005930" in out
        assert "외-700" in out and "기-200" in out  # 음수 부호 = 순매도 사실값
        # 매수 편향 라벨(🔥·grade·"Top")이 순매도에 재사용되지 않는다(codex 주의)
        assert "오늘의 수급 Top" not in out
        assert "Top" not in out
        assert "🔥" not in out  # both_buy=True 여도 순매도 렌더는 무시
        assert "GRADEX" not in out  # grade 값이 순매도 행에 렌더되지 않음

    def test_money_flow_sell_absent_when_no_sells(self):
        mf = {"etfs": [], "stocks": [], "etfs_sell": [], "stocks_sell": []}
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "money_flow": mf,
        }
        out = F.format_kr_daily(data)
        assert "순매도 상위" not in out

    def test_foreign_inst_tally_section_labeled_provisional(self):
        # I4: 가집계 섹션은 '장중 추정' 라벨 + 금액만(시그널 단어 없이)
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "foreign_inst": {
                "buy": [
                    {
                        "code": "005930",
                        "name": "삼성전자",
                        "foreign_eok": 700.0,
                        "orgn_eok": 300.0,
                        "combined_eok": 1000.0,
                    }
                ],
                "sell": [
                    {
                        "code": "000660",
                        "name": "SK하이닉스",
                        "foreign_eok": -500.0,
                        "orgn_eok": -100.0,
                        "combined_eok": -600.0,
                    }
                ],
            },
        }
        out = F.format_kr_daily(data)
        assert "가집계" in out and "장중 추정" in out  # 추정 라벨 필수
        assert "삼성전자" in out and "외+700" in out
        assert "SK하이닉스" in out and "외-500" in out  # 순매도 음수 그대로

    def test_no_foreign_inst_section_when_empty(self):
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "foreign_inst": {"buy": [], "sell": []},
        }
        assert "가집계" not in F.format_kr_daily(data)

    def test_foreign_inst_none_renders_dash_not_zero(self):
        # 결측(None) 금액은 '-' 로 — 가짜 0(외+0) 금지
        data = {
            "bizdate": "20260525",
            "kospi": _make_kr_side(),
            "kosdaq": _make_kr_side(),
            "kospi_daily": [],
            "foreign_inst": {
                "buy": [
                    {
                        "code": "005930",
                        "name": "삼성전자",
                        "foreign_eok": None,
                        "orgn_eok": 300.0,
                        "combined_eok": None,
                    }
                ],
                "sell": [],
            },
        }
        out = F.format_kr_daily(data)
        assert "외-" in out  # None → '-'
        assert "외+0" not in out  # 가짜 0 아님


# ──────────────────────────────────────────────
#  format_us_daily
# ──────────────────────────────────────────────


def _us_entry(label, close=100.0, pct=1.0, vol_ratio=1.0, date="2026-05-22"):
    return {
        "label": label,
        "close": close,
        "pct": pct,
        "vol_ratio": vol_ratio,
        "date": date,
    }


def _build_us_data(hyg_pct=0.3, ief_pct=0.0):
    return {
        "indices": {
            "^GSPC": _us_entry("S&P500", close=5000.0, pct=0.5),
            "^IXIC": _us_entry("나스닥", close=16000.0, pct=0.8),
            "^DJI": _us_entry("다우", close=39000.0, pct=0.3),
            "^RUT": _us_entry("러셀2000", close=2000.0, pct=-0.2),
        },
        "volatility": {
            "^VIX": _us_entry("VIX", close=15.0, pct=-2.0),
            "^VVIX": _us_entry("VVIX", close=80.0, pct=-1.0),
            "^SKEW": _us_entry("SKEW", close=140.0, pct=0.5),
        },
        "risk_onoff": {
            "HYG": _us_entry("고수익채권", pct=hyg_pct),
            "IEF": _us_entry("7-10Y국채", pct=ief_pct),
        },
        "macro": {
            "^TNX": _us_entry("10Y금리", close=4.5, pct=0.5),
        },
        "sectors": {
            "XLK": _us_entry("기술", close=200.0, pct=1.2),
            "XLF": _us_entry("금융", close=50.0, pct=0.6),
        },
        "watch": {
            "QQQ": _us_entry("나스닥100", close=500.0, pct=1.0, vol_ratio=1.6),
            "SMH": _us_entry("반도체", close=300.0, pct=2.0, vol_ratio=None),
        },
    }


class TestFormatUsDaily:
    def test_contains_required_structure_tokens(self):
        out = F.format_us_daily(_build_us_data())
        assert "🇺🇸" in out
        assert "미국장 마감" in out
        assert "📊" in out
        assert "주요 지수" in out
        assert "S&P500" in out
        assert "🌡" in out  # 🌡️ 의 base 문자
        assert "변동성·꼬리위험" in out
        assert "💹" in out
        assert "매크로" in out
        assert "💼" in out
        assert "섹터" in out
        assert "⭐" in out
        assert "워치 ETF" in out

    def test_risk_on_label_when_hyg_gap_exceeds_threshold(self):
        out = F.format_us_daily(_build_us_data(hyg_pct=0.5, ief_pct=0.0))
        assert "위험선호" in out

    def test_risk_off_label_when_hyg_underperforms(self):
        out = F.format_us_daily(_build_us_data(hyg_pct=-0.5, ief_pct=0.0))
        assert "안전자산" in out

    def test_neutral_label_when_gap_within_threshold(self):
        out = F.format_us_daily(_build_us_data(hyg_pct=0.1, ief_pct=0.0))
        assert "중립" in out

    def test_hot_marker_when_vol_ratio_high(self):
        out = F.format_us_daily(_build_us_data())
        # QQQ 는 vol_ratio=1.6 → 🔥 표시
        assert "🔥" in out

    def test_sector_shows_relative_strength_and_vol_ratio(self):
        # I5: 섹터에 ^GSPC(0.5%) 대비 상대강도(%p) + 거래량강도 병기
        data = _build_us_data()
        data["sectors"] = {
            "XLK": _us_entry("기술", close=200.0, pct=1.2, vol_ratio=1.6),
            "XLF": _us_entry("금융", close=50.0, pct=0.3, vol_ratio=0.9),
        }
        out = F.format_us_daily(data)
        assert "vs S&P500" in out  # 부제
        assert "vs+0.70" in out and "×1.60" in out  # XLK: 1.2-0.5, vol 1.6
        assert "vs-0.20" in out and "×0.90" in out  # XLF: 0.3-0.5, vol 0.9


# ──────────────────────────────────────────────
#  format_weekly
# ──────────────────────────────────────────────


class TestFormatWeekly:
    def test_contains_required_tokens(self):
        kospi_daily = [
            _make_daily_row(f"05.{20 + i:02d}", scale=i + 1) for i in range(5)
        ]
        watch_5d = {"QQQ": 2.5, "SMH": -1.2}
        out = F.format_weekly(kospi_daily, watch_5d)
        assert "📅" in out
        assert "주간 매매동향 리포트" in out
        assert "🇰🇷" in out
        assert "코스피" in out
        assert "5거래일 누적" in out
        assert "🇺🇸" in out
        assert "워치 ETF" in out

    def test_handles_empty_watch_5d(self):
        kospi_daily = [_make_daily_row("05.25")]
        out = F.format_weekly(kospi_daily, {})
        # watch_5d 가 비어있으면 워치 ETF 섹션 미출력
        assert "워치 ETF" not in out
        # 그러나 코스피 섹션은 출력됨
        assert "코스피" in out

    def test_truncates_to_5_days_when_more_rows(self):
        # 7일분 입력 → 5일만 사용
        rows = [_make_daily_row(f"05.{15 + i:02d}") for i in range(7)]
        out = F.format_weekly(rows, {"QQQ": 1.0})
        # 일별 표에 5개만 표시 — 05.15, 05.16, 05.17, 05.18, 05.19 만 출력
        assert "05.15" in out
        assert "05.19" in out
        assert "05.21" not in out  # 6번째 입력
