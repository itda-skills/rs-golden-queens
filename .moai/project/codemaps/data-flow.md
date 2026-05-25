# 데이터 흐름 — rs-golden-queens

시스템을 통과하는 데이터의 변환 단계를 세 실행 경로(한국장·미국장·주간)와 dry-run 변형으로 분리하여 서술한다.

---

## 경로 A — 한국장 일간 (`daily_kr.py`)

GitHub Actions `flow-kr.yml`이 평일 KST 18:10에 트리거하는 경로.

```
1. cron 트리거 (UTC 09:10, 평일)
   └─ flow-kr.yml → python daily_kr.py
   └─ 환경변수: GOLDENQUEENS_BOT_TOKEN, GOLDENQUEENS_CHAT_ID, TZ=Asia/Seoul

2. 휴장 게이트 — calendar_utils.is_kr_trading_day(now)
   └─ exchange_calendars XKRX 캘린더 조회
   └─ 비거래일: send("[KR] 오늘은 휴장입니다") → 종료
   └─ 거래일: 다음 단계 진행

3. 데이터 수집 — fetchers/naver_kr.fetch_today(bizdate)
   ├─ fetch_daily_summary("KOSPI")
   │   └─ GET m.stock.naver.com/api/index/KOSPI/integration (JSON)
   │   └─ 반환: {bizdate, personal, foreign, institutional,
   │             program_arb, program_nonarb, program_total} (억원)
   ├─ fetch_daily_summary("KOSDAQ")  (동일 구조)
   ├─ fetch_kospi_intraday(bizdate)
   │   └─ GET finance.naver.com/sise/investorDealTrendTime.naver (EUC-KR HTML)
   │   └─ 반환: [{"time", "personal", "foreign", "institutional", ...}]
   └─ fetch_kospi_daily(bizdate)
       └─ GET finance.naver.com/sise/investorDealTrendDay.naver (EUC-KR HTML)
       └─ 반환: [{"date", "personal", "foreign", "institutional", ...}] (최대 10행)

4. 포맷 — formatter.format_kr_daily(data)
   └─ 한국 색 컨벤션 적용 (🔴▲ 양수 / 🔵▼ 음수)
   └─ Markdown 문자열 생성

5. 텔레그램 발송 — telegram_push.send(text)
   └─ POST api.telegram.org/bot{TOKEN}/sendMessage
   └─ 반환: {"ok": True, "result": {"message_id": N}}
```

---

## 경로 B — 미국장 일간 (`daily_us.py`)

GitHub Actions `flow-us.yml`이 dual-cron으로 트리거하는 경로. 두 cron 모두 매일 평일 실행되지만, DST 게이트로 이중 발송을 방지한다.

```
1. dual-cron 트리거 (평일)
   ├─ EDT 시즌용: UTC 20:30 (flow-us.yml cron '30 20 * * 1-5')
   │   └─ MARKET_SCHEDULE=edt 주입
   └─ EST 시즌용: UTC 21:30 (flow-us.yml cron '30 21 * * 1-5')
       └─ MARKET_SCHEDULE=est 주입
   (두 cron 모두 항상 활성 — 게이트로 하나만 통과)

2. DST 게이트 — @MX:WARN 이중 발송 방지
   └─ os.environ["MARKET_SCHEDULE"] 읽기 → "edt" | "est"
   └─ calendar_utils.is_us_in_dst(now)
       └─ datetime.now(America/New_York).dst() != timedelta(0) 판정
   └─ MARKET_SCHEDULE == "edt" AND 실제 EST 시즌 → sys.exit(0)
   └─ MARKET_SCHEDULE == "est" AND 실제 EDT 시즌 → sys.exit(0)
   └─ 일치: 다음 단계 진행

3. 휴장 게이트 — calendar_utils.is_us_trading_day(now)
   └─ pandas_market_calendars NYSE 캘린더 조회
   └─ 비거래일: send("[US] 오늘은 휴장입니다") → 종료
   └─ 거래일: 다음 단계 진행

4. 데이터 수집 — fetchers/us_market.fetch_us_close(target_date)
   └─ yfinance.download() (여러 ticker 일괄)
   └─ 수집 범위 (최근 45거래일 window에서 최신값 추출):
       ├─ indices: ^GSPC, ^IXIC, ^DJI, ^RUT
       ├─ volatility: ^VIX, ^VVIX, ^SKEW
       ├─ risk_onoff: HYG, IEF
       ├─ macro: ^TNX, ^TYX, DX-Y.NYB, KRW=X, CL=F, GC=F
       ├─ sectors: XLK, XLF, XLV, XLY, XLC, XLI, XLP, XLE, XLU, XLB, XLRE
       └─ watch: QQQ, SMH, NLR, XLE, GLD, SLV, ITA, XOVR
   └─ 각 ticker: {label, close, pct, vol_ratio, date} | None

5. 포맷 — formatter.format_us_daily(data)
   └─ Markdown 문자열 생성

6. 텔레그램 발송 — telegram_push.send(text)
   └─ POST api.telegram.org/bot{TOKEN}/sendMessage
```

---

## 경로 C — 주간 리포트 (`weekly.py`)

GitHub Actions `flow-weekly.yml`이 평일 KST 18:30에 트리거하는 경로. 스크립트 내부 게이트가 실제 발송 여부를 결정한다.

```
1. cron 트리거 (UTC 09:30, 평일)
   └─ flow-weekly.yml → python weekly.py
   (월~금 매일 트리거되지만 마지막 거래일에만 발송)

2. 마지막 거래일 게이트 — calendar_utils.is_last_kr_trading_day_of_week(now)
   └─ 오늘 KST 날짜가 KR 거래일인지 확인 (exchange_calendars XKRX)
   └─ 오늘+1 ~ 이번 주 금요일까지 KR 비거래일인지 확인
   └─ 조건 불충족: 침묵 종료 (발송 없음, exit code 0)
   └─ 조건 충족: 다음 단계 진행
   (금요일 휴장 → 목요일에 True 반환)

3a. 코스피 일별 수집 — fetchers/naver_kr.fetch_kospi_daily(bizdate)
    └─ 네이버 데스크탑 EUC-KR HTML 파싱
    └─ 반환: 최근 10거래일 일별 순매수 (억원)

3b. 워치ETF 5일 누적 등락 — weekly._watch_5d_pct()
    └─ yfinance.download(WATCH tickers, 최근 20일 window)
    └─ 각 ticker: (오늘 종가 / 6일전 종가 - 1) × 100 (%)
    └─ 반환: {"QQQ": 2.5, "SMH": -1.3, ...}

4. 포맷 — formatter.format_weekly(kospi_daily, watch_5d)
   └─ kospi_daily 최신 5행 사용
   └─ Markdown 문자열 생성

5. 텔레그램 발송 — telegram_push.send(text)
   └─ POST api.telegram.org/bot{TOKEN}/sendMessage
```

---

## Dry-run 변형

`MARKET_FLOW_DRY_RUN=1` 환경변수 설정 시 모든 경로에서 적용된다.

```
telegram_push.send() 호출 시:
   └─ _is_dry_run() == True 판정
   └─ HTTP 호출 없음
   └─ 구분선 + "[DRY-RUN]" 헤더 + 텍스트를 stdout 출력
   └─ TTY 환경이면 ANSI 색상 적용 (+숫자 빨강, -숫자 파랑)
   └─ {"ok": True, "dry_run": True, "result": {"message_id": 0}} 반환

활성화 방법:
   - make daily-kr DRY=1  (Makefile이 MARKET_FLOW_DRY_RUN=1 자동 주입)
   - MARKET_FLOW_DRY_RUN=1 python daily_us.py
```

---

## 에러 처리 전략

| 경로 | 전략 |
|---|---|
| 휴장 게이트 라이브러리 오류 | 예외 전파 → GitHub Actions 실패로 기록 |
| Naver HTTP 오류 | `urllib` 예외 전파 → 워크플로우 실패 |
| yfinance 개별 ticker 실패 | `except Exception: pass` → `None` 반환, 메시지에서 해당 항목 생략 |
| 텔레그램 전송 실패 | `RuntimeError` 예외 전파 (환경변수 없는 경우) |
| dry-run 환경 | HTTP 없음, 항상 성공 반환 |

---

## 시간대 처리

| 함수 | 위치 | 기준 시간대 |
|---|---|---|
| `is_kr_trading_day()` / `is_last_kr_trading_day_of_week()` | `calendar_utils.py` | KST (Asia/Seoul) |
| `is_us_in_dst()` / `is_us_trading_day()` | `calendar_utils.py` | ET (America/New_York) |
| `daily_kr.main()` | `daily_kr.py` | KST |
| `daily_us.main()` | `daily_us.py` | ET |
| `weekly.main()` | `weekly.py` | KST |
| `_watch_5d_pct()` | `weekly.py` | 시스템 로컬 (yfinance 기준) |

---

## 출처

- `market_flow/daily_kr.py`, `daily_us.py`, `weekly.py` 직접 확인
- `market_flow/calendar_utils.py` 직접 확인 (DST·거래일 판정 구현)
- `market_flow/telegram_push.py` 직접 확인 (dry-run 분기)
- `market_flow/fetchers/naver_kr.py`, `fetchers/us_market.py` 직접 확인
- `.github/workflows/flow-us.yml` (dual-cron 구조 확인)
- `.moai/project/tech.md` §3 (운영 환경·DST 게이트 메커니즘)
- SPEC-MF-SCHED-001 (DST 자동 반영 + 휴장 인지)
