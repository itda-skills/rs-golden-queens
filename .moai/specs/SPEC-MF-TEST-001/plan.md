# SPEC-MF-TEST-001 Implementation Plan

## Approach Summary

`market_flow/` 패키지에 대응하는 테스트 슈트를 프로젝트 루트 `tests/` 하위에 신설한다. 단위(`tests/unit/`) → 통합(`tests/integration/`) → 라이브(`tests/live/`) 3축 구조이며, live는 `@pytest.mark.live`로 표시되어 `conftest.py`의 자동 deselect 훅에 의해 기본 실행에서 제외된다. 외부 API 응답은 `tests/fixtures/`에 정적 캡처본으로 저장하여 단위·통합 테스트의 결정성을 확보한다.

본 SPEC은 **`market_flow/` 코드를 변경하지 않는다** (REQ-MF-TEST-NEG-001). 테스트만 추가하며, 픽스처 기반 모킹으로 외부 의존성을 차단한다.

구현 방법론은 `.moai/config/sections/quality.yaml`의 `development_mode`에 따른다. 본 SPEC은 "테스트를 추가"하는 작업 자체이므로 TDD의 RED-GREEN 사이클이 자연 적용되지 않는다 (테스트가 곧 산출물). 대신 다음 순서를 따른다:

1. **Discover**: 각 모듈의 공개 API와 의존 경계를 식별 (구현 코드 읽기)
2. **Capture**: 실 API 1회 호출하여 fixture 저장
3. **Assert**: 캡처 fixture 기반 단위·통합 테스트 작성
4. **Verify**: pytest 실행, 커버리지 80% 확인, live 마커 분리 동작 확인

---

## Pre-Implementation Research (사전 조사)

본 SPEC 구현을 시작하기 전에 다음 항목을 plan 보강으로 마무리해야 한다. 각 항목 결과는 plan.md 또는 별도 `research.md`에 기록한다.

### R1. 기존 `tests/` 디렉터리 잔재 확인

목적: 커밋 8fd2c7f에서 `tests/` 13개 파일이 삭제되었으나 디렉터리 자체나 빈 파일 잔재가 있는지 확인하여 깨끗한 상태에서 시작.

검증 절차:
1. `ls -la /Users/yuji/rs-golden-queens/tests/` 존재 여부 확인.
2. 존재하면 `git log --all --diff-filter=D --name-only -- tests/`로 삭제 이력 확인.
3. 잔재 파일이 있으면 별도 PR로 정리 (본 SPEC에 포함시킬지 결정).

**예상 결과**: 8fd2c7f에서 디렉터리째 삭제되었을 가능성 높음. 본 SPEC에서 완전히 신설.

### R2. CI `.github/workflows/test.yml` 현행 정책 확인

목적: baa183f 이후 live 마커 기반 정책의 정확한 구성을 파악하여 본 SPEC의 변경을 최소화.

검증 절차:
1. `Read .github/workflows/test.yml` 로 현행 잡 정의 확인.
2. `pytest` 호출 명령과 마커 처리 패턴 확인.
3. 매트릭스 OS·Python 버전 확인 (Linux + Python 3.13 예상).
4. 캐시·의존성 설치 단계 확인.

**결정 사항**: 본 SPEC에서 test.yml에 추가할 명령은 다음 형태로 통일:
- 기본 잡: `pytest -m "not live" --cov=market_flow --cov-report=term --cov-fail-under=0`
- live 잡(선택, 수동 트리거): `pytest -m live`

`--cov-fail-under=0`으로 시작하여 80% 미달이어도 실패하지 않게 함. 임계값 강제는 별도 SPEC.

### R3. `pytest-mock` 도입 여부 결정

목적: `unittest.mock` 표준 라이브러리만 사용할지, `pytest-mock`의 `mocker` 픽스처를 도입할지 결정.

비교:

| 항목 | unittest.mock | pytest-mock |
|------|---------------|-------------|
| 가독성 | 데코레이터·context manager | `mocker.patch(...)` 한 줄 |
| 외부 의존성 | 표준 라이브러리 | +1 패키지 |
| 자동 정리 | 수동 (with 블록 또는 데코레이터) | 픽스처 스코프 자동 정리 |
| 학습 부담 | 익숙함 | mocker API 학습 필요 (얕음) |

**결정**: `pytest-mock` 도입. 자동 정리와 가독성 이점이 표준 라이브러리만 사용의 이점을 상쇄한다. `requirements-dev.txt`에 추가.

### R4. yfinance 모킹 대상 경로 확인

목적: `daily_us.py`와 `weekly.py`가 yfinance를 어떻게 import하는지 파악하여 mock 대상 경로를 정확히 지정.

검증 절차 (구현 코드 grep 결과):

- `market_flow/fetchers/us_market.py:5`: `import yfinance as yf` → `yf.download(...)` 호출
- `market_flow/weekly.py:12`: `import yfinance as yf` (모듈 레벨) → `_watch_5d_pct` 내부에서 `yf.download(...)` 호출

**결정**: mock 경로는 사용처 모듈로 지정.
- `mocker.patch("market_flow.fetchers.us_market.yf.download", ...)` — us_market 단위 테스트
- `mocker.patch("market_flow.weekly.yf.download", ...)` — weekly 통합 스모크
- 통합 스모크에서 `fetch_us_close` 자체를 모킹하는 경우는 `mocker.patch("market_flow.daily_us.fetch_us_close", ...)` (import 경로 확인 필요)

`daily_us.py:12`는 `from fetchers.us_market import fetch_us_close`로 `daily_us` 네임스페이스에 바인딩되므로 mock 대상은 `market_flow.daily_us.fetch_us_close`.

### R5. 네이버 fixture 캡처 절차 확인

목적: 네이버 모바일/데스크탑 API를 1회 호출하여 fixture를 저장하는 절차를 명확히.

검증 절차:
1. `python -c "from market_flow.fetchers.naver_kr import fetch_daily_summary; import json; print(json.dumps(fetch_daily_summary('KOSPI')))"` 출력 캡처.
2. 모바일 API는 JSON으로 직접 응답하므로 `urllib.request.urlopen` 결과를 그대로 저장:
   ```
   import urllib.request
   from market_flow.fetchers.naver_kr import UA
   req = urllib.request.Request("https://m.stock.naver.com/api/index/KOSPI/integration", headers=UA)
   with urllib.request.urlopen(req, timeout=10) as r:
       open("tests/fixtures/naver_kr/mobile_kospi.json", "wb").write(r.read())
   ```
3. 데스크탑 API는 euc-kr 인코딩이므로 디코딩 후 utf-8로 저장:
   ```
   body = urllib.request.urlopen(req, timeout=10).read().decode("euc-kr", errors="replace")
   open("tests/fixtures/naver_kr/intraday.html", "w", encoding="utf-8").write(body)
   ```
4. fixture 로드 시 단위 테스트는 utf-8로 읽어 `body` 변수로 사용. 단, `_parse_trend_rows`는 이미 디코딩된 문자열을 받으므로 동작 일치.
5. fixture 캡처 스크립트는 `tests/fixtures/regen_fixtures.py`로 저장하여 향후 재생성 가능하게 함. 본 스크립트는 직접 실 호출이므로 `if __name__ == "__main__"` 가드 + 명시적 실행.

**결정**: fixture 캡처 스크립트 작성 (Task 0).

### R6. yfinance pickle vs 코드 내 DataFrame 구성

목적: yfinance 응답의 fixture 저장 방식 결정.

옵션 A (pickle):
- 장점: 실 응답의 MultiIndex 구조 완전 보존
- 단점: pandas 버전 호환성, 바이너리 파일 (diff 어려움)

옵션 B (코드 내 DataFrame 구성):
- 장점: 명시적, 다양한 시나리오(빈 데이터, NaN, 단일 ticker 등) 작성 용이
- 단점: 실 응답 구조 재현이 번거로움, MultiIndex 구성 코드 복잡

**결정**: 하이브리드. 기본은 옵션 B로 단위 테스트의 다양한 케이스(NaN, 부족한 데이터, 예외)를 명시적으로 작성. 통합 스모크에서는 옵션 A의 pickle fixture를 사용하여 실 응답 구조 회귀 안전망 확보.

pickle 호환성 문제 회피를 위해 `requirements.txt`에 `pandas>=2.0`이 이미 명시되어 있어 안정.

### R7. `__main__` 블록 커버리지 처리

목적: `if __name__ == "__main__":` 블록이 커버리지 측정에서 미커버로 잡혀 80% 달성을 방해하는지 확인.

검증 절차:
1. 각 모듈의 `__main__` 블록 라인 수 카운트.
2. `daily_kr.py`, `daily_us.py`, `weekly.py`는 main()이 `__main__`에서 직접 호출되며 통합 스모크가 main() 자체를 호출하므로 `__main__` 블록도 자연 커버됨 (단, `sys.argv` 분기는 별도).
3. `fetchers/naver_kr.py:110-113`, `fetchers/us_market.py:89-92`는 `print(json.dumps(...))`만 수행 — 통합 스모크로 커버 불가.
4. `telegram_push.py:88-91`은 점검 메시지 발송 — 통합 스모크에서 커버 안 됨.

**결정**: `__main__` 블록 전체에 `# pragma: no cover` 부착 또는 `pyproject.toml`/`.coveragerc`에 `exclude_lines = ["if __name__ == .__main__.:"]` 추가. 후자 선호 (소스 미변경 — REQ-MF-TEST-NEG-001 부합).

`pyproject.toml`이 없으면 `.coveragerc`를 신설하여 다음 등록:
```
[run]
omit = */__main__.py

[report]
exclude_lines =
    pragma: no cover
    if __name__ == .__main__.:
```

### R8. conftest.py의 live 자동 deselect 패턴

목적: 기존 conftest.py 패턴 (8fd2c7f 이전)을 추정하여 동일/유사 패턴 채택.

표준 패턴:
```
# tests/conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "live: 실제 네트워크 호출 테스트 (기본 deselect)")

def pytest_collection_modifyitems(config, items):
    if config.getoption("-m") and "live" in config.getoption("-m"):
        return  # 사용자가 명시한 경우 그대로 진행
    skip_live = pytest.mark.skip(reason="기본 실행에서 live 테스트는 자동 제외 (-m live로 명시)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
```

**결정**: 위 패턴 채택. `-m` 옵션 파싱은 단순 substring 검사로 충분 (정확한 표현식 평가는 pytest 내부에 위임).

---

## Task Breakdown

### Task 0: fixture 캡처

`tests/fixtures/regen_fixtures.py` 작성 후 1회 실행:
- 네이버 모바일 KOSPI/KOSDAQ JSON 응답 저장
- 네이버 데스크탑 일별/시간별 HTML 응답 저장 (euc-kr → utf-8 변환)
- yfinance `INDICES`/`SECTORS`/`WATCH` ticker 카테고리의 `yf.download` 결과 pickle 저장

스크립트는 `python tests/fixtures/regen_fixtures.py` 수동 실행 전제. CI에서 자동 실행하지 않음 (실 네트워크 호출).

WHY: 캡처 시점 기준 fixture를 정적 저장하여 단위·통합 테스트의 결정성 확보. fixture 재생성 절차를 명시화하여 향후 스키마 변경 대응 용이.

### Task 1: 디렉터리 및 pytest 설정 생성

생성:
- `tests/__init__.py` (빈 파일)
- `tests/conftest.py` — live 마커 등록 + 자동 deselect 훅 + 공통 픽스처
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/live/__init__.py`
- `tests/fixtures/.gitkeep` (또는 `regen_fixtures.py`로 대체)
- `pytest.ini` 또는 `pyproject.toml`의 `[tool.pytest.ini_options]` — markers 등록, testpaths, addopts
- `.coveragerc` — `__main__` 블록 제외 설정 (R7 결정)
- `requirements-dev.txt` — `pytest>=8.0`, `pytest-cov>=5.0`, `pytest-mock>=3.12`

`tests/conftest.py` 골자:
- `pytest_configure`: `live` 마커 등록
- `pytest_collection_modifyitems`: live 자동 skip (R8 패턴)
- `autouse` 픽스처 `_clean_market_flow_env`: 테스트 시작 시 `MARKET_FLOW_DRY_RUN`/`GOLDENQUEENS_BOT_TOKEN`/`GOLDENQUEENS_CHAT_ID` 삭제, 종료 시 원복 (`monkeypatch` 활용)
- 픽스처 `naver_mobile_kospi_json`, `naver_mobile_kosdaq_json`, `naver_intraday_html`, `naver_daily_html`: fixture 파일 로드
- 픽스처 `yf_indices_df`, `yf_sectors_df`, `yf_watch_df`: pickle 로드 또는 코드 내 DataFrame 구성

### Task 2: 단위 테스트 — formatter

`tests/unit/test_formatter.py`:

**`_vw` (시각 폭)**
- `test_vw_ascii_single_char`: `_vw("a") == 1`
- `test_vw_ascii_string`: `_vw("hello") == 5`
- `test_vw_cjk_char`: `_vw("한") == 2`
- `test_vw_cjk_string`: `_vw("한국어") == 6`
- `test_vw_wide_emoji_known`: 각 `_WIDE_EMOJI` 멤버 → 2
- `test_vw_emoji_high_codepoint`: `_vw("\U0001F680") == 2` (로켓 이모지 등 `>= 0x1F000`)
- `test_vw_mixed_string`: `_vw("📊 외인") == 2 + 1 + 4` (이모지 + 공백 + 한글 2자)

**`_padr` / `_padl`**
- `test_padr_pads_with_spaces`: `_padr("ab", 5) == "ab   "`
- `test_padl_pads_with_spaces`: `_padl("ab", 5) == "   ab"`
- `test_pad_cjk_width_correct`: `_padr("한", 4) == "한  "` (CJK 폭 2 + 공백 2)
- `test_pad_no_truncate_when_already_wider`: `_padr("hello", 3) == "hello"` (잘림 없음)

**`_table`**
- `test_table_with_header_has_separator`: 헤더 있을 때 출력 라인이 ` ```, header, sep, rows..., ``` ` 순서
- `test_table_without_header_no_separator`: 헤더 없으면 separator 라인 없음
- `test_table_aligns_l_left_padded`: `aligns=['l']`이면 좌측 정렬
- `test_table_aligns_r_right_padded`: `aligns=['r']`이면 우측 정렬
- `test_table_starts_and_ends_with_backticks`: 첫·마지막 라인 정확히 ` ``` `

**`emoji` / `arrow` / `mark` / `signed` / `signed_pct`**
- `test_emoji_positive_red`: `emoji(100) == "🔴"`
- `test_emoji_negative_blue`: `emoji(-1) == "🔵"`
- `test_emoji_zero_white`: `emoji(0) == "⚪"`
- `test_emoji_none_white`: `emoji(None) == "⚪"`
- 동일 패턴으로 `arrow` 검증
- `test_mark_combines_emoji_and_arrow`: `mark(100) == "🔴▲"`
- `test_signed_default_format`: `signed(1234) == "+1,234"`
- `test_signed_none`: `signed(None) == "-"`
- `test_signed_pct`: `signed_pct(1.5) == "+1.50%"`, `signed_pct(None) == "-"`

**`kr_weekday`**
- `test_kr_weekday_monday`: `kr_weekday("20260525") == "5/25(월)"`
- `test_kr_weekday_friday`: `kr_weekday("20260529") == "5/29(금)"`

**`format_kr_daily` / `format_us_daily` / `format_weekly`**
- `test_format_kr_daily_basic_structure`: fixture 기반 데이터 입력 → 출력에 `"📊"`, `"코스피"`, `"코스닥"`, `"프로그램매매"`, triple-backtick 블록 4개 이상 포함
- `test_format_kr_daily_5day_cumulative_when_enough_rows`: `kospi_daily` 5개 이상 → "5거래일 누적" 섹션 포함
- `test_format_kr_daily_no_5day_when_fewer_rows`: `kospi_daily` < 5 → "5거래일 누적" 섹션 없음
- `test_format_us_daily_basic_structure`: 출력에 `"🇺🇸"`, `"주요 지수"`, `"변동성"`, `"매크로"`, `"섹터"`, `"워치 ETF"` 토큰 포함
- `test_format_us_daily_risk_onoff_labels`: HYG/IEF 갭에 따른 "위험선호"/"안전자산"/"중립" 라벨 분기 (3가지 시나리오)
- `test_format_weekly_basic`: 출력에 `"📅"`, `"주간"`, `"코스피"` 토큰 포함

### Task 3: 단위 테스트 — telegram_push

`tests/unit/test_telegram_push.py`:

**`_is_dry_run`**
- `test_is_dry_run_true_value`: `MARKET_FLOW_DRY_RUN=1` → True
- `test_is_dry_run_true_uppercase`: `TRUE` → True
- `test_is_dry_run_yes`: `yes` → True
- `test_is_dry_run_false_value`: `0`, `false`, `no`, 빈 문자열, 미설정 → False
- `test_is_dry_run_with_whitespace`: `" 1 "` → True (strip)

**`_env`**
- `test_env_returns_value`: 환경변수 설정 → 값 반환
- `test_env_raises_when_missing`: 미설정 → `RuntimeError` 발생, 메시지에 키 이름 포함
- `test_env_raises_when_empty`: 빈 문자열 → `RuntimeError`

**`send` dry-run 경로 (REQ-MF-TEST-004)**
- `test_send_dry_run_does_not_call_urlopen`: `MARKET_FLOW_DRY_RUN=1` + `mocker.patch("urllib.request.urlopen")` → call_count == 0
- `test_send_dry_run_prints_message`: capsys로 stdout 캡처, 본문 포함 확인
- `test_send_dry_run_returns_stub_response`: 반환값 `{"ok": True, "dry_run": True, "result": {"message_id": 0}}`
- `test_send_dry_run_works_without_secrets`: `GOLDENQUEENS_BOT_TOKEN`/`GOLDENQUEENS_CHAT_ID` 미설정에도 RuntimeError 미발생

**`send` 실제 HTTP 경로 (REQ-MF-TEST-005)**
- `test_send_real_calls_urlopen_once`: `MARKET_FLOW_DRY_RUN` unset + secrets 설정 + `urlopen` mock → call_count == 1
- `test_send_real_url_format`: mock된 Request 객체 URL에 `bot{token}/sendMessage` 포함
- `test_send_real_payload_contains_required_keys`: POST 페이로드(decode 후) 키에 `chat_id`, `text`, `parse_mode`, `disable_notification`, `disable_web_page_preview` 모두 포함
- `test_send_real_returns_parsed_json`: mock 응답 JSON을 그대로 반환

**`_colorize_for_stdout`**
- `test_colorize_no_tty_returns_original`: `sys.stdout.isatty()` False → 원본 그대로
- `test_colorize_tty_applies_red_for_positive`: tty + `+123` → ANSI red 시퀀스 포함
- `test_colorize_tty_applies_blue_for_negative`: tty + `-123` → ANSI blue 시퀀스 포함

### Task 4: 단위 테스트 — fetchers/naver_kr

`tests/unit/test_naver_kr.py`:

**`fetch_daily_summary`**
- `test_fetch_daily_summary_kospi_returns_7_keys`: fixture `mobile_kospi.json` mock → dict에 `bizdate`, `personal`, `foreign`, `institutional`, `program_arb`, `program_nonarb`, `program_total` 모두 존재
- `test_fetch_daily_summary_kosdaq`: KOSDAQ 동일
- `test_fetch_daily_summary_invalid_market_raises`: `assert market in ("KOSPI", "KOSDAQ")` → `AssertionError`
- `test_fetch_daily_summary_handles_none`: 모바일 응답에 `personalValue: null`이면 `personal = None`
- `test_fetch_daily_summary_strips_commas_and_plus`: `"+1,234"` → `1234`

**`fetch_kospi_intraday` / `fetch_kospi_daily`**
- `test_fetch_kospi_intraday_returns_list_with_time_key`: fixture `intraday.html` mock → list, 각 row에 `time` 키
- `test_fetch_kospi_daily_returns_list_with_date_key`: 동일하지만 `date` 키
- `test_fetch_kospi_intraday_skips_short_rows`: 11컬럼 미만 행은 결과에 포함되지 않음 (custom fixture로 검증)
- `test_fetch_kospi_daily_dash_becomes_zero`: 셀이 `"-"`이면 0으로 정규화

**`_parse_trend_rows` 직접 호출**
- `test_parse_trend_rows_empty_body_returns_empty_list`
- `test_parse_trend_rows_with_time_col_true`: 첫 키가 `time`
- `test_parse_trend_rows_with_time_col_false`: 첫 키가 `date`
- `test_parse_trend_rows_negative_numbers`: `"-1,234"` 처리 (현재 코드는 `+`만 제거, `-`는 유지 → int로 변환)

**`fetch_today`**
- `test_fetch_today_combines_four_sources`: `fetch_daily_summary("KOSPI")`, `fetch_daily_summary("KOSDAQ")`, `fetch_kospi_intraday`, `fetch_kospi_daily` 4회 호출 모두 모킹 → 반환 dict에 `bizdate`, `kospi`, `kosdaq`, `kospi_intraday`, `kospi_daily` 키 존재
- `test_fetch_today_uses_today_when_bizdate_none`: `bizdate=None` → `datetime.now().strftime("%Y%m%d")` 사용 (mocker로 datetime 고정 후 검증)

모든 테스트는 `mocker.patch("market_flow.fetchers.naver_kr.urllib.request.urlopen", ...)` 로 외부 호출 차단.

### Task 5: 단위 테스트 — fetchers/us_market

`tests/unit/test_us_market.py`:

**`_fetch_yf`**
- `test_fetch_yf_basic_output_structure`: pickle/구성된 DataFrame mock → dict에 6개 ticker별 `{label, close, pct, vol_ratio, date}` 키
- `test_fetch_yf_pct_calculation`: `close = [100, 110]` → `pct == 10.0`
- `test_fetch_yf_vol_ratio_calculation`: 6개 거래량 → `vol_ratio = vol[-1] / mean(vol[-6:-1])`
- `test_fetch_yf_vol_ratio_none_when_insufficient_data`: 5개 미만 거래량 → `vol_ratio is None`
- `test_fetch_yf_returns_none_when_close_short`: `close` 2개 미만 → 해당 ticker `None`
- `test_fetch_yf_single_ticker_branch`: `tickers` 단일 → MultiIndex 아닌 DataFrame 분기 동작
- `test_fetch_yf_per_ticker_exception_isolated`: 한 ticker에서 예외 → 해당 ticker만 `None`, 나머지 정상

**`fetch_us_close`**
- `test_fetch_us_close_returns_6_categories`: mock된 `_fetch_yf` → 반환 dict 키 `indices`, `volatility`, `risk_onoff`, `macro`, `sectors`, `watch`

**`fetch_watch_history`**
- `test_fetch_watch_history_calls_fetch_yf_with_watch`: WATCH 카탈로그로 호출됨 검증

모든 테스트는 `mocker.patch("market_flow.fetchers.us_market.yf.download", ...)` 로 yfinance 차단.

### Task 6: 통합 스모크 테스트

`tests/integration/test_daily_kr.py`:
- `test_daily_kr_main_dry_run_produces_output`:
  - `monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")`
  - `mocker.patch("market_flow.daily_kr.fetch_today", return_value=<fixture data>)`
  - `daily_kr.main()` 호출
  - `capsys.readouterr()`로 stdout 캡처, `"📊"`, `"코스피"`, `"✅ 한국장 푸시"` 토큰 존재 확인
  - SystemExit 미발생 (정상 종료)

`tests/integration/test_daily_us.py`:
- `test_daily_us_main_dry_run_produces_output`:
  - `MARKET_FLOW_DRY_RUN=1`
  - `mocker.patch("market_flow.daily_us.fetch_us_close", return_value=<fixture data>)`
  - `daily_us.main()` 호출
  - stdout에 `"🇺🇸"`, `"S&P500"`, `"✅ 미국장 푸시"` 토큰

`tests/integration/test_weekly.py`:
- `test_weekly_main_dry_run_produces_output`:
  - `MARKET_FLOW_DRY_RUN=1`
  - `mocker.patch("market_flow.weekly.fetch_kospi_daily", return_value=<fixture data>)`
  - `mocker.patch("market_flow.weekly._watch_5d_pct", return_value={"QQQ": 1.5, ...})`
  - `weekly.main()` 호출
  - stdout에 `"📅"`, `"주간"`, `"✅ 주간 리포트 푸시"` 토큰

- `test_weekly_watch_5d_pct_with_mocked_yfinance`:
  - `mocker.patch("market_flow.weekly.yf.download", return_value=<DataFrame>)`
  - `_watch_5d_pct()` 호출 → 예상 dict 반환
  - `(close[-1] / close[-6] - 1) * 100` 계산 검증

### Task 7: 라이브 마커 테스트

`tests/live/test_naver_live.py`:
```
@pytest.mark.live
def test_fetch_daily_summary_kospi_smoke():
    from market_flow.fetchers.naver_kr import fetch_daily_summary
    result = fetch_daily_summary("KOSPI")
    assert isinstance(result, dict)
    assert "bizdate" in result
    # 수치 값은 검증하지 않음 (외부 변동)
```

`tests/live/test_yfinance_live.py`:
```
@pytest.mark.live
def test_fetch_us_close_smoke():
    from market_flow.fetchers.us_market import fetch_us_close
    result = fetch_us_close()
    assert set(result.keys()) == {"indices", "volatility", "risk_onoff", "macro", "sectors", "watch"}
    assert result["indices"]["^GSPC"] is not None
```

총 2개 라이브 테스트. 기본 실행에서는 자동 deselect.

### Task 8: CI 통합

`.github/workflows/test.yml` 수정 (R2에서 현행 구조 확인 후 최소 변경):
- 기존 `pytest` 호출을 다음으로 교체:
  ```yaml
  - name: Install dev dependencies
    run: pip install -r requirements-dev.txt
  - name: Run tests
    run: pytest -m "not live" --cov=market_flow --cov-report=term --cov-fail-under=0
  ```
- (선택) `workflow_dispatch` 트리거에 입력 옵션 추가하여 수동으로 live 잡 실행 가능하게 함:
  ```yaml
  - name: Run live tests (manual only)
    if: github.event_name == 'workflow_dispatch' && inputs.run_live == 'true'
    run: pytest -m live
  ```

본 SPEC에서는 `--cov-fail-under=0` (정보 표시만, 실패 없음). 80% 강제는 별도 SPEC.

### Task 9: 자체 검증

- `pytest` 실행 → 단위·통합 전부 통과, live는 deselected 표시
- `pytest -m live` 실행 → live 2개 통과(네트워크 필요), unit/integration 모두 deselected
- `pytest --cov=market_flow --cov-report=term -m "not live"` → 커버리지 80%+ 확인
- `ruff check tests/` 클린
- `MARKET_FLOW_DRY_RUN`/`GOLDENQUEENS_*` 환경변수 누수 없음 확인 (autouse 픽스처 동작)

---

## File-by-File Breakdown

### tests/conftest.py
- `pytest_configure`: live 마커 등록
- `pytest_collection_modifyitems`: live 자동 deselect 훅
- `autouse` 픽스처: 환경변수 격리
- 공통 픽스처: fixture 파일 로더

### tests/fixtures/regen_fixtures.py
- 네이버 모바일 API JSON 캡처
- 네이버 데스크탑 API HTML 캡처 (euc-kr → utf-8)
- yfinance DataFrame pickle 저장
- `if __name__ == "__main__":` 가드로 수동 실행만 허용

### tests/unit/test_formatter.py
- 시각 폭 헬퍼 (`_vw`, `_padr`, `_padl`) — 8개 케이스
- 테이블 렌더 (`_table`) — 5개 케이스
- 색·부호 헬퍼 (`emoji`, `arrow`, `mark`, `signed`, `signed_pct`) — 9개 케이스
- 한국 요일 (`kr_weekday`) — 2개 케이스
- 포맷터 (`format_kr_daily`, `format_us_daily`, `format_weekly`) — 6개 케이스

### tests/unit/test_telegram_push.py
- `_is_dry_run` — 5개 케이스
- `_env` — 3개 케이스
- `send` dry-run — 4개 케이스
- `send` 실제 HTTP — 4개 케이스
- `_colorize_for_stdout` — 3개 케이스

### tests/unit/test_naver_kr.py
- `fetch_daily_summary` — 5개 케이스
- `fetch_kospi_intraday` / `fetch_kospi_daily` — 4개 케이스
- `_parse_trend_rows` — 4개 케이스
- `fetch_today` — 2개 케이스

### tests/unit/test_us_market.py
- `_fetch_yf` — 7개 케이스
- `fetch_us_close` — 1개 케이스
- `fetch_watch_history` — 1개 케이스

### tests/integration/test_daily_kr.py
- 1개 통합 스모크

### tests/integration/test_daily_us.py
- 1개 통합 스모크

### tests/integration/test_weekly.py
- 2개 통합 스모크 (main + `_watch_5d_pct`)

### tests/live/test_naver_live.py
- 1개 live

### tests/live/test_yfinance_live.py
- 1개 live

### pytest.ini (또는 pyproject.toml [tool.pytest.ini_options])
```
[pytest]
testpaths = tests
markers =
    live: 실제 네트워크 호출 테스트 (기본 deselect)
addopts = -ra
```

### .coveragerc
```
[run]
source = market_flow

[report]
exclude_lines =
    pragma: no cover
    if __name__ == .__main__.:
```

### requirements-dev.txt
```
-r market_flow/requirements.txt
pytest>=8.0
pytest-cov>=5.0
pytest-mock>=3.12
```

### .github/workflows/test.yml (수정)
- `pip install -r requirements-dev.txt` 추가
- pytest 명령을 `pytest -m "not live" --cov=market_flow --cov-report=term --cov-fail-under=0`로 변경

---

## Technical Stack

- Python 3.13 (현행 `market_flow/` 그대로)
- 표준 라이브러리: `unittest.mock`, `urllib`, `json`, `pathlib`
- 신규 dev 의존성:
  - `pytest>=8.0`
  - `pytest-cov>=5.0`
  - `pytest-mock>=3.12`
- 기존 의존성 재사용: `yfinance`, `pandas`, `python-dotenv` (fixture 캡처 시에만 실제 호출)
- 린트: `ruff check tests/` (Python 가이드 표준)

---

## Risks & Mitigations

| 위험 | 가능성 | 영향 | 완화책 |
|------|--------|------|--------|
| fixture 캡처 시점 응답 스키마와 실 응답 불일치 (몇 달 후 발견) | 중간 | 중간 (단위 통과, 실 운영 실패) | live 마커 스모크가 옵트인 실행 시 차이 감지. `regen_fixtures.py` 절차 명시로 빠른 재생성 |
| pickle pandas 버전 호환성 | 낮음 | 중간 (CI에서 unpickle 실패) | `pandas>=2.0` 명시. 문제 발생 시 옵션 B(코드 내 DataFrame 구성)로 fallback |
| live 자동 deselect 훅이 다른 마커와 충돌 | 매우 낮음 | 낮음 | 표준 pytest API만 사용, 다른 플러그인 미사용 환경에서 검증 |
| 통합 스모크가 한국어 토큰에 의존 → formatter 변경 시 깨짐 | 중간 | 낮음 (테스트 수정으로 해결) | 구조 토큰(triple-backtick, 섹션 헤더 키워드) 위주 검증 |
| `MARKET_FLOW_DRY_RUN` 등 환경변수 누수 | 중간 | 중간 (테스트 격리 위반) | `autouse` 픽스처 + `monkeypatch.setenv/delenv` 일관 사용 |
| yfinance mock 경로 잘못 지정 시 실 호출 | 낮음 | 높음 (CI 네트워크 호출) | R4의 mock 경로 검증 후 명시. `conftest.py`에 yfinance 전역 차단 픽스처 검토 |
| 커버리지 80% 미달 | 중간 | 낮음 (목표 조정으로 해결) | `__main__` 블록 제외 설정. 미달 시 78%로 임계값 조정 또는 추가 테스트 |
| fixture 파일 용량 과대 | 낮음 | 매우 낮음 | 캡처 fixture 합산 < 1MB 예상. 문제 시 gzip 또는 ticker 카테고리 축소 |
| `_colorize_for_stdout` 테스트가 capsys 환경에서 tty=False 분기만 커버 | 중간 | 낮음 (정밀도) | `mocker.patch("sys.stdout.isatty", return_value=True)`로 tty 분기 강제 |
| `regen_fixtures.py` 실행 시 네이버 차단 (UA 검증, rate limit) | 낮음 | 중간 (fixture 재생성 불가) | 캡처 후 결과를 저장소에 커밋. 향후 재생성 시 user-agent 갱신 검토 |

---

## Milestones (priority-ordered, no time estimates)

**Priority High**
- M1: 사전 조사 R1~R8 완료, 결정 사항 plan.md에 반영
- M2: Task 0 (fixture 캡처) 완료 — `tests/fixtures/` 모든 파일 저장소 커밋
- M3: Task 1 (디렉터리 + 설정) 완료 — `pytest` 빈 실행 통과
- M4: Task 2~5 (단위 테스트 4개 모듈) 완료 — 모든 단위 테스트 통과, 외부 호출 0회
- M5: Task 6 (통합 스모크 3개) 완료 — `main()` 호출이 SystemExit 없이 stdout 생성

**Priority Medium**
- M6: Task 7 (live 마커 2개) 완료 — `pytest -m live` 통과, 기본 실행에서 자동 deselect
- M7: Task 8 (CI 통합) 완료 — `.github/workflows/test.yml` 갱신, GitHub Actions에서 실행 확인
- M8: 커버리지 80%+ 달성 확인 (`pytest --cov=market_flow --cov-report=term -m "not live"`)

**Priority Low**
- M9: `ruff check tests/` 통과
- M10: 머지 후 첫 주 CI 안정성 모니터링 (flaky 발생 시 픽스처/모킹 보강)

---

## Reference Implementation Pointers

- `market_flow/formatter.py:23-35` — `_vw` 시각 폭 계산
- `market_flow/formatter.py:48-76` — `_table` 등폭 렌더
- `market_flow/telegram_push.py:33-34` — `_is_dry_run` 환경변수 파싱
- `market_flow/telegram_push.py:58-85` — `send` dry-run/실 HTTP 분기
- `market_flow/fetchers/naver_kr.py:23-49` — `fetch_daily_summary` 모바일 API
- `market_flow/fetchers/naver_kr.py:70-94` — `_parse_trend_rows` 11컬럼 정규식
- `market_flow/fetchers/us_market.py:25-69` — `_fetch_yf` yfinance 어댑터
- `market_flow/daily_kr.py:18-23` — `main()` 진입점
- `market_flow/weekly.py:20-36` — `_watch_5d_pct` 5거래일 누적 계산
- commit `8fd2c7f` — naver_investor_flow 제거 + market_flow 도입 (구 tests 삭제 시점)
- commit `baa183f` — CI live 마커 기반 전환
- commit `d78d0a6` — `--no-telegram` dry-run 추가

---

## Quality Gates

- TRUST 5:
  - **Tested**: 단위 + 통합 + live 마커 분리 구조, 외부 호출 0회 보장
  - **Readable**: 테스트 이름이 `test_<함수>_<시나리오>_<기대결과>` 패턴, fixture 의도 명확
  - **Unified**: `ruff check tests/` 클린
  - **Secured**: fixture에 실 토큰·chat_id 미포함, autouse 픽스처로 환경변수 격리
  - **Trackable**: 커밋 메시지에 `SPEC-MF-TEST-001` 참조
- Coverage: `market_flow/` 80%+ (live 제외, `__main__` 블록 exclude)
- Lint: `ruff check tests/` 클린
- 테스트: `pytest -m "not live"` 전부 통과, `pytest -m live` 옵트인 통과
- 외부 호출 0회: 단위·통합 테스트 실행 중 실 네트워크 호출 없음 (검증: mock call_count + CI 네트워크 차단 환경에서 통과)
- 운영 검증: CI 첫 5회 실행에서 flaky 0건
