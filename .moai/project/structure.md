# structure.md — rs-golden-queens

## 디렉토리 트리

```
rs-golden-queens/
├── README.md                          # 저장소 가이드 + 빠른 시작
├── Makefile                           # 운영 타겟
├── market_flow/                       # 메인 패키지
│   ├── __init__.py
│   ├── README.md                      # 패키지 상세 문서 (1순위 참조)
│   ├── requirements.txt               # yfinance, pandas, python-dotenv, pandas_market_calendars, exchange_calendars
│   ├── .env.example                   # 로컬 환경변수 템플릿
│   ├── daily_kr.py                    # 한국장 매매동향 진입점
│   ├── daily_us.py                    # 미국장 마감 요약 진입점 (DST 게이트 포함)
│   ├── weekly.py                      # 주간 리포트 진입점 (마지막 거래일 게이트)
│   ├── calendar_utils.py              # DST/거래일/마지막 거래일 판정 (SPEC-MF-SCHED-001)
│   ├── formatter.py                   # 색 컨벤션 + 단위 포맷
│   ├── telegram_push.py               # Telegram sendMessage + MARKET_FLOW_DRY_RUN 분기
│   └── fetchers/
│       ├── __init__.py
│       ├── naver_kr.py                # 네이버 모바일/데스크탑 페이지
│       └── us_market.py               # yfinance WATCH ETF
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # market_flow를 sys.path에 등록 + 공통 fixture
│   ├── test_calendar_utils.py         # 26 tests
│   ├── test_daily_kr.py               # 5 tests
│   ├── test_daily_us.py               # 10 tests
│   └── test_weekly.py                 # 5 tests
├── .github/
│   └── workflows/
│       ├── flow-kr.yml                # 평일 KST 18:10
│       ├── flow-us.yml                # dual-cron DST 자동 반영
│       ├── flow-weekly.yml            # 월~금 KST 18:30, 마지막 거래일 게이트
│       └── test.yml                   # Linux × Python 3.10/3.11/3.12
├── .moai/
│   ├── config/                        # MoAI 설정 (user.yaml, language.yaml 등)
│   └── project/                       # 프로젝트 문서 (product.md, structure.md, tech.md)
└── .claude/                           # Claude Code 에이전트 규칙·스킬·훅
```

## 디렉토리 역할

| 디렉토리 | 역할 |
|---|---|
| `market_flow/` | 메인 Python 패키지. 데이터 수집·포맷·알림·거래일 판정 전부 포함. |
| `market_flow/fetchers/` | 외부 데이터 소스 어댑터. 네이버(한국) + yfinance(미국) |
| `tests/` | 단위 테스트 46개. 전부 mock 기반, 네트워크 없음. |
| `.github/workflows/` | CI 매트릭스(`test.yml`) + 세 종류의 발송 워크플로우. |
| `.moai/` | MoAI-ADK 설정·프로젝트 문서. |
| `.claude/` | Claude Code 에이전트 규칙·스킬·훅 (MoAI-ADK 운영 설정). |

## `market_flow/` 모듈 표

| 모듈 | 역할 | 라인 수 |
|---|---|---|
| `daily_kr.py` | 한국장 일간 진입점. XKRX 휴장 게이트 → 네이버 fetch → 텔레그램 발송. | 48 |
| `daily_us.py` | 미국장 일간 진입점. DST 게이트 → NYSE 휴장 게이트 → yfinance fetch → 텔레그램 발송. | 59 |
| `weekly.py` | 주간 리포트 진입점. 마지막 KR 거래일 게이트 → 코스피+워치ETF → 텔레그램 발송. | 69 |
| `calendar_utils.py` | `is_us_in_dst`, `is_us_trading_day`, `is_kr_trading_day`, `is_last_kr_trading_day_of_week`. 결정론적 테스트를 위해 `now` 파라미터 주입 지원. | 135 |
| `formatter.py` | 한국 색 컨벤션(🔴▲/🔵▼), KR/US/주간 포맷 함수. | 362 |
| `telegram_push.py` | Telegram Bot API `sendMessage`. `MARKET_FLOW_DRY_RUN=1`이면 stdout만 출력. | 91 |
| `fetchers/naver_kr.py` | 네이버 모바일/데스크탑 페이지 fetch + HTML 파싱. | 113 |
| `fetchers/us_market.py` | yfinance로 WATCH ETF·지수·섹터·매크로 수집. | 92 |

## 진입점 매핑

| 진입점 | 명령 | 용도 |
|---|---|---|
| `python daily_kr.py [DATE]` | `make daily-kr [DATE=YYYYMMDD]` | 한국장 일간 발송 |
| `python daily_us.py [DATE]` | `make daily-us [DATE=YYYY-MM-DD]` | 미국장 일간 발송 |
| `python weekly.py` | `make weekly` | 주간 리포트 발송 |

모든 진입점은 `market_flow/` 디렉토리에서 실행한다 (Makefile의 `cd $(PKG_DIR)` 참조).

## Makefile 타겟

| 타겟 | 역할 |
|---|---|
| `help` | 사용 가능한 명령 목록 출력 (기본 타겟) |
| `install` | 의존성 설치 (uv 우선, fallback pip) |
| `daily-kr [DATE=YYYYMMDD]` | 한국장 매매동향 발송 |
| `daily-us [DATE=YYYY-MM-DD]` | 미국장 마감 요약 발송 |
| `weekly` | 주간 리포트 발송 |
| `notify-test` | 텔레그램 핑 메시지 (환경변수 동작 확인) |
| `smoke-kr` | 네이버 fetch 단독 점검 (텔레그램 발송 없음) |
| `smoke-us` | yfinance fetch 단독 점검 (텔레그램 발송 없음) |
| `clean` | `__pycache__`, `.pytest_cache`, `htmlcov` 제거 |

dry-run: `make <타겟> DRY=1` → `MARKET_FLOW_DRY_RUN=1`이 자동 주입되어 텔레그램 없이 stdout 출력.

## CI 워크플로우

### `test.yml` — 코드 품질 검증

- 트리거: `push` (main), `pull_request` (main), `workflow_dispatch`
- 러너: ubuntu-latest 단일 OS
- 매트릭스: Python 3.10 / 3.11 / 3.12 (3잡)
- 실행: `pytest tests/ -q -m "not live"`
- `fail-fast: false`

### `flow-kr.yml` — 한국장 일간 발송

- 트리거: `cron '10 9 * * 1-5'` (평일 KST 18:10) + `workflow_dispatch`
- 러너: ubuntu-latest, Python 3.13
- 작업 디렉토리: `market_flow`
- 실행: `python daily_kr.py`
- 환경변수: `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`, `TZ=Asia/Seoul`

### `flow-us.yml` — 미국장 일간 발송 (DST 자동 반영)

- 트리거: dual-cron + `workflow_dispatch`
  - EDT 시즌: `cron '30 20 * * 1-5'` (UTC 20:30 = NYSE 16:00 EDT + 30분)
  - EST 시즌: `cron '30 21 * * 1-5'` (UTC 21:30 = NYSE 16:00 EST + 30분)
- 러너: ubuntu-latest, Python 3.13
- 작업 디렉토리: `market_flow`
- 실행: `python daily_us.py`
- 환경변수: `MARKET_SCHEDULE` (`edt` 또는 `est`, `github.event.schedule`로 주입), `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`, `TZ=Asia/Seoul`

### `flow-weekly.yml` — 주간 리포트 발송

- 트리거: `cron '30 9 * * 1-5'` (평일 KST 18:30) + `workflow_dispatch`
- 러너: ubuntu-latest, Python 3.13
- 작업 디렉토리: `market_flow`
- 실행: `python weekly.py`
- 환경변수: `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`, `TZ=Asia/Seoul`
- 비고: 스크립트 내부 `is_last_kr_trading_day_of_week()` 게이트가 실제 발송 여부를 결정. 금요일 휴장 시 직전 거래일에 이월.

## 테스트 구조

| 구분 | 파일 | 테스트 수 | 특징 |
|---|---|---|---|
| calendar_utils | `test_calendar_utils.py` | 26 | 시각 파라미터 주입으로 결정론적 테스트 |
| daily_kr | `test_daily_kr.py` | 5 | mock 기반, 휴장 분기 포함 |
| daily_us | `test_daily_us.py` | 10 | DST 게이트·휴장 게이트 포함 |
| weekly | `test_weekly.py` | 5 | 마지막 거래일 게이트 포함 |
| **합계** | — | **46** | 전부 mock, 네트워크 없음 |

live 마커 기반 테스트는 현재 없음. SPEC-MF-TEST-001 (draft)에서 향후 구축 예정.

## 출처

- `market_flow/` 각 모듈 직접 측정 (라인 수 2026-05-25 기준)
- `.github/workflows/*.yml` 직접 확인
- `Makefile` 직접 확인
- `tests/` 디렉토리 직접 확인
