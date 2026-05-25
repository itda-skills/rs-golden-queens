# 시스템 개요 — rs-golden-queens

## 시스템 정체성

한국장·미국장 마감 후 텔레그램 채널로 매매동향 요약을 자동 푸시하는 개인 투자 데이터 보조 서비스. 네이버 금융(한국 데이터)과 yfinance(미국 데이터)를 결합하여 매일 세 종류의 리포트를 자동 발송한다. 한국·미국 거래소 휴장 인지 및 미국 서머타임(DST) 자동 반영을 포함한다.

---

## 핵심 책임 흐름

```
cron 트리거 (GitHub Actions)
      │
      ▼
진입점 스크립트 (daily_kr.py / daily_us.py / weekly.py)
      │
      ├─[DST 게이트, US만]─ MARKET_SCHEDULE vs is_us_in_dst() 불일치 → sys.exit(0)
      │
      ├─[휴장 게이트]──────  calendar_utils.is_kr/us_trading_day()
      │                       휴장 시 "[KR/US] 오늘은 휴장입니다" 발송 후 종료
      │
      ├─[데이터 수집]──────  fetchers/naver_kr.py  (네이버 모바일/데스크탑)
      │                       fetchers/us_market.py (yfinance)
      │
      ├─[포맷]─────────────  formatter.py
      │                       format_kr_daily / format_us_daily / format_weekly
      │
      └─[발송]─────────────  telegram_push.send()
                              MARKET_FLOW_DRY_RUN=1 → stdout만 출력 (HTTP 미호출)
```

---

## 패키지 경계

| 디렉터리 | 역할 |
|---|---|
| `market_flow/` | 메인 Python 패키지. 진입점·캘린더·포맷·알림 전부 포함 |
| `market_flow/fetchers/` | 외부 데이터 소스 어댑터 (네이버, yfinance) |
| `tests/` | 단위 테스트 46개. 전부 mock 기반, 네트워크 없음 |
| `.github/workflows/` | cron 자동화 + CI 매트릭스 (4개 워크플로우) |

---

## 아키텍처 패턴

| 항목 | 내용 |
|---|---|
| 구조 | 단일 Python 패키지 (`market_flow/`) |
| 진입점 | 세 개의 독립 스크립트 (`daily_kr.py`, `daily_us.py`, `weekly.py`) |
| 상태 | 완전 무상태. 수집 결과를 디스크·DB에 저장하지 않음 |
| 배포 | GitHub Actions cron (코드 저장소 == 실행 환경) |
| DST 처리 | dual-cron + 환경변수 게이트 (`MARKET_SCHEDULE`) |

---

## 외부 의존성

| 라이브러리 | 버전 | 용도 |
|---|---|---|
| `yfinance` | `>=0.2.40` | 미국 시장 데이터 (지수·섹터·ETF·매크로) |
| `pandas` | `>=2.0` | yfinance 의존, 시계열 데이터 처리 |
| `python-dotenv` | `>=1.0` | 로컬 `.env` 파일 로딩 |
| `pandas_market_calendars` | `>=4.4` | NYSE 거래일 판정 (SPEC-MF-SCHED-001) |
| `exchange_calendars` | `>=4.5` | XKRX 거래일 판정 (SPEC-MF-SCHED-001) |

표준 라이브러리: `zoneinfo`, `datetime`, `sys`, `os`, `urllib`, `json`, `re`, `pathlib`

---

## 운영 시각 체계

| 워크플로우 | cron (UTC) | 한국 시각 | 게이트 |
|---|---|---|---|
| `flow-kr.yml` | `10 9 * * 1-5` | 평일 KST 18:10 | XKRX 휴장 인지 |
| `flow-us.yml` EDT | `30 20 * * 1-5` | 익일 KST 05:30 | DST 게이트 + NYSE 휴장 인지 |
| `flow-us.yml` EST | `30 21 * * 1-5` | 익일 KST 06:30 | DST 게이트 + NYSE 휴장 인지 |
| `flow-weekly.yml` | `30 9 * * 1-5` | 평일 KST 18:30 | 마지막 KR 거래일 게이트 |

---

## 출처

- `market_flow/README.md` (패키지 상세 문서, 1순위 참조)
- `.moai/project/product.md` (목적·핵심 기능·비목표)
- `.moai/project/tech.md` §1 (기술 스택), §3 (운영 환경), §4 (환경변수)
- SPEC-MF-SCHED-001 (DST 자동 반영 + 휴장 인지)
