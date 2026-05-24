# 시스템 개요 — rs-golden-queens

## 시스템 정체성

네이버 금융 공개 페이지에서 한국 주식시장 투자자 매매동향·종목별 매매 랭킹을 매일 자동 수집하여 텔레그램으로 발송하는 **단독 자동화 서비스**.

---

## 아키텍처 패턴

| 항목 | 내용 |
|---|---|
| 구조 | 단일 Python 패키지 (`naver_investor_flow/`) |
| 진입점 | 무상태 CLI (`cli.py`) + cron 스크립트 (`collect.py`) |
| 의존성 | stdlib only — 외부 라이브러리 0건 |
| 상태 | 완전 무상태. 수집 결과를 디스크·DB에 저장하지 않음 |
| 배포 | GitHub Actions cron (코드 저장소 == 실행 환경) |

---

## 시스템 경계도

```
사용자 (KST 18:10)
      │ cron 트리거
      ▼
GitHub Actions (daily.yml)
      │ python -m naver_investor_flow.collect
      ▼
   collect.py
      │ 9회 HTTP 호출
      ├──── http_client ──────────► Naver Finance (finance.naver.com)
      │         │ raw bytes (EUC-KR)
      │         ▼
      │    decode_response
      │         │ str
      │    ┌────┴─────────────────────┐
      │    │                         │
      │    ▼                         ▼
      │ parser_flow              parser_rank
      │ (flow_day 1회)           (deal_rank 8조합)
      │    │ list[dict]              │ list[dict]
      │    └────────────┬───────────┘
      │                 ▼
      │            formatter (마크다운 보고서)
      │                 │ str
      ├────────── stdout (Actions 로그)
      │                 │
      └── notify_telegram ──────► Telegram Bot API
                                  (sendMessage POST)
```

---

## 두 가지 실행 양식

### (a) 단발 CLI 조회 — `cli.py`

사람이 직접 호출하는 단건 조회 경로.

```
python -m naver_investor_flow flow_day [--bizdate YYYYMMDD] [--format json|table|csv] [--limit N]
python -m naver_investor_flow deal_rank --market kospi|kosdaq --investor foreign|institution --side buy|sell
```

- `__main__.py`가 `cli.main()`으로 디스패치
- 결과를 stdout으로 출력하고 즉시 종료 (exit code 참조 → `entry-points.md`)

### (b) cron 자동 보고 — `collect.py`

GitHub Actions `daily.yml`이 매일 KST 18:10에 호출하는 통합 수집 경로.

```
python -m naver_investor_flow.collect
```

- flow_day 1회 + deal_rank 8조합 = 총 9회 HTTP 호출
- 마크다운 보고서 빌드 → stdout 출력 + 텔레그램 전송
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 환경변수 부재 시 stdout만 출력하고 exit 0

---

## 핵심 설계 원칙

### 1. stdlib-only

`urllib.request` · `html.parser` · `csv` · `json` · `datetime` · `re` 만 사용.
`requests`, `httpx`, `aiohttp`, `bs4`, `lxml` 도입 금지.

근거: 의존성 0 → GitHub Actions 캐시 불필요 / 보안 표면 0 / Python 3.10~3.12 모든 버전 동일 동작.

### 2. 무상태

수집 결과를 저장하지 않는다. 본 저장소는 **코드 저장 목적만**이다.
commit / Release / Pages에 데이터를 남기지 않으며, `shared/itda_path.py` 같은 외부 디렉토리 의존도 없다.

### 3. 사실 데이터만

수집·표시하는 모든 데이터는 네이버 금융 공개 페이지의 사실 자료다.
투자 권유·종목 추천·매매 신호는 제공하지 않는다. 모든 출력 말미에 SPEC-GOV-STOCK-001 P-1 동형 디스클레이머를 첨부한다.

---

## 출처

- `HANDOFF.md` §1 (출생 배경), §2 (기술 결정), §5.3 (절대 하지 말 것)
- `.moai/project/product.md` (목적·핵심 기능·비목표)
- `.moai/project/tech.md` §1 (기술 스택), §4 (설계 결정)
