---
id: SPEC-MF-SCHED-001
version: 0.1.0
status: draft
created: 2026-05-25
updated: 2026-05-25
author: Chinseok
priority: medium
issue_number: 0
---

# SPEC-MF-SCHED-001: market_flow 스케줄링 정합화 (DST 자동 반영 + 휴장 인지)

## HISTORY

- 2026-05-25 (v0.1.0): 초안 작성. `market_flow/`의 3개 텔레그램 봇(`daily_kr.py`, `daily_us.py`, `weekly.py`)과 3개 GitHub Actions 워크플로우(`flow-kr.yml`, `flow-us.yml`, `flow-weekly.yml`)에 대해 (a) 미국장 DST 자동 반영, (b) 한국·미국 휴장일 인지 및 한 줄 메시지 발송, (c) 주간 리포트의 그 주 마지막 거래일 자동 이월 발송을 명세. dual-cron + 환경변수 게이트 전략과 휴장 판정 라이브러리(`pandas_market_calendars` / `pykrx` 검증 후 `exchange_calendars` fallback) 도입을 포함. naver_investor_flow 제거(commit 8fd2c7f) 및 `--no-telegram` dry-run 추가(commit d78d0a6) 이후 상태를 전제. issue_number는 추후 결정.

---

## Overview

### 배경

현재 `market_flow/` 하위 텔레그램 봇은 GitHub Actions cron으로 평일 정기 발송되고 있다:

- `flow-kr.yml` — 평일 KST 18:10 (UTC cron `10 9 * * 1-5`) `python daily_kr.py`
- `flow-us.yml` — 평일 KST 06:30 (UTC cron `30 21 * * 1-5`) `python daily_us.py` — DST 미반영, EST 기준 고정
- `flow-weekly.yml` — 금요일 KST 18:30 (UTC cron `30 9 * * 5`) `python weekly.py`

다음 세 가지 정합성 결함이 식별되었다:

1. **DST 미반영 (US)**: `flow-us.yml`의 cron은 UTC 21:30 고정이다. NYSE 마감(16:00 ET)은 EDT 기간(3월 둘째 일요일~11월 첫째 일요일)에는 UTC 20:00, EST 기간에는 UTC 21:00이므로, 마감 30분 후 발송 목표 시각은 EDT에서 UTC 20:30, EST에서 UTC 21:30이다. 현 cron은 EST 기준만 정확하며, EDT 기간에는 발송이 1시간 늦다.

2. **휴장 인지 부재**: 한국·미국 거래소 휴장일에도 워크플로우는 그대로 실행되어 빈 데이터 또는 에러를 보고하거나, 아무 메시지도 발송하지 않는다. 사용자는 "오늘은 휴장임"을 텔레그램에서 명시적으로 확인할 수 있어야 한다.

3. **금요일 휴장 시 주간 리포트 누락**: `flow-weekly.yml`은 금요일에만 트리거되므로 금요일이 한국 휴장일(예: 광복절이 금요일에 걸리는 경우)이면 그 주 주간 리포트가 발송되지 않는다.

### 목표

3개 워크플로우 + 3개 스크립트가 다음을 만족하도록 명세한다:

1. 한국장 일일 보고서는 평일 KST 18:10에 발송한다 (현 동작 유지).
2. 미국장 마감 보고서는 NYSE 현지 마감 30분 후(EDT/EST 시즌 자동 반영)에 정확히 한 번 발송한다.
3. 한국·미국 각 거래소의 비거래일에는 해당 시장의 워크플로우가 "[KR] 오늘은 휴장입니다" / "[US] 오늘은 휴장입니다" 한 줄 메시지를 발송한다.
4. 주간 리포트는 금요일이 한국 거래일이면 금요일에, 금요일이 휴장이면 그 주의 마지막 한국 거래일에 한 번 발송한다.
5. 기존 `--no-telegram` dry-run 플래그는 휴장 메시지 발송에도 동일하게 적용된다 (텔레그램 API 호출 없이 stdout 출력).

코드 수정 없이 cron만으로는 DST 반영이 불가능하므로, **dual-cron + 환경변수 게이트** 전략을 채택한다. 휴장 판정은 거래소 공식 캘린더 라이브러리에 위임한다.

### 비목표 (Non-Goals)

- NYSE 반장(early close, 13:00 ET 마감) 시각 동적 조정 — 거래일로 간주하여 30분 후 발송을 정상 수행한다 (즉 EDT 기간 17:00 ET → UTC 21:30 발송도 그대로 진행).
- 한국 거래소 반장 시각 동적 조정 — 동일하게 정상 발송한다.
- 휴장 메시지 다국어화 (한국어 한 줄 메시지 고정).
- 주간 리포트 본문 형식 변경 (`formatter.format_weekly`는 불변).
- 한국장 발송 시각(KST 18:10) 변경 — 네이버 18:03 갱신을 전제로 이미 안정 운영 중.
- 워크플로우 이름 변경 (`flow-kr.yml`, `flow-us.yml`, `flow-weekly.yml` 파일명·잡 이름 유지).
- 휴장 메시지 외의 풍부한 알림(예: 직전 거래일 데이터 재발송) — 본 SPEC 범위 밖.

---

## EARS Requirements

### REQ-MF-SCHED-001: 한국장 정시 발송 (Ubiquitous)

The system **shall** send the Korean market daily flow report via Telegram on every weekday (Mon-Fri) at **KST 18:10** when the day is a Korean trading day.

- 발송 트리거: `flow-kr.yml`의 cron `10 9 * * 1-5` (UTC 09:10 = KST 18:10)
- 작업 디렉토리: `market_flow/`
- 실행 커맨드: `python daily_kr.py`
- 검증 방법: GitHub Actions 워크플로우 실행 로그 확인, 텔레그램 채널 수신 확인

### REQ-MF-SCHED-002: 미국장 마감 30분 후 발송 (Ubiquitous)

The system **shall** send the US market closing summary via Telegram **30 minutes after NYSE close** on every NYSE trading day, with the wall-clock timing automatically adjusted for Daylight Saving Time:

- EDT 기간 (3월 둘째 일요일 ~ 11월 첫째 일요일): NYSE 마감 16:00 EDT → 발송 16:30 EDT = **UTC 20:30**
- EST 기간 (11월 첫째 일요일 ~ 3월 둘째 일요일): NYSE 마감 16:00 EST → 발송 16:30 EST = **UTC 21:30**

검증 방법: 2026년 EDT 전환 직후 평일과 EST 전환 직후 평일의 워크플로우 실행 시각 로그 확인.

### REQ-MF-SCHED-003: dual-cron + 환경변수 게이트 (State-driven)

**While** the current US Eastern Time is in **EDT season**, only the EDT-tagged cron job **shall** proceed with sending; the EST-tagged cron job **shall** exit immediately with status 0 without calling Telegram.

**While** the current US Eastern Time is in **EST season**, only the EST-tagged cron job **shall** proceed; the EDT-tagged cron job **shall** exit immediately with status 0.

- `flow-us.yml`에 두 개의 cron 표현식을 등록한다:
  - EDT용: `30 20 * * 1-5` (UTC 20:30 = EDT 16:30)
  - EST용: `30 21 * * 1-5` (UTC 21:30 = EST 16:30)
- 각 잡은 환경변수 `MARKET_SCHEDULE=edt` 또는 `MARKET_SCHEDULE=est`를 주입한다.
- `daily_us.py`는 `America/New_York` 타임존에서 `datetime.now().dst()`가 0이 아니면 EDT, 0이면 EST로 판정한다.
- 환경변수와 실제 시즌이 일치하지 않으면 `sys.exit(0)`으로 즉시 종료한다 (이중 발송 방지).
- 검증 방법: 단위 테스트에서 `now` 파라미터로 임의 시각 주입 → 게이트 통과/차단 검증.

### REQ-MF-SCHED-004: 주간 리포트 조건부 발송 (Event-driven)

**When** the weekly workflow is triggered on a weekday (Mon-Fri) at **KST 18:30**, the system **shall** send the weekly report **only when** today is the last Korean trading day of the current week (Mon-Fri). Otherwise the system **shall** exit immediately with status 0.

- "그 주의 마지막 한국 거래일"의 정의: 오늘이 한국 거래일이면서, 오늘 이후 같은 주 금요일까지의 모든 날(오늘+1 ~ 금요일)이 비거래일.
- `flow-weekly.yml`의 cron을 `30 9 * * 5`에서 `30 9 * * 1-5`로 확장한다.
- 평년 금요일이 한국 거래일이면 평소처럼 금요일에 발송된다.
- 금요일이 휴장이면 직전 한국 거래일(보통 목요일)에 발송된다. 목요일도 휴장이면 수요일, 그 이전으로 거슬러 올라간다.
- 검증 방법: 단위 테스트에서 `now` 주입으로 금요일/목요일/수요일이 마지막 거래일인 시나리오 각각 검증.

### REQ-MF-HOL-001: 한국 휴장일 메시지 (State-driven)

**While** today is a Korean stock exchange (XKRX) **non-trading day** (weekend or holiday) at the time `flow-kr.yml` executes, the system **shall** send the message **"[KR] 오늘은 휴장입니다"** via Telegram and skip all data fetching from Naver.

- 현 cron은 `1-5`로 평일에만 트리거되므로 주말은 자연 회피된다.
- 평일 휴장(공휴일 등)에 한해 휴장 메시지를 발송한다.
- 메시지 본문은 정확히 `[KR] 오늘은 휴장입니다` 한 줄(텔레그램 표준 텍스트, Markdown/HTML 미사용).
- 검증 방법: fixture 날짜(예: 2025-05-05 어린이날)로 휴장 판정 호출 → 메시지 송신 mock 호출 검증.

### REQ-MF-HOL-002: 미국 휴장일 메시지 (State-driven)

**While** today (in the New York timezone, evaluated at the script's local time) is an NYSE **non-trading day** (weekend or holiday) at the time `flow-us.yml`'s gate-passing job executes, the system **shall** send the message **"[US] 오늘은 휴장입니다"** via Telegram and skip all data fetching from yfinance.

- 휴장 판정 기준 날짜: 스크립트 실행 시점의 `America/New_York` 로컬 날짜 (UTC 날짜가 아님).
- DST 게이트(REQ-MF-SCHED-003)를 통과한 잡에서만 휴장 검사를 수행한다 (이중 발송 방지).
- 메시지 본문은 정확히 `[US] 오늘은 휴장입니다` 한 줄.
- 검증 방법: fixture 날짜(예: 2025-12-25 크리스마스, 2025-07-04 독립기념일)로 휴장 판정 호출 → 메시지 송신 mock 호출 검증.

### REQ-MF-HOL-003: 휴장 판정 라이브러리 (Ubiquitous)

The system **shall** determine NYSE non-trading days using **`pandas_market_calendars`** (NYSE calendar). The system **shall** determine Korean stock exchange (XKRX) non-trading days using **`pykrx`** if its existing API can deterministically answer the question "is `YYYYMMDD` a KRX trading day?". **If** `pykrx` cannot answer this question reliably, **then** the system **shall** use **`exchange_calendars`** (XKRX calendar) instead.

- `pykrx` 적합성 검증은 plan.md의 사전 조사 항목으로 명시 (`get_previous_business_day`, `get_nearest_business_day_in_a_week` 등의 정확도/오프라인 동작 확인).
- 라이브러리 결정 결과(`pykrx` 단독 vs `exchange_calendars` 도입)는 plan.md에 기록한다.
- `pandas_market_calendars`는 `market_flow/requirements.txt`에 추가한다.
- 검증 방법: 알려진 휴장일/거래일 fixture로 두 캘린더 호출 결과 검증.

### REQ-MF-HOL-004: 거래소 로컬 날짜 기준 (Ubiquitous)

The system **shall** evaluate "today" for trading-day decisions using each exchange's **local calendar date** at the time of execution, not the UTC date and not the GitHub Actions runner's date.

- 한국: `datetime.now(ZoneInfo("Asia/Seoul")).date()`
- 미국: `datetime.now(ZoneInfo("America/New_York")).date()`
- 사유: GitHub Actions cron은 최대 약 15~20분 지연이 가능하지만, 발송 의도는 항상 "거래소 현지 그 날"의 마감 데이터를 다루는 것이다.
- 검증 방법: 자정 경계 시각(KST 00:05, ET 23:55 등)에 시각 주입 단위 테스트로 거래소 로컬 날짜 계산 검증.

### REQ-MF-DRY-001: dry-run 플래그 일관성 (State-driven)

**While** the `--no-telegram` flag is passed to any of `daily_kr.py`, `daily_us.py`, or `weekly.py`, **and** the system would have sent any message (normal report **or** holiday message **or** weekly report), the system **shall** print the would-be message body to stdout instead of calling the Telegram Bot API. No Telegram HTTP request **shall** be made under this flag.

- 기존 commit d78d0a6에서 추가된 `--no-telegram` dry-run 플래그의 의미를 휴장 메시지에도 확장한다.
- 검증 방법: 휴장일 fixture + `--no-telegram` 조합 단위 테스트로 stdout 캡처 및 `requests.post` 미호출 검증.

### REQ-MF-SCHED-005: 시각 주입 가능성 (Ubiquitous)

The core decision functions — DST gate, trading-day check, last-trading-day check — **shall** accept an injectable `now: datetime` parameter (with a default of `datetime.now(tz)` for production). Unit tests **shall** drive these functions with arbitrary frozen times.

- 사유: GitHub Actions 환경에서 시각을 모킹하지 않고도 핵심 분기 로직을 결정론적으로 테스트하기 위함.
- 검증 방법: pytest로 DST 전환일, 휴장일, 마지막 거래일 시나리오를 시각 주입으로 재현.

### REQ-MF-SCHED-NEG-001: 절대 제약 (Unwanted)

The system **shall not** introduce any of the following:

- 이중 발송: 동일 거래일에 동일 시장(KR 또는 US)의 정상 보고서가 2회 이상 텔레그램으로 전송되어서는 안 된다. DST 게이트(REQ-MF-SCHED-003)와 휴장 게이트는 이를 보장하기 위해 존재한다.
- 휴장일 데이터 수집 호출: 한국 휴장 판정이 참이면 `fetchers.naver_kr` 호출을 절대 수행하지 않아야 하며, 미국 휴장 판정이 참이면 `fetchers.us_market`을 호출하지 않아야 한다 (외부 API 부하 절감 및 빈 데이터 오류 회피).
- `formatter.format_weekly` 본문 형식 변경: 주간 리포트 본문 텍스트는 불변이다 (이월 발송에서도 동일 본문).
- `daily_kr.py` 발송 시각 변경: KST 18:10 cron은 변경되지 않는다 (네이버 18:03 갱신 의존).
- GitHub Actions secrets 이름 변경: `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`는 불변.

**If** a workflow modification would cause double-sends on the same trading day, **then** the change must be rejected in code review.

---

## Files to Modify / Create

**MODIFY**
- `.github/workflows/flow-us.yml` — dual-cron 추가, `MARKET_SCHEDULE` 환경변수 주입
- `.github/workflows/flow-weekly.yml` — cron을 `30 9 * * 5` → `30 9 * * 1-5`로 확장
- `market_flow/daily_kr.py` — 한국 휴장 판정 분기, 시각 주입 파라미터, `--no-telegram` 휴장 메시지 분기 추가
- `market_flow/daily_us.py` — DST 게이트, 미국 휴장 판정 분기, 시각 주입 파라미터, `--no-telegram` 휴장 메시지 분기 추가
- `market_flow/weekly.py` — "오늘이 그 주 마지막 거래일?" 게이트, 시각 주입 파라미터 추가
- `market_flow/requirements.txt` — `pandas_market_calendars` 추가, `pykrx` 검증 결과에 따라 `exchange_calendars` 조건부 추가

**NEW (구체적 모듈 구조는 plan.md에서 결정)**
- 휴장·DST 판정 헬퍼 (위치는 plan.md에서 결정. 후보: `market_flow/calendar_utils.py`)
- 단위 테스트 파일 (`market_flow/tests/` 또는 프로젝트 루트 `tests/` — plan.md에서 결정)

**UNCHANGED**
- `market_flow/formatter.py` — 본문 포맷터 불변 (REQ-MF-SCHED-NEG-001)
- `market_flow/telegram_push.py` — Telegram 전송 함수 불변 (`--no-telegram` 분기는 호출 측에서 처리)
- `market_flow/fetchers/` — 휴장이면 호출 자체를 생략하므로 fetcher 변경 불필요
- `.github/workflows/flow-kr.yml` — 한국장 cron은 불변 (휴장 메시지는 스크립트 내부 분기로 처리)

---

## Context Variables (Decision Summary)

본 SPEC이 구체화하는 결정 사항:

| 항목 | 결정 | 사유 |
|------|------|------|
| US DST 전략 | dual-cron + 환경변수 게이트 | GitHub Actions cron은 정적 UTC만 지원; 스크립트가 시즌 자체 판정 |
| US 휴장 캘린더 | `pandas_market_calendars` (NYSE) | 업계 표준, 반장일 정보까지 포함, crush/quant 생태계에서 검증됨 |
| KR 휴장 캘린더 | `pykrx` 우선, 부족 시 `exchange_calendars` (XKRX) | 기존 의존성 재사용 시도 후 fallback |
| weekly cron 확장 | `30 9 * * 5` → `30 9 * * 1-5` | 금요일 휴장 시 직전 거래일 이월을 가능하게 함 |
| 휴장 메시지 본문 | `[KR] 오늘은 휴장입니다` / `[US] 오늘은 휴장입니다` | 사용자 확정 사양 |
| 거래소 날짜 기준 | 거래소 로컬 타임존의 date() | GitHub Actions 실행 시각 변동에 무관한 결정론적 판정 |
| 시각 주입 | 핵심 판정 함수에 `now: datetime` 파라미터 | 단위 테스트 결정성 확보 |
| 반장 처리 | 정상 거래일과 동일하게 처리 (Non-Goals) | 30분 후 발송 룰을 단일화하여 복잡도 회피 |

---

## Exclusions (What NOT to Build)

다음 항목은 SPEC-MF-SCHED-001의 범위 밖이며 구현되지 않는다:

1. **NYSE/KRX 반장 시각 동적 조정** — 반장일도 정상 거래일로 간주, 30분 후 발송 룰 단일 적용. 향후 필요 시 별도 SPEC.
2. **휴장 메시지 다국어화** — 한국어 한 줄 메시지 고정. i18n은 별도 SPEC.
3. **휴장 사유 표기** — "[KR] 오늘은 어린이날 휴장입니다" 같은 사유 부기 미지원. 한 줄 텍스트 고정.
4. **직전 거래일 데이터 재발송** — 휴장일에 "어제 데이터" 발송 같은 보완 기능 미지원. 한 줄 메시지만 발송.
5. **`formatter.format_weekly` 본문 변경** — 주간 리포트 본문은 이월 발송에서도 동일.
6. **`flow-kr.yml` cron 변경** — KST 18:10 발송 시각은 불변. 휴장 처리는 스크립트 내부 분기로 한정.
7. **`telegram_push.send` 시그니처 변경** — 텔레그램 전송 단위 함수는 불변. dry-run 분기는 호출 측 책임.
8. **다중 텔레그램 채널 분기** — 시장별/사용자별 채널 라우팅 없음. `GOLDENQUEENS_CHAT_ID` 단일 채널 고정.
9. **휴장 캘린더 캐시·로컬 DB** — 매 실행마다 라이브러리 호출. 캐시 도입은 별도 SPEC.
10. **GitHub Actions 외부 트리거 (webhook, manual ad-hoc)** — `workflow_dispatch` 트리거는 그대로 유지하되 신규 기능 추가하지 않음.
11. **3개 워크플로우 통합** — `flow-kr.yml` / `flow-us.yml` / `flow-weekly.yml`의 3개 파일 구조 유지. 단일 워크플로우 병합은 별도 SPEC.
12. **자정·반장 경계 알림 분리** — 마감 후 30분 후 발송 룰 외 추가 알림 시점 없음.

---

## References

- 현행 스크립트:
  - `market_flow/daily_kr.py` — 한국장 일일 발송 (Naver 데이터)
  - `market_flow/daily_us.py` — 미국장 마감 발송 (yfinance)
  - `market_flow/weekly.py` — 주간 리포트 발송 (Naver + yfinance)
- 현행 워크플로우:
  - `.github/workflows/flow-kr.yml` — cron `10 9 * * 1-5`
  - `.github/workflows/flow-us.yml` — cron `30 21 * * 1-5` (DST 미반영, 본 SPEC에서 dual-cron 도입)
  - `.github/workflows/flow-weekly.yml` — cron `30 9 * * 5` (본 SPEC에서 `30 9 * * 1-5`로 확장)
- 선행 작업:
  - commit `d78d0a6` — `--no-telegram` dry-run 플래그 도입
  - commit `8fd2c7f` — naver_investor_flow 제거 및 market_flow 봇 도입
- 외부 라이브러리:
  - `pandas_market_calendars` — NYSE 캘린더 (예정 추가)
  - `pykrx` — 기존 의존성 (KR 거래일 판정 적합성은 plan.md에서 검증)
  - `exchange_calendars` — XKRX 캘린더 (조건부 추가)
- GitHub Actions cron 정밀도: 공식 문서상 최대 약 15~20분 지연 가능 — 본 SPEC은 거래소 로컬 날짜 기준 판정으로 이 지연에 무관한 결정성 확보 (REQ-MF-HOL-004)
