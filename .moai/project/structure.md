# structure.md — rs-golden-queens

## 디렉토리 트리

```
rs-golden-queens/
├── README.md                        # 사용자 가이드 + 빠른 시작
├── HANDOFF.md                       # 핸드오프 노트 (untracked) — 숨은 결정·함정 기록
├── Makefile                         # 11개 운영 타겟
├── .github/
│   └── workflows/
│       ├── daily.yml                # cron 10 9 * * * UTC + workflow_dispatch
│       └── test.yml                 # push/PR · 3 OS × 3 Python 버전 매트릭스
├── naver_investor_flow/             # 메인 패키지
│   ├── __init__.py                  # __version__ = "0.2.0"
│   ├── __main__.py                  # `python -m naver_investor_flow ...` → cli.main()
│   ├── cli.py                       # argparse CLI (flow_day / deal_rank 서브커맨드)
│   ├── collect.py                   # cron 진입점 — 9콜 + 보고서 + 텔레그램
│   ├── formatter.py                 # json/table/csv + 디스클레이머
│   ├── http_client.py               # urllib GET + EUC-KR 디코딩 + UA/Referer/Accept
│   ├── notify_telegram.py           # Telegram sendMessage (stdlib urllib)
│   ├── parser_flow.py               # flow_day HTML 파서 (html.parser 상태 기계)
│   └── parser_rank.py               # deal_rank HTML 파서 (href 정규식 종목코드 추출)
├── tests/
│   ├── conftest.py                  # pytest fixture 설정
│   ├── fixtures/                    # 라이브 캡처 HTML (EUC-KR, 2026-05-23)
│   │   ├── flow_day_sample.html
│   │   └── deal_rank_sample.html
│   ├── test_cli.py                  # CLI 단위 테스트 (mock)
│   ├── test_collect.py              # collect 단위 테스트 (mock)
│   ├── test_formatter.py            # formatter 단위 테스트 (단위 negative assertion 포함)
│   ├── test_http_client.py          # http_client 단위 테스트 (mock)
│   ├── test_live_smoke.py           # 라이브 호출 — 로컬 수동 검증용 (CI 제외)
│   ├── test_notify_telegram.py      # notify_telegram 단위 테스트 (mock)
│   ├── test_parser_flow.py          # parser_flow 단위 테스트 (fixture)
│   └── test_parser_rank.py          # parser_rank 단위 테스트 (fixture)
├── .moai/
│   ├── config/                      # MoAI 설정 (user.yaml, language.yaml 등)
│   └── project/                     # 프로젝트 문서 (product.md, structure.md, tech.md)
└── .claude/                         # Claude Code 에이전트 규칙·스킬·훅
```

## 디렉토리 역할

| 디렉토리 | 역할 |
|---|---|
| `naver_investor_flow/` | 메인 Python 패키지. HTTP 호출·파싱·포맷·알림·CLI·cron 진입점 전부 포함. |
| `tests/` | 단위 테스트 7개 + 라이브 스모크 1개. fixture는 EUC-KR 라이브 캡처 2건. |
| `.github/workflows/` | CI 매트릭스(`test.yml`) + 일일 cron(`daily.yml`) 워크플로우. |
| `.moai/` | MoAI-ADK 설정·프로젝트 문서. |
| `.claude/` | Claude Code 에이전트 규칙·스킬·훅 (MoAI-ADK 운영 설정). |

## `naver_investor_flow/` 모듈 표

| 모듈 | 역할 | 라인 수 |
|---|---|---|
| `__init__.py` | 패키지 진입점. `__version__ = "0.2.0"` | 7 |
| `__main__.py` | `python -m naver_investor_flow ...` → `cli.main()` 디스패치 | 6 |
| `http_client.py` | urllib GET + EUC-KR 디코딩 + Windows Chrome UA/Referer/Accept 헤더. 외부에서 재사용 가능한 가장 일반적인 계층. | 129 |
| `parser_flow.py` | `investorDealTrendDay.naver` HTML 파서. `html.parser.HTMLParser` 서브클래스, 상태기계. 11컬럼 → dict. 억원 단위. | 149 |
| `parser_rank.py` | `sise_deal_rank_iframe.naver` HTML 파서. `href="...code=NNNNNN..."` 정규식으로 종목코드 6자리 추출. 백만원 단위. | 194 |
| `formatter.py` | json/table/csv 출력 + SPEC-GOV-STOCK-001 P-1 동형 디스클레이머. 단위 스키마 의도적 차별화(flow_day=억원, deal_rank=백만원). | 233 |
| `cli.py` | argparse — `flow_day` / `deal_rank` 서브커맨드. 사람이 단발 조회할 때 사용. | 223 |
| `collect.py` | **cron 진입점**. 9콜(flow_day 1 + deal_rank 8조합) + 마크다운 보고서 + 텔레그램 전송. | 178 |
| `notify_telegram.py` | Telegram Bot API `sendMessage`. stdlib `urllib`만 사용. `TelegramConfig.from_env()`로 환경변수 관리. | 109 |

## 진입점 매핑

| 진입점 | 명령 | 용도 |
|---|---|---|
| `python -m naver_investor_flow.collect` | cron/Makefile `collect` 타겟 | 9콜 통합 수집 + 텔레그램 (cron 진입점과 동일) |
| `python -m naver_investor_flow flow_day` | `__main__.py` → `cli.main()` | flow_day 단발 CLI 조회 |
| `python -m naver_investor_flow deal_rank` | `__main__.py` → `cli.main()` | deal_rank 단발 CLI 조회 |

`collect.py`는 `__main__.py`를 거치지 않는다. 독립 cron 진입점(`python -m naver_investor_flow.collect`)으로 직접 호출한다.

## 빌드/실행 시스템: Makefile 타겟

| 타겟 | 역할 |
|---|---|
| `help` | 사용 가능한 명령 목록 출력 (기본 타겟) |
| `install-dev` | pytest 설치 (uv 우선, fallback pip). 실행 자체에는 불필요. |
| `test` | 단위 테스트 (mock + fixture, `--ignore=tests/test_live_smoke.py`) |
| `test-live` | 라이브 호출 포함 전체 테스트 (네이버 직접 호출) |
| `test-cov` | 커버리지 리포트 (coverage 패키지 필요) |
| `collect` | 9콜 통합 수집 + 텔레그램 알림 (cron 진입점과 동일) |
| `flow` | flow_day 단독 조회 (오늘 날짜 자동 주입) |
| `rank` | deal_rank 단독 조회 — `MARKET`/`INVESTOR`/`SIDE` 인자 필요 |
| `notify-test` | 텔레그램 헬로 메시지 1회 (환경변수 동작 확인) |
| `smoke-headers` | HTTP 헤더 라이브 점검 — UA·Referer·Accept 실제 전송 확인 |
| `clean` | `__pycache__`·`.pytest_cache`·`htmlcov` 제거 |
| `version` | 패키지 버전 출력 |

## CI 워크플로우

### `test.yml` — 코드 품질 검증

- 트리거: `push` (main), `pull_request` (main), `workflow_dispatch`
- 매트릭스: 3 OS (ubuntu-latest, macos-latest, windows-latest) × 3 Python (3.10, 3.11, 3.12) = 9잡
- 실행: `pytest tests/ -q --ignore=tests/test_live_smoke.py` (라이브 테스트 제외)
- `fail-fast: false` — 한 잡 실패해도 나머지 계속 실행

### `daily.yml` — 일일 수집 자동화

- 트리거: `schedule: cron "10 9 * * *"` UTC + `workflow_dispatch` (수동 트리거)
- 러너: ubuntu-latest, Python 3.11 고정
- 타임아웃: 5분
- 환경변수: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (GitHub Secrets)
- 실행: `python -m naver_investor_flow.collect`

## 테스트 구조

| 구분 | 파일 수 | 특징 |
|---|---|---|
| 단위 테스트 | 7개 | mock + fixture, 네트워크 없음. `make test` / CI 포함. |
| 라이브 스모크 | 1개 (`test_live_smoke.py`) | 실 네트워크 호출. `make test`에서 `--ignore`. CI 제외. `make test-live`로만 실행. |

fixture 파일: `tests/fixtures/flow_day_sample.html`, `tests/fixtures/deal_rank_sample.html` — EUC-KR 라이브 캡처 (2026-05-23).

`test_formatter.py`는 단위 스키마 의도적 차별화를 negative assertion으로 강제한다 (`flow_day` 출력에 `unit_amount`/`unit_quantity` 필드가 없음을, `deal_rank` 출력에 `unit` 필드가 없음을 검증).

## 출처

- `README.md` 디렉토리 구조 섹션
- `HANDOFF.md` §2.2 패키지 레이아웃 표
- `.github/workflows/daily.yml`, `test.yml` 직접 확인
- `Makefile` 11개 타겟 직접 확인
- `naver_investor_flow/` 각 모듈 라인 수 직접 측정
