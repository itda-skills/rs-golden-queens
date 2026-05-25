# SPEC-MF-SCHED-001 Acceptance Criteria

## Overview

본 문서는 SPEC-MF-SCHED-001의 구현이 "완료"로 인정되기 위한 관측 가능한 증거(observable evidence)를 정의한다. 모든 시나리오는 Given/When/Then 형식으로 기술되며, **단위 테스트로 결정론적으로 검증 가능**해야 한다 (시각 주입 `now: datetime` 파라미터 사용).

각 시나리오는 다음 라벨 중 하나로 분류된다:
- **Must-pass**: 머지 차단 기준. 하나라도 실패하면 머지 거부.
- **Should-pass**: 권장 통과. 실패 시 별도 후속 PR 합의.

---

## 1. DST 자동 반영 (REQ-MF-SCHED-002, REQ-MF-SCHED-003)

### Scenario 1.1: EDT 시즌 EDT 잡 통과 [Must-pass]

- **Given**: 환경변수 `MARKET_SCHEDULE=edt`, `now = datetime(2025, 6, 15, 16, 30, tzinfo=ZoneInfo("America/New_York"))` (EDT 시즌 임의 평일)
- **When**: `daily_us.main(now=now)` 실행
- **Then**:
  - DST 게이트가 통과한다 (`sys.exit` 미발생)
  - 휴장 판정이 거래일 → `fetchers.us_market.fetch_us_close`가 호출된다
  - `telegram_push.send`가 정상 보고서 본문으로 정확히 1회 호출된다
- **검증 도구**: pytest + `unittest.mock.patch`

### Scenario 1.2: EDT 시즌 EST 잡 차단 [Must-pass]

- **Given**: 환경변수 `MARKET_SCHEDULE=est`, `now = datetime(2025, 6, 15, 17, 30, tzinfo=ZoneInfo("America/New_York"))` (EDT 시즌)
- **When**: `daily_us.main(now=now)` 실행
- **Then**:
  - 게이트 차단으로 `SystemExit(0)`이 발생한다
  - `telegram_push.send`는 **호출되지 않는다**
  - `fetchers.us_market.fetch_us_close`는 **호출되지 않는다**

### Scenario 1.3: EST 시즌 EST 잡 통과 [Must-pass]

- **Given**: `MARKET_SCHEDULE=est`, `now = datetime(2025, 12, 15, 16, 30, tzinfo=ZoneInfo("America/New_York"))` (EST 시즌)
- **When**: `daily_us.main(now=now)`
- **Then**: 게이트 통과, 정상 발송 1회.

### Scenario 1.4: EST 시즌 EDT 잡 차단 [Must-pass]

- **Given**: `MARKET_SCHEDULE=edt`, `now = datetime(2025, 12, 15, 17, 30, tzinfo=ZoneInfo("America/New_York"))` (EST 시즌)
- **When**: `daily_us.main(now=now)`
- **Then**: `SystemExit(0)`, `send` 미호출.

### Scenario 1.5: DST 전환일 경계 — 봄 전환 직후 평일 [Must-pass]

- **Given**: `now = datetime(2025, 3, 10, 16, 30, tzinfo=ZoneInfo("America/New_York"))` (2025-03-09 EST→EDT 전환 직후 첫 평일)
- **When**: `is_us_in_dst(now)` 호출
- **Then**: `True` 반환. `MARKET_SCHEDULE=edt` 잡이 통과, `est` 잡은 차단.

### Scenario 1.6: DST 전환일 경계 — 가을 전환 직후 평일 [Must-pass]

- **Given**: `now = datetime(2025, 11, 3, 16, 30, tzinfo=ZoneInfo("America/New_York"))` (2025-11-02 EDT→EST 전환 직후 첫 평일)
- **When**: `is_us_in_dst(now)` 호출
- **Then**: `False` 반환. `est` 잡 통과, `edt` 잡 차단.

### Scenario 1.7: `workflow_dispatch` 수동 실행 — MARKET_SCHEDULE 미설정 [Should-pass]

- **Given**: 환경변수 `MARKET_SCHEDULE`이 unset 또는 빈 문자열, `now`는 임의 시각
- **When**: `daily_us.main(now=now)`
- **Then**: DST 게이트는 무시되어 통과한다 (수동 실행은 시즌 게이트와 무관). 이어서 휴장 판정 결과에 따라 분기.

---

## 2. 한국 휴장 인지 (REQ-MF-HOL-001, REQ-MF-HOL-004)

### Scenario 2.1: 어린이날 휴장 메시지 [Must-pass]

- **Given**: `now = datetime(2025, 5, 5, 18, 10, tzinfo=ZoneInfo("Asia/Seoul"))` (월요일, 어린이날)
- **When**: `daily_kr.main(now=now)` 실행
- **Then**:
  - `telegram_push.send`가 정확히 한 번 호출되며 인자는 **정확히** 문자열 `"[KR] 오늘은 휴장입니다"`
  - `fetchers.naver_kr.fetch_today`는 **호출되지 않는다**
  - 종료 코드 0

### Scenario 2.2: 광복절 휴장 메시지 (금요일) [Must-pass]

- **Given**: `now = datetime(2025, 8, 15, 18, 10, tzinfo=ZoneInfo("Asia/Seoul"))` (금요일, 광복절)
- **When**: `daily_kr.main(now=now)`
- **Then**: Scenario 2.1과 동일 검증.

### Scenario 2.3: 정상 거래일은 휴장 메시지 미발송 [Must-pass]

- **Given**: `now = datetime(2025, 5, 26, 18, 10, tzinfo=ZoneInfo("Asia/Seoul"))` (월요일, 정상 거래일)
- **When**: `daily_kr.main(now=now)`
- **Then**:
  - `fetchers.naver_kr.fetch_today`가 호출됨
  - `telegram_push.send` 인자가 휴장 메시지 문자열과 **다르다** (정상 보고서 본문)

### Scenario 2.4: 휴장 메시지 dry-run [Must-pass]

- **Given**: Scenario 2.1과 동일 `now`, 인자에 `--no-telegram` 포함
- **When**: `daily_kr.main(argv=["--no-telegram"], now=now)`
- **Then**:
  - `telegram_push.send`가 **호출되지 않는다**
  - stdout에 `"[KR] 오늘은 휴장입니다"`가 출력된다 (capsys로 캡처)

---

## 3. 미국 휴장 인지 (REQ-MF-HOL-002, REQ-MF-HOL-004)

### Scenario 3.1: 크리스마스 휴장 메시지 [Must-pass]

- **Given**: `MARKET_SCHEDULE=est`, `now = datetime(2025, 12, 25, 16, 30, tzinfo=ZoneInfo("America/New_York"))` (목요일, 크리스마스, EST 시즌)
- **When**: `daily_us.main(now=now)`
- **Then**:
  - DST 게이트 통과 (EST 시즌 + est 잡)
  - `telegram_push.send`가 **정확히** `"[US] 오늘은 휴장입니다"` 한 번 호출
  - `fetchers.us_market.fetch_us_close`는 **호출되지 않는다**

### Scenario 3.2: 독립기념일 휴장 메시지 [Must-pass]

- **Given**: `MARKET_SCHEDULE=edt`, `now = datetime(2025, 7, 4, 16, 30, tzinfo=ZoneInfo("America/New_York"))` (금요일, 독립기념일, EDT 시즌)
- **When**: `daily_us.main(now=now)`
- **Then**: Scenario 3.1과 동일 검증 (`"[US] 오늘은 휴장입니다"`).

### Scenario 3.3: 추수감사절 다음날 정상 발송 (반장일이지만 거래일) [Must-pass]

- **Given**: `MARKET_SCHEDULE=est`, `now = datetime(2025, 11, 28, 16, 30, tzinfo=ZoneInfo("America/New_York"))` (반장일, EST 시즌 직전이지만 11/28은 11/2 전환 이후 → EST)
- **When**: `daily_us.main(now=now)`
- **Then**:
  - 게이트 통과
  - 휴장 판정 결과 거래일 → **정상 보고서** 발송 (휴장 메시지 미발송)
  - 검증 의도: 반장일도 거래일로 간주한다 (Non-Goals).

### Scenario 3.4: 미국 휴장 dry-run [Must-pass]

- **Given**: Scenario 3.1 + `--no-telegram`
- **When**: `daily_us.main(argv=["--no-telegram"], now=now)`
- **Then**: `send` 미호출, stdout에 `"[US] 오늘은 휴장입니다"` 출력.

---

## 4. 주간 리포트 이월 발송 (REQ-MF-SCHED-004)

### Scenario 4.1: 정상 금요일에 발송 [Must-pass]

- **Given**: `now = datetime(2025, 9, 19, 18, 30, tzinfo=ZoneInfo("Asia/Seoul"))` (금요일, 정상 거래일)
- **When**: `weekly.main(now=now)`
- **Then**:
  - `is_last_kr_trading_day_of_week(now) == True`
  - `fetchers.naver_kr.fetch_kospi_daily` 호출
  - `telegram_push.send`가 주간 리포트 본문으로 1회 호출

### Scenario 4.2: 평일(월~목)에는 침묵 스킵 [Must-pass]

- **Given**: `now = datetime(2025, 9, 18, 18, 30, tzinfo=ZoneInfo("Asia/Seoul"))` (목요일, 그 주 금요일은 정상 거래일)
- **When**: `weekly.main(now=now)`
- **Then**:
  - `SystemExit(0)` 또는 정상 return (게이트 차단)
  - `telegram_push.send` **미호출**
  - 휴장 한 줄 메시지도 **미발송** (weekly는 침묵 스킵)
  - `fetchers.naver_kr.fetch_kospi_daily` 미호출

### Scenario 4.3: 금요일 휴장 → 목요일에 이월 발송 [Must-pass]

- **Given**: `now = datetime(2025, 8, 14, 18, 30, tzinfo=ZoneInfo("Asia/Seoul"))` (목요일), 2025-08-15는 광복절 휴장
- **When**: `weekly.main(now=now)`
- **Then**:
  - `is_last_kr_trading_day_of_week(now) == True`
  - 정상 주간 리포트 본문으로 `telegram_push.send` 1회 호출
  - 본문 형식은 기존 `formatter.format_weekly` 출력과 동일 (REQ-MF-SCHED-NEG-001)

### Scenario 4.4: 금요일이 광복절이면 금요일에는 스킵 [Must-pass]

- **Given**: `now = datetime(2025, 8, 15, 18, 30, tzinfo=ZoneInfo("Asia/Seoul"))` (금요일, 광복절)
- **When**: `weekly.main(now=now)`
- **Then**:
  - 오늘이 KR 거래일이 아니므로 `is_last_kr_trading_day_of_week(now) == False`
  - 게이트 차단, `send` 미호출

### Scenario 4.5: 금/목 연속 휴장 → 수요일에 이월 [Must-pass]

- **Given**: 가상 시나리오로 fixture에서 금/목 두 날을 휴장으로 모킹. `now`는 그 주 수요일 18:30 KST.
- **When**: `weekly.main(now=now)`
- **Then**: 수요일에 정상 발송 1회.

### Scenario 4.6: 주간 리포트 dry-run [Must-pass]

- **Given**: Scenario 4.1 + `--no-telegram`
- **When**: `weekly.main(argv=["--no-telegram"], now=now)`
- **Then**: `send` 미호출, stdout에 주간 리포트 본문 출력.

---

## 5. 시각 주입 가능성 (REQ-MF-SCHED-005)

### Scenario 5.1: `now=None` 시 기본값 사용 [Must-pass]

- **Given**: 시각을 명시하지 않음
- **When**: `is_kr_trading_day()`, `is_us_trading_day()`, `is_us_in_dst()`, `is_last_kr_trading_day_of_week()` 각각 호출
- **Then**: 예외 없이 bool 값 반환. 내부적으로 `datetime.now(tz)` 호출.
- **검증 도구**: smoke test, monkeypatch로 `datetime` 고정 후 결정성 확인.

### Scenario 5.2: 모든 핵심 분기가 `now` 인자로 결정 [Must-pass]

- **Given**: 동일 fixture를 명시 `now`로 두 번 호출
- **When**: 호출 사이에 시스템 시각이 변해도 결과는 동일해야 함
- **Then**: 결과 bool이 두 호출에서 일치.

---

## 6. dry-run 일관성 (REQ-MF-DRY-001)

### Scenario 6.1: 모든 발송 경로에 dry-run 적용 [Must-pass]

세 스크립트(`daily_kr`, `daily_us`, `weekly`) × 발송 종류(정상 보고서, 휴장 한 줄)의 조합에서 `--no-telegram`이 일관되게 동작:

| 스크립트 | 시나리오 | --no-telegram 효과 |
|---------|---------|------|
| daily_kr | 정상 거래일 | 보고서 본문 stdout, send 미호출 |
| daily_kr | KR 휴장 | `"[KR] 오늘은 휴장입니다"` stdout, send 미호출 |
| daily_us | 정상 거래일 + 게이트 통과 | 보고서 본문 stdout |
| daily_us | US 휴장 + 게이트 통과 | `"[US] 오늘은 휴장입니다"` stdout |
| weekly | 마지막 거래일 | 주간 리포트 stdout |
| weekly | 마지막 거래일 아님 | 출력 없음(또는 빈 종료 메시지만), send 미호출 |

### Scenario 6.2: dry-run이 텔레그램 API 미접촉 [Must-pass]

- **Given**: 임의 시나리오 + `--no-telegram`
- **When**: 스크립트 실행
- **Then**: `requests.post`(또는 telegram_push 내부 HTTP 호출)가 **0회** 호출됨. 검증 도구: `unittest.mock.patch("requests.post")` 후 `call_count == 0`.

---

## 7. 절대 제약 (REQ-MF-SCHED-NEG-001)

### Scenario 7.1: 이중 발송 회귀 차단 [Must-pass]

- **Given**: 동일 `now` (EDT 시즌 평일) 기준 EDT 잡과 EST 잡을 각각 호출 (CI에서 두 매트릭스 잡으로 시뮬레이션 가능하나, 단위 테스트는 순차 실행)
- **When**: `MARKET_SCHEDULE=edt`로 한 번, `MARKET_SCHEDULE=est`로 한 번 호출
- **Then**: `telegram_push.send` **총 호출 횟수 = 1** (EDT 잡만 통과)
- **검증 도구**: 두 번의 `daily_us.main` 호출에서 mock의 call_count 합산.

### Scenario 7.2: 휴장일 외부 fetcher 미호출 [Must-pass]

- **Given**: KR 휴장일 또는 US 휴장일 fixture
- **When**: 해당 스크립트 main 실행
- **Then**: `fetchers.naver_kr.fetch_today` / `fetchers.us_market.fetch_us_close`의 `call_count == 0`.

### Scenario 7.3: `formatter.format_weekly` 본문 불변 [Must-pass]

- **Given**: 동일 입력 데이터로 본 SPEC 머지 전/후 `formatter.format_weekly`를 호출
- **When**: 두 출력 비교
- **Then**: 바이트 단위로 동일.
- **검증 도구**: 기존 `formatter` 테스트가 있으면 그대로 통과. 없으면 회귀 fixture를 신규 추가하여 머지 전 출력을 캡처하고 머지 후와 비교.

### Scenario 7.4: KR 워크플로우 cron 불변 [Must-pass]

- **Given**: `.github/workflows/flow-kr.yml`의 `on.schedule[0].cron`
- **When**: 본 SPEC 머지 후 파일 검사
- **Then**: 값이 `'10 9 * * 1-5'`로 유지된다.
- **검증 도구**: 워크플로우 YAML 파싱 후 assert (또는 단순 grep으로 변경 여부 확인).

### Scenario 7.5: `telegram_push.send` 시그니처 불변 [Must-pass]

- **Given**: `inspect.signature(telegram_push.send)`
- **When**: 본 SPEC 머지 후 시그니처 확인
- **Then**: 머지 전 시그니처와 동일 (파라미터 추가/제거 없음).

---

## 8. 휴장 캘린더 라이브러리 (REQ-MF-HOL-003)

### Scenario 8.1: NYSE 캘린더 fixture 정확도 [Must-pass]

- **Given**: `pandas_market_calendars` NYSE 캘린더로 다음 날짜 조회
- **When**: 각 날짜에 대해 거래일 여부 판정
- **Then**:
  - 2025-12-25 (크리스마스) → 휴장
  - 2025-07-04 (독립기념일) → 휴장
  - 2025-11-27 (추수감사절) → 휴장
  - 2025-11-28 (추수감사절 다음날) → 거래일 (반장)
  - 2025-09-15 (정상 평일) → 거래일
  - 2025-01-01 (신정) → 휴장

### Scenario 8.2: KR 캘린더 fixture 정확도 [Must-pass]

- **Given**: plan.md R1에서 결정된 라이브러리(`pykrx` 또는 `exchange_calendars` XKRX)로 다음 날짜 조회
- **When**: 각 날짜에 대해 거래일 여부 판정
- **Then**:
  - 2025-05-05 (어린이날) → 휴장
  - 2025-08-15 (광복절, 금요일) → 휴장
  - 2025-10-03 (개천절, 금요일) → 휴장
  - 2025-05-26 (월요일 정상) → 거래일
  - 2025-12-25 (크리스마스, 한국 휴장) → 휴장
  - 2026-01-01 (신정) → 휴장

---

## 9. 통합 점검 (Definition of Done)

본 SPEC이 머지되기 위한 종합 체크리스트:

### 9.1 코드 변경 [Must-pass]

- [ ] `market_flow/calendar_utils.py` 신설, 4개 공개 함수 구현 (`is_us_in_dst`, `is_us_trading_day`, `is_kr_trading_day`, `is_last_kr_trading_day_of_week`)
- [ ] `market_flow/daily_kr.py`에 KR 휴장 분기 + 시각 주입 + dry-run 일관성
- [ ] `market_flow/daily_us.py`에 DST 게이트 + US 휴장 분기 + 시각 주입 + dry-run 일관성
- [ ] `market_flow/weekly.py`에 마지막 거래일 게이트 + 시각 주입 + dry-run 일관성
- [ ] `.github/workflows/flow-us.yml` dual-cron 등록 + `MARKET_SCHEDULE` 환경변수 주입
- [ ] `.github/workflows/flow-weekly.yml` cron 확장 (`30 9 * * 5` → `30 9 * * 1-5`)
- [ ] `.github/workflows/flow-kr.yml` 변경 없음 (회귀 차단 확인)
- [ ] `market_flow/requirements.txt`에 `pandas_market_calendars` 추가, plan R1 결정에 따라 `exchange_calendars` 또는 `pykrx` 추가/유지

### 9.2 테스트 [Must-pass]

- [ ] 위 9개 섹션의 Must-pass 시나리오 전부 단위 테스트로 구현
- [ ] `pytest market_flow/tests/` 전체 통과
- [ ] 시각 주입이 모든 핵심 분기에서 작동 (Scenario 5.2)
- [ ] dry-run 시 `requests.post` 0회 호출 (Scenario 6.2)
- [ ] 이중 발송 회귀 테스트 통과 (Scenario 7.1)

### 9.3 품질 게이트 [Must-pass]

- [ ] `ruff check market_flow/` 클린
- [ ] `market_flow/calendar_utils.py` 라인 커버리지 85%+
- [ ] LSP 변경 파일 zero errors, zero warnings
- [ ] @MX 태그 부착 (`@MX:ANCHOR` on `is_*_trading_day` with `@MX:REASON`, `@MX:WARN` on DST 게이트, `@MX:NOTE` 보조)
- [ ] @MX 태그 설명 언어는 한국어 (`language.yaml.code_comments: ko`)

### 9.4 운영 검증 [Should-pass]

- [ ] 머지 후 첫 번째 미국 휴장일(또는 fixture 시뮬레이션)에서 텔레그램 한 줄 메시지 수신
- [ ] 머지 후 첫 번째 한국 휴장일에서 텔레그램 한 줄 메시지 수신
- [ ] 머지 후 첫 번째 DST 시즌 전환 후 평일에 EDT/EST 잡 중 정확히 한 쪽만 발송 (Actions 실행 로그로 확인)
- [ ] 머지 후 첫 번째 "금요일 휴장" 주에 직전 거래일에 주간 리포트 수신

### 9.5 문서·추적성 [Must-pass]

- [ ] 커밋 메시지에 `SPEC-MF-SCHED-001` 명시
- [ ] plan.md의 사전 조사(R1~R5) 결정 사항이 plan.md 또는 research.md에 기록됨
- [ ] 변경 파일 목록이 spec.md의 "Files to Modify / Create" 섹션과 일치

---

## 10. 회귀 차단 (Regression Suite)

본 SPEC 이후에도 다음 기존 동작이 유지되어야 한다:

- 정상 평일 한국 거래일 KST 18:10에 평소 보고서 발송 (REQ-MF-SCHED-001)
- 정상 평일 미국 거래일에 마감 30분 후 보고서 발송 (REQ-MF-SCHED-002)
- 정상 금요일에 주간 리포트 KST 18:30 발송 (Scenario 4.1)
- `formatter.format_weekly` 본문 형식 (Scenario 7.3)
- `--no-telegram` 플래그의 기존 동작(commit d78d0a6) (Scenario 6.2)
- `GOLDENQUEENS_BOT_TOKEN` / `GOLDENQUEENS_CHAT_ID` secrets 사용 패턴

회귀 검증은 기존 테스트 슈트(있다면) + 본 SPEC에서 추가된 회귀 시나리오(Scenario 7.x)로 보장한다.
