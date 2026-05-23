# rs-golden-queens

네이버 금융 공개 페이지에서 한국 주식 시장의 **투자자 매매동향**(개인·외국인·기관)과
**외국인·기관 종목별 매매 랭킹**을 수집하여 텔레그램으로 알림 전송하는 자동화 저장소.

- 매일 KST 18:10 자동 실행 (시간외 거래 18:00 종료 직후)
- 수집 데이터는 저장하지 않음 — 텔레그램 메시지로만 즉시 발송
- 외부 API 키·종속성 0 (stdlib만, `requirements.txt` 없음)
- 사실 데이터만 — 투자 권유·종목 추천 없음

## 동작 개요

1회 실행에 9개 페이지를 페치한다.

| 페이지 | 의미 | 단위 |
|---|---|---|
| `investorDealTrendDay.naver?bizdate=YYYYMMDD` | 최근 10영업일 시장 매매동향 (개인·외국인·기관계 + 기관 6개 분류 + 기타외인) | 억원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=buy` | KOSPI 외국인 순매수 상위 | 백만원 |
| `... sosok=01 ... 9000 ... sell` | KOSPI 외국인 순매도 상위 | 백만원 |
| `... sosok=01 ... 1000 ... buy` | KOSPI 기관 순매수 상위 | 백만원 |
| `... sosok=01 ... 1000 ... sell` | KOSPI 기관 순매도 상위 | 백만원 |
| `... sosok=02 ... 9000 ... buy/sell` | KOSDAQ 외국인 순매수/매도 | 백만원 |
| `... sosok=02 ... 1000 ... buy/sell` | KOSDAQ 기관 순매수/매도 | 백만원 |

응답은 `EUC-KR`로 인코딩되어 있고, iframe 구조에 의존한다. 실제 브라우저처럼 보이도록
`Windows Chrome User-Agent`·`Accept`·`Accept-Language: ko-KR`·iframe 부모 페이지 `Referer`를
포함시킨다.

## 사용법

### 자동 실행 (GitHub Actions)

`.github/workflows/daily.yml`이 매일 KST 18:10에 자동 실행된다.
저장소 Settings → Secrets and variables → Actions에 다음 두 값을 등록하면 텔레그램 발송이 활성화된다.

| Secret 이름 | 의미 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 발급받은 봇 토큰 (예: `1234567890:ABC-DEF...`) |
| `TELEGRAM_CHAT_ID` | 메시지를 받을 chat ID (개인·그룹·채널 모두 가능) |

둘 중 하나라도 비어 있으면 보고서는 GitHub Actions 로그에만 남고 텔레그램은 호출되지 않는다.

수동 실행: 저장소 Actions 탭 → "Daily collect" → "Run workflow".

### 로컬 실행

`Makefile`이 자주 쓰는 명령을 래핑한다.

```bash
git clone git@github.com:itda-skills/rs-golden-queens.git
cd rs-golden-queens

make              # 사용 가능한 명령 목록
make test         # 단위 테스트 (mock + fixture, 네트워크 없음)
make test-live    # 라이브 호출 포함 전체 테스트
make collect      # 9콜 통합 수집 (cron 진입점과 동일)
make flow         # flow_day 단독 조회
make rank MARKET=kospi INVESTOR=foreign SIDE=buy   # 종목 랭킹 단독
make notify-test  # 텔레그램 헬로 메시지 (환경변수 동작 확인)
make smoke-headers # HTTP 헤더(UA·Referer·Accept) 라이브 점검
make clean        # __pycache__·캐시 제거
make version      # 패키지 버전
```

또는 Make 없이 직접:

# 1) 통합 수집 (9콜 + 마크다운 보고서 출력)
python3 -m naver_investor_flow.collect

# 2) 텔레그램까지 보내려면 환경변수 주입
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 -m naver_investor_flow.collect

# 3) 개별 조회 — CLI (단일 페이지만 보고 싶을 때)
python3 -m naver_investor_flow flow_day
python3 -m naver_investor_flow flow_day --bizdate 20260520 --format table
python3 -m naver_investor_flow deal_rank --market kospi --investor foreign --side buy
python3 -m naver_investor_flow deal_rank --market kosdaq --investor institution --side sell --limit 5
```

CLI 옵션:

- `flow_day` — 일별 시장 매매동향 (단위: 억원)
  - `--bizdate YYYYMMDD` (선택): 기준일. 미지정 시 오늘 자동 주입. 비영업일 입력 시 직전 영업일 데이터로 자동 보정 (네이버 동작)
  - `--limit N` (선택, 1~10): 출력 행 수 제한
- `deal_rank` — 종목별 외국인/기관 매매 랭킹 (단위: 백만원)
  - `--market {kospi|kosdaq}` (필수)
  - `--investor {foreign|institution}` (필수)
  - `--side {buy|sell}` (필수)
  - `--limit N` (선택, 1~30)
- 공통: `--format {json|table|csv}` (기본 `json`)

### 텔레그램 봇 준비

1. Telegram에서 [@BotFather](https://t.me/BotFather)에 `/newbot` 발급 요청 → `TELEGRAM_BOT_TOKEN` 획득
2. 봇과 1:1 대화 시작 (또는 그룹/채널에 봇을 admin으로 초대)
3. chat ID 조회:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool
   ```
   `result[].message.chat.id` 또는 그룹 채팅의 음수 ID가 `TELEGRAM_CHAT_ID`
4. GitHub 저장소 Settings → Secrets에 두 값 등록

## 출력 예시

```
📊 네이버 투자자 매매동향 — 기준일 20260523 (KST)
수집 시각: 2026-05-23T18:10:01+09:00

▎일별 시장 매매 (억원, 부호=순매수)
  2026-05-22  개인 +10,655 / 외국인 -19,221 / 기관계 +7,583
  2026-05-21  개인 -26,754 / 외국인 -2,212 / 기관계 +29,008
  ...

▎KOSPI 외국인 매수 TOP3 (백만원)
  1. 삼성전자 (005930)  +1,095,426
  2. 현대차 (005380)  +77,272
  3. 삼성전기 (009150)  +47,198

... (8조합 각 TOP3)

─────────
출처: finance.naver.com (사실 데이터, 투자 권유 아님)
```

## 디렉토리 구조

```
rs-golden-queens/
├── README.md
├── .github/workflows/
│   ├── daily.yml          # cron `10 9 * * *` UTC (KST 18:10) + workflow_dispatch
│   └── test.yml           # push/PR · 3 OS × 3 Python 버전 매트릭스
├── naver_investor_flow/
│   ├── __init__.py
│   ├── __main__.py        # `python -m naver_investor_flow ...` 진입점
│   ├── cli.py             # 개별 조회 CLI (argparse)
│   ├── collect.py         # 9콜 통합 수집 + 텔레그램 알림 진입점
│   ├── http_client.py     # urllib + EUC-KR + UA/Referer/Accept
│   ├── parser_flow.py     # flow_day HTML 파서 (html.parser)
│   ├── parser_rank.py     # deal_rank HTML 파서
│   ├── formatter.py       # json/table/csv + 디스클레이머
│   └── notify_telegram.py # Telegram sendMessage (stdlib urllib)
└── tests/
    ├── conftest.py
    ├── fixtures/          # 라이브 캡처 HTML (EUC-KR)
    ├── test_cli.py
    ├── test_collect.py
    ├── test_formatter.py
    ├── test_http_client.py
    ├── test_live_smoke.py # 라이브 호출 — 로컬 검증용
    ├── test_notify_telegram.py
    ├── test_parser_flow.py
    └── test_parser_rank.py
```

## 테스트

```bash
# mock + fixture (네트워크 없음)
python3 -m pytest tests/ -q --ignore=tests/test_live_smoke.py

# 라이브 포함 (네이버 금융 직접 호출)
python3 -m pytest tests/ -q
```

## 면책

본 저장소는 네이버 금융의 공개 페이지를 정중하게 페치한다. 호출 빈도는 일 1회.
수집 데이터는 사실 자료이며 투자 권유·종목 추천·시점 판단이 아니다. 데이터 정확성·완전성·시의성을
보장하지 않으며, 투자 결정 전 공식 출처를 확인할 것.
