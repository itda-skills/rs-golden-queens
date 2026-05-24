# 모듈 책임과 공개 인터페이스 — rs-golden-queens

`naver_investor_flow/` 패키지 8개 모듈 각각의 책임·공개 인터페이스·의존성·호출자를 정리한다.

---

## `__init__.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/__init__.py` |
| 라인 수 | 7 |

**책임:** 패키지 버전 선언. 런타임에 패키지를 임포트할 때 `__version__`을 노출한다.

**공개 심볼:**

```python
__version__: str = "0.2.0"
```

**stdlib 의존:** 없음

**내부 의존:** 없음

**호출자:** `make version` 타겟 (`python -c "from naver_investor_flow import __version__; print(__version__)"`)

---

## `__main__.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/__main__.py` |
| 라인 수 | 6 |

**책임:** `python -m naver_investor_flow ...` 명령을 `cli.main()`으로 위임하는 얇은 디스패처.

**공개 심볼:** 없음 (진입점 역할)

**stdlib 의존:** 없음

**내부 의존:** `naver_investor_flow.cli` (→ `main()`)

**호출자:** Python 인터프리터 (`-m naver_investor_flow` 플래그)

---

## `cli.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/cli.py` |
| 라인 수 | 223 |

**책임:** `flow_day` / `deal_rank` 두 서브커맨드를 받아 HTTP 호출 → 파싱 → 포맷 → stdout 출력을 조율하는 CLI 진입점.

**공개 함수:**

```python
def main(argv: list[str] | None = None) -> None:
    """CLI 진입점.

    argv: 인자 리스트 (None이면 sys.argv[1:] 사용)
    exit code: 0(정상), 2(HTTP 오류), 3(파싱 오류), 4(네트워크), 5(인코딩), 64(사용법)
    """
```

**내부 함수 (공개되지 않음):**

```python
def _build_flow_url(bizdate: str | None) -> str: ...
    # bizdate 미지정 시 오늘 KST 날짜 자동 주입
def _build_rank_url(market: str, investor: str, side: str) -> str: ...
def _handle_flow_day(args: argparse.Namespace) -> None: ...
def _handle_deal_rank(args: argparse.Namespace) -> None: ...
def _print_error(obj: dict) -> None: ...
```

**상수:**

```python
BASE_FLOW = "https://finance.naver.com/sise/investorDealTrendDay.naver"
BASE_RANK = "https://finance.naver.com/sise/sise_deal_rank_iframe.naver"
REFERER_FLOW = "https://finance.naver.com/sise/sise_trans_style.naver"
REFERER_RANK = "https://finance.naver.com/sise/sise_deal_rank.naver"
MARKET_MAP = {"kospi": "01", "kosdaq": "02"}
INVESTOR_MAP = {"foreign": "9000", "institution": "1000"}
```

**stdlib 의존:** `argparse`, `datetime`, `json`, `sys`

**내부 의존:** `http_client` (`fetch_html`, `HttpError`, `NetworkError`, `EncodingError`), `parser_flow` (`parse_flow_day`), `parser_rank` (`parse_deal_rank`), `formatter` (`format_output`)

**호출자:** `__main__.py` (→ `main()`), `make flow`, `make rank`

---

## `collect.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/collect.py` |
| 라인 수 | 178 |

**책임:** cron 진입점. flow_day 1회 + deal_rank 8조합(총 9회 HTTP 호출) → 마크다운 보고서 빌드 → stdout 출력 + 텔레그램 전송.

**공개 함수:**

```python
def fetch_flow_day(bizdate: str | None = None) -> list[dict]:
    """flow_day 데이터 수집. bizdate 미지정 시 오늘 KST 자동 주입."""

def fetch_deal_rank(market: str, investor: str, side: str) -> list[dict]:
    """단일 deal_rank 조합 수집. market: 'kospi'|'kosdaq', investor: 'foreign'|'institution', side: 'buy'|'sell'"""

def build_report(
    flow_rows: list[dict],
    rank_results: list[tuple[tuple[str, str, str], list[dict]]],
    *,
    bizdate: str,
    fetched_at: str,
) -> str:
    """수집 결과를 사람이 읽는 마크다운 요약으로 변환."""

def main(argv: list[str] | None = None) -> int:
    """수집 + 보고서 + 텔레그램 전송. 반환값: exit code (0=정상, 1=전체 실패)"""
```

**상수:**

```python
DEAL_RANK_COMBOS = [
    ("kospi", "foreign", "buy"), ("kospi", "foreign", "sell"),
    ("kospi", "institution", "buy"), ("kospi", "institution", "sell"),
    ("kosdaq", "foreign", "buy"), ("kosdaq", "foreign", "sell"),
    ("kosdaq", "institution", "buy"), ("kosdaq", "institution", "sell"),
]
```

**stdlib 의존:** `datetime`, `sys`, `traceback`

**내부 의존:** `http_client` (`fetch_html`), `parser_flow` (`parse_flow_day`), `parser_rank` (`parse_deal_rank`), `notify_telegram` (`TelegramConfig`, `send_message`)

**호출자:** GitHub Actions `daily.yml` (`python -m naver_investor_flow.collect`), `make collect`

---

## `http_client.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/http_client.py` |
| 라인 수 | 129 |

**책임:** urllib 기반 HTTP GET + EUC-KR 디코딩 + Windows Chrome UA/Accept/Referer 헤더 조립. 패키지 전체에서 재사용되는 가장 일반적인 네트워크 계층.

**공개 클래스 및 함수:**

```python
class HttpError(Exception):
    """HTTP 4xx/5xx 응답 — exit code 2. 속성: code: int, url: str"""
    def __init__(self, code: int, url: str) -> None: ...

class NetworkError(Exception):
    """연결 실패·타임아웃 — exit code 4. 속성: detail: str"""
    def __init__(self, detail: str) -> None: ...

class EncodingError(Exception):
    """EUC-KR·UTF-8 모두 디코딩 실패 — exit code 5"""
    pass

def fetch(url: str, timeout: float = 10.0, referer: str | None = None) -> bytes:
    """GET 요청 → raw bytes 반환. Raises: HttpError, NetworkError"""

def decode_response(raw: bytes) -> str:
    """raw bytes → str. EUC-KR 우선 시도, 실패 시 UTF-8 fallback. Raises: EncodingError"""

def fetch_html(url: str, timeout: float = 10.0, referer: str | None = None) -> str:
    """fetch + decode_response 합성. Raises: HttpError, NetworkError, EncodingError"""
```

**상수:**

```python
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..."  # Windows Chrome
DEFAULT_TIMEOUT = 10.0
```

**stdlib 의존:** `socket`, `urllib.error`, `urllib.request`

**내부 의존:** 없음

**호출자:** `cli.py` (`fetch_html`), `collect.py` (`fetch_html`)

---

## `parser_flow.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/parser_flow.py` |
| 라인 수 | 149 |

**책임:** 네이버 금융 `investorDealTrendDay.naver` HTML을 파싱하여 일별 시장 매매동향 데이터(11컬럼)를 dict 리스트로 추출. `HTMLParser` 서브클래스 상태 기계 구현. 단위=억원.

**공개 함수:**

```python
def parse_flow_day(html: str) -> list[dict]:
    """flow_day HTML → dict 리스트.
    
    반환 dict 구조:
    {
        "date": "YYYY-MM-DD",
        "individual_eok": int,        # 개인 순매수 (억원)
        "foreign_eok": int,           # 외국인 순매수 (억원)
        "institution_total_eok": int, # 기관계 순매수 (억원)
        "institution_breakdown": {
            "financial_inv": int,     # 금융투자
            "insurance": int,         # 보험
            "trust": int,             # 투신
            "bank": int,              # 은행
            "other_finance": int,     # 기타금융
            "pension": int,           # 연기금
        },
        "foreign_etc_eok": int,       # 기타외국인 (억원)
    }
    최대 10행. 빈 테이블이면 [].
    """
```

**내부 클래스 (공개되지 않음):**

```python
class _FlowDayParser(HTMLParser):
    """상태 기계. summary='순매수에 관한 표' 또는 class='type_1' 테이블 탐지 후 파싱."""
```

**stdlib 의존:** `re`, `html.parser`

**내부 의존:** 없음

**호출자:** `cli.py` (`parse_flow_day`), `collect.py` (`parse_flow_day` via `fetch_flow_day`)

---

## `parser_rank.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/parser_rank.py` |
| 라인 수 | 194 |

**책임:** 네이버 금융 `sise_deal_rank_iframe.naver` HTML을 파싱하여 종목별 외국인·기관 매매 랭킹(최대 30행)을 dict 리스트로 추출. `href="...code=NNNNNN..."` 정규식으로 6자리 종목코드 추출. 단위=백만원.

**공개 함수:**

```python
def parse_deal_rank(html: str) -> list[dict]:
    """deal_rank HTML → dict 리스트 (최대 30건).

    반환 dict 구조:
    {
        "rank": int,           # 순위 (1~30)
        "name": str,           # 종목명
        "code": str | None,    # 종목코드 6자리 (예: "005930"), 추출 실패 시 None
        "quantity": int,       # 순매수 수량 (주)
        "amount_mn_krw": int,  # 순매수 금액 (백만원)
        "volume": int,         # 당일 거래량 (주)
    }
    빈 테이블이면 [].
    """
```

**내부 함수·클래스 (공개되지 않음):**

```python
def _extract_code(href: str) -> str | None:
    """href에서 종목코드 6자리 추출. 예: code=005930"""

class _RankParser(HTMLParser):
    """summary='순매수' 또는 '순매도' 테이블 탐지. table 중첩 깊이(_depth)로 내부 테이블 구분."""
```

**stdlib 의존:** `re`, `html.parser`

**내부 의존:** 없음

**호출자:** `cli.py` (`parse_deal_rank`), `collect.py` (`parse_deal_rank` via `fetch_deal_rank`)

---

## `formatter.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/formatter.py` |
| 라인 수 | 233 |

**책임:** 파싱 결과를 json / table / csv 세 가지 포맷으로 변환하고 말미에 SPEC-GOV-STOCK-001 P-1 동형 디스클레이머를 첨부. `flow_day`=억원, `deal_rank`=백만원 단위 스키마를 의도적으로 차별화 (통일 금지).

**공개 함수·상수:**

```python
DISCLAIMER: str  # SPEC-GOV-STOCK-001 P-1 동형 디스클레이머 고정 문자열

def format_output(
    mode: str,           # "flow_day" | "deal_rank"
    data: list[dict],
    meta: dict,
    fmt: str = "json",   # "json" | "table" | "csv"
    limit: int | None = None,
) -> str:
    """통합 출력 포맷터. 빈 데이터도 정상 처리 (empty 응답 반환)."""
```

**JSON 출력 스키마 (mode별 차별화):**

```
flow_day  → { mode, unit: "억원",   meta: {...}, data: [...] }
deal_rank → { mode, unit_amount: "백만원", unit_quantity: "주", meta: {...}, data: [...] }
```

[HARD] `flow_day` JSON에는 `unit_amount`/`unit_quantity` 필드 없음. `deal_rank` JSON에는 `unit` 필드 없음. 이 차별화는 `test_formatter.py`의 negative assertion으로 강제된다.

**stdlib 의존:** `csv`, `io`, `json`, `datetime`

**내부 의존:** 없음

**호출자:** `cli.py` (`format_output`), `collect.py` (보고서 빌드에서 직접 `formatter` 미사용 — `build_report`에서 별도 마크다운 생성)

---

## `notify_telegram.py`

| 항목 | 내용 |
|---|---|
| 경로 | `naver_investor_flow/notify_telegram.py` |
| 라인 수 | 109 |

**책임:** Telegram Bot API `sendMessage` 엔드포인트에 plain text 메시지를 POST 전송. stdlib `urllib`만 사용. `TelegramConfig.from_env()`로 환경변수 (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)를 읽어 활성화 여부를 결정. 미설정 시 no-op.

**공개 클래스 및 함수:**

```python
class TelegramConfig:
    """환경변수 기반 텔레그램 설정 컨테이너."""
    token: str | None
    chat_id: str | None

    @property
    def enabled(self) -> bool:
        """token과 chat_id 둘 다 존재해야 True."""

    @classmethod
    def from_env(cls, env: dict | None = None) -> "TelegramConfig":
        """환경변수에서 token·chat_id 읽기. env=None이면 os.environ 사용."""

def truncate_for_telegram(text: str, limit: int = 4096) -> str:
    """4096자 초과 시 말미에 '\\n…(잘림)' 표시 후 자름."""

def send_message(
    text: str,
    config: TelegramConfig | None = None,
    timeout: float = 10.0,
) -> bool:
    """텔레그램 메시지 전송. 성공=True, 미설정·실패=False. 실패 사유는 stderr 출력."""
```

**상수:**

```python
API_BASE = "https://api.telegram.org"
MAX_MESSAGE_CHARS = 4096
DEFAULT_TIMEOUT = 10.0
```

**stdlib 의존:** `json`, `os`, `socket`, `sys`, `urllib.error`, `urllib.parse`, `urllib.request`

**내부 의존:** 없음

**호출자:** `collect.py` (`TelegramConfig.from_env()`, `send_message()`)

---

## 출처

- `naver_investor_flow/` 각 모듈 소스코드 직접 확인
- `.moai/project/structure.md` 모듈 표
- `HANDOFF.md` §2.2 패키지 레이아웃
