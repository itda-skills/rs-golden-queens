---
id: SPEC-MF-TEST-001
version: 0.1.0
status: draft
created: 2026-05-25
updated: 2026-05-25
author: Chinseok
priority: high
issue_number: 0
---

# SPEC-MF-TEST-001: market_flow 패키지 테스트 슈트 복원

## HISTORY

- 2026-05-25 (v0.1.0): 초안 작성. 커밋 8fd2c7f에서 `naver_investor_flow/` 패키지가 제거되며 함께 삭제된 `tests/` 디렉터리(13개 파일)를 `market_flow/` 패키지에 맞춰 새로 구축. 단위 테스트(formatter/telegram_push/fetchers)·통합 스모크(daily_kr/daily_us/weekly main()) · `pytest.mark.live` 마커 기반 실제 네트워크 스모크의 3축 구조로 명세. CI 정책(baa183f 이후 live 마커 기반 단일 Linux 매트릭스)과 정합. 픽스처는 `tests/fixtures/`에 정적 저장하여 외부 의존성 최소화. issue_number는 추후 결정.

---

## Overview

### 배경

커밋 8fd2c7f에서 구 `naver_investor_flow/` 패키지가 신규 `market_flow/` 패키지로 완전 교체되었다. 이 과정에서 구 패키지를 대상으로 작성된 기존 `tests/` 디렉터리(13개 파일)도 함께 삭제되었으며, 현재 `market_flow/` 패키지는 **테스트 커버리지가 0%**인 상태로 운영 중이다. CI 워크플로우(`test.yml`)는 커밋 baa183f에서 live 마커 기반·Linux 단일 OS로 이미 전환되어 있으나, 실행할 테스트 자체가 존재하지 않아 사실상 무의미한 통과 상태가 지속되고 있다.

`market_flow/` 패키지는 다음 8개 모듈로 구성된다:

```
market_flow/
├── __init__.py
├── formatter.py              # CJK/이모지 시각 폭 보정, 등폭 테이블 렌더
├── telegram_push.py          # MARKET_FLOW_DRY_RUN=1 시 stdout (TTY ANSI 색)
├── daily_kr.py               # 한국장 엔트리 (평일 KST 18:10)
├── daily_us.py               # 미국장 엔트리 (화~토 KST 06:30)
├── weekly.py                 # 주간 엔트리 (금 KST 18:30)
└── fetchers/
    ├── __init__.py
    ├── naver_kr.py           # 네이버 모바일/데스크탑 API 파서
    └── us_market.py          # yfinance 어댑터 (지수·VIX·섹터·매크로·워치)
```

평일·휴장 게이트와 DST 게이트를 다루는 후속 SPEC(SPEC-MF-SCHED-001)이 별도로 진행 중이며, 본 SPEC은 그와 독립적으로 **현재 코드 베이스의 정합성·회귀 안전망 확보**를 목적으로 한다. SPEC-MF-SCHED-001 머지 후 추가되는 `calendar_utils.py` 등은 본 SPEC의 범위 밖이며, 해당 SPEC이 자체 테스트를 동반한다.

### 목표

`market_flow/` 패키지가 다음을 만족하도록 테스트 슈트를 신설한다:

1. **단위 테스트**: 각 모듈(`formatter.py`, `telegram_push.py`, `fetchers/naver_kr.py`, `fetchers/us_market.py`)의 순수 로직을 외부 의존성 없이 결정론적으로 검증.
2. **통합 스모크**: `daily_kr.py`, `daily_us.py`, `weekly.py`의 `main()` 호출이 `MARKET_FLOW_DRY_RUN=1` + 네트워크 모킹 조건에서 비정상 종료 없이 stdout 출력을 생성.
3. **라이브 마커 분리**: `pytest.mark.live`로 표시된 실제 네이버/yfinance 호출 스모크 1~2개를 deselect 기본 정책으로 운영. CI는 live 미포함으로 실행, 별도 잡에서 live 옵트인.
4. **픽스처 정적화**: 네이버 모바일/데스크탑 응답과 yfinance 다운로드 결과의 캡처본을 `tests/fixtures/` 아래에 저장하여 단위·통합 테스트에서 재사용.
5. **커버리지 목표**: `market_flow/` 전체 80% 이상 (live 제외, 통합 스모크 포함).

테스트 프레임워크는 `pytest`(+ `pytest-mock` 또는 `unittest.mock`)를 사용한다. 추가 외부 의존성은 picklable한 yfinance DataFrame fixture 직렬화를 위해 필요 시 `pytest-mock`만 도입한다.

### 비목표 (Non-Goals)

- `market_flow/` 코드 변경 — 본 SPEC은 테스트만 추가한다. `daily_*.py`/`weekly.py`의 시그니처 변경, `formatter.py`의 로직 변경 등은 별도 SPEC.
- SPEC-MF-SCHED-001이 도입할 `calendar_utils.py`·DST 게이트·휴장 게이트 테스트 — 해당 SPEC이 자체 acceptance에서 다룬다.
- 텔레그램 API 응답 스키마 변경 대응 — 텔레그램 봇 API는 외부 시스템으로 간주, mock 응답 형태는 현행 코드가 기대하는 최소 형태(`{"ok": True, "result": {"message_id": ...}}`)로 고정.
- 네이버 모바일 API 또는 yfinance의 응답 스키마 회귀 자동 감지 — 본 SPEC은 캡처 시점의 응답을 정답으로 간주. 스키마 변경 자동 감지는 별도 SPEC.
- 코드 커버리지 100% — `__main__` 분기, 예외 경로의 일부는 80% 목표 달성에 포함되지 않을 수 있음.
- 성능 벤치마크·부하 테스트 — 본 SPEC 범위 밖.
- 형태소·자연어 출력 검증 — 텔레그램 보고서 본문의 한국어 문장이 자연스러운지 등의 정성 평가는 비대상. 구조·수치·이모지·시각 폭 등 결정론적으로 검증 가능한 속성에 한정.
- `pytest-asyncio` 도입 — `market_flow/`는 동기 코드이므로 비동기 테스트 인프라 불필요.

---

## EARS Requirements

### REQ-MF-TEST-001: 테스트 디렉터리 신설 (Ubiquitous)

The system **shall** provide a `tests/` directory at the project root containing pytest-compatible test modules covering all `market_flow/` modules. The directory layout **shall** follow the standard structure:

- `tests/__init__.py`
- `tests/conftest.py` — 공통 픽스처 및 `pytest.mark.live` deselect 훅
- `tests/unit/` — 단위 테스트
- `tests/integration/` — 통합 스모크
- `tests/live/` — `@pytest.mark.live` 부착된 실제 네트워크 스모크
- `tests/fixtures/` — 캡처된 API 응답 정적 파일 (JSON/HTML/pickle)

`tests/` 위치는 프로젝트 루트(`/Users/yuji/rs-golden-queens/tests/`)로 고정한다 (CI `test.yml`의 pytest 실행 경로와 일치).

### REQ-MF-TEST-002: 기본 실행에서 라이브 자동 제외 (State-driven)

**While** the user invokes plain `pytest` without explicit marker arguments, the system **shall** automatically **deselect** all tests marked with `@pytest.mark.live` and **shall** run only unit and integration tests.

- `conftest.py`의 `pytest_collection_modifyitems` 훅으로 구현한다.
- 사용자가 `pytest -m live`를 명시하면 live 테스트만 실행한다.
- 사용자가 `pytest -m "not live"`를 명시해도 동일 결과(불필요한 중복 옵션이지만 충돌 없음).
- 사용자가 `pytest -m "live or not live"`를 명시하면 모든 테스트 실행 (옵트인 전체).
- 검증 방법: CI 로그에서 기본 `pytest` 호출 시 live 테스트가 "deselected"로 표시되고, `pytest -m live` 호출 시 unit/integration이 deselect.

### REQ-MF-TEST-003: formatter 시각 폭 보정 검증 (Ubiquitous)

The system **shall** verify that `market_flow/formatter.py`의 `_vw`, `_padr`, `_padl` 함수가 다음 입력 클래스에 대해 정확한 시각 폭을 계산한다:

- ASCII 문자: 1칸
- CJK 문자 (`unicodedata.east_asian_width(c) in ("W", "F")`): 2칸
- `_WIDE_EMOJI` 집합에 속하는 이모지(🔴🔵⚪🔥🇰🇷🇺🇸📊📈📉📅⭐💵💹💼🌡️🔁): 2칸
- 코드포인트 `>= 0x1F000`의 기타 이모지: 2칸
- 혼합 문자열 (예: `"📊 외인 (KOSPI)"`): 합산 폭 일치

추가로 `_table()` 함수가 헤더·구분선·행을 등폭 정렬하여 triple-backtick(```...```) 블록을 생성하는지 검증:
- 출력 첫·마지막 라인이 정확히 ```` ``` ````
- 헤더가 있으면 두 번째 라인이 헤더, 세 번째 라인이 `sep_char * 폭`
- 각 행의 정렬은 `aligns` 인자(`'l'` 좌측, `'r'` 우측)에 따름

### REQ-MF-TEST-004: telegram_push dry-run 검증 (State-driven)

**While** the environment variable `MARKET_FLOW_DRY_RUN` is set to `"1"`, `"true"`, or `"yes"` (case-insensitive after `.strip().lower()`), the `telegram_push.send()` function **shall**:

- HTTP 요청을 **하지 않는다** (`urllib.request.urlopen`이 호출되지 않음을 mock으로 검증).
- 메시지 본문을 stdout에 출력한다 (구분선 `─` × 60 + parse_mode/silent 메타 + 본문).
- 반환값으로 `{"ok": True, "dry_run": True, "result": {"message_id": 0}}` 형태의 dict를 돌려준다 (호출자가 `resp["result"]["message_id"]`를 참조할 수 있도록).
- 환경변수 `GOLDENQUEENS_BOT_TOKEN`·`GOLDENQUEENS_CHAT_ID`를 읽지 않는다 (이들이 미설정이어도 RuntimeError가 발생하지 않아야 함).

### REQ-MF-TEST-005: telegram_push 실제 HTTP 분기 모킹 검증 (Event-driven)

**When** `MARKET_FLOW_DRY_RUN`이 unset이거나 falsy 값이며 `GOLDENQUEENS_BOT_TOKEN`·`GOLDENQUEENS_CHAT_ID` 환경변수가 설정된 상태에서 `telegram_push.send("text")`가 호출되면, the system **shall**:

- `urllib.request.urlopen`을 정확히 1회 호출한다 (mock으로 검증).
- 호출된 Request 객체의 URL이 `https://api.telegram.org/bot{token}/sendMessage` 형식과 일치한다.
- POST 페이로드(`urllib.parse.urlencode` 결과)가 `chat_id`, `text`, `parse_mode`, `disable_notification`, `disable_web_page_preview` 5개 키를 포함한다.
- 응답 JSON을 그대로 파싱하여 반환한다.

ANSI 색상 처리(`_colorize_for_stdout`)는 dry-run 경로에서만 호출되며, `sys.stdout.isatty()`가 False면 색상 미적용 — pytest의 capsys 환경에서 자연 검증된다.

### REQ-MF-TEST-006: fetchers/naver_kr 파서 결정성 검증 (Ubiquitous)

The system **shall** verify that `market_flow/fetchers/naver_kr.py`의 파서가 다음 캡처 fixture에 대해 기대 dict/list를 반환한다:

- `fetch_daily_summary(market)`: 모바일 API JSON fixture (`tests/fixtures/naver_kr/mobile_kospi.json`, `mobile_kosdaq.json`)를 입력 → `{bizdate, personal, foreign, institutional, program_arb, program_nonarb, program_total}` 7-키 dict 반환. `None`/빈 문자열은 `to_int`에서 `None`으로 정규화. 콤마·`+` 부호는 제거.
- `fetch_kospi_intraday(bizdate)`: 데스크탑 HTML fixture (`tests/fixtures/naver_kr/intraday.html`, euc-kr 디코딩 결과) → 11컬럼 정규식 매칭으로 N개 row 반환. 각 row는 `time` 키를 포함하며 11개 숫자 컬럼은 `int`.
- `fetch_kospi_daily(bizdate)`: 데스크탑 HTML fixture (`tests/fixtures/naver_kr/daily.html`) → `date` 키를 포함한 동일 11컬럼 row 반환.
- `_parse_trend_rows(body, time_col)`: 부족한 셀(<11)은 무시. `"-"`이거나 빈 셀은 `0`으로 정규화.

`urllib.request.urlopen`은 모든 단위 테스트에서 모킹되어 외부 호출이 발생하지 않아야 한다 (`monkeypatch` 또는 `unittest.mock.patch`).

### REQ-MF-TEST-007: fetchers/us_market 변환 로직 검증 (Ubiquitous)

The system **shall** verify that `market_flow/fetchers/us_market.py`의 `_fetch_yf` 함수가 `yfinance.download` 반환(MultiIndex pandas DataFrame)을 다음 규칙대로 변환한다:

- 입력 fixture: pickle 직렬화된 yfinance DataFrame (`tests/fixtures/us_market/yf_indices.pkl` 등) 또는 동등한 pandas DataFrame을 코드 내에서 구성.
- 출력: `{ticker: {label, close, pct, vol_ratio, date}}` dict.
- `pct` 계산: `(close[-1] - close[-2]) / close[-2] * 100`.
- `vol_ratio` 계산: `vol[-1] / vol[-6:-1].mean()`. 거래량 데이터가 6개 미만이면 `None`.
- `close.dropna()` 결과가 2개 미만이면 해당 ticker 출력은 `None`.
- 개별 ticker에서 예외 발생 시 해당 ticker만 `None`으로 두고 나머지 처리 계속.
- `fetch_us_close()`는 6개 카테고리(`indices`, `volatility`, `risk_onoff`, `macro`, `sectors`, `watch`) dict를 반환.

`yfinance.download`는 `monkeypatch`로 모킹되어 실제 야후 호출이 발생하지 않아야 한다.

### REQ-MF-TEST-008: daily_kr/daily_us/weekly 통합 스모크 (Event-driven)

**When** `MARKET_FLOW_DRY_RUN=1` 환경 + fetcher 모킹(또는 `tests/fixtures/`에서 로드한 결정론적 입력)에서 다음 main 함수가 호출되면, the system **shall** 비정상 종료 없이 stdout 출력을 생성한다:

- `daily_kr.main()`: `fetchers.naver_kr.fetch_today`를 fixture 데이터로 모킹 → `formatter.format_kr_daily` 호출 → `telegram_push.send`가 dry-run으로 stdout 출력 → `print(f"✅ 한국장 푸시: ...")` 실행. SystemExit 미발생.
- `daily_us.main()`: `fetchers.us_market.fetch_us_close`를 fixture 데이터로 모킹 → `formatter.format_us_daily` 호출 → dry-run stdout → 푸시 완료 메시지 출력.
- `weekly.main()`: `fetchers.naver_kr.fetch_kospi_daily` + `weekly._watch_5d_pct`(또는 그 내부 `yf.download`) 모킹 → `formatter.format_weekly` 호출 → dry-run stdout → 푸시 완료 메시지.

출력에는 텔레그램 본문이 포함되어야 한다 (capsys로 캡처 후 한국장은 `"📊"`·`"코스피"` 토큰, 미국장은 `"🇺🇸"`·`"S&P500"` 토큰, 주간은 `"📅"`·`"주간"` 토큰 포함 검증).

### REQ-MF-TEST-009: 라이브 마커 스모크 (Optional)

**Where** the `live` pytest marker is registered and the user explicitly runs `pytest -m live`, the system **shall** execute 1~2 실제 네트워크 스모크 테스트:

- `tests/live/test_naver_live.py::test_fetch_today_smoke` — 실제 네이버 모바일 API 호출하여 `fetch_daily_summary("KOSPI")`가 예외 없이 dict 반환, `bizdate` 키 존재 확인. 수치 값은 검증하지 않음 (외부 변동).
- `tests/live/test_yfinance_live.py::test_fetch_us_close_smoke` — 실제 yfinance 호출하여 `fetch_us_close()`가 6개 카테고리 키 dict 반환, `indices["^GSPC"]`가 None이 아님 확인.

각 테스트는 `@pytest.mark.live`로 표시되어 기본 실행에서 자동 제외된다 (REQ-MF-TEST-002 정합).

### REQ-MF-TEST-010: 캡처 fixture 정적 저장 (Ubiquitous)

The system **shall** store captured API responses as static files under `tests/fixtures/`:

- `tests/fixtures/naver_kr/mobile_kospi.json` — `https://m.stock.naver.com/api/index/KOSPI/integration` 응답
- `tests/fixtures/naver_kr/mobile_kosdaq.json` — KOSDAQ 모바일 응답
- `tests/fixtures/naver_kr/intraday.html` — `investorDealTrendTime.naver` 응답 (euc-kr 디코딩 후 utf-8로 저장)
- `tests/fixtures/naver_kr/daily.html` — `investorDealTrendDay.naver` 응답 (동일 처리)
- `tests/fixtures/us_market/yf_indices.pkl` — `yf.download(INDICES, ...)` 결과 DataFrame
- `tests/fixtures/us_market/yf_sectors.pkl` — `yf.download(SECTORS, ...)` 결과
- `tests/fixtures/us_market/yf_watch.pkl` — `yf.download(WATCH, ...)` 결과

각 fixture는 실제 API 1회 호출 후 정적 저장된다. fixture 재생성 방법(스크립트 또는 절차)은 plan.md의 Task에 기록한다.

### REQ-MF-TEST-011: 커버리지 임계값 (Ubiquitous)

The system **shall** achieve at least **80% line coverage** on the `market_flow/` package when running `pytest --cov=market_flow --cov-report=term -m "not live"`.

- 측정 대상: `market_flow/__init__.py`, `formatter.py`, `telegram_push.py`, `fetchers/__init__.py`, `fetchers/naver_kr.py`, `fetchers/us_market.py`, `daily_kr.py`, `daily_us.py`, `weekly.py`.
- 제외 대상: `if __name__ == "__main__":` 블록 (관용적으로 coverage `# pragma: no cover` 마커 부착 가능 — plan.md에서 결정).
- live 마커 테스트는 커버리지 측정에서 제외 (CI에서 항상 deselect되므로 자연 제외).
- 80% 미달 시 CI 실패 처리는 본 SPEC 범위 밖 (현 CI 정책 따라 경고만, fail은 후속 SPEC).

### REQ-MF-TEST-NEG-001: 절대 제약 (Unwanted)

The system **shall not** introduce any of the following:

- **외부 API 호출 발생 (단위·통합 테스트)**: 단위·통합 테스트는 `urllib.request.urlopen`, `yf.download`, `requests.post`(존재 시), Telegram API에 대해 절대 실제 호출을 발생시키지 않아야 한다. 모든 외부 호출은 mock 또는 fixture로 차단된다.
- **`market_flow/` 코드 변경**: 본 SPEC은 테스트만 추가한다. 테스트를 만들기 위해 `market_flow/` 측의 시그니처나 동작을 변경하는 것은 거부된다. 만약 테스트 가능성을 위한 리팩토링이 불가피하다면 별도 SPEC(SPEC-MF-REFACTOR-XXX 등)으로 분리.
- **CI 매트릭스 확장**: 본 SPEC은 baa183f에서 확정된 "Linux 단일 OS, live 마커 기반" 정책을 유지한다. macOS/Windows 매트릭스 추가는 별도 SPEC.
- **테스트 픽스처의 실 시크릿 포함**: `tests/fixtures/`의 모든 캡처본은 실제 텔레그램 토큰·chat_id를 포함해서는 안 된다. fixture에 환경변수 값이 포함되는 경우 더미 값(`TEST_TOKEN`, `0`)으로 치환.
- **테스트가 `MARKET_FLOW_DRY_RUN`을 영구 변경**: 테스트는 `monkeypatch.setenv` 또는 동등한 격리 메커니즘으로 환경변수를 설정해야 하며, 테스트 종료 후 원복되어야 한다. 다른 테스트의 환경에 영향을 주어선 안 된다.
- **flaky 시간 의존성**: 단위·통합 테스트는 `datetime.now()` 또는 시계 의존 함수에 대해 mock 또는 frozen-time fixture로 결정성을 확보해야 한다. CI 실행 시각에 따라 통과/실패가 갈리는 테스트는 거부.

**If** a test would require a real external API call to pass, **then** the test must be marked with `@pytest.mark.live` and placed under `tests/live/`.

---

## Files to Modify / Create

**NEW**
- `tests/__init__.py` — 빈 파일
- `tests/conftest.py` — `pytest.mark.live` 등록 + 자동 deselect 훅 + 공통 픽스처(환경변수 격리, MARKET_FLOW_DRY_RUN 기본값 등)
- `tests/unit/__init__.py`
- `tests/unit/test_formatter.py` — `_vw`, `_padr`, `_padl`, `_table`, `format_kr_daily`, `format_us_daily`, `format_weekly`, `emoji`, `arrow`, `mark`, `signed`, `signed_pct`, `kr_weekday` 검증
- `tests/unit/test_telegram_push.py` — `_is_dry_run`, `send` dry-run/실 HTTP 분기, `_colorize_for_stdout`, `_env`(누락 시 RuntimeError) 검증
- `tests/unit/test_naver_kr.py` — `fetch_daily_summary`, `fetch_kospi_intraday`, `fetch_kospi_daily`, `_parse_trend_rows`, `fetch_today` 검증 (모킹된 `urllib.request.urlopen`)
- `tests/unit/test_us_market.py` — `_fetch_yf`, `fetch_us_close`, `fetch_watch_history` 검증 (모킹된 `yf.download`)
- `tests/integration/__init__.py`
- `tests/integration/test_daily_kr.py` — `daily_kr.main()` 통합 스모크
- `tests/integration/test_daily_us.py` — `daily_us.main()` 통합 스모크
- `tests/integration/test_weekly.py` — `weekly.main()` + `_watch_5d_pct` 통합 스모크
- `tests/live/__init__.py`
- `tests/live/test_naver_live.py` — `@pytest.mark.live` 부착 네이버 실 호출
- `tests/live/test_yfinance_live.py` — `@pytest.mark.live` 부착 yfinance 실 호출
- `tests/fixtures/naver_kr/mobile_kospi.json`
- `tests/fixtures/naver_kr/mobile_kosdaq.json`
- `tests/fixtures/naver_kr/intraday.html`
- `tests/fixtures/naver_kr/daily.html`
- `tests/fixtures/us_market/yf_indices.pkl`
- `tests/fixtures/us_market/yf_sectors.pkl`
- `tests/fixtures/us_market/yf_watch.pkl`
- (선택) `tests/fixtures/regen_fixtures.py` — 실 API 1회 호출 후 fixture를 재생성하는 보조 스크립트 (plan.md에서 위치·필요성 결정)

**MODIFY**
- `pyproject.toml` 또는 `pytest.ini` (택일) — pytest 설정. `markers = ["live: ..."]` 등록, `testpaths = ["tests"]`, `addopts = "-ra"` 등. 파일이 없으면 신규 생성하여 추가.
- `market_flow/requirements.txt` 또는 별도 `requirements-dev.txt` — `pytest`, `pytest-cov`, (선택) `pytest-mock` 추가. `market_flow/requirements.txt`에 추가할지 dev-only로 분리할지는 plan.md에서 결정.
- `.github/workflows/test.yml` — 단위·통합 잡과 (선택) live 옵트인 잡 추가. baa183f 정책을 그대로 유지하며 본 SPEC에서 추가되는 명령(`pytest -m "not live" --cov=market_flow`)을 반영. 변경 최소화 원칙.

**UNCHANGED**
- `market_flow/` 패키지 전체 (테스트만 추가, 코드 동결 — REQ-MF-TEST-NEG-001)
- `.github/workflows/flow-kr.yml`, `flow-us.yml`, `flow-weekly.yml` (운영 워크플로우는 본 SPEC 범위 밖)
- `.moai/specs/SPEC-MF-SCHED-001/` (별도 SPEC의 영역; 본 SPEC과 독립 진행)

---

## Context Variables (Decision Summary)

본 SPEC이 구체화하는 결정 사항:

| 항목 | 결정 | 사유 |
|------|------|------|
| 테스트 프레임워크 | pytest | 표준, 마커·파라미터·픽스처 기능 풍부 |
| 모킹 라이브러리 | `unittest.mock` (표준) + 필요 시 `pytest-mock` | 표준 라이브러리 우선, mocker 픽스처가 가독성 개선 시 도입 |
| 테스트 디렉터리 위치 | 프로젝트 루트 `tests/` | CI `test.yml` 기존 경로 정합, `market_flow/tests/` 내부 배치는 비표준 |
| 단위/통합/라이브 분리 | `tests/unit/`, `tests/integration/`, `tests/live/` 하위 디렉터리 | 의도 명확, 마커 누락 시에도 디렉터리 기반 선별 가능 |
| live 마커 deselect 메커니즘 | `conftest.py`의 `pytest_collection_modifyitems` 훅 | 사용자가 `-m live`를 명시하지 않으면 자동 제외, 기존 conftest 패턴 차용 |
| 네이버 fixture 형식 | JSON(모바일) + HTML(데스크탑) 정적 파일 | 캡처 형식 그대로 보존, 디코딩 처리는 fetcher에서 |
| yfinance fixture 형식 | pickle 직렬화 DataFrame | pandas DataFrame 정확 재현, 텍스트 직렬화는 MultiIndex 손실 위험 |
| 환경변수 격리 | `monkeypatch.setenv` 또는 `pytest.fixture(autouse=True)` | 테스트 간 환경변수 누수 방지 (REQ-MF-TEST-NEG-001) |
| 커버리지 목표 | 80% (line coverage, live 제외) | 회귀 안전망 충분 + 과도한 mock 부담 회피 |
| CI 통합 | 기존 `test.yml`에 단위·통합 잡 통합, live 옵트인은 별도 잡 | baa183f 정책 유지, 변경 최소화 |
| `__main__` 블록 처리 | `# pragma: no cover` 또는 통합 스모크에서 자연 커버 | 80% 달성 위해 필요 시 pragma 부착 (plan.md에서 결정) |

---

## Exclusions (What NOT to Build)

다음 항목은 SPEC-MF-TEST-001의 범위 밖이며 구현되지 않는다:

1. **`market_flow/` 코드 변경** — 테스트만 추가, 패키지 동결. 테스트 가능성을 위한 리팩토링이 필요하다면 별도 SPEC.
2. **`calendar_utils.py` 등 SPEC-MF-SCHED-001 신규 모듈 테스트** — 해당 SPEC이 자체 acceptance에서 다룬다. 본 SPEC 머지 후 SPEC-MF-SCHED-001이 머지되면 그쪽이 자체 테스트 추가.
3. **macOS·Windows CI 매트릭스** — baa183f의 Linux 단일 OS 정책 유지. 다중 OS 매트릭스는 별도 SPEC.
4. **API 스키마 회귀 자동 감지** — 네이버 모바일 API나 yfinance 응답 스키마가 변경되면 fixture 재생성 후 테스트 재실행. 자동 스키마 비교는 별도 SPEC.
5. **부하·성능 벤치마크** — 함수 응답 시간 측정, 메모리 사용량 추적 등은 비대상.
6. **텔레그램 봇 API 응답 변형 테스트** — `{"ok": False, "error_code": ...}` 등 비정상 응답에 대한 분기. 현행 `telegram_push.send`는 응답을 그대로 반환만 하므로 본 SPEC에서는 정상 응답 mock만 사용.
7. **`__main__` 직접 실행 테스트** — `python -m market_flow.daily_kr` 같은 모듈 실행 검증. main()을 직접 호출하는 통합 스모크로 대체.
8. **다국어 본문 자연어 평가** — 텔레그램 본문이 한국어로 자연스럽게 읽히는지 등의 정성 검증. 결정론적 토큰 존재 여부만 검증.
9. **이미지·차트 비교 테스트** — `formatter.py`는 텍스트 테이블만 생성하므로 비대상.
10. **로컬 개발 `.env` 파일 처리 테스트** — `dotenv.load_dotenv`는 import 실패 시 silent skip이며 fixture 파일을 사용해 테스트하면 mock 부담만 늘어남. 환경변수 직접 주입(`monkeypatch.setenv`)으로 검증 충분.
11. **테스트 결과 HTML 리포트 자동 게시** — `--cov-report=html` 생성은 CI 잡 옵션으로만, GitHub Pages 등 배포 자동화는 별도 SPEC.
12. **flaky 재시도 메커니즘** — `pytest-rerunfailures` 등 도입은 비대상. 모든 테스트는 결정론적이어야 함 (REQ-MF-TEST-NEG-001).

---

## Dependencies

본 SPEC이 의존하는 컨텍스트 및 선·후행 작업:

**선행 (이미 머지됨)**
- commit `8fd2c7f` — `naver_investor_flow/` 제거, `market_flow/` 도입 (본 SPEC의 테스트 대상 패키지 확정)
- commit `baa183f` — CI test.yml의 live 마커 기반·Linux 단일 OS 전환 (본 SPEC의 CI 정책 전제)
- commit `d78d0a6` — `--no-telegram` dry-run 추가 (`telegram_push.py`의 `MARKET_FLOW_DRY_RUN` 환경변수는 이를 일반화한 형태)

**병행/독립**
- SPEC-MF-SCHED-001 — DST 게이트·휴장 게이트. 본 SPEC과 파일 충돌 없음 (`market_flow/calendar_utils.py` 신설은 SPEC-MF-SCHED-001 측, `tests/`는 본 SPEC 측). 머지 순서 무관.

**외부 의존성 (신규)**
- `pytest>=8.0` — 테스트 러너
- `pytest-cov>=5.0` — 커버리지 측정
- (선택) `pytest-mock>=3.12` — mocker 픽스처 (plan.md에서 도입 여부 결정)

**기존 의존성 (재사용)**
- `yfinance`, `pandas`, `python-dotenv` (`market_flow/requirements.txt`) — fixture 생성 및 일부 통합 스모크에서 import 검증

---

## Risks

| 위험 | 가능성 | 영향 | 완화책 |
|------|--------|------|--------|
| 캡처 fixture가 네이버/yfinance 응답 스키마 변경으로 부정확해짐 | 중간 | 중간 (단위 테스트는 통과하나 실 운영과 불일치) | live 마커 스모크(REQ-MF-TEST-009)로 1~2개 옵트인 검증. fixture 재생성 절차를 plan.md에 명시 |
| `urllib.request.urlopen` 모킹 누락으로 단위 테스트가 실 네트워크 호출 | 낮음 | 높음 (CI flaky, 외부 부하) | `conftest.py`에 `autouse` 픽스처로 `urllib.request.urlopen`을 기본 차단 후 명시적 unmock 패턴 검토 (plan.md에서 결정) |
| `yfinance.download` pickle fixture가 pandas 버전 호환성 문제 | 낮음 | 중간 (CI에서 unpickle 실패) | pickle 대신 fixture를 코드 내에서 DataFrame으로 구성하는 패턴을 우선 시도, pickle은 fallback. plan.md에서 결정 |
| `pytest.mark.live` 등록 누락 시 `PytestUnknownMarkWarning` | 낮음 | 매우 낮음 (경고만) | `pyproject.toml` 또는 `pytest.ini`의 `markers` 섹션에 명시 등록 |
| `MARKET_FLOW_DRY_RUN` 환경변수가 다른 테스트에 누수 | 중간 | 중간 (테스트 격리 위반) | `monkeypatch.setenv`/`monkeypatch.delenv` 일관 사용, `autouse` 픽스처로 테스트 시작 시 환경 초기화 |
| 통합 스모크가 `formatter.py` 출력의 한국어 토큰 검증에 의존 → 본문 형식 변경 시 깨짐 | 중간 | 낮음 (테스트 수정으로 해결) | 구조 토큰(triple-backtick 블록 존재, 섹션 헤더 존재) 위주로 검증, 본문 문자열 정확 매칭 회피 |
| `daily_us.main()`이 `fetch_us_close()`를 호출하며 yfinance를 import — fixture 모킹이 import 경로 잘못 잡으면 실 호출 | 낮음 | 높음 (CI에서 네트워크 호출) | `monkeypatch.setattr("market_flow.fetchers.us_market.yf.download", ...)` 처럼 사용처 경로로 모킹. plan.md에 mock 경로 명시 |
| 커버리지 80%가 `__main__` 블록·예외 경로 때문에 미달 | 중간 | 낮음 (목표 조정으로 해결) | `# pragma: no cover` 부착 또는 임계값 78%로 조정. plan.md에서 결정 |
| `tests/fixtures/`가 저장소 용량 증가 | 낮음 | 매우 낮음 | 캡처 fixture는 모두 < 50KB 수준 추정. 합산 < 1MB 예상. 문제 발생 시 gzip 압축 검토 |
| 라이브 마커 자동 deselect 훅이 다른 pytest 플러그인과 충돌 | 매우 낮음 | 낮음 | 표준 `pytest_collection_modifyitems` API 사용, 다른 플러그인 미사용 환경에서 검증 |

---

## References

- 대상 패키지:
  - `market_flow/__init__.py`
  - `market_flow/formatter.py` — CJK/이모지 폭 보정 + 등폭 테이블 렌더
  - `market_flow/telegram_push.py` — `MARKET_FLOW_DRY_RUN` 환경변수 기반 dry-run
  - `market_flow/daily_kr.py`, `daily_us.py`, `weekly.py` — 발송 엔트리
  - `market_flow/fetchers/naver_kr.py` — 네이버 모바일/데스크탑 파서
  - `market_flow/fetchers/us_market.py` — yfinance 어댑터
- 선행 커밋:
  - `8fd2c7f` — naver_investor_flow 제거 및 market_flow 도입 (구 tests 삭제 시점)
  - `baa183f` — CI test.yml live 마커 기반 + Linux 단일 OS 전환
  - `d78d0a6` — `--no-telegram` dry-run 플래그 도입
- 외부 라이브러리:
  - `pytest` (테스트 러너)
  - `pytest-cov` (커버리지)
  - `pytest-mock` (선택, plan.md에서 결정)
- 외부 API (캡처 후 정적 사용):
  - 네이버 모바일: `https://m.stock.naver.com/api/index/{KOSPI|KOSDAQ}/integration`
  - 네이버 데스크탑: `https://finance.naver.com/sise/investorDealTrend{Time|Day}.naver`
  - yfinance: `yf.download(...)` 다중 ticker 호출
- 관련 SPEC:
  - SPEC-MF-SCHED-001 (병행, 독립) — DST·휴장 게이트
  - SPEC-REPORT-001 (별도 봇 베이스, 본 SPEC과 무관)
- 디렉터리 규약:
  - 프로젝트 루트 `tests/` (CI `test.yml` 기존 실행 경로)
  - `tests/fixtures/` (캡처 정적 파일)
  - `@pytest.mark.live` (실 네트워크 옵트인)
