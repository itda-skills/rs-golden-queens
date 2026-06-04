"""SPEC-MF-SCHED-001: calendar_utils 결정론적 판정 테스트.

시각 주입(`now: datetime`) 기반으로 DST/거래일/마지막 거래일을
결정론적으로 검증한다. acceptance.md Section 1.5, 1.6, 5, 8 커버.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from market_flow import calendar_utils as cu

KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")


# ──────────────────────────────────────────────
#  DST 판정 (is_us_in_dst)
# ──────────────────────────────────────────────


class TestIsUsInDst:
    def test_edt_period_returns_true(self):
        now = datetime(2025, 6, 15, 10, 0, tzinfo=ET)
        assert cu.is_us_in_dst(now) is True

    def test_est_period_returns_false(self):
        now = datetime(2025, 12, 15, 10, 0, tzinfo=ET)
        assert cu.is_us_in_dst(now) is False

    def test_spring_forward_next_weekday_is_edt(self):
        # 2025-03-09 일요일에 EST→EDT 전환 → 3-10 월요일은 EDT
        now = datetime(2025, 3, 10, 16, 30, tzinfo=ET)
        assert cu.is_us_in_dst(now) is True

    def test_fall_back_next_weekday_is_est(self):
        # 2025-11-02 일요일에 EDT→EST 전환 → 11-03 월요일은 EST
        now = datetime(2025, 11, 3, 16, 30, tzinfo=ET)
        assert cu.is_us_in_dst(now) is False

    def test_accepts_utc_now(self):
        # UTC 입력도 내부적으로 ET로 변환되어 판정되어야 한다
        now = datetime(2025, 6, 15, 20, 0, tzinfo=ZoneInfo("UTC"))
        assert cu.is_us_in_dst(now) is True

    def test_default_now_returns_bool(self):
        # 시각 미지정 시 현재 시각 기반 bool 반환 (예외 없음)
        assert isinstance(cu.is_us_in_dst(), bool)


# ──────────────────────────────────────────────
#  미국 거래일 판정 (is_us_trading_day)
# ──────────────────────────────────────────────


class TestIsUsTradingDay:
    def test_christmas_is_holiday(self):
        now = datetime(2025, 12, 25, 16, 30, tzinfo=ET)
        assert cu.is_us_trading_day(now) is False

    def test_independence_day_is_holiday(self):
        now = datetime(2025, 7, 4, 16, 30, tzinfo=ET)
        assert cu.is_us_trading_day(now) is False

    def test_thanksgiving_is_holiday(self):
        now = datetime(2025, 11, 27, 16, 30, tzinfo=ET)
        assert cu.is_us_trading_day(now) is False

    def test_day_after_thanksgiving_is_trading_day_even_early_close(self):
        # 11/28은 반장이지만 거래일로 간주
        now = datetime(2025, 11, 28, 16, 30, tzinfo=ET)
        assert cu.is_us_trading_day(now) is True

    def test_regular_weekday_is_trading_day(self):
        now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
        assert cu.is_us_trading_day(now) is True

    def test_weekend_is_holiday(self):
        now = datetime(2025, 5, 24, 16, 30, tzinfo=ET)  # 토요일
        assert cu.is_us_trading_day(now) is False

    def test_new_year_is_holiday(self):
        now = datetime(2025, 1, 1, 16, 30, tzinfo=ET)
        assert cu.is_us_trading_day(now) is False


# ──────────────────────────────────────────────
#  한국 거래일 판정 (is_kr_trading_day)
# ──────────────────────────────────────────────


class TestIsKrTradingDay:
    def test_childrens_day_is_holiday(self):
        now = datetime(2025, 5, 5, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is False

    def test_liberation_day_friday_is_holiday(self):
        now = datetime(2025, 8, 15, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is False

    def test_foundation_day_friday_is_holiday(self):
        now = datetime(2025, 10, 3, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is False

    def test_regular_monday_is_trading_day(self):
        now = datetime(2025, 5, 26, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is True

    def test_weekend_is_holiday(self):
        now = datetime(2025, 5, 24, 18, 10, tzinfo=KST)  # 토요일
        assert cu.is_kr_trading_day(now) is False

    def test_new_year_is_holiday(self):
        now = datetime(2026, 1, 1, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is False

    def test_kr_christmas_is_holiday(self):
        now = datetime(2025, 12, 25, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is False

    def test_local_election_day_is_holiday(self):
        # 2026-06-03 제9회 전국동시지방선거 — exchange_calendars(XKRX)가 거래일로
        # 오판하는 임시공휴일. _KR_EXTRA_CLOSED override 로 휴장 처리돼야 한다.
        now = datetime(2026, 6, 3, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is False

    def test_day_before_election_is_trading_day(self):
        # 6/2(화)는 정상 거래일 — override 가 인접 거래일을 침범하지 않는다.
        now = datetime(2026, 6, 2, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is True

    def test_day_after_election_is_trading_day(self):
        # 6/4(목)도 정상 거래일.
        now = datetime(2026, 6, 4, 18, 10, tzinfo=KST)
        assert cu.is_kr_trading_day(now) is True


# ──────────────────────────────────────────────
#  마지막 거래일 판정 (is_last_kr_trading_day_of_week)
# ──────────────────────────────────────────────


class TestIsLastKrTradingDayOfWeek:
    def test_friday_is_trading_day_returns_true_on_friday(self):
        # 2025-09-19 금요일 정상 거래일
        now = datetime(2025, 9, 19, 18, 30, tzinfo=KST)
        assert cu.is_last_kr_trading_day_of_week(now) is True

    def test_friday_is_trading_day_returns_false_on_thursday(self):
        # 2025-09-18 목요일, 다음날 금요일 정상 거래일 → 목요일 False
        now = datetime(2025, 9, 18, 18, 30, tzinfo=KST)
        assert cu.is_last_kr_trading_day_of_week(now) is False

    def test_friday_holiday_thursday_is_last_trading_day(self):
        # 2025-08-14 목요일, 다음날 8/15 광복절 → 목요일이 마지막 거래일
        now = datetime(2025, 8, 14, 18, 30, tzinfo=KST)
        assert cu.is_last_kr_trading_day_of_week(now) is True

    def test_friday_holiday_returns_false_on_friday(self):
        # 2025-08-15 금요일 광복절 → 오늘이 거래일 아님 → False
        now = datetime(2025, 8, 15, 18, 30, tzinfo=KST)
        assert cu.is_last_kr_trading_day_of_week(now) is False

    def test_monday_returns_false(self):
        # 정상 주의 월요일은 그 주 마지막 거래일이 아님
        now = datetime(2025, 9, 15, 18, 30, tzinfo=KST)
        assert cu.is_last_kr_trading_day_of_week(now) is False

    def test_default_now_returns_bool(self):
        assert isinstance(cu.is_last_kr_trading_day_of_week(), bool)


class TestFormatHolidayMessage:
    """SPEC-MF-SCHED-001 REQ-MF-HOL-001/002: 휴장 메시지 포맷.

    형식: `[MARKET] YYYY-MM-DD (요일) 오늘은 휴장입니다`
    날짜는 시장별 로컬 타임존(KR=KST, US=ET) 기준 (REQ-MF-HOL-004).
    """

    def test_kr_childrens_day(self):
        now = datetime(2025, 5, 5, 18, 10, tzinfo=KST)
        assert (
            cu.format_holiday_message("KR", now)
            == "[KR] 2025-05-05 (월) 오늘은 휴장입니다"
        )

    def test_kr_liberation_day_friday(self):
        now = datetime(2025, 8, 15, 18, 10, tzinfo=KST)
        assert (
            cu.format_holiday_message("KR", now)
            == "[KR] 2025-08-15 (금) 오늘은 휴장입니다"
        )

    def test_us_christmas_thursday(self):
        now = datetime(2025, 12, 25, 16, 30, tzinfo=ET)
        assert (
            cu.format_holiday_message("US", now)
            == "[US] 2025-12-25 (목) 오늘은 휴장입니다"
        )

    def test_us_independence_day_friday(self):
        now = datetime(2025, 7, 4, 16, 30, tzinfo=ET)
        assert (
            cu.format_holiday_message("US", now)
            == "[US] 2025-07-04 (금) 오늘은 휴장입니다"
        )

    def test_us_uses_et_local_date_not_utc(self):
        """ET 자정 직전 호출 시 ET 로컬 날짜를 사용하는지 검증."""
        # 2025-12-25 23:30 ET → UTC로는 2025-12-26 04:30이지만 ET 로컬은 여전히 12-25
        now = datetime(2025, 12, 25, 23, 30, tzinfo=ET)
        assert (
            cu.format_holiday_message("US", now)
            == "[US] 2025-12-25 (목) 오늘은 휴장입니다"
        )

    def test_kr_uses_kst_local_date(self):
        """UTC로 받은 시각도 KST 로컬 날짜로 변환되는지 검증."""
        from zoneinfo import ZoneInfo as _ZI

        # 2025-05-04 22:00 UTC = 2025-05-05 07:00 KST (어린이날)
        now = datetime(2025, 5, 4, 22, 0, tzinfo=_ZI("UTC"))
        assert (
            cu.format_holiday_message("KR", now)
            == "[KR] 2025-05-05 (월) 오늘은 휴장입니다"
        )

    def test_default_now_returns_string(self):
        msg = cu.format_holiday_message("KR")
        assert msg.startswith("[KR] ")
        assert msg.endswith(") 오늘은 휴장입니다")


# ──────────────────────────────────────────────
#  기대 거래일 (last_us_trading_day) — #10 P0-a 신선도 기준
# ──────────────────────────────────────────────


class TestLastUsTradingDay:
    def test_trading_day_returns_self(self):
        # 2025-09-15 월요일 거래일 → 자기 자신
        now = datetime(2025, 9, 15, 16, 30, tzinfo=ET)
        assert cu.last_us_trading_day(now) == "2025-09-15"

    def test_weekend_returns_prev_friday(self):
        # 2025-09-13 토요일 → 직전 거래일 09-12 금요일
        now = datetime(2025, 9, 13, 10, 0, tzinfo=ET)
        assert cu.last_us_trading_day(now) == "2025-09-12"

    def test_holiday_returns_prev_session(self):
        # 2025-12-25 크리스마스(목, 휴장) → 직전 거래일 12-24 수요일
        now = datetime(2025, 12, 25, 16, 30, tzinfo=ET)
        assert cu.last_us_trading_day(now) == "2025-12-24"

    def test_accepts_utc_now(self):
        # UTC 시각도 ET로 변환해 판정 (2025-09-15 20:00 UTC = 16:00 ET 월)
        from zoneinfo import ZoneInfo as _ZI

        now = datetime(2025, 9, 15, 20, 0, tzinfo=_ZI("UTC"))
        assert cu.last_us_trading_day(now) == "2025-09-15"


# ──────────────────────────────────────────────
#  거래일 목록 (kr_trading_days / us_trading_days) — calendar.json 정합
# ──────────────────────────────────────────────


class TestTradingDaysRange:
    def test_kr_excludes_extra_closed_election_day(self):
        # 6/3 제9회 지방선거는 _KR_EXTRA_CLOSED override 로 제외되고 인접일은 유지된다.
        # calendar.json(build_calendar_snapshot)이 이 함수로 생성되므로 재생성 시에도
        # 6/3 이 거래일로 되살아나지 않는다.
        days = cu.kr_trading_days(date(2026, 6, 1), date(2026, 6, 5))
        assert "2026-06-03" not in days
        assert "2026-06-02" in days
        assert "2026-06-04" in days

    def test_us_keeps_election_day(self):
        # 미국은 한국 지방선거와 무관 — 6/3은 NYSE 정상 거래일로 유지된다.
        days = cu.us_trading_days(date(2026, 6, 1), date(2026, 6, 5))
        assert "2026-06-03" in days
