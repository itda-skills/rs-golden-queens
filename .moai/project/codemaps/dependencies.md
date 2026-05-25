# 의존성 그래프 — rs-golden-queens

---

## 외부 라이브러리 (`market_flow/requirements.txt`)

| 라이브러리 | 버전 제약 | 용도 | 도입 SPEC |
|---|---|---|---|
| `yfinance` | `>=0.2.40` | Yahoo Finance에서 미국 지수·섹터·ETF·매크로 데이터 수집 | — |
| `pandas` | `>=2.0` | yfinance 의존 라이브러리, 시계열 DataFrame 처리 | — |
| `python-dotenv` | `>=1.0` | 로컬 개발용 `market_flow/.env` 파일 자동 로딩 | — |
| `pandas_market_calendars` | `>=4.4` | NYSE 거래일 판정 (`is_us_trading_day`) | SPEC-MF-SCHED-001 |
| `exchange_calendars` | `>=4.5` | XKRX 거래일 판정 (`is_kr_trading_day`, `is_last_kr_trading_day_of_week`) | SPEC-MF-SCHED-001 |

설치 명령:

```bash
pip install -r market_flow/requirements.txt
# 또는
make install   # uv 우선, fallback pip
```

**설계 원칙:** 필요 최소 의존성. 불필요한 HTTP 클라이언트(`requests`, `httpx`)·파서(`bs4`, `lxml`)·프레임워크 도입 금지. 네이버 fetch는 표준 라이브러리 `urllib`으로 직접 구현.

---

## 표준 라이브러리 사용처

| stdlib 모듈 | 사용 파일 | 역할 |
|---|---|---|
| `zoneinfo` | `calendar_utils.py`, `daily_kr.py`, `daily_us.py`, `weekly.py` | KST/ET 시간대 처리 (`ZoneInfo("Asia/Seoul")`, `ZoneInfo("America/New_York")`) |
| `datetime` | 모든 진입점, `calendar_utils.py`, `fetchers/naver_kr.py`, `fetchers/us_market.py` | 날짜·시각 연산 |
| `os` | `telegram_push.py` | 환경변수 읽기 (`GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`, `MARKET_FLOW_DRY_RUN`) |
| `sys` | 모든 진입점, `telegram_push.py` | `sys.argv`, `sys.exit()` |
| `urllib.request` | `fetchers/naver_kr.py`, `telegram_push.py` | HTTP GET (네이버), POST (Telegram sendMessage) |
| `urllib.parse` | `telegram_push.py` | `urlencode` (Telegram 요청 페이로드 인코딩) |
| `json` | `fetchers/naver_kr.py`, `telegram_push.py` | JSON 파싱·응답 처리 |
| `re` | `fetchers/naver_kr.py`, `telegram_push.py` | HTML 패턴 추출, 부호 숫자 ANSI 색상 치환 |
| `pathlib` | `telegram_push.py` | `.env` 파일 경로 해석 |
| `typing` | `calendar_utils.py`, 진입점 | `Optional` 타입 힌트 |

---

## 옵션 개발 의존성

| 패키지 | 용도 | 런타임 필요 여부 |
|---|---|---|
| `pytest` | 단위 테스트 실행 | 불필요 (CI 전용) |

설치: `make install` 또는 `pip install pytest`

테스트 실행 (네트워크 없음):

```bash
python -m pytest tests/ -q -m "not live"
```

---

## 외부 서비스 의존

### 네이버 금융

`market_flow/fetchers/naver_kr.py`가 직접 fetch.

| 엔드포인트 | 인코딩 | 데이터 |
|---|---|---|
| `m.stock.naver.com/api/index/{MARKET}/integration` | UTF-8 JSON | 코스피·코스닥 당일 매매동향 + 프로그램매매 |
| `finance.naver.com/sise/investorDealTrendDay.naver?bizdate={YYYYMMDD}` | EUC-KR HTML | 코스피 일별 10거래일 순매수 |
| `finance.naver.com/sise/investorDealTrendTime.naver?bizdate={YYYYMMDD}` | EUC-KR HTML | 코스피 시간별 누적 순매수 |

**주의:** 네이버 데스크탑 페이지는 EUC-KR 인코딩. `_get(url, decode="euc-kr")` 명시 필요. 모바일 API는 UTF-8.

### Yahoo Finance (via yfinance)

`market_flow/fetchers/us_market.py`가 `yfinance.download()`로 수집.

수집 ticker 목록:

| 그룹 | Ticker 목록 |
|---|---|
| 지수 | `^GSPC`, `^IXIC`, `^DJI`, `^RUT` |
| 변동성 | `^VIX`, `^VVIX`, `^SKEW` |
| 위험선호 | `HYG`, `IEF` |
| 매크로 | `^TNX`, `^TYX`, `DX-Y.NYB`, `KRW=X`, `CL=F`, `GC=F` |
| 섹터 ETF | `XLK`, `XLF`, `XLV`, `XLY`, `XLC`, `XLI`, `XLP`, `XLE`, `XLU`, `XLB`, `XLRE` |
| 워치 ETF | `QQQ`, `SMH`, `NLR`, `XLE`, `GLD`, `SLV`, `ITA`, `XOVR` |

### Telegram Bot API

`market_flow/telegram_push.py`가 직접 POST.

| 항목 | 내용 |
|---|---|
| 엔드포인트 | `https://api.telegram.org/bot{TOKEN}/sendMessage` |
| 메서드 | POST (`urllib.request`) |
| 인증 | `GOLDENQUEENS_BOT_TOKEN` 환경변수 |
| 파라미터 | `chat_id`, `text`, `parse_mode`, `disable_notification`, `disable_web_page_preview` |
| dry-run | `MARKET_FLOW_DRY_RUN=1` 시 HTTP 미호출, stdout 출력 |

---

## GitHub Secrets

| 시크릿 이름 | 의미 |
|---|---|
| `GOLDENQUEENS_BOT_TOKEN` | Telegram Bot 인증 토큰 |
| `GOLDENQUEENS_CHAT_ID` | 수신 chat_id (채널은 `-100` 시작) |

시크릿 이름 변경 금지 (SPEC-MF-SCHED-NEG-001). 변경 시 GitHub Actions 시크릿 재등록 필요.

등록 위치: `Repository → Settings → Secrets and variables → Actions`

---

## 내부 모듈 의존성 그래프

```
daily_kr.py ──────┬── calendar_utils.py ──── pandas_market_calendars
                  │                     └─── exchange_calendars
                  ├── fetchers/naver_kr.py ── urllib (stdlib)
                  ├── formatter.py
                  └── telegram_push.py ────── urllib (stdlib)
                                          └── python-dotenv (optional)

daily_us.py ──────┬── calendar_utils.py (공유)
                  ├── fetchers/us_market.py ─ yfinance ── pandas
                  ├── formatter.py (공유)
                  └── telegram_push.py (공유)

weekly.py ────────┬── calendar_utils.py (공유)
                  ├── fetchers/naver_kr.py (공유)
                  ├── fetchers/us_market.py (WATCH 상수)
                  ├── yfinance (직접 import — _watch_5d_pct)
                  ├── formatter.py (공유)
                  └── telegram_push.py (공유)
```

**주목할 점:**

- `daily_kr.py`, `daily_us.py`, `weekly.py`는 `calendar_utils.py`, `formatter.py`, `telegram_push.py`를 공통으로 사용하지만 서로 직접 의존하지 않는다.
- `calendar_utils.py`는 외부 라이브러리(`pandas_market_calendars`, `exchange_calendars`)에 의존하며, 진입점 스크립트 중 유일하게 외부 캘린더 라이브러리를 사용하는 모듈이다.
- `telegram_push.py`는 표준 라이브러리만 사용한다 (`urllib`, `json`, `os`, `sys`, `re`, `pathlib`). `python-dotenv`는 import 실패 시 graceful fallback.
- `fetchers/naver_kr.py`는 표준 라이브러리만 사용한다 (`urllib`, `json`, `re`, `datetime`).

---

## 출처

- `market_flow/requirements.txt` 직접 확인
- `market_flow/` 각 모듈 import 구문 직접 확인
- `.moai/project/tech.md` §1 (기술 스택), §2 (외부 통합), §4 (환경변수)
- SPEC-MF-SCHED-001 (pandas_market_calendars, exchange_calendars 도입 근거)
- SPEC-MF-SCHED-NEG-001 (시크릿 이름 불변 제약)
