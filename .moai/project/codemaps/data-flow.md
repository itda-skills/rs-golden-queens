# 데이터 흐름 — rs-golden-queens

시스템을 통과하는 데이터의 변환 단계를 두 실행 경로(A, B)와 에러 흐름으로 분리하여 서술한다.

---

## 경로 A — 단발 CLI 조회 (`flow_day`)

사용자가 `python -m naver_investor_flow flow_day` 또는 `make flow`를 호출하는 경우.

### 단계별 변환

```
1. 사용자 입력 (argparse)
   └─ --bizdate YYYYMMDD  (선택)
   └─ --format json|table|csv  (기본: json)
   └─ --limit N  (선택)

2. URL 조립 — cli._build_flow_url(bizdate)
   └─ bizdate 미지정 시: datetime.date.today() (KST) → YYYYMMDD 자동 주입
   └─ 출력: "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=YYYYMMDD&sosok="

3. HTTP 호출 — http_client.fetch_html(url, referer=REFERER_FLOW)
   └─ urllib.request.urlopen (GET)
   └─ 헤더: User-Agent (Windows Chrome), Accept, Accept-Language, Referer
   └─ 응답: raw bytes (EUC-KR 인코딩)
   └─ decode_response: EUC-KR → str (UTF-8 fallback)
   └─ 출력: HTML str (약 7.8KB)

4. 파싱 — parser_flow.parse_flow_day(html)
   └─ _FlowDayParser (HTMLParser 서브클래스 상태 기계)
   └─ summary='순매수에 관한 표' 또는 class='type_1' 테이블 탐지
   └─ 11컬럼 td 추출 (날짜 + 개인/외국인/기관 수치)
   └─ _date_to_iso: "YY.MM.DD" → "YYYY-MM-DD"
   └─ _parse_int: 콤마 제거 → int (억원 단위)
   └─ 출력: list[dict] (최대 10행, 억원 단위)

   반환 dict 예시:
   {
     "date": "2026-05-22",
     "individual_eok": -1234,
     "foreign_eok": +567,
     "institution_total_eok": +890,
     "institution_breakdown": {
       "financial_inv": 100, "insurance": 50, "trust": 200,
       "bank": 30, "other_finance": 80, "pension": 430
     },
     "foreign_etc_eok": -12
   }

5. 포맷 변환 — formatter.format_output(mode="flow_day", data, meta, fmt, limit)
   └─ json: _build_flow_day_envelope → JSON 직렬화
   └─ table: _format_table_flow → 고정폭 텍스트 표
   └─ csv: _format_csv_flow → RFC 4180 CSV
   └─ 모든 포맷 말미에 DISCLAIMER 첨부
   └─ flow_day JSON 최상위 필드: { mode, unit: "억원", meta, data }
      [HARD] unit_amount / unit_quantity 필드 없음

6. stdout 출력 → sys.exit(0)
```

---

## 경로 A' — 단발 CLI 조회 (`deal_rank` 변형)

`python -m naver_investor_flow deal_rank --market kospi --investor foreign --side buy` 등.

단계 1~6은 `flow_day`와 동일 구조. 변형 사항만 기술한다.

```
1. 사용자 입력 (argparse)
   └─ --market kospi|kosdaq  (필수)
   └─ --investor foreign|institution  (필수)
   └─ --side buy|sell  (필수)
   └─ --format, --limit  (선택)
   [HARD] --bizdate 옵션 없음 (SPEC REQ-020.4: 네이버 서버가 파라미터 무시)

2. URL 조립 — cli._build_rank_url(market, investor, side)
   └─ MARKET_MAP: {"kospi": "01", "kosdaq": "02"}
   └─ INVESTOR_MAP: {"foreign": "9000", "institution": "1000"}
   └─ 출력 예: "https://finance.naver.com/sise/sise_deal_rank_iframe.naver
               ?sosok=01&investor_gubun=9000&type=buy"

3. HTTP 호출 — http_client.fetch_html(url, referer=REFERER_RANK)
   └─ REFERER_RANK: "https://finance.naver.com/sise/sise_deal_rank.naver"
   └─ 응답: raw bytes (EUC-KR)
   └─ decode_response → str

4. 파싱 — parser_rank.parse_deal_rank(html)
   └─ _RankParser (HTMLParser 서브클래스, table 중첩 깊이 추적)
   └─ summary='순매수' 또는 '순매도' 테이블 탐지
   └─ 4컬럼 td 추출 (종목명 a태그 + 수량 + 금액 + 거래량)
   └─ _extract_code: href="...code=NNNNNN..." 정규식 → 6자리 종목코드
   └─ 종목코드 0-padding 유지 (예: "005930")
   └─ 출력: list[dict] (최대 30행, 백만원 단위)

   반환 dict 예시:
   {
     "rank": 1,
     "name": "삼성전자",
     "code": "005930",
     "quantity": 3672,        # 주
     "amount_mn_krw": 1095426, # 백만원
     "volume": 36168689        # 주
   }

5. 포맷 변환 — formatter.format_output(mode="deal_rank", ...)
   └─ deal_rank JSON 최상위 필드: { mode, unit_amount: "백만원", unit_quantity: "주", meta, data }
      [HARD] unit 필드 없음 (flow_day와 스키마 의도적 차별화)
```

**8조합 병렬 개념:**
`collect.py`는 8조합을 순차적으로 실행하지만, CLI에서는 단일 조합만 호출한다.
8조합 전체를 한 번에 수집하려면 `collect.py` 경로(경로 B)를 사용해야 한다.

---

## 경로 B — cron 자동 보고 (`collect.main()`)

GitHub Actions `daily.yml`이 UTC 09:10에 트리거하는 통합 수집 경로.

```
1. cron 트리거 (UTC 09:10 = KST 18:10)
   └─ GitHub Actions runner (ubuntu-latest, Python 3.11)
   └─ 환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (GitHub Secrets)

2. KST 현재 시각 산정
   └─ datetime.timezone(timedelta(hours=9))
   └─ _kst_today() → YYYYMMDD (bizdate로 사용)
   └─ fetched_at → ISO 8601 KST 문자열

3. flow_day 수집 (1회)
   └─ collect.fetch_flow_day(bizdate)
   └─ → http_client.fetch_html(url, referer=REFERER_FLOW)
   └─ → parser_flow.parse_flow_day(html) → list[dict]
   실패 시: flow_rows=[], stderr에 traceback 출력 후 계속 진행

4. deal_rank 수집 (8조합 순차)
   └─ DEAL_RANK_COMBOS 순서:
       (kospi, foreign, buy), (kospi, foreign, sell),
       (kospi, institution, buy), (kospi, institution, sell),
       (kosdaq, foreign, buy), (kosdaq, foreign, sell),
       (kosdaq, institution, buy), (kosdaq, institution, sell)
   └─ 각 조합: collect.fetch_deal_rank(market, investor, side)
   └─ → http_client.fetch_html(url, referer=REFERER_RANK)
   └─ → parser_rank.parse_deal_rank(html) → list[dict]
   실패 시: rows=[], stderr에 traceback 출력 후 다음 조합 계속

5. 마크다운 보고서 빌드 — collect.build_report(flow_rows, rank_results, bizdate, fetched_at)
   └─ 헤더: "📊 네이버 투자자 매매동향 — 기준일 YYYYMMDD (KST)"
   └─ flow_day: 최대 5행 (날짜 + 개인/외국인/기관계 억원)
   └─ deal_rank: 8조합 각 TOP3 (종목명·코드·금액 백만원)
   └─ 말미: "출처: finance.naver.com (사실 데이터, 투자 권유 아님)"
   └─ 출력: str (마크다운 텍스트)
   [주의] collect.build_report는 formatter.py를 사용하지 않음 (자체 마크다운 생성)

6. stdout 출력 (Actions 로그)
   └─ print(report)

7. 텔레그램 전송 — notify_telegram.send_message(report, config=cfg)
   └─ TelegramConfig.from_env(): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 읽기
   └─ cfg.enabled == False → stdout만 출력, 정상 종료 (exit 0)
   └─ cfg.enabled == True:
      └─ truncate_for_telegram(text): 4096자 초과 시 "\n…(잘림)" 추가 후 자름
      └─ urllib.parse.urlencode → POST 페이로드
      └─ urllib.request.urlopen (POST, 10초 타임아웃)
      └─ 응답 JSON 파싱 → ok 필드 확인
      └─ 성공: True 반환, 실패: False + stderr 출력

8. exit code 결정
   └─ flow_rows==[] AND 모든 deal_rank rows==[] → exit 1 (전체 실패)
   └─ 그 외 → exit 0 (텔레그램 전송 실패 포함)
```

---

## 에러 흐름

### CLI (`cli.py`) exit code

| 예외 클래스 | exit code | 원인 |
|---|---|---|
| `HttpError` | 2 | HTTP 4xx/5xx 응답 |
| 파싱 예외 (`Exception`) | 3 | HTML 테이블 구조 불일치 등 |
| `NetworkError` | 4 | 연결 실패·타임아웃 |
| `EncodingError` | 5 | EUC-KR·UTF-8 모두 디코딩 실패 |
| argparse 오류 | 64 | 필수 인자 누락·잘못된 값 |

에러 발생 시 JSON 형태로 stdout에 출력:
```json
{"status": "http_error", "code": 404, "url": "https://..."}
{"status": "parse_error", "stage": "flow_day", "detail": "..."}
{"status": "network_error", "detail": "..."}
{"status": "encoding_error", "detail": "..."}
```

### cron (`collect.py`) 에러 처리 전략

`collect.py`는 개별 호출 실패를 무시하고 계속 진행하는 best-effort 전략을 사용한다.

```
flow_day 실패  → flow_rows = []  + traceback → stderr
deal_rank 실패 → rows = []       + traceback → stderr (해당 조합만)
보고서 빌드   → 성공한 데이터만 포함 (빈 섹션: "(데이터 없음)" 표시)
텔레그램 실패 → stderr 출력, exit code 0 유지
전체 실패     → exit code 1 (flow_rows==[] AND 모든 deal_rank 빈 경우)
```

---

## 시간대 처리

모든 시각은 KST(UTC+9), ISO 8601, `datetime.timezone(timedelta(hours=9))`로 생성한다.

| 함수 | 위치 | 출력 형식 |
|---|---|---|
| `collect._kst_today()` | `collect.py` | `"YYYYMMDD"` (URL 파라미터용) |
| `collect.main()` → `fetched_at` | `collect.py` | `"YYYY-MM-DDTHH:MM:SS+09:00"` |
| `formatter._now_kst()` | `formatter.py` | `"YYYY-MM-DDTHH:MM:SS+09:00"` (meta.fetched_at 기본값) |
| `cli._build_flow_url()` | `cli.py` | `datetime.date.today().strftime("%Y%m%d")` |

**주의:** `cli._build_flow_url()`은 `datetime.date.today()`를 사용한다. GitHub Actions runner 시간대가 UTC이므로, runner에서 `today()`를 호출하면 UTC 기준 날짜가 된다. 실제 cron 경로(`collect.py`)는 `_kst_today()`로 KST 날짜를 명시적으로 산정한다.

---

## 단위 스키마 비대칭 (의도적 설계)

| 경로 | 단위 | JSON 필드 |
|---|---|---|
| `flow_day` (경로 A) | **억원** (100,000,000 KRW) | `unit: "억원"` |
| `deal_rank` (경로 A') | **백만원** (1,000,000 KRW) | `unit_amount: "백만원"`, `unit_quantity: "주"` |

[HARD] 두 단위를 통일하지 않는다. 100배 차이로 사용자 의사결정 오류 방지가 일관성 미감보다 우선한다. `test_formatter.py`가 negative assertion으로 강제한다.

---

## 출처

- `naver_investor_flow/cli.py` — `_build_flow_url`, `_handle_flow_day`, `_handle_deal_rank` 직접 확인
- `naver_investor_flow/collect.py` — `main`, `fetch_flow_day`, `fetch_deal_rank`, `build_report` 직접 확인
- `naver_investor_flow/http_client.py` — `fetch`, `decode_response`, `fetch_html` 직접 확인
- `naver_investor_flow/parser_flow.py` — `_FlowDayParser._build_row` 직접 확인
- `naver_investor_flow/parser_rank.py` — `_RankParser._build_row`, `_extract_code` 직접 확인
- `naver_investor_flow/formatter.py` — 엔벨로프 구조 직접 확인
- `naver_investor_flow/notify_telegram.py` — `send_message`, `truncate_for_telegram` 직접 확인
- `HANDOFF.md` §3.1 (bizdate 필수), §3.2 (deal_rank bizdate 무시), §3.5 (단위 차별화)
- `.moai/project/tech.md` §3 (외부 통합), §8 (에러 코드), §4 (단위 의도적 차별화)
