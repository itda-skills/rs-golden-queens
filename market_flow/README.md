# 골든퀸즈 매매동향 봇 (rs-golden-queens)

매일 한국장·미국장 마감 후 텔레그램 채널 `골든봇초대방`으로 매매동향 요약을 자동 푸시한다. GitHub Actions가 정해진 시각에 트리거.

## 푸시 스케줄 (KST)

| 작업 | 시각 | 요일 | 내용 |
|---|---|---|---|
| `flow-kr` | 18:10 | 월~금 | 코스피·코스닥 외인·기관·개인 + 프로그램매매 + 10거래일 추이 |
| `flow-us` | 06:30 | 화~토 | 지수·변동성·섹터 11개·워치ETF·매크로 |
| `flow-weekly` | 18:30 | 금 | 코스피 5거래일 누적 + 미국 워치ETF 5거래일 등락 |

## 폴더 구조

```
rs-golden-queens/
├── README.md
├── requirements.txt
├── .env.example                  # 로컬용 환경변수 템플릿
├── .gitignore
├── fetchers/
│   ├── __init__.py
│   ├── naver_kr.py              # 한국 매매동향 (네이버 모바일+데스크탑)
│   └── us_market.py             # 미국장 (yfinance)
├── formatter.py                  # 한국식 색 컨벤션 (🔴▲ 상승 / 🔵▼ 하락)
├── telegram_push.py              # 텔레그램 발송 (env 우선)
├── daily_kr.py                   # 한국장 entry
├── daily_us.py                   # 미국장 entry
├── weekly.py                     # 주간 entry
└── .github/workflows/
    ├── flow-kr.yml
    ├── flow-us.yml
    └── flow-weekly.yml
```

## 데이터 소스

| 항목 | 코스피 | 코스닥 |
|---|---|---|
| 당일 합산 (외인·기관·개인) | 네이버 모바일 API | 네이버 모바일 API |
| 프로그램매매 (차익/비차익) | 네이버 모바일 API | 네이버 모바일 API |
| 10거래일 추이 | 네이버 데스크탑 | (미제공) |

| 미국장 | 소스 |
|---|---|
| 지수·변동성·섹터·워치ETF·매크로 | yfinance |

## 설치 & 운영

### 1. GitHub Secrets 등록 (필수)

repo Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|---|---|
| `GOLDENQUEENS_BOT_TOKEN` | BotFather에서 받은 봇 토큰 |
| `GOLDENQUEENS_CHAT_ID` | 채널 chat_id (`-100...` 음수) |

> chat_id 확인: `curl "https://api.telegram.org/bot<TOKEN>/getUpdates"` 후 채널에서 메시지 한 줄 보내고 응답의 `chat.id` 추출

### 2. 워크플로우 자동 시작

repo에 push되면 `.github/workflows/`가 자동 활성화. cron 시각에 자동 실행.

수동 실행: GitHub repo → Actions 탭 → 원하는 workflow → "Run workflow"

### 3. 로컬 개발/테스트

```bash
# 가상환경
python -m venv .venv
source .venv/bin/activate

# 의존성
pip install -r requirements.txt

# 환경변수
cp .env.example .env
# .env에 실제 토큰/chat_id 기입

# 수동 실행
python daily_kr.py            # 오늘 한국장
python daily_kr.py 20260522   # 특정일
python daily_us.py            # 최신 미국장
python daily_us.py 2026-05-22 # 특정일
python weekly.py              # 주간 리포트
```

## 메시지 컨벤션

- **색**: 🔴▲ 상승 / 🔵▼ 하락 / ⚪– 보합 (한국 증시 컨벤션)
- **단위**: 한국장 = 억원, 미국장 = USD / %
- **Markdown** 파싱

## 워치 ETF 수정

[fetchers/us_market.py](fetchers/us_market.py) 의 `WATCH` 리스트와 [formatter.py](formatter.py) 의 `WATCH` 리스트를 같이 수정.

```python
WATCH = [
    ("QQQ", "나스닥100"),
    ("SMH", "반도체"),
    # ("HUMN", "휴머노이드"),   # ← 추가하려면
    ...
]
```

## 휴장일 & 서머타임

- **한국 휴장일**: 네이버 API가 직전 거래일 데이터를 반환 → 같은 데이터가 휴장일에도 발송됨 (현재는 그대로 진행)
- **미국 서머타임 종료** (11월 첫째 일요일 이후): 미국장 마감이 한국 06:00 → flow-us cron 30분 늦추기 권장 (`30 22 * * 1-5`)

## 트러블슈팅

### "환경변수가 비어있음" 에러
- 로컬: `.env` 파일 존재 확인
- GitHub Actions: repo Secrets 에 정확한 이름으로 등록됐는지 확인

### Telegram "Bad Request: chat not found"
- chat_id 음수(`-100...`) 인지 확인. 양수면 개인 채팅 ID
- 봇이 채널/그룹에 관리자(Post Messages 권한)로 들어가 있는지 확인

### yfinance 데이터 없음
- 미국 휴장일 (Memorial Day, Thanksgiving 등) 직후엔 직전 거래일 데이터 반환
- 일부 티커는 야후가 갑자기 차단할 수 있음 → fetcher 코드에서 try/except로 None 처리됨

## 라이선스

내부용 — 외부 배포 금지.
