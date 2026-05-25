# SPEC-MF-SCHED-001 Implementation Plan

## Approach Summary

`market_flow/`의 3개 텔레그램 봇과 3개 GitHub Actions 워크플로우에 (1) DST 자동 반영(US dual-cron + 환경변수 게이트), (2) 한국·미국 휴장 인지(거래소 캘린더 라이브러리 위임), (3) 주간 리포트 마지막 거래일 이월(weekly cron 확장 + 게이트)을 추가한다.

모든 변경은 **추가적(additive)**이며, 핵심 판정 로직은 시각 주입(`now: datetime` 파라미터)으로 결정론적 단위 테스트가 가능하도록 설계한다. `formatter.py`, `telegram_push.py`, `fetchers/` 모듈은 변경하지 않는다 (휴장이면 fetcher 호출 자체를 생략하는 방식).

구현 방법론은 `.moai/config/sections/quality.yaml`의 `development_mode`에 따른다(현 기본값 TDD: RED → GREEN → REFACTOR). 핵심 판정 함수에 대해 시각 주입 기반 결정론적 테스트를 RED 단계에서 작성한다.

---

## Pre-Implementation Research (사전 조사)

본 SPEC 구현을 시작하기 전에 다음 항목을 plan 보강으로 마무리해야 한다. 각 항목은 결정 사항을 plan.md(또는 별도 `research.md`)에 기록한다.

### R1. `pykrx`의 거래일 판정 API 적합성 검증

목적: KR 휴장 판정을 위해 신규 라이브러리(`exchange_calendars`)를 도입할지, 기존 `pykrx`로 충분한지 결정한다.

검증 절차:
1. `market_flow/requirements.txt`에 `pykrx`가 명시되어 있는지 확인 (현재 `yfinance`, `pandas`, `python-dotenv` 3개만 명시되어 있어 실제 의존성 채택 여부 확인 필요 — `weekly.py`의 `fetchers.naver_kr.fetch_kospi_daily` 구현체가 `pykrx`를 쓰는지 우선 확인).
2. `pykrx`가 채택돼 있다면 다음 API의 동작을 확인:
   - `pykrx.stock.get_previous_business_day(date=YYYYMMDD)` — 지정일이 거래일이면 그대로 반환, 비거래일이면 직전 거래일 반환 (반환값이 입력값과 같으면 "거래일", 다르면 "비거래일")
   - `pykrx.stock.get_nearest_business_day_in_a_week(date=YYYYMMDD, prev=True)` — 동일 패턴
3. 검증 fixture: 2025-05-05(어린이날, 비거래일), 2025-08-15(광복절, 금요일 비거래일), 2025-11-28(평일 정상 거래일).
4. 오프라인 동작 여부 확인: GitHub Actions Linux 환경에서 추가 네트워크 호출 없이 결정 가능한지 (캘린더 데이터가 패키지에 번들되어 있는지).
5. **결정 기준**:
   - `pykrx`로 위 3개 fixture 모두 정확히 판정 + 네트워크 호출 없이 동작 → `pykrx` 채택, `exchange_calendars` 미도입
   - 그 외 → `exchange_calendars`(XKRX 캘린더) 도입, `requirements.txt`에 추가

### R2. `pandas_market_calendars` NYSE 캘린더 동작 확인

목적: 미국 휴장 판정 라이브러리 API 안정성 및 GitHub Actions 호환성 확인.

검증 절차:
1. 설치: `pip install pandas_market_calendars` (의존성 무게 확인 — pandas, numpy 등 이미 yfinance 경유로 포함되어 있음)
2. 사용 패턴:
   ```python
   import pandas_market_calendars as mcal
   nyse = mcal.get_calendar("NYSE")
   schedule = nyse.schedule(start_date="2025-12-25", end_date="2025-12-25")
   # 빈 DataFrame → 휴장, 행 있음 → 거래일
   ```
3. 검증 fixture: 2025-12-25(크리스마스, 휴장), 2025-07-04(독립기념일, 휴장), 2025-11-27(추수감사절, 휴장), 2025-11-28(추수감사절 다음날, 13:00 ET 조기 마감 거래일), 2025-09-15(정상 평일).
4. 오프라인 동작 확인: 캘린더 데이터가 번들에 포함되어 외부 API 호출 없이 동작하는지.

### R3. 모듈 위치 결정

질문: 휴장·DST 판정 헬퍼를 어디에 둘 것인가?

옵션:
- **옵션 A** (권장): `market_flow/calendar_utils.py` 신설. 세 스크립트(`daily_kr.py`, `daily_us.py`, `weekly.py`)가 공통 임포트.
  - 장점: 단일 진입점, 테스트 집중, 응집도 ↑
  - 단점: 신규 모듈 추가
- **옵션 B**: 각 스크립트에 헬퍼 인라인.
  - 장점: 파일 수 변화 없음
  - 단점: 중복 코드, 테스트 분산

**결정**: 옵션 A. `market_flow/calendar_utils.py`에 다음을 둔다:
- `is_kr_trading_day(now: datetime | None = None) -> bool`
- `is_us_trading_day(now: datetime | None = None) -> bool`
- `is_us_in_dst(now: datetime | None = None) -> bool`
- `is_last_kr_trading_day_of_week(now: datetime | None = None) -> bool`

각 함수의 기본값은 `datetime.now(<해당 타임존>)`.

### R4. 테스트 디렉토리 위치 결정

질문: 테스트를 `market_flow/tests/`에 둘 것인지, 프로젝트 루트 `tests/`에 둘 것인지?

검증 절차:
1. `ls /Users/yuji/rs-golden-queens/tests/` 와 `ls /Users/yuji/rs-golden-queens/market_flow/tests/` 존재 여부 확인.
2. `.github/workflows/test.yml`의 pytest 실행 경로 확인.
3. 기존 관례를 따른다 (없으면 `market_flow/tests/`를 신설하여 `market_flow/` 자체 응집성 유지).

### R5. `--no-telegram` dry-run 처리 위치 확인

질문: 현행 `--no-telegram` 플래그가 어디서 분기되는가? (commit d78d0a6)

검증 절차:
1. `git show d78d0a6` 또는 현 코드에서 `--no-telegram` 문자열 검색.
2. 휴장 메시지에서도 동일 분기를 재사용할 수 있도록 모듈 설계.

---

## Task Breakdown

### Task 1 (RED): 시각 주입 가능한 판정 함수 테스트 작성

`market_flow/tests/test_calendar_utils.py` 작성. 다음 케이스를 모두 작성하여 RED 상태(import 실패 또는 함수 부재)에서 시작:

**DST 판정 (`is_us_in_dst`)**
- `test_us_dst_edt_period`: `now = 2025-06-15 10:00 EDT` → True
- `test_us_dst_est_period`: `now = 2025-12-15 10:00 EST` → False
- `test_us_dst_transition_spring_forward`: `now = 2025-03-09 02:30 ET` 전후 → 전환일 다음 평일(3/10)은 EDT
- `test_us_dst_transition_fall_back`: `now = 2025-11-02 02:30 ET` 전후 → 전환일 다음 평일(11/3)은 EST

**미국 거래일 판정 (`is_us_trading_day`)**
- `test_us_holiday_christmas`: `now = 2025-12-25 (ET)` → False
- `test_us_holiday_independence`: `now = 2025-07-04 (ET)` → False
- `test_us_thanksgiving_next_day_early_close`: `now = 2025-11-28 (ET)` → True (반장도 거래일)
- `test_us_regular_weekday`: `now = 2025-09-15 (ET)` → True
- `test_us_weekend`: `now = 2025-05-24 (ET, 토)` → False

**한국 거래일 판정 (`is_kr_trading_day`)**
- `test_kr_holiday_childrens_day`: `now = 2025-05-05 (KST)` → False
- `test_kr_holiday_liberation_day`: `now = 2025-08-15 (KST, 금)` → False
- `test_kr_regular_weekday`: `now = 2025-05-26 (KST, 월)` → True
- `test_kr_weekend`: `now = 2025-05-24 (KST, 토)` → False

**마지막 거래일 판정 (`is_last_kr_trading_day_of_week`)**
- `test_friday_is_trading_day`: 금요일이 거래일 → 금요일에 True, 같은 주 다른 평일에 False
- `test_friday_is_holiday_thursday_is_last`: 금요일 휴장 → 목요일 True, 금요일 False
- `test_friday_and_thursday_holiday`: 금/목 휴장 → 수요일 True

**시각 주입 누락 검출**
- `test_default_uses_now`: `now=None` 호출 시 현재 시각 기반 동작 (smoke test, monkeypatch로 datetime 고정 가능)

WHY: 시각 주입 테스트가 없으면 cron 실행 시점에 따라 비결정적 동작이 발생한다. RED 단계에서 모든 분기를 frozen-time fixture로 고정한다.

### Task 2 (GREEN): `calendar_utils.py` 구현

`market_flow/calendar_utils.py`에 다음 함수 구현:

```
is_us_in_dst(now: datetime | None = None) -> bool
is_us_trading_day(now: datetime | None = None) -> bool
is_kr_trading_day(now: datetime | None = None) -> bool
is_last_kr_trading_day_of_week(now: datetime | None = None) -> bool
```

구현 메모:
- `is_us_in_dst`: `now.astimezone(ZoneInfo("America/New_York")).dst()`가 `timedelta(0)`가 아니면 True.
- `is_us_trading_day`: R2 결정 결과(`pandas_market_calendars` NYSE)로 판정. 입력은 `now.astimezone(ZoneInfo("America/New_York")).date()`.
- `is_kr_trading_day`: R1 결정 결과(`pykrx` 또는 `exchange_calendars` XKRX)로 판정. 입력은 `now.astimezone(ZoneInfo("Asia/Seoul")).date()`.
- `is_last_kr_trading_day_of_week`: 오늘이 KR 거래일이면서, 오늘+1 ~ 같은 주 금요일까지의 모든 날이 비거래일이면 True. 토/일은 자연스럽게 비거래일로 처리.

Python 3.13 사용 (현행 워크플로우 `python-version: '3.13'`). 표준 라이브러리: `zoneinfo`, `datetime`.

### Task 3 (RED): 스크립트 분기 테스트 작성

`market_flow/tests/test_daily_kr.py`, `test_daily_us.py`, `test_weekly.py` 작성. 다음 케이스:

**daily_kr.py**
- `test_kr_holiday_sends_one_liner`: 한국 휴장일에 `daily_kr.main(now=<2025-05-05>)` 호출 → `telegram_push.send` mock 호출 인자가 `"[KR] 오늘은 휴장입니다"`, `fetchers.naver_kr.fetch_today`는 호출되지 않음.
- `test_kr_holiday_dry_run`: 위와 동일 + `--no-telegram` → stdout에 메시지 출력, `telegram_push.send` 미호출.
- `test_kr_trading_day_sends_report`: 평일 정상 거래일 → 기존 동작(fetcher 호출 + 보고서 발송) 유지.

**daily_us.py**
- `test_us_dst_gate_blocks_off_season`: `MARKET_SCHEDULE=est` 환경변수 + `now`가 EDT 시즌 → `sys.exit(0)` 즉시 종료, `telegram_push.send` 미호출.
- `test_us_dst_gate_passes_in_season`: `MARKET_SCHEDULE=edt` + `now`가 EDT 시즌 → 정상 진행.
- `test_us_holiday_sends_one_liner`: DST 게이트 통과 후 미국 휴장일 → `"[US] 오늘은 휴장입니다"` 송신, `fetchers.us_market.fetch_us_close` 미호출.
- `test_us_holiday_dry_run`: 위와 동일 + `--no-telegram` → stdout, 미호출.
- `test_us_trading_day_sends_summary`: 정상 거래일 → 기존 동작 유지.

**weekly.py**
- `test_weekly_skips_on_non_last_trading_day`: `now`가 월/화/수/목(금요일이 정상 거래일) → `sys.exit(0)`, `telegram_push.send` 미호출.
- `test_weekly_sends_on_friday_normal`: 금요일 + 거래일 → 정상 발송.
- `test_weekly_sends_on_thursday_when_friday_holiday`: `now`가 목요일 + 금요일 휴장 → 목요일 발송.
- `test_weekly_dry_run_on_last_trading_day`: 위와 동일 + `--no-telegram` → stdout 출력만.

### Task 4 (GREEN): 스크립트 수정

**`daily_kr.py`** 변경:
- `main(argv=None, now=None)` 시그니처로 변경. `now`는 기본값 `datetime.now(ZoneInfo("Asia/Seoul"))`.
- `--no-telegram` 플래그 파싱은 기존 commit d78d0a6의 방식을 재사용.
- 분기:
  1. `if not is_kr_trading_day(now): _emit("[KR] 오늘은 휴장입니다", dry_run)` 후 return.
  2. else 기존 데이터 수집 + 보고서 발송 경로.
- `_emit(text, dry_run)` 헬퍼: `dry_run`이면 `print(text)`, 아니면 `telegram_push.send(text)`.

**`daily_us.py`** 변경:
- `main(argv=None, now=None)` 시그니처. `now`는 기본값 `datetime.now(ZoneInfo("America/New_York"))`.
- 분기:
  1. DST 게이트: `os.getenv("MARKET_SCHEDULE")`이 `"edt"`인데 `not is_us_in_dst(now)`이거나, `"est"`인데 `is_us_in_dst(now)`면 `sys.exit(0)`. 환경변수가 미설정이면 게이트 무시 (로컬/`workflow_dispatch` 수동 실행 지원).
  2. `if not is_us_trading_day(now): _emit("[US] 오늘은 휴장입니다", dry_run)` 후 return.
  3. else 기존 데이터 수집 + 보고서 발송.

**`weekly.py`** 변경:
- `main(argv=None, now=None)` 시그니처. `now` 기본값 `datetime.now(ZoneInfo("Asia/Seoul"))`.
- 분기:
  1. `if not is_last_kr_trading_day_of_week(now): sys.exit(0)`.
  2. else 기존 데이터 수집 + 발송.
- 휴장 한 줄 메시지 발송 없음 (주간 리포트는 침묵 스킵; 마지막 거래일에 한 번 발송).

### Task 5: GitHub Actions 워크플로우 수정

**`.github/workflows/flow-us.yml`**:
- `on.schedule`에 두 개의 cron 등록:
  ```yaml
  schedule:
    - cron: '30 20 * * 1-5'  # EDT: NYSE 16:00 EDT 마감 + 30분
    - cron: '30 21 * * 1-5'  # EST: NYSE 16:00 EST 마감 + 30분
  ```
- 한 잡 안에서 `MARKET_SCHEDULE`을 cron 식별로 주입하는 방법: GitHub Actions의 `github.event.schedule` 컨텍스트로 분기.
  ```yaml
  - name: Send US market summary
    env:
      MARKET_SCHEDULE: ${{ github.event.schedule == '30 20 * * 1-5' && 'edt' || 'est' }}
      GOLDENQUEENS_BOT_TOKEN: ${{ secrets.GOLDENQUEENS_BOT_TOKEN }}
      GOLDENQUEENS_CHAT_ID:   ${{ secrets.GOLDENQUEENS_CHAT_ID }}
      TZ: Asia/Seoul
    run: python daily_us.py
  ```
- `workflow_dispatch` 수동 트리거 시 `MARKET_SCHEDULE`은 빈 문자열이 되어 게이트가 무시되도록 스크립트에서 처리 (Task 4 참조).

**`.github/workflows/flow-weekly.yml`**:
- `on.schedule`을 `'30 9 * * 5'` → `'30 9 * * 1-5'`로 확장.
- 다른 설정은 불변.

**`.github/workflows/flow-kr.yml`**:
- 변경 없음 (REQ-MF-SCHED-NEG-001: KR cron 불변).

### Task 6: `requirements.txt` 갱신

`market_flow/requirements.txt`에 추가:
- `pandas_market_calendars>=4.4` (NYSE 캘린더, 정확한 버전 핀은 사전 검증 결과로 결정)
- R1 결정에 따라 `exchange_calendars>=4.5` 조건부 추가
- R1에서 `pykrx`가 누락된 의존성으로 확인되면 명시적으로 추가

### Task 7 (REFACTOR): 일관성 정리

- `calendar_utils.py`에 docstring 추가, 모든 함수에 타입 힌트 명시 (Python 3.13).
- 시각 비교/타임존 변환 로직이 중복되면 헬퍼로 추출.
- `daily_kr.py`, `daily_us.py`, `weekly.py`의 `_emit` 헬퍼가 동일하면 `calendar_utils.py` 또는 `telegram_push.py` 측으로 정리 (단, `telegram_push.py` 시그니처 자체는 변경하지 않음 — REQ-MF-SCHED-NEG-001).
- `ruff check market_flow/` 통과 확인.
- 모든 단위 테스트 통과 확인.

### Task 8: MX 태그 부착

`.claude/rules/moai/workflow/mx-tag-protocol.md`에 따라:
- `calendar_utils.is_us_in_dst` → `# @MX:NOTE: [AUTO] DST 시즌 판정 (America/New_York 기준)` (신규 공개 함수, 정량적 fan_in 측정 후 ANCHOR 승격 고려)
- `calendar_utils.is_*_trading_day` → `# @MX:ANCHOR: [AUTO] 거래일 판정 진입점` + `# @MX:REASON: fan_in >= 3 (daily_kr, daily_us, weekly에서 직접 호출)`
- `daily_us.main`의 DST 게이트 분기 → `# @MX:WARN: [AUTO] 이중 발송 방지 게이트 - 환경변수와 실제 시즌 불일치 시 sys.exit(0)` + `# @MX:REASON: dual-cron 구조상 두 잡 중 하나만 진행해야 함`
- 태그 설명 언어는 `language.yaml.code_comments: ko`에 따라 한국어.

---

## Single Module vs Inlined Helpers — Decision Point

`calendar_utils.py` 신설 vs 각 스크립트 인라인:

**Option A — `calendar_utils.py` 모듈 신설 (권장)**
- 장점: 테스트 단일 집중, fan_in 3 이상 명확, 향후 통합 시 단일 진입점
- 단점: 모듈 1개 증가

**Option B — 각 스크립트 인라인**
- 장점: 파일 수 증가 없음
- 단점: 중복, 테스트 분산, ANCHOR 태그 정당화 어려움

**Recommendation**: Option A. 의사결정 사유:
- 세 스크립트가 동일한 거래일·DST 판정 로직을 요구 → DRY 원칙
- @MX:ANCHOR 태그가 fan_in >= 3을 명시적으로 표현하려면 단일 함수 진입점이 필요
- 단위 테스트가 한 모듈에 집중되면 시각 주입 fixture 공유 가능

---

## Technical Stack

- Python 3.13 (현행 워크플로우 `python-version: '3.13'`)
- 표준 라이브러리: `zoneinfo`, `datetime`, `os`, `sys`, `argparse` 또는 직접 파싱
- 신규 의존성:
  - `pandas_market_calendars` (확정)
  - `exchange_calendars` 또는 `pykrx` (R1 사전 조사 결과로 결정)
- 테스트 프레임워크: pytest (저장소 `test.yml`이 pytest 사용 중인지 R4에서 확인)
- 린트: `ruff check` (Python 가이드 표준)

---

## Risks & Mitigations

| 위험 | 가능성 | 영향 | 완화책 |
|------|--------|------|--------|
| GitHub Actions `github.event.schedule` 표현식 미지원 | 낮음 | 높음 (DST 게이트 무력화) | 사전에 단순 워크플로우로 `github.event.schedule` 값 출력 테스트; 미지원 시 두 잡(`job_edt`, `job_est`)으로 분리하고 각 잡에 환경변수 하드코딩 |
| `pandas_market_calendars` 또는 KR 캘린더 라이브러리가 GitHub Actions Linux runner에서 외부 네트워크 호출 시도 | 낮음 | 중간 (실패 시 발송 누락) | 사전 조사에서 오프라인 동작 확인; 호출 실패 시 fail-safe로 "거래일로 간주"하여 보고서 발송 (휴장일에 정상 데이터 시도 → 빈 데이터로 발송되더라도 안전한 fallback) — 다만 본 SPEC은 fallback 동작 미규정. 별도 PR에서 결정 필요 |
| `pykrx`의 휴장 데이터가 최신 공휴일 반영 지연 | 중간 | 중간 (휴장인데 정상 발송 시도) | R1 검증 후 부족하면 `exchange_calendars` 채택. 최소 1년 주기로 의존성 업데이트 권장. |
| GitHub Actions cron 15~20분 지연으로 인한 거래소 로컬 날짜 경계 문제 | 매우 낮음 | 낮음 | REQ-MF-HOL-004로 거래소 로컬 날짜 기준 판정 → cron 지연과 무관 |
| dual-cron 구조에서 둘 다 발송하는 이중 발송 사고 | 낮음 | 높음 (사용자 신뢰 손상) | 단위 테스트에서 게이트 양방향(EDT시즌·EST잡, EST시즌·EDT잡) 차단 검증 + `test_us_dst_gate_blocks_off_season` |
| `workflow_dispatch` 수동 실행 시 `MARKET_SCHEDULE` 미설정으로 게이트 통과 → 휴장일에도 발송 | 낮음 | 낮음 (수동 실행은 의도된 동작) | 휴장 게이트(REQ-MF-HOL-002)는 별도 단계라 휴장일에는 한 줄 메시지로 안전하게 처리됨 |
| `weekly.py` cron 확장으로 평일 18:30에 매번 실행되어 GitHub Actions 분 단위 사용량 증가 | 중간 | 매우 낮음 | 게이트 함수가 빠르게 `sys.exit(0)`. 무료 quota 영향 미미 |
| `--no-telegram` 분기 누락으로 휴장 메시지가 실제 텔레그램에 전송됨 | 낮음 | 중간 | `test_*_holiday_dry_run` 단위 테스트로 회귀 차단 |
| `formatter.format_weekly` 우발적 호출 회귀 (`weekly.py`에서 fetcher → formatter 경로) | 낮음 | 낮음 | 게이트 통과 시점에만 호출되므로 기존 동작 동일. `test_weekly_sends_on_*` 회귀 테스트로 확인 |

---

## Milestones (priority-ordered, no time estimates)

**Priority High**
- M1: 사전 조사 R1~R5 완료, 라이브러리 결정 plan.md에 기록
- M2: Task 1, Task 2 완료 — `calendar_utils.py` GREEN, 모든 시각 주입 테스트 통과
- M3: Task 3, Task 4 완료 — 세 스크립트 모두 DST 게이트 + 휴장 게이트 + 마지막 거래일 게이트 동작, 단위 테스트 통과
- M4: Task 5 완료 — `flow-us.yml` dual-cron, `flow-weekly.yml` cron 확장 머지

**Priority Medium**
- M5: Task 6 완료 — `requirements.txt` 갱신, `pip install -r requirements.txt` 클린
- M6: Task 7 완료 — `ruff check` 통과, 코드 정리
- M7: Task 8 완료 — @MX 태그 부착 및 보고서 생성

**Priority Low**
- M8: 실제 DST 전환 후 첫 평일(2026년 가을 EDT→EST 전환 후 첫 평일) 워크플로우 로그 사후 검증 (별도 SPEC/이슈로 추적)

---

## Reference Implementation Pointers

- 현행 `daily_kr.py:1-27` — 한국장 발송 진입점, 인자/시각 주입 위치
- 현행 `daily_us.py:1-26` — 미국장 발송 진입점, 타겟 날짜 인자 처리 방식
- 현행 `weekly.py:1-49` — 주간 리포트 진입점, yfinance + Naver 결합 패턴
- 현행 `flow-us.yml` — cron 단일 등록 패턴 (dual-cron으로 확장)
- 현행 `flow-weekly.yml` — 요일 한정 cron (`* * 5` → `* * 1-5`)
- commit `d78d0a6` — `--no-telegram` dry-run 분기 위치 (휴장 메시지에서도 재사용)
- `.github/workflows/test.yml` — 테스트 워크플로우 (단위 테스트 통합 위치 확인용)

---

## Quality Gates

- TRUST 5:
  - **Tested**: `test_calendar_utils.py` + `test_daily_kr.py` + `test_daily_us.py` + `test_weekly.py` 전부 통과, 시각 주입 fixture로 결정론적 검증
  - **Readable**: 함수명이 의미를 자명하게 전달 (`is_kr_trading_day`, `is_last_kr_trading_day_of_week`)
  - **Unified**: `ruff check market_flow/` 클린
  - **Secured**: 외부 입력은 환경변수와 cron 식별만; 텔레그램 secret은 기존 처리 그대로
  - **Trackable**: 커밋 메시지에 `SPEC-MF-SCHED-001` 참조
- Coverage: `market_flow/calendar_utils.py` 85%+ 권장
- Lint: `ruff check market_flow/` 클린
- 테스트: 전체 pytest 통과
- LSP: 변경 파일 zero errors
- 운영 검증: 머지 후 첫 미국 휴장일 + 첫 한국 휴장일에서 텔레그램 한 줄 메시지 수신 확인 (수동 sanity)
