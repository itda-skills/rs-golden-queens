# rs-golden-queens

한국장·미국장 마감 후 텔레그램 채널로 매매동향 요약을 자동 푸시하는 개인 투자 데이터 보조 봇.
GitHub Actions가 정해진 시각에 트리거하며, 수집 데이터는 저장하지 않고 텔레그램으로만 즉시 발송한다.

- 사실 데이터만 제공 — 투자 권유·종목 추천·시점 판단 없음
- DST 자동 반영 — 미국 서머타임 전환 시 발송 시각 자동 조정
- 휴장 인지 — KR/US 비거래일에 "[KR/US] 오늘은 휴장입니다" 한 줄 발송

## 푸시 스케줄

| 워크플로우 | 시각 (KST) | 요일 | 내용 |
|---|---|---|---|
| `flow-kr` | 18:10 | 월~금 | 코스피·코스닥 외인·기관·개인 + 프로그램매매 + 10거래일 추이 |
| `flow-us` | NYSE 마감 +30분 (EDT: 06:30, EST: 07:30) | 화~토 | 지수·변동성·섹터·워치ETF·매크로 |
| `flow-weekly` | 18:30 | 그 주 마지막 KR 거래일 | 코스피 5거래일 누적 + 워치ETF 5거래일 등락 |

### 휴장 처리

- **한국 휴장일**: `daily_kr.py`가 XKRX 캘린더를 조회하여 "[KR] 오늘은 휴장입니다" 한 줄 발송
- **미국 휴장일**: `daily_us.py`가 NYSE 캘린더를 조회하여 "[US] 오늘은 휴장입니다" 한 줄 발송
- **주간 이월 발송**: 금요일이 KR 휴장이면 그 주 마지막 거래일(목/수/...)에 자동 이월 발송

## 폴더 구조

```
rs-golden-queens/
├── README.md
├── Makefile                          # 운영 타겟
├── market_flow/                      # 메인 패키지
│   ├── __init__.py
│   ├── README.md                     # 패키지 상세 문서
│   ├── requirements.txt              # yfinance, pandas, python-dotenv, pandas_market_calendars, exchange_calendars
│   ├── .env.example                  # 로컬 환경변수 템플릿
│   ├── daily_kr.py                   # 한국장 매매동향 진입점
│   ├── daily_us.py                   # 미국장 마감 요약 진입점
│   ├── weekly.py                     # 주간 리포트 진입점
│   ├── calendar_utils.py             # DST/거래일/마지막 거래일 판정 (SPEC-MF-SCHED-001)
│   ├── formatter.py                  # 색 컨벤션 (🔴▲ 상승 / 🔵▼ 하락)
│   ├── telegram_push.py              # Telegram sendMessage + DRY_RUN 분기
│   └── fetchers/
│       ├── __init__.py
│       ├── naver_kr.py               # 네이버 모바일/데스크탑 데이터
│       └── us_market.py              # yfinance WATCH ETF
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_calendar_utils.py        # 26 tests
│   ├── test_daily_kr.py              # 5 tests
│   ├── test_daily_us.py              # 10 tests
│   └── test_weekly.py               # 5 tests
└── .github/workflows/
    ├── flow-kr.yml                   # 평일 KST 18:10
    ├── flow-us.yml                   # dual-cron DST 자동 반영
    ├── flow-weekly.yml               # 월~금 KST 18:30, 마지막 거래일 게이트
    └── test.yml                      # Linux × Python 3.10/3.11/3.12
```

## 데이터 소스

| 항목 | 소스 | 단위 |
|---|---|---|
| 한국 코스피/코스닥 매매동향 (외인·기관·개인) | 네이버 모바일/데스크탑 | 억원 |
| 프로그램매매 (차익/비차익) | 네이버 모바일 API | 억원 |
| 10거래일 추이 (코스피) | 네이버 데스크탑 | 억원 |
| 미국장 지수·변동성·섹터·워치ETF·매크로 | yfinance | USD/% |
| 한국 거래일 판정 | `exchange_calendars` (XKRX) | — |
| 미국 거래일 판정 | `pandas_market_calendars` (NYSE) | — |

## 설치 & 운영

### GitHub Secrets 등록

저장소 Settings → Secrets and variables → Actions에 다음 두 값을 등록한다.

| Secret 이름 | 의미 |
|---|---|
| `GOLDENQUEENS_BOT_TOKEN` | BotFather에서 발급받은 봇 토큰 |
| `GOLDENQUEENS_CHAT_ID` | 수신 chat_id (채널은 `-100` 으로 시작) |

둘 다 있어야 텔레그램 발송이 활성화된다. 하나라도 없으면 보고서를 stdout만 출력하고 정상 종료.

```bash
# chat_id 확인
curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool
# result[].message.chat.id 또는 채널/그룹의 음수 ID
```

### 로컬 개발

```bash
# 가상환경
python -m venv .venv && source .venv/bin/activate

# 의존성 설치
pip install -r market_flow/requirements.txt

# 환경변수
cp market_flow/.env.example market_flow/.env
# .env에 실제 토큰/chat_id 기입

# Makefile 타겟
make daily-kr              # 한국장 (오늘)
make daily-kr DATE=20260522
make daily-us              # 미국장
make daily-kr DRY=1        # dry-run (텔레그램 발송 없이 stdout)
make smoke-kr              # 네이버 fetch 단독 점검
make smoke-us              # yfinance fetch 단독 점검
make notify-test           # 텔레그램 핑
```

### 수동 실행

GitHub 저장소 Actions 탭 → 원하는 workflow → "Run workflow".

## 워치 ETF 수정

`market_flow/fetchers/us_market.py`의 `WATCH` 리스트와 `market_flow/formatter.py`의 `WATCH` 리스트를 동시에 수정한다.

```python
WATCH = [
    ("QQQ", "나스닥100"),
    ("SMH", "반도체"),
    # ("HUMN", "휴머노이드"),  ← 추가하려면 양쪽 파일 모두 수정
]
```

## 휴장일 & DST 정책 (SPEC-MF-SCHED-001)

### 한국 휴장 (XKRX)

`daily_kr.py`와 `weekly.py`가 `exchange_calendars` 라이브러리의 XKRX 캘린더를 참조한다.

- 거래일: 정상 발송
- 비거래일: "[KR] 오늘은 휴장입니다" 한 줄 발송

### 미국 휴장 (NYSE) + DST 자동 반영

`flow-us.yml`은 dual-cron 구조를 사용한다.

- EDT 시즌 (3월 둘째 일요일 ~ 11월 첫째 일요일): `cron '30 20 * * 1-5'` (UTC 20:30 = KST 익일 05:30)
- EST 시즌 (11월 첫째 일요일 ~ 3월 둘째 일요일): `cron '30 21 * * 1-5'` (UTC 21:30 = KST 익일 06:30)

두 cron이 모두 트리거되지만, `MARKET_SCHEDULE` 환경변수(값: `edt` 또는 `est`)와 실제 DST 시즌이 불일치하면 `daily_us.py`가 즉시 종료한다. 결과적으로 한 시즌에 한 번만 발송.

### 주간 이월 발송

`flow-weekly.yml`은 월~금 KST 18:30마다 트리거되지만, `weekly.py`의 `is_last_kr_trading_day_of_week()` 게이트를 통과한 날에만 발송한다. 금요일이 KR 휴장이면 그 주 마지막 거래일로 자동 이월된다.

## 메시지 컨벤션

- **색**: 🔴▲ 상승 / 🔵▼ 하락 / ⚪– 보합 (한국 증시 컨벤션)
- **단위**: 한국장 = 억원, 미국장 = USD / %
- **형식**: Telegram Markdown 파싱

## 면책

본 서비스는 사실 데이터만 제공한다. 투자 권유·종목 추천·시점 판단이 아니며, 데이터 정확성·완전성·시의성을 보장하지 않는다. 투자 결정 전 공식 출처를 반드시 확인할 것.

## 라이선스

내부용 — 외부 배포 금지.
