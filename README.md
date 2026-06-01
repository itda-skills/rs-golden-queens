# rs-golden-queens

한국장·미국장 마감 후 텔레그램 채널로 매매동향 요약을 자동 푸시하는 개인 투자 데이터 보조 봇.
Cloudflare cron-worker(`cron-worker/`)가 GitHub Actions `flow-*` 워크플로우를 정시에 `workflow_dispatch`로 호출한다.
수집 데이터는 저장하지 않고 텔레그램으로만 즉시 발송한다.

- 사실 데이터만 제공 — 투자 권유·종목 추천·시점 판단 없음
- DST 자동 반영 — 미국 서머타임 전환 시 발송 시각 자동 조정
- 휴장 인지 — KR/US 비거래일에 "[KR/US] 오늘은 휴장입니다" 한 줄 발송

## 푸시 스케줄

아래 시각은 `cron-worker`의 cron 설정 기준이다. 저장소의 GitHub Actions에는 cron을 두지 않는다.

| 워크플로우 | 시각 (KST) | 요일 | 내용 |
|---|---|---|---|
| `flow-kr` | 18:10 | 월~금 | 코스피·코스닥 외인·기관·개인 + 프로그램매매 + 10거래일 추이 |
| `flow-us` | 07:00 | 화~토 | 지수·변동성·섹터·워치ETF·매크로 |
| `flow-weekly` | 18:15 | 그 주 마지막 KR 거래일 | 코스피·코스닥 5거래일 누적 + 워치ETF 5거래일 등락 |

### 휴장 처리

- **한국 휴장일**: `daily_kr.py`가 XKRX 캘린더를 조회하여 "[KR] 오늘은 휴장입니다" 한 줄 발송
- **미국 휴장일**: `daily_us.py`가 NYSE 캘린더를 조회하여 "[US] 오늘은 휴장입니다" 한 줄 발송
- **주간 이월 발송**: 금요일이 KR 휴장이면 그 주 마지막 거래일(목/수/...)에 자동 이월 발송

## 폴더 구조

```
rs-golden-queens/
├── README.md
├── Makefile                          # 운영 타겟
├── requirements.txt                   # Python 의존성
├── main.py                            # CLI 진입점
├── market_flow/                      # 메인 패키지
│   ├── __init__.py
│   ├── README.md                     # 패키지 상세 문서
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
├── tests/                            # pytest (unit/integration/live)
└── .github/workflows/
    ├── flow-kr.yml                   # cron-worker dispatch 대상
    ├── flow-kr-test.yml              # TEST_GOLDENQUEENS_* 한국장 테스트 푸시
    ├── flow-us.yml                   # cron-worker dispatch 대상
    ├── flow-us-test.yml              # TEST_GOLDENQUEENS_* 미국장 테스트 푸시
    ├── flow-weekly.yml               # cron-worker dispatch 대상, 마지막 거래일 게이트
    ├── flow-weekly-test.yml          # TEST_GOLDENQUEENS_* 주간 테스트 푸시
    ├── flow-telegram-test.yml        # TEST_GOLDENQUEENS_* 테스트 핑
    └── test.yml                      # CI 테스트
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

저장소 Settings → Secrets and variables → Actions에 다음 값을 등록한다.

| Secret 이름 | 의미 |
|---|---|
| `GOLDENQUEENS_BOT_TOKEN` | BotFather에서 발급받은 봇 토큰 |
| `GOLDENQUEENS_CHAT_ID` | 수신 chat_id (채널은 `-100` 으로 시작) |
| `TEST_GOLDENQUEENS_BOT_TOKEN` | `--test` 발송에 사용할 테스트 봇 토큰 |
| `TEST_GOLDENQUEENS_CHAT_ID` | `--test` 발송에 사용할 테스트 수신 chat_id |

운영 발송은 `GOLDENQUEENS_*` 둘 다 있어야 활성화된다. `--test` 발송은 `TEST_GOLDENQUEENS_*` 둘 다 있어야 활성화된다.

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
make notify-test TEST=1    # 테스트 봇/채널로 실제 핑 전송
make smoke-kr              # KR 데이터 소스 단독 점검 (네이버 + KIS)
make smoke-us              # yfinance fetch 단독 점검
make notify-test           # 텔레그램 핑
```

### 수동 실행

정시 발사는 `cron-worker`가 GitHub API로 각 workflow의 `workflow_dispatch`를 호출한다(로컬 수동 발사는 `make cron-trigger WF=...`).
수동 실행은 GitHub 저장소 Actions 탭 → 원하는 workflow → "Run workflow".
테스트 봇/채널로 핑을 보내려면 `텔레그램 테스트 전송` workflow를 수동 실행한다.

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

### 미국 휴장 (NYSE) + DST

`flow-us.yml`은 `workflow_dispatch`만 제공하고, 정시 호출은 `cron-worker`가 담당한다.
`daily_us.py`는 NYSE 캘린더로 휴장 여부를 판정한다. `MARKET_SCHEDULE=edt|est`가 주입된 경우에는 실제 DST 시즌과 대조해 불일치 실행을 스킵한다.

### 주간 이월 발송

`cron-worker`가 `flow-weekly.yml`을 월~금 KST 18:15에 호출하고, `weekly.py`의 `is_last_kr_trading_day_of_week()` 게이트를 통과한 날에만 발송한다. 금요일이 KR 휴장이면 그 주 마지막 거래일로 자동 이월된다.

## 메시지 컨벤션

- **색**: 🔴▲ 상승 / 🔵▼ 하락 / ⚪– 보합 (한국 증시 컨벤션)
- **단위**: 한국장 = 억원, 미국장 = USD / %
- **형식**: Telegram Markdown 파싱

## 면책

본 서비스는 사실 데이터만 제공한다. 투자 권유·종목 추천·시점 판단이 아니며, 데이터 정확성·완전성·시의성을 보장하지 않는다. 투자 결정 전 공식 출처를 반드시 확인할 것.

## 라이선스

내부용 — 외부 배포 금지.
