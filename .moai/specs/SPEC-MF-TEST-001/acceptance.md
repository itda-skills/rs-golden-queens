# SPEC-MF-TEST-001 Acceptance Criteria

## Overview

본 문서는 SPEC-MF-TEST-001의 구현이 "완료"로 인정되기 위한 관측 가능한 증거(observable evidence)를 정의한다. 모든 시나리오는 Given/When/Then 형식으로 기술되며, **pytest 실행 결과·커버리지 리포트·CI 로그**로 결정론적으로 검증 가능해야 한다.

각 시나리오는 다음 라벨 중 하나로 분류된다:
- **Must-pass**: 머지 차단 기준. 하나라도 실패하면 머지 거부.
- **Should-pass**: 권장 통과. 실패 시 별도 후속 PR 합의.

---

## 1. 테스트 슈트 구조 (REQ-MF-TEST-001)

### Scenario 1.1: 표준 디렉터리 구조 존재 [Must-pass]

- **Given**: 본 SPEC 머지 후 저장소 상태
- **When**: `ls tests/` 및 `ls tests/{unit,integration,live,fixtures}` 실행
- **Then**:
  - `tests/__init__.py` 존재
  - `tests/conftest.py` 존재
  - `tests/unit/` 디렉터리 존재 + `__init__.py`
  - `tests/integration/` 디렉터리 존재 + `__init__.py`
  - `tests/live/` 디렉터리 존재 + `__init__.py`
  - `tests/fixtures/` 디렉터리 존재 (또는 fixture 파일 다수)

### Scenario 1.2: 단위 테스트 모듈 4개 존재 [Must-pass]

- **Given**: `tests/unit/` 디렉터리
- **When**: `ls tests/unit/test_*.py`
- **Then**: 다음 파일이 모두 존재:
  - `test_formatter.py`
  - `test_telegram_push.py`
  - `test_naver_kr.py`
  - `test_us_market.py`

### Scenario 1.3: 통합 테스트 모듈 3개 존재 [Must-pass]

- **Given**: `tests/integration/` 디렉터리
- **When**: `ls tests/integration/test_*.py`
- **Then**: 다음 파일이 모두 존재:
  - `test_daily_kr.py`
  - `test_daily_us.py`
  - `test_weekly.py`

### Scenario 1.4: 라이브 테스트 모듈 2개 존재 [Should-pass]

- **Given**: `tests/live/` 디렉터리
- **When**: `ls tests/live/test_*.py`
- **Then**: 다음 파일이 모두 존재:
  - `test_naver_live.py`
  - `test_yfinance_live.py`

### Scenario 1.5: pytest 설정 파일 존재 [Must-pass]

- **Given**: 저장소 루트
- **When**: `pytest.ini` 또는 `pyproject.toml`의 `[tool.pytest.ini_options]` 섹션 검사
- **Then**:
  - `testpaths` 설정에 `tests` 포함
  - `markers` 섹션에 `live`가 설명과 함께 등록됨
- **검증 도구**: 파일 grep 또는 `pytest --markers` 출력에서 `live` 마커 등장

---

## 2. 라이브 마커 자동 deselect (REQ-MF-TEST-002)

### Scenario 2.1: 기본 pytest 실행에서 live 자동 제외 [Must-pass]

- **Given**: 모든 테스트가 작성된 상태
- **When**: `pytest` (마커 옵션 없음) 실행
- **Then**:
  - 단위·통합 테스트는 모두 실행됨
  - live 마커 부착 테스트는 "deselected" 또는 "skipped"로 표시됨
  - 종료 코드 0 (모든 비-live 테스트 통과 가정)
- **검증 도구**: pytest 출력 파싱 또는 `-v` 옵션으로 개별 항목 확인

### Scenario 2.2: `-m live` 명시 시 live만 실행 [Must-pass]

- **Given**: 동일 상태 + 네트워크 사용 가능
- **When**: `pytest -m live` 실행
- **Then**:
  - live 테스트 2개만 실행됨 (네트워크 가능 시 통과)
  - 단위·통합 테스트는 "deselected" 표시
- **검증 도구**: pytest 출력에서 collected/deselected/selected 카운트 확인

### Scenario 2.3: `-m "not live"` 명시 시 비-live 실행 [Must-pass]

- **Given**: 동일 상태
- **When**: `pytest -m "not live"` 실행
- **Then**: Scenario 2.1과 동일 결과 (live는 deselected, 비-live는 모두 실행 + 통과)

### Scenario 2.4: live 마커가 pytest에 등록되어 unknown 경고 없음 [Must-pass]

- **Given**: pytest 설정 + `@pytest.mark.live` 부착 테스트
- **When**: `pytest -W error::pytest.PytestUnknownMarkWarning` 실행 (또는 일반 실행 후 warning 검사)
- **Then**: `PytestUnknownMarkWarning` 미발생

---

## 3. formatter 시각 폭 보정 (REQ-MF-TEST-003)

### Scenario 3.1: ASCII 폭 정확 [Must-pass]

- **Given**: `from market_flow.formatter import _vw`
- **When**: `_vw("hello")` 호출
- **Then**: `5` 반환

### Scenario 3.2: CJK 문자 폭 2 [Must-pass]

- **Given**: 동일 import
- **When**: `_vw("한국어")` 호출
- **Then**: `6` 반환 (한글 3자 × 2)

### Scenario 3.3: 알려진 와이드 이모지 폭 2 [Must-pass]

- **Given**: `_WIDE_EMOJI` 집합의 각 멤버
- **When**: `_vw(emoji)` 호출
- **Then**: `2` 반환 (각각)
- **검증 도구**: parametrize로 `_WIDE_EMOJI`의 모든 멤버 검증

### Scenario 3.4: 고유니코드 이모지 폭 2 [Must-pass]

- **Given**: `_WIDE_EMOJI`에 없지만 코드포인트 ≥ 0x1F000인 이모지 (예: `"\U0001F680"`)
- **When**: `_vw(emoji)` 호출
- **Then**: `2` 반환

### Scenario 3.5: 좌측·우측 패딩 정확 [Must-pass]

- **Given**: `_padr`, `_padl`
- **When**: `_padr("ab", 5)`, `_padl("ab", 5)`, `_padr("한", 4)`
- **Then**:
  - `_padr("ab", 5) == "ab   "` (3개 공백)
  - `_padl("ab", 5) == "   ab"` (3개 공백)
  - `_padr("한", 4) == "한  "` (2개 공백, 한글 폭 2 + 공백 2 = 4)

### Scenario 3.6: triple-backtick 블록 렌더 [Must-pass]

- **Given**: `_table([["a", "b"]], ["l", "l"], header=["H1", "H2"])`
- **When**: 결과 문자열 라인 분리
- **Then**:
  - 첫 라인 == ` ``` `
  - 두 번째 라인은 헤더 (`"H1  H2"` 또는 정렬에 맞춰)
  - 세 번째 라인은 separator (`─` × (sum(widths) + 2*(cols-1)))
  - 네 번째 라인은 데이터 행
  - 다섯 번째 라인 == ` ``` `

### Scenario 3.7: format_kr_daily 구조 검증 [Must-pass]

- **Given**: fixture 데이터 (모바일 KOSPI/KOSDAQ + 5개 이상 daily rows)
- **When**: `format_kr_daily(data)` 호출
- **Then**: 출력 문자열에 다음 토큰 모두 포함:
  - `"📊"`, `"마감 매매동향"`, `"단위: 억원"`
  - `"🇰🇷"`, `"코스피"`, `"코스닥"`
  - `"📈"`, `"프로그램매매"`
  - `"🔁"`, `"5거래일 누적"`
  - triple-backtick 블록 ≥ 4개

### Scenario 3.8: format_us_daily 구조 검증 [Must-pass]

- **Given**: fixture 데이터 (6개 카테고리 dict)
- **When**: `format_us_daily(data)` 호출
- **Then**: 출력에 다음 토큰 모두 포함:
  - `"🇺🇸"`, `"미국장 마감"`
  - `"📊"`, `"주요 지수"`, `"S&P500"` 또는 `"나스닥"`
  - `"🌡️"`, `"변동성·꼬리위험"`
  - `"💵"`, `"위험선호"` 또는 `"안전자산"` 또는 `"중립"`
  - `"💹"`, `"매크로"`
  - `"💼"`, `"섹터"`
  - `"⭐"`, `"워치 ETF"`

### Scenario 3.9: format_us_daily Risk On/Off 라벨 분기 [Must-pass]

- **Given**: HYG/IEF 갭이 다음 3가지 시나리오
  - `hyg.pct - ief.pct > 0.2` → `"🔴▲ *위험선호*"`
  - `hyg.pct - ief.pct < -0.2` → `"🔵▼ *안전자산*"`
  - `-0.2 ≤ gap ≤ 0.2` → `"⚪– *중립*"`
- **When**: 각 시나리오로 `format_us_daily(data)` 호출
- **Then**: 해당 라벨이 출력에 포함됨
- **검증 도구**: parametrize 3개 케이스

### Scenario 3.10: format_weekly 구조 검증 [Must-pass]

- **Given**: fixture 데이터 (`kospi_daily` 5개, `watch_5d` 일부)
- **When**: `format_weekly(kospi_daily, watch_5d)` 호출
- **Then**: 출력에 `"📅"`, `"주간 매매동향 리포트"`, `"🇰🇷"`, `"코스피"`, `"5거래일 누적"`, `"🇺🇸"`, `"워치 ETF"` 토큰 포함

---

## 4. telegram_push dry-run (REQ-MF-TEST-004)

### Scenario 4.1: MARKET_FLOW_DRY_RUN=1 시 HTTP 미호출 [Must-pass]

- **Given**: `monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")`, `mocker.patch("urllib.request.urlopen")`
- **When**: `telegram_push.send("test message")` 호출
- **Then**: `urllib.request.urlopen` mock의 `call_count == 0`

### Scenario 4.2: dry-run 시 stdout 출력 [Must-pass]

- **Given**: Scenario 4.1과 동일 환경 + capsys 캡처
- **When**: `telegram_push.send("hello")` 호출
- **Then**:
  - stdout에 `"hello"` 문자열 포함
  - stdout에 구분선 `─` × 60 라인 ≥ 3회 포함

### Scenario 4.3: dry-run 반환값 형태 [Must-pass]

- **Given**: Scenario 4.1과 동일 환경
- **When**: `resp = telegram_push.send("msg")` 후 `resp` 검사
- **Then**:
  - `resp["ok"] is True`
  - `resp["dry_run"] is True`
  - `resp["result"]["message_id"] == 0`
- **사유**: 호출자(`daily_kr.py` 등)가 `resp["result"]["message_id"]`를 참조하므로 stub 형태 유지

### Scenario 4.4: dry-run 시 secrets 미요구 [Must-pass]

- **Given**: `MARKET_FLOW_DRY_RUN=1`, `GOLDENQUEENS_BOT_TOKEN` 미설정, `GOLDENQUEENS_CHAT_ID` 미설정
- **When**: `telegram_push.send("msg")` 호출
- **Then**: `RuntimeError` 미발생, 정상 stub 응답 반환

### Scenario 4.5: dry-run 트루시 값 변형 [Must-pass]

- **Given**: `MARKET_FLOW_DRY_RUN` 값이 다음 중 하나: `"1"`, `"true"`, `"TRUE"`, `"yes"`, `"YES"`, `" 1 "` (공백 포함)
- **When**: `telegram_push._is_dry_run()` 호출
- **Then**: 모두 `True` 반환
- **검증 도구**: parametrize

### Scenario 4.6: dry-run 폴시 값 변형 [Must-pass]

- **Given**: `MARKET_FLOW_DRY_RUN` 값이 다음 중 하나: 미설정, `""`, `"0"`, `"false"`, `"no"`, `"random"`
- **When**: `telegram_push._is_dry_run()` 호출
- **Then**: 모두 `False` 반환

---

## 5. telegram_push 실제 HTTP 분기 (REQ-MF-TEST-005)

### Scenario 5.1: 실 HTTP 분기에서 urlopen 1회 호출 [Must-pass]

- **Given**:
  - `monkeypatch.delenv("MARKET_FLOW_DRY_RUN", raising=False)`
  - `monkeypatch.setenv("GOLDENQUEENS_BOT_TOKEN", "TEST_TOKEN")`
  - `monkeypatch.setenv("GOLDENQUEENS_CHAT_ID", "12345")`
  - `mock_response`를 반환하는 `mocker.patch("market_flow.telegram_push.urllib.request.urlopen")`
- **When**: `telegram_push.send("test")` 호출
- **Then**: mock의 `call_count == 1`

### Scenario 5.2: 호출 URL 형식 정확 [Must-pass]

- **Given**: Scenario 5.1과 동일
- **When**: mock의 `call_args` 검사
- **Then**: 첫 번째 인자 Request 객체의 URL이 `"https://api.telegram.org/botTEST_TOKEN/sendMessage"`와 일치

### Scenario 5.3: POST 페이로드에 필수 키 포함 [Must-pass]

- **Given**: Scenario 5.1과 동일
- **When**: mock에 전달된 Request의 `data` 속성 디코딩 + `urllib.parse.parse_qs`
- **Then**: 키 집합이 `{"chat_id", "text", "parse_mode", "disable_notification", "disable_web_page_preview"}`를 포함

### Scenario 5.4: 응답 JSON 파싱 후 반환 [Must-pass]

- **Given**: Scenario 5.1 + mock 응답이 `{"ok": True, "result": {"message_id": 42}}` JSON
- **When**: `resp = telegram_push.send("test")`
- **Then**: `resp["result"]["message_id"] == 42`

### Scenario 5.5: secrets 누락 시 RuntimeError [Must-pass]

- **Given**: `MARKET_FLOW_DRY_RUN` 미설정, `GOLDENQUEENS_BOT_TOKEN` 미설정
- **When**: `telegram_push.send("test")` 호출
- **Then**: `RuntimeError` 발생, 메시지에 `"GOLDENQUEENS_BOT_TOKEN"` 문자열 포함

---

## 6. fetchers/naver_kr 파서 (REQ-MF-TEST-006)

### Scenario 6.1: fetch_daily_summary 7-key 반환 [Must-pass]

- **Given**: `tests/fixtures/naver_kr/mobile_kospi.json` 파일 + `urllib.request.urlopen` mock
- **When**: `fetch_daily_summary("KOSPI")` 호출
- **Then**: 반환 dict가 다음 키를 모두 포함:
  - `bizdate`, `personal`, `foreign`, `institutional`
  - `program_arb`, `program_nonarb`, `program_total`

### Scenario 6.2: invalid market AssertionError [Must-pass]

- **Given**: 동일 import
- **When**: `fetch_daily_summary("NYSE")` 호출
- **Then**: `AssertionError` 발생

### Scenario 6.3: None 값 정규화 [Must-pass]

- **Given**: 모바일 응답 fixture에 `personalValue: null` 또는 빈 문자열
- **When**: `fetch_daily_summary("KOSPI")` 호출
- **Then**: 반환 dict의 `personal` 값이 `None`

### Scenario 6.4: 콤마·플러스 부호 제거 [Must-pass]

- **Given**: 모바일 응답에 `personalValue: "+1,234"`
- **When**: `fetch_daily_summary("KOSPI")` 호출
- **Then**: `personal == 1234`

### Scenario 6.5: HTML 파서 11컬럼 추출 [Must-pass]

- **Given**: `tests/fixtures/naver_kr/intraday.html` 또는 `daily.html` fixture
- **When**: `fetch_kospi_intraday(bizdate)` 또는 `fetch_kospi_daily(bizdate)` 호출 (`urlopen` mock)
- **Then**:
  - 반환 list 길이 ≥ 1
  - 각 row dict가 11개 데이터 키 + 첫 키(`time` 또는 `date`) 포함
  - 모든 숫자 값은 `int` 타입

### Scenario 6.6: 부족한 셀 행 무시 [Must-pass]

- **Given**: 커스텀 HTML 문자열로 11컬럼 미만 행 포함
- **When**: `_parse_trend_rows(body, time_col=False)` 호출
- **Then**: 부족한 행은 결과에 미포함

### Scenario 6.7: "-" 또는 빈 셀 → 0 [Must-pass]

- **Given**: 커스텀 HTML에 셀 값 `"-"` 포함
- **When**: `_parse_trend_rows(body, time_col=False)` 호출
- **Then**: 해당 셀에 대응되는 값이 정수 `0`

### Scenario 6.8: fetch_today가 4개 소스 통합 [Must-pass]

- **Given**: 모든 `_get` 호출이 mock된 상태
- **When**: `fetch_today("20260525")` 호출
- **Then**: 반환 dict가 `bizdate`, `kospi`, `kosdaq`, `kospi_intraday`, `kospi_daily` 5개 키 포함

### Scenario 6.9: 외부 호출 0회 (단위 테스트 격리) [Must-pass]

- **Given**: 위 모든 단위 테스트 실행
- **When**: 실 네트워크가 차단된 환경에서 `pytest tests/unit/test_naver_kr.py -m "not live"` 실행
- **Then**: 모든 테스트 통과, 실제 네이버 호출 0회
- **검증 도구**: `mocker.spy` 또는 mock의 `call_count`

---

## 7. fetchers/us_market 변환 (REQ-MF-TEST-007)

### Scenario 7.1: _fetch_yf 출력 구조 [Must-pass]

- **Given**: `mocker.patch("market_flow.fetchers.us_market.yf.download", return_value=<DataFrame>)`
- **When**: `_fetch_yf(INDICES)` 호출
- **Then**: 반환 dict의 각 ticker 값이 `{label, close, pct, vol_ratio, date}` 5-key dict (또는 None)

### Scenario 7.2: pct 계산 정확 [Must-pass]

- **Given**: `close = [100.0, 110.0]` (마지막 2개 거래일 종가)
- **When**: `_fetch_yf` 호출
- **Then**: 해당 ticker의 `pct == 10.0` (부동소수점 허용 오차 1e-9)

### Scenario 7.3: vol_ratio 계산 정확 [Must-pass]

- **Given**: `vol = [100, 100, 100, 100, 100, 200]` (마지막 6개)
- **When**: `_fetch_yf` 호출
- **Then**: `vol_ratio == 2.0` (200 / mean([100, 100, 100, 100, 100]) == 2.0)

### Scenario 7.4: 거래량 부족 시 vol_ratio None [Must-pass]

- **Given**: `vol` 길이 5 이하
- **When**: `_fetch_yf` 호출
- **Then**: `vol_ratio is None`

### Scenario 7.5: close 2개 미만 → ticker None [Must-pass]

- **Given**: 특정 ticker의 `close.dropna()` 길이가 1
- **When**: `_fetch_yf` 호출
- **Then**: 반환 dict에서 해당 ticker 값이 `None`

### Scenario 7.6: 단일 ticker 분기 동작 [Must-pass]

- **Given**: `tickers = [("^GSPC", "S&P500")]` (길이 1) + MultiIndex 아닌 DataFrame mock
- **When**: `_fetch_yf(tickers)` 호출
- **Then**: 예외 없이 정상 반환, `^GSPC` 키에 dict 또는 None

### Scenario 7.7: 개별 ticker 예외 격리 [Must-pass]

- **Given**: DataFrame에서 특정 ticker 접근 시 KeyError 발생하도록 mock
- **When**: `_fetch_yf(INDICES)` 호출
- **Then**:
  - 해당 ticker는 `None`
  - 다른 ticker는 정상 처리됨 (예외가 전파되지 않음)

### Scenario 7.8: fetch_us_close가 6개 카테고리 반환 [Must-pass]

- **Given**: `_fetch_yf` mock
- **When**: `fetch_us_close()` 호출
- **Then**: 반환 dict의 키 집합이 정확히 `{"indices", "volatility", "risk_onoff", "macro", "sectors", "watch"}`

### Scenario 7.9: 외부 yfinance 호출 0회 [Must-pass]

- **Given**: 위 모든 단위 테스트 실행
- **When**: `pytest tests/unit/test_us_market.py -m "not live"` (네트워크 차단 환경)
- **Then**: 모든 테스트 통과, 실 yfinance 호출 0회

---

## 8. 통합 스모크 (REQ-MF-TEST-008)

### Scenario 8.1: daily_kr.main() dry-run 정상 종료 [Must-pass]

- **Given**:
  - `monkeypatch.setenv("MARKET_FLOW_DRY_RUN", "1")`
  - `mocker.patch("market_flow.daily_kr.fetch_today", return_value=<fixture>)`
- **When**: `daily_kr.main()` 호출
- **Then**:
  - `SystemExit` 미발생
  - capsys stdout에 `"📊"`, `"코스피"`, `"✅ 한국장 푸시"` 토큰 모두 포함
  - 실제 네이버 호출 0회 (`fetch_today` mock)
  - 실제 텔레그램 호출 0회 (dry-run)

### Scenario 8.2: daily_us.main() dry-run 정상 종료 [Must-pass]

- **Given**:
  - `MARKET_FLOW_DRY_RUN=1`
  - `mocker.patch("market_flow.daily_us.fetch_us_close", return_value=<fixture>)`
- **When**: `daily_us.main()` 호출
- **Then**:
  - SystemExit 미발생
  - stdout에 `"🇺🇸"`, `"S&P500"` (또는 `"나스닥"`), `"✅ 미국장 푸시"` 포함
  - yfinance 호출 0회, 텔레그램 호출 0회

### Scenario 8.3: weekly.main() dry-run 정상 종료 [Must-pass]

- **Given**:
  - `MARKET_FLOW_DRY_RUN=1`
  - `mocker.patch("market_flow.weekly.fetch_kospi_daily", return_value=<fixture>)`
  - `mocker.patch("market_flow.weekly._watch_5d_pct", return_value={"QQQ": 1.5})`
- **When**: `weekly.main()` 호출
- **Then**:
  - SystemExit 미발생
  - stdout에 `"📅"`, `"주간"`, `"✅ 주간 리포트 푸시"` 포함

### Scenario 8.4: weekly._watch_5d_pct 계산 검증 [Must-pass]

- **Given**: `mocker.patch("market_flow.weekly.yf.download", return_value=<DataFrame>)`
- **When**: `_watch_5d_pct()` 호출
- **Then**:
  - 반환 dict의 키는 `WATCH`의 ticker 부분집합
  - 값은 `(close[-1] / close[-6] - 1) * 100` 결과 (허용 오차 1e-9)

### Scenario 8.5: 통합 스모크가 외부 호출 0회 [Must-pass]

- **Given**: Scenario 8.1~8.4 전체 실행
- **When**: 네트워크 차단 환경에서 `pytest tests/integration/ -m "not live"` 실행
- **Then**: 모든 통합 스모크 통과, 실 외부 호출 0회

---

## 9. 라이브 마커 스모크 (REQ-MF-TEST-009)

### Scenario 9.1: 네이버 live 스모크 통과 [Should-pass]

- **Given**: 네트워크 사용 가능 + 네이버 차단 없음
- **When**: `pytest -m live tests/live/test_naver_live.py` 실행
- **Then**:
  - `fetch_daily_summary("KOSPI")` 결과가 dict 타입
  - `"bizdate"` 키가 결과에 존재
  - 수치 값 검증은 하지 않음 (외부 변동)

### Scenario 9.2: yfinance live 스모크 통과 [Should-pass]

- **Given**: 네트워크 사용 가능 + yfinance/Yahoo 정상
- **When**: `pytest -m live tests/live/test_yfinance_live.py` 실행
- **Then**:
  - `fetch_us_close()` 결과가 6개 카테고리 키 dict
  - `result["indices"]["^GSPC"]`가 `None`이 아님

### Scenario 9.3: 라이브 테스트가 기본 실행에서 자동 제외 [Must-pass]

- **Given**: 모든 테스트
- **When**: `pytest` (마커 없음) 실행 — 네트워크 차단 환경에서도
- **Then**:
  - live 테스트 2개는 실행되지 않음 (deselected/skipped)
  - 비-live 테스트는 모두 통과
  - 종료 코드 0
- **사유**: CI에서 네트워크 차단 시에도 기본 실행이 영향받지 않아야 함

---

## 10. 캡처 fixture (REQ-MF-TEST-010)

### Scenario 10.1: 네이버 fixture 파일 존재 [Must-pass]

- **Given**: 저장소 루트
- **When**: `ls tests/fixtures/naver_kr/` 실행
- **Then**: 다음 파일이 모두 존재:
  - `mobile_kospi.json`
  - `mobile_kosdaq.json`
  - `intraday.html`
  - `daily.html`

### Scenario 10.2: yfinance fixture 파일 존재 [Must-pass]

- **Given**: 저장소 루트
- **When**: `ls tests/fixtures/us_market/` 실행
- **Then**: 다음 파일이 모두 존재 (또는 코드 내 DataFrame 구성으로 대체된 경우 그에 대응되는 픽스처 함수가 conftest.py에 존재):
  - `yf_indices.pkl`
  - `yf_sectors.pkl`
  - `yf_watch.pkl`

### Scenario 10.3: fixture에 실 시크릿 미포함 [Must-pass]

- **Given**: `tests/fixtures/` 모든 파일
- **When**: 파일 내용에서 다음 패턴 grep:
  - `GOLDENQUEENS_BOT_TOKEN`
  - `GOLDENQUEENS_CHAT_ID`
  - 텔레그램 봇 토큰 형식 (`\d{9,10}:[A-Za-z0-9_-]{35}`)
- **Then**: 위 패턴 0회 매칭

### Scenario 10.4: fixture 재생성 절차 문서화 [Should-pass]

- **Given**: 저장소
- **When**: `tests/fixtures/regen_fixtures.py` 또는 plan.md에서 fixture 재생성 절차 검색
- **Then**: 재생성 명령 또는 스크립트가 명시되어 있음

---

## 11. 커버리지 (REQ-MF-TEST-011)

### Scenario 11.1: market_flow 80% 커버리지 [Must-pass]

- **Given**: 모든 테스트 작성 완료
- **When**: `pytest --cov=market_flow --cov-report=term -m "not live"` 실행
- **Then**: 총 라인 커버리지 ≥ 80%
- **검증 도구**: pytest-cov 출력의 TOTAL 라인 % 값 확인

### Scenario 11.2: 각 모듈별 커버리지 확인 [Should-pass]

- **Given**: 커버리지 리포트
- **When**: 모듈별 % 확인
- **Then**: 각 모듈이 다음 최소 임계값 만족:
  - `formatter.py` ≥ 85%
  - `telegram_push.py` ≥ 85%
  - `fetchers/naver_kr.py` ≥ 80%
  - `fetchers/us_market.py` ≥ 75% (yfinance MultiIndex 분기 복잡도)
  - `daily_kr.py` ≥ 80%
  - `daily_us.py` ≥ 80%
  - `weekly.py` ≥ 80%

### Scenario 11.3: `__main__` 블록 커버리지 제외 [Should-pass]

- **Given**: `.coveragerc` 또는 동등 설정
- **When**: 커버리지 측정
- **Then**: `if __name__ == "__main__":` 분기는 측정 대상에서 제외됨

---

## 12. 절대 제약 (REQ-MF-TEST-NEG-001)

### Scenario 12.1: market_flow/ 코드 변경 없음 [Must-pass]

- **Given**: 본 SPEC 머지 직전 `market_flow/` 디렉터리 git diff
- **When**: 머지 후 `git diff main -- market_flow/` 실행
- **Then**: 0 lines changed (빈 diff)
- **검증 도구**: CI 잡에서 `git diff --exit-code main -- market_flow/` 또는 PR 리뷰

### Scenario 12.2: 단위·통합 테스트에서 외부 호출 0회 [Must-pass]

- **Given**: 네트워크 차단 환경 (예: `--cap-drop=NET_RAW`)
- **When**: `pytest -m "not live"` 실행
- **Then**: 모든 테스트 통과 (네트워크 차단으로도 영향 없음)

### Scenario 12.3: live 마커 미부착 테스트가 live 아님 [Must-pass]

- **Given**: 모든 테스트
- **When**: `tests/unit/`과 `tests/integration/`의 모든 파일에서 `@pytest.mark.live` 검색
- **Then**: 매칭 0건

### Scenario 12.4: 환경변수 누수 없음 [Must-pass]

- **Given**: 테스트 실행 전 `MARKET_FLOW_DRY_RUN` 미설정 상태
- **When**: `pytest tests/` 실행 후 환경 확인 (다음 테스트 시작 전 fixture에서 검사)
- **Then**: 각 테스트는 자체 환경에서만 동작, 다음 테스트로 환경 전이 없음
- **검증 도구**: `autouse` 픽스처에서 시작·종료 환경 비교

### Scenario 12.5: flaky 결정성 [Must-pass]

- **Given**: 동일 테스트를 시각이 다른 두 시점에 실행
- **When**: `pytest -m "not live"` 2회 실행
- **Then**: 두 실행 결과가 동일 (통과/실패 동일, 출력 동일)

---

## 13. 통합 점검 (Definition of Done)

본 SPEC이 머지되기 위한 종합 체크리스트:

### 13.1 코드 변경 [Must-pass]

- [ ] `tests/` 디렉터리 전체 신설 (Scenario 1.1~1.5)
- [ ] 단위 테스트 4개 모듈 (`test_formatter.py`, `test_telegram_push.py`, `test_naver_kr.py`, `test_us_market.py`) 작성
- [ ] 통합 스모크 3개 모듈 (`test_daily_kr.py`, `test_daily_us.py`, `test_weekly.py`) 작성
- [ ] live 마커 모듈 2개 (`test_naver_live.py`, `test_yfinance_live.py`) 작성
- [ ] `tests/conftest.py`에 live 자동 deselect 훅 + 환경변수 격리 autouse 픽스처
- [ ] `tests/fixtures/` 정적 캡처본 7개 파일
- [ ] `pytest.ini` (또는 `pyproject.toml`)에 markers + testpaths 등록
- [ ] `.coveragerc`에 `__main__` 블록 제외 설정
- [ ] `requirements-dev.txt`에 pytest/pytest-cov/pytest-mock 추가
- [ ] `market_flow/` 코드 미변경 (Scenario 12.1)

### 13.2 테스트 [Must-pass]

- [ ] 위 13개 섹션의 Must-pass 시나리오 전부 통과
- [ ] `pytest -m "not live"` 전체 통과
- [ ] `pytest -m live` 통과 (네트워크 가능 환경에서)
- [ ] live 자동 deselect 동작 (Scenario 2.1)
- [ ] 외부 호출 0회 (Scenario 6.9, 7.9, 8.5, 12.2)

### 13.3 품질 게이트 [Must-pass]

- [ ] `ruff check tests/` 클린
- [ ] 커버리지 ≥ 80% (Scenario 11.1)
- [ ] LSP 변경 파일 zero errors
- [ ] 테스트가 결정론적 (Scenario 12.5)
- [ ] 환경변수 누수 없음 (Scenario 12.4)

### 13.4 CI 통합 [Should-pass]

- [ ] `.github/workflows/test.yml`에 `pytest -m "not live" --cov=market_flow` 명령 통합
- [ ] CI 첫 5회 실행에서 flaky 0건
- [ ] (선택) `workflow_dispatch` 트리거에 live 옵트인 옵션 추가

### 13.5 문서·추적성 [Must-pass]

- [ ] 커밋 메시지에 `SPEC-MF-TEST-001` 명시
- [ ] plan.md의 사전 조사(R1~R8) 결정 사항이 plan.md 또는 research.md에 기록됨
- [ ] 변경 파일 목록이 spec.md의 "Files to Modify / Create" 섹션과 일치
- [ ] fixture 재생성 절차 문서화 (Scenario 10.4)

---

## 14. 회귀 차단 (Regression Suite)

본 SPEC 머지 이후 다음 동작이 유지되어야 한다:

- `market_flow/` 패키지의 기존 모든 동작 (코드 미변경이므로 자동 보장)
- 기존 GitHub Actions 운영 워크플로우(`flow-kr.yml`, `flow-us.yml`, `flow-weekly.yml`)의 cron·실행 명령 (본 SPEC은 `test.yml`만 수정)
- `--no-telegram` dry-run 플래그의 기존 동작 (d78d0a6에서 도입, 본 SPEC에서 환경변수 기반 dry-run 검증으로 회귀 차단)
- `MARKET_FLOW_DRY_RUN` 환경변수 기반 dry-run 동작 (telegram_push.py 현행 코드)
- live 마커가 등록되어 있지 않던 기존 상태에서 신규 마커가 도입되어도 기존 pytest 호출 명령의 결과가 깨지지 않음 (`pytest` 그대로 호출 시 live는 자동 deselect)

회귀 검증은 본 SPEC에서 추가된 모든 테스트로 보장한다. 후속 SPEC-MF-SCHED-001 머지 시에는 본 SPEC의 테스트 슈트가 그대로 통과해야 하며, SPEC-MF-SCHED-001이 추가하는 `calendar_utils.py`·시각 주입 로직은 자체 acceptance에서 다룬다.
