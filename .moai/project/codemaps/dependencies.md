# 의존성 그래프 — rs-golden-queens

---

## 외부 의존성: 0건 (stdlib-only 정책)

[HARD] `requests`, `httpx`, `aiohttp`, `bs4`, `lxml` 등 외부 라이브러리 도입 금지.
`requirements.txt` 없음. `pyproject.toml` 없음.

정책 검증 명령:
```bash
grep -rE "^(import|from) (requests|httpx|aiohttp|bs4|lxml)" naver_investor_flow/
# 기대치: 0건
```

---

## 사용 stdlib 모듈

| stdlib 모듈 | 사용 모듈 | 역할 |
|---|---|---|
| `urllib.request` | `http_client.py`, `notify_telegram.py` | HTTP GET (네이버), POST (Telegram sendMessage) |
| `urllib.error` | `http_client.py`, `notify_telegram.py` | `HTTPError`, `URLError` 예외 처리 |
| `urllib.parse` | `notify_telegram.py` | `urlencode` (Telegram 요청 파라미터 인코딩) |
| `html.parser` | `parser_flow.py`, `parser_rank.py` | `HTMLParser` 서브클래스 상태기계 파싱 |
| `csv` | `formatter.py` | CSV 출력 (RFC 4180) |
| `json` | `formatter.py`, `cli.py`, `notify_telegram.py` | JSON 출력·파싱 |
| `io` | `formatter.py` | `StringIO` (CSV 버퍼) |
| `argparse` | `cli.py` | `flow_day` / `deal_rank` 서브커맨드 CLI |
| `socket` | `http_client.py` | `socket.timeout` 예외 처리 |
| `datetime` + `timezone` + `timedelta` | `collect.py`, `formatter.py`, `cli.py` | KST(+09:00) 현재 시각 산정 |
| `re` | `parser_flow.py`, `parser_rank.py` | 날짜 패턴 변환, `code=NNNNNN` href 정규식 추출 |
| `os` | `notify_telegram.py` | 환경변수 읽기 (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) |
| `sys` | `cli.py`, `collect.py`, `notify_telegram.py` | `stderr` 출력, `exit()` |
| `traceback` | `collect.py` | 예외 스택 트레이스 출력 |

---

## 내부 모듈 의존성 그래프

```
python -m naver_investor_flow [args]
         │
         ▼
     __main__
         │ cli.main()
         ▼
        cli ─────────────┬──── http_client ──► (urllib.request, urllib.error, socket)
                         │
                         ├──── parser_flow ──► (html.parser, re)
                         │
                         ├──── parser_rank ──► (html.parser, re)
                         │
                         └──── formatter ───► (csv, io, json, datetime)


python -m naver_investor_flow.collect
         │
         ▼
      collect ──────────┬──── http_client ──► (urllib.request, urllib.error, socket)
                        │
                        ├──── parser_flow ──► (html.parser, re)
                        │
                        ├──── parser_rank ──► (html.parser, re)
                        │
                        └──── notify_telegram ──► (urllib.request, urllib.error,
                                                    urllib.parse, json, os, socket)
```

**주목할 점:**

- `cli.py`와 `collect.py`는 `http_client`, `parser_flow`, `parser_rank`를 공통으로 사용하지만 **서로 직접 의존하지 않는다**.
- `collect.py`는 `formatter.py`를 임포트하지 않는다. 보고서는 `collect.build_report()`가 자체 마크다운으로 생성한다.
- `cli.py`는 `notify_telegram.py`를 임포트하지 않는다. 텔레그램 전송은 cron 경로에서만 발생한다.
- `__main__.py`는 `cli`만 임포트하는 얇은 디스패처다.
- `parser_flow.py`와 `parser_rank.py`는 완전히 독립적이며 서로를 참조하지 않는다.

---

## 옵션 개발 의존성

| 패키지 | 용도 | 런타임 필요 여부 |
|---|---|---|
| `pytest` | 테스트 실행 전용 | 불필요 |

설치: `make install-dev` (uv 우선, fallback pip)

런타임 실행(`collect`, `cli`)에는 Python 3.10+ 외 추가 설치 없음.

---

## 외부 API 통합

### 네이버 금융 공개 페이지 9종

1회 `collect.py` 실행 시 9개 URL 호출.

| URL 패턴 | 설명 | 단위 |
|---|---|---|
| `investorDealTrendDay.naver?bizdate=YYYYMMDD&sosok=` | 최근 10영업일 시장 매매동향 | 억원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=buy` | KOSPI 외국인 순매수 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=sell` | KOSPI 외국인 순매도 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=1000&type=buy` | KOSPI 기관 순매수 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=1000&type=sell` | KOSPI 기관 순매도 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=02&investor_gubun=9000&type=buy` | KOSDAQ 외국인 순매수 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=02&investor_gubun=9000&type=sell` | KOSDAQ 외국인 순매도 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=02&investor_gubun=1000&type=buy` | KOSDAQ 기관 순매수 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=02&investor_gubun=1000&type=sell` | KOSDAQ 기관 순매도 상위 | 백만원 |

응답 인코딩: `EUC-KR`. `http_client.decode_response()`가 EUC-KR 우선 시도, 실패 시 UTF-8 fallback.

[HARD] `WebFetch` 금지. Anthropic 인프라 IP 차단·헤더 정규화 위험. `urllib` 자체 호출만 사용.

### Telegram Bot API

- 엔드포인트: `https://api.telegram.org/bot{TOKEN}/sendMessage`
- 메서드: POST, `application/x-www-form-urlencoded`
- 파라미터: `chat_id`, `text`, `disable_web_page_preview=true`
- parse_mode: 없음 (plain text) — 종목명 특수문자 이스케이프 부담 회피
- 최대 메시지: 4096자. 초과 시 `truncate_for_telegram()`이 `\n…(잘림)` 표시 후 자름.

---

## 출처

- `naver_investor_flow/` 각 모듈 import 구문 직접 확인
- `.moai/project/tech.md` §2 (사용 stdlib 모듈), §3 (외부 통합), §4 (HARD 정책)
- `HANDOFF.md` §2.1 (stdlib only), §3.4 (WebFetch 금지)
