# tech.md — rs-golden-queens

## 1. 기술 스택 개요

| 항목 | 내용 |
|---|---|
| 언어 | Python 3.10+ (CI 매트릭스: 3.10/3.11/3.12), Python 3.13 (운영 워크플로우) |
| 패키지 관리 | `market_flow/requirements.txt` (pip / uv) |
| 외부 의존성 | yfinance, pandas, python-dotenv, pandas_market_calendars, exchange_calendars |
| 테스트 | pytest (`-m "not live"` 기본, live 마커 확장 예정) |
| CI | GitHub Actions — Linux 단일 OS × Python 3.10/3.11/3.12 = 3잡 |

설계 원칙: "외부 의존성 최소화 + 검증된 라이브러리 채택". 데이터 수집 목적에 한해 yfinance, pandas, pandas_market_calendars, exchange_calendars를 사용한다. 불필요한 프레임워크·HTTP 클라이언트·파서 라이브러리는 도입하지 않는다.

## 2. 외부 통합

### 네이버 금융 (한국 데이터)

`market_flow/fetchers/naver_kr.py`가 네이버 모바일/데스크탑 페이지를 직접 fetch한다.

| 데이터 | 소스 페이지 | 단위 |
|---|---|---|
| 코스피·코스닥 당일 합산 (외인·기관·개인) | 네이버 모바일 API | 억원 |
| 프로그램매매 (차익/비차익) | 네이버 모바일 API | 억원 |
| 10거래일 추이 (코스피) | 네이버 데스크탑 | 억원 |

### yfinance (미국 데이터)

`market_flow/fetchers/us_market.py`가 Yahoo Finance에서 수집한다.

| 데이터 | 내용 |
|---|---|
| 지수 | S&P 500 (^GSPC), 나스닥 (^IXIC), 다우 (^DJI) |
| 변동성 | VIX (^VIX) |
| 섹터 ETF | XLK, XLV, XLF 등 11개 |
| 워치 ETF | QQQ, SMH 등 (`WATCH` 리스트 — 수정 시 fetcher + formatter 양쪽 수정) |
| 매크로 | 국채 금리, DXY 등 |

### pandas_market_calendars (NYSE 거래일 판정)

`market_flow/calendar_utils.py`의 `is_us_trading_day()` 함수가 사용한다. 반장일도 거래일로 간주.

### exchange_calendars (XKRX 거래일 판정)

`market_flow/calendar_utils.py`의 `is_kr_trading_day()`, `is_last_kr_trading_day_of_week()` 함수가 사용한다.

### Telegram Bot API

- 엔드포인트: `https://api.telegram.org/bot{TOKEN}/sendMessage`
- 메서드: POST
- 인증: `GOLDENQUEENS_BOT_TOKEN` 환경변수
- `MARKET_FLOW_DRY_RUN=1` 설정 시 API 호출 없이 stdout 출력으로 대체

## 3. 운영 환경

### cron 시각 산정

| 워크플로우 | cron 표현식 | KST 시각 | 근거 |
|---|---|---|---|
| `flow-kr.yml` | `10 9 * * 1-5` | 평일 18:10 | 네이버 18:03 갱신 + 7분 마진 |
| `flow-us.yml` (EDT) | `30 20 * * 1-5` | 익일 05:30 | NYSE 16:00 EDT + 30분 |
| `flow-us.yml` (EST) | `30 21 * * 1-5` | 익일 06:30 | NYSE 16:00 EST + 30분 |
| `flow-weekly.yml` | `30 9 * * 1-5` | 평일 18:30 | KST 18:10보다 20분 후, 마지막 거래일 게이트 |

### DST 게이트 메커니즘 (SPEC-MF-SCHED-001)

`flow-us.yml`은 두 cron이 동시에 활성화되어 EDT/EST 시즌마다 두 잡이 모두 트리거된다. 이중 발송을 방지하기 위해:

1. 워크플로우가 `MARKET_SCHEDULE=edt` 또는 `MARKET_SCHEDULE=est`를 주입 (`github.event.schedule`로 분기)
2. `daily_us.py`가 `is_us_in_dst()`로 실제 DST 시즌을 확인
3. `MARKET_SCHEDULE`과 실제 시즌이 불일치하면 즉시 `sys.exit(0)`

결과: 한 시즌에 한 번만 발송.

### 휴장 처리 흐름

```
flow-kr 트리거
  → is_kr_trading_day() → 비거래일: "[KR] 오늘은 휴장입니다" 발송, 종료
                         → 거래일: 데이터 수집 → 정상 발송

flow-us 트리거
  → DST 게이트 (MARKET_SCHEDULE 불일치면 종료)
  → is_us_trading_day() → 비거래일: "[US] 오늘은 휴장입니다" 발송, 종료
                         → 거래일: 데이터 수집 → 정상 발송

flow-weekly 트리거
  → is_last_kr_trading_day_of_week() → 아니면: 침묵 종료 (발송 없음)
                                      → 마지막 거래일: 데이터 수집 → 주간 리포트 발송
```

## 4. 환경변수 명명 표준

| 환경변수 | 의미 | 위치 |
|---|---|---|
| `GOLDENQUEENS_BOT_TOKEN` | Telegram Bot 토큰 | GitHub Secrets / `.env` |
| `GOLDENQUEENS_CHAT_ID` | 수신 chat_id (채널은 `-100` 시작) | GitHub Secrets / `.env` |
| `MARKET_FLOW_DRY_RUN` | `1`이면 텔레그램 발송 없이 stdout 출력 | Makefile `DRY=1` 또는 export |
| `MARKET_SCHEDULE` | `edt` 또는 `est` — DST 게이트용 | `flow-us.yml`이 자동 주입 |

`GOLDENQUEENS_*` 시크릿 이름은 변경 불가 (SPEC-MF-SCHED-NEG-001). `TELEGRAM_BOT_TOKEN` 등 일반 명칭과 의도적으로 구분.

### GitHub Secrets 등록 위치

```
Repository → Settings → Secrets and variables → Actions
  GOLDENQUEENS_BOT_TOKEN
  GOLDENQUEENS_CHAT_ID
```

두 값 모두 있어야 텔레그램 발송이 활성화된다. 하나라도 없으면 `telegram_push.py`가 stdout 출력만 하고 정상 종료 (exit code 0).

## 5. CI 매트릭스

| OS | Python 3.10 | Python 3.11 | Python 3.12 |
|---|---|---|---|
| ubuntu-latest | O | O | O |

총 3잡. `fail-fast: false`. pytest `-m "not live"` 옵션으로 네트워크 호출이 필요한 테스트는 제외.

## 6. 개발 환경 요구사항

| 항목 | 요구사항 |
|---|---|
| Python | 3.10+ |
| make | Makefile 사용 시 필요 |
| pip / uv | 의존성 설치 |

설치 명령:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r market_flow/requirements.txt
# 또는
make install   # uv 우선, fallback pip
```

## 7. 검증 명령

```bash
# 단위 테스트 (mock, 네트워크 없음)
python -m pytest tests/ -q -m "not live"

# 코드 품질 (ruff 설치 시)
ruff check market_flow/ tests/

# 개별 fetch 점검 (텔레그램 발송 없음)
make smoke-kr   # 네이버 fetch 단독
make smoke-us   # yfinance fetch 단독

# dry-run (텔레그램 발송 없이 전체 리포트 stdout)
make daily-kr DRY=1
make daily-us DRY=1
make weekly DRY=1

# 텔레그램 연결 확인
make notify-test
```

## 8. 의도적 결정 (HARD 제약)

| 결정 | 내용 |
|---|---|
| dry-run은 환경변수로만 | `MARKET_FLOW_DRY_RUN`으로만 제어. CLI 플래그 없음. `telegram_push.py` 내부에서 분기. |
| 반장 시각 동적 조정 없음 | 반장일은 정상 거래일로 처리. NYSE/KRX 반장 시각 조회·분기 구현 없음. |
| `GOLDENQUEENS_*` 시크릿 이름 불변 | SPEC-MF-SCHED-NEG-001. 이름 변경 시 GitHub Actions 시크릿 재등록 필요 → 변경 금지. |
| `flow-kr.yml` cron 불변 | `10 9 * * 1-5` 고정. 네이버 갱신 주기 변경 확인 전 수정 금지. |
| `formatter.format_weekly` 본문 형식 불변 | 텔레그램 파싱 의존. 구조 변경 시 수신 측에 영향. |

## 출처

- `market_flow/requirements.txt` 직접 확인
- `market_flow/calendar_utils.py` 직접 확인 (DST/거래일 판정 구현)
- `market_flow/daily_kr.py`, `daily_us.py`, `weekly.py` 직접 확인 (진입점·게이트 로직)
- `market_flow/telegram_push.py` 직접 확인 (DRY_RUN 분기)
- `.github/workflows/flow-kr.yml`, `flow-us.yml`, `flow-weekly.yml`, `test.yml` 직접 확인
- `Makefile` 직접 확인
- SPEC-MF-SCHED-001 (DST 자동 반영 + 휴장 인지)
