# tech.md — rs-golden-queens

## 1. 기술 스택 개요

| 항목 | 내용 |
|---|---|
| 언어 | Python 3.10+ |
| 의존성 정책 | **stdlib only** — 외부 라이브러리 0건. `requirements.txt` 없음. |
| 옵션 개발 의존 | `pytest` (테스트 실행 전용. 수집·실행 자체에 불필요.) |
| 패키지 관리 | pyproject.toml 없음. `make install-dev`로 pytest만 설치. |
| CI 매트릭스 | 3 OS × 3 Python 버전 = 9잡 (ubuntu/macos/windows × 3.10/3.11/3.12) |

## 2. 사용 stdlib 모듈

| 모듈 | 사용처 | 역할 |
|---|---|---|
| `urllib.request` | `http_client.py`, `notify_telegram.py` | HTTP GET (네이버), POST (Telegram sendMessage) |
| `urllib.error` | `http_client.py`, `notify_telegram.py` | HTTPError, URLError 예외 처리 |
| `urllib.parse` | `notify_telegram.py` | urlencode (Telegram 요청 파라미터 인코딩) |
| `html.parser` | `parser_flow.py`, `parser_rank.py` | HTMLParser 서브클래스 상태기계 파싱 |
| `csv` | `formatter.py` | CSV 출력 (RFC 4180) |
| `json` | `formatter.py`, `cli.py`, `notify_telegram.py` | JSON 출력·파싱 |
| `io` | `formatter.py` | StringIO (CSV 버퍼) |
| `argparse` | `cli.py` | flow_day / deal_rank 서브커맨드 CLI |
| `socket` | `http_client.py` | socket.timeout 예외 처리 |
| `datetime` + `timezone` | `collect.py`, `formatter.py`, `cli.py` | KST(+09:00) 현재 시각 산정 |
| `re` | `parser_flow.py`, `parser_rank.py` | 날짜 패턴 변환, `code=NNNNNN` href 정규식 추출 |
| `os` | `notify_telegram.py` | 환경변수 읽기 (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) |
| `sys`, `traceback` | `collect.py`, `cli.py` | stderr 출력, exit code 관리 |

## 3. 외부 통합

### 네이버 금융 공개 페이지 (9종)

1회 실행(`collect.py`)에 9개 페이지를 호출한다.

| URL 패턴 | 의미 | 단위 |
|---|---|---|
| `investorDealTrendDay.naver?bizdate=YYYYMMDD&sosok=` | 최근 10영업일 시장 매매동향 (개인·외국인·기관계 + 기관 6분류 + 기타외인) | 억원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=buy` | KOSPI 외국인 순매수 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=sell` | KOSPI 외국인 순매도 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=1000&type=buy` | KOSPI 기관 순매수 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=01&investor_gubun=1000&type=sell` | KOSPI 기관 순매도 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=02&investor_gubun=9000&type=buy` | KOSDAQ 외국인 순매수 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=02&investor_gubun=9000&type=sell` | KOSDAQ 외국인 순매도 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=02&investor_gubun=1000&type=buy` | KOSDAQ 기관 순매수 상위 | 백만원 |
| `sise_deal_rank_iframe.naver?sosok=02&investor_gubun=1000&type=sell` | KOSDAQ 기관 순매도 상위 | 백만원 |

응답 인코딩: `EUC-KR`. `http_client.decode_response()`가 EUC-KR 우선 시도, 실패 시 UTF-8 fallback.

### Telegram Bot API

- 엔드포인트: `https://api.telegram.org/bot{TOKEN}/sendMessage`
- 메서드: POST, `application/x-www-form-urlencoded`
- 파라미터: `chat_id`, `text`, `disable_web_page_preview`
- parse_mode: 없음 (plain text) — 종목명 특수문자(예: `KODEX 200선물인버스2X`) 이스케이프 부담 회피
- 메시지 최대 4096자. 초과 시 `truncate_for_telegram()`이 `\n…(잘림)` 표시 후 자름.

## 4. Decisions & Constraints

### [HARD] stdlib-only 정책

`requests`·`httpx`·`aiohttp`·`bs4`·`lxml` 도입 금지. `urllib` + `html.parser` + `csv` + `datetime` + `re`만 사용.

근거:
- 의존성 0 → GitHub Actions 캐시 불필요 (checkout + python setup만으로 실행 가능)
- 보안 표면 0 — 외부 패키지 취약점 벡터 없음
- Python 3.10~3.13 어디서나 동일 동작 (버전 호환 이슈 없음)

정책 검증:
```bash
grep -rE "^(import|from) (requests|httpx|aiohttp|bs4|lxml)" naver_investor_flow/
# 기대치: 0건
```

### [HARD] WebFetch 금지

Anthropic의 `WebFetch` 도구는 Anthropic 인프라 IP에서 발신한다. 데이터센터 IP 대역은 네이버 같은 정적 페이지도 차단당할 수 있으며, 인프라가 동적 렌더링·헤더 정규화를 수행하므로 코드에서 설정한 헤더(UA·Referer)가 그대로 전달되지 않는다. 본 저장소는 무조건 `urllib` 자체 호출만 사용한다.

### [HARD] 데이터 저장 금지

commit/Release/Pages에 수집 결과를 저장하지 않는다. 본 저장소는 **코드 저장 목적만**이다. 수집 데이터 이력이 필요하면 별도 데이터 저장소로 분리해야 한다. `shared/itda_path.py` 같은 외부 디렉토리 의존도 없다.

### [HARD] 단위 의도적 차별화 — 통일 금지

| MODE | 금액 단위 | JSON 필드 |
|---|---|---|
| `flow_day` | **억원** (100,000,000 KRW) | `unit: "억원"` |
| `deal_rank` | **백만원** (1,000,000 KRW) | `unit_amount: "백만원"`, `unit_quantity: "주"` |

- `flow_day` JSON에는 `unit_amount` / `unit_quantity` 필드가 **없다**
- `deal_rank` JSON에는 `unit` 필드가 **없다**
- 두 스키마를 mutually exclusive로 설계하여 LLM·다운스트림이 섞어 쓰면 schema mismatch로 즉시 깨지게 함
- 100억원 ≠ 100백만원 (100배 차이). 사용자 의사결정 오류 방지가 일관성 미감보다 우선
- `test_formatter.py`가 negative assertion으로 강제. **"통일하자"는 충동을 누를 것**

### [HARD] `deal_rank --bizdate` 신설 금지 (REQ-020.4)

`sise_deal_rank_iframe.naver`에 `bizdate=20260515` / `20260520` / 생략 → **모두 동일 응답**. 네이버 서버단이 이 파라미터를 보지 않는다. CLI에 `--bizdate` 옵션을 신설하면 사용자를 오인시키므로 SPEC `REQ-020.4`로 명시적 거부되어 있다.

### `flow_day`는 bizdate 필수 자동 주입

`investorDealTrendDay.naver`는 `bizdate=` 없이 호출하면 **1.6KB 빈 페이지** 반환. `bizdate=YYYYMMDD` 명시 시 7.8KB·10영업일 데이터 정상 반환. `collect.fetch_flow_day()`와 `cli._build_flow_url()`이 미지정 시 오늘 KST 날짜를 자동 주입한다. 비영업일·미래 날짜 입력 시 네이버가 직전 영업일 데이터로 자동 보정.

### Referer 헤더 — 현재 효과 0이지만 유지

라이브에서 Referer 유/무 응답 크기 동일(16385 bytes). 그럼에도 유지하는 이유: 실제 브라우저처럼 흉내내기 위한 사용자 명시 요청 + 미래 차단 회피 보험. 네이버가 정책을 바꿔 차단을 시작할 경우에 대비. 비용 거의 0이므로 유지 권장. `http_client.fetch(referer=...)` 인자로 받아 `collect.py`와 `cli.py`가 iframe별 부모 페이지 URL을 주입한다.

- flow_day Referer: `https://finance.naver.com/sise/sise_trans_style.naver`
- deal_rank Referer: `https://finance.naver.com/sise/sise_deal_rank.naver`

## 5. 라이브 falsification 함정 3건

코드만 봐서는 알 수 없는 함정. 비슷한 변경 시 라이브 1회 확인을 반드시 끼울 것.

### 함정 1: [HARD] `flow_day`의 `bizdate`는 필수

- 증상: `bizdate=` 없이 호출 → 1.6KB 빈 페이지 반환
- 정상 호출: `bizdate=YYYYMMDD` 명시 → 7.8KB·10영업일 데이터
- 비영업일·미래 날짜: 네이버가 직전 영업일 데이터로 자동 보정해 반환
- 대응: `collect.fetch_flow_day()`와 `cli._build_flow_url()`이 미지정 시 오늘 KST 자동 주입
- **다시 만들면 안 되는 것**: "bizdate 없으면 최신을 알아서 주겠지" 가정. 라이브 1회로 즉시 깨짐.

### 함정 2: [HARD] `deal_rank`는 `bizdate`를 무시한다

- 증상: `bizdate=20260515` / `20260520` / 생략 → 모두 동일 응답
- 원인: 네이버 서버단이 이 파라미터를 보지 않음
- 결론: CLI에 `--bizdate` 옵션 신설 금지 — 있어도 의미 없고 사용자를 오인시킴
- SPEC `REQ-020.4`로 명시적 거부 박혀 있음

### 함정 3: [HARD] 단위 혼용 — 의도적 스키마 차별화

- 코드만 보면 "왜 두 모드 단위가 다른가?" 의문이 생길 수 있음
- flow_day=억원, deal_rank=백만원. 100배 차이.
- 통일하면 사용자 의사결정 오류 발생. 의도적 차별화가 정책.
- `test_formatter.py`의 negative assertion이 통일을 코드 레벨에서 막음

## 6. 운영 환경

### cron 시각 산정

| 시각 | 설명 |
|---|---|
| KST 09:00 | 한국 주식 개장 |
| KST 15:30 | 본장 마감 |
| KST 18:00 | 시간외 거래 종료 |
| **KST 18:10** | **cron 실행 시각** — 시간외 종료 + 네이버 페이지 갱신 안정 마진 10분 |
| UTC 09:10 | GitHub Actions cron 표현식 기준 (`10 9 * * *`) |

평일/주말 구분 없음: 네이버는 주말에도 직전 영업일 데이터를 그대로 반환한다. 메시지가 1회 더 발송될 뿐 비용 사실상 0이며 cron 표현식이 단순해 유지보수에도 유리하다.

`workflow_dispatch`도 함께 등록되어 있어 Actions 탭에서 수동 트리거 가능.

### Telegram 환경변수 명명 표준

| 환경변수 | 의미 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather 발급 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 수신 chat ID (개인=양수, 그룹/채널=보통 음수) |

`python-telegram-bot`·`telegraf` 등 공식 표준 명명. 짧은 `TG_BOT_TOKEN`·`BOT_TOKEN` 등은 검색·호환성에서 불리하여 채택 안 함.

**둘 다 있어야 활성**. 하나라도 비면 `collect.py`가 stdout만 출력하고 정상 종료 (exit code 0). 로컬·CI 코드 경로 동일.

### GitHub Secrets 등록 위치

```
Repository → Settings → Secrets and variables → Actions
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
```

Secrets 없이도 cron은 안 깨진다. Secrets 없이 push 후 cron 동작을 먼저 확인하고 이후에 Secrets를 채워도 된다.

## 7. 개발 환경 요구사항

| 항목 | 요구사항 |
|---|---|
| Python | 3.10+ |
| make | Makefile 사용 시 필요 |
| pytest | 옵션. 테스트 실행 시만 필요. |

설치 명령:
```bash
make install-dev    # pytest 설치 (uv 우선, fallback pip)
```

실행 자체(수집·CLI)에는 Python 3.10+ 외 추가 설치 없음.

## 8. 에러 코드 체계

`cli.py` 기준 exit code:

| 코드 | 의미 |
|---|---|
| 0 | 정상 (데이터 없는 empty 포함) |
| 2 | HTTP 오류 (4xx/5xx) |
| 3 | HTML 파싱 오류 |
| 4 | 네트워크 연결 실패 / 타임아웃 |
| 5 | EUC-KR·UTF-8 모두 디코딩 실패 |
| 64 | 사용법 오류 (argparse 인자 누락·오입력) |

`collect.py` exit code: 0 (수집 성공 또는 텔레그램 전송 실패), 1 (flow_day + 모든 deal_rank 전부 실패).

`make rank` 타겟: MARKET/INVESTOR/SIDE 인자 누락 시 exit 64.

## 9. CI 매트릭스

| OS | Python 3.10 | Python 3.11 | Python 3.12 |
|---|---|---|---|
| ubuntu-latest | O | O | O |
| macos-latest | O | O | O |
| windows-latest | O | O | O |

총 9잡. `fail-fast: false` — 한 잡 실패해도 나머지 계속 실행.

라이브 테스트 제외 이유: 매트릭스 9잡 × 8 deal_rank = 72콜로 네이버에 불필요한 부하 발생. `test_live_smoke.py`는 `--ignore`로 제외. 라이브는 `make test-live` (로컬·수동) 또는 `daily.yml` cron이 1일 1회 본격 실행.

## 10. 검증 명령

다음 세션이 안전한 상태인지 1분 안에 검증 (HANDOFF.md §6 그대로):

```bash
make clean
make test                    # 150 passed / 0 failed / 0 skipped
make test-live               # 170 passed / 0 failed / 0 skipped (네트워크 필요)
make smoke-headers           # 4헤더 (UA·Accept·Accept-Language·Referer) 라이브 확인
make collect                 # 9콜 + 마크다운 보고서 stdout

# requests/bs4 등 외부 라이브러리 0건 확인
grep -rE "^(import|from) (requests|httpx|aiohttp|bs4|lxml)" naver_investor_flow/
# WebFetch 0건 확인
grep -rl "WebFetch" naver_investor_flow/
# requirements.txt 미생성 확인
ls requirements.txt 2>&1
```

기대치: 모두 PASS, 마지막 셋 다 매칭 0건 / 파일 없음.

## 출처

- `HANDOFF.md` §2 (기술 결정), §3 (라이브 falsification 함정), §4 (운영 메모), §6 (검증 명령)
- `.moai/project/interview.md` Round 2 (Constraints and Non-Goals), Round 3 (Documentation Priority)
- `naver_investor_flow/http_client.py` — 헤더·에러 코드 직접 확인
- `naver_investor_flow/formatter.py` — 단위 스키마 직접 확인
- `naver_investor_flow/collect.py` — 9콜 구조·텔레그램 no-op 직접 확인
- `naver_investor_flow/cli.py` — exit code 체계 직접 확인
- `.github/workflows/daily.yml`, `test.yml` — cron·매트릭스 직접 확인
- `Makefile` — 타겟별 역할 직접 확인
