# 진입점 — rs-golden-queens

시스템에 진입할 수 있는 모든 경로와 그 파라미터를 정리한다.

---

## Python 모듈 진입점

### `python -m naver_investor_flow` → 단발 CLI 조회

```
python -m naver_investor_flow {flow_day|deal_rank} [옵션]
```

실행 흐름: `__main__.py` → `cli.main()`

서브커맨드가 없으면 help를 stderr에 출력하고 exit 64.

### `python -m naver_investor_flow.collect` → cron 통합 수집

```
python -m naver_investor_flow.collect
```

실행 흐름: `collect.py` → `collect.main()`

`__main__.py`를 거치지 않는다. 독립 cron 진입점으로 직접 호출된다.

---

## CLI 서브커맨드 옵션 표

### `flow_day` — 일별 시장 매매동향

```
python -m naver_investor_flow flow_day [--bizdate YYYYMMDD] [--format json|table|csv] [--limit N]
```

| 옵션 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `--bizdate` | `YYYYMMDD` | (오늘 KST 자동 주입) | 조회 영업일. 미지정 시 KST 기준 오늘 날짜 자동 주입. 비영업일·미래 날짜 입력 시 네이버가 직전 영업일 데이터로 보정. |
| `--format` | `json\|table\|csv` | `json` | 출력 포맷 |
| `--limit` | `int` | None (전체) | 출력 행 수 제한 (1~10) |

**[HARD] `flow_day`에서 `bizdate` 파라미터는 HTTP 호출 시 필수로 주입해야 한다.** 미지정 시 네이버가 1.6KB 빈 페이지를 반환한다. `_build_flow_url()`이 이를 처리한다.

### `deal_rank` — 종목별 외국인·기관 매매 랭킹

```
python -m naver_investor_flow deal_rank --market kospi|kosdaq --investor foreign|institution --side buy|sell [--format json|table|csv] [--limit N]
```

| 옵션 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `--market` | `kospi\|kosdaq` | 필수 | — | 시장 구분 |
| `--investor` | `foreign\|institution` | 필수 | — | 투자자 구분 |
| `--side` | `buy\|sell` | 필수 | — | 매매 방향 |
| `--format` | `json\|table\|csv` | 선택 | `json` | 출력 포맷 |
| `--limit` | `int` | 선택 | None (전체) | 출력 행 수 제한 (1~30) |

**[HARD] `deal_rank`에 `--bizdate` 옵션 신설 금지 (SPEC REQ-020.4).** 네이버 서버단이 이 파라미터를 무시한다. 신설하면 사용자를 오인시킨다. (HANDOFF.md §3.2 참조)

---

## cron 진입점

### `.github/workflows/daily.yml` — 일일 자동 수집

| 항목 | 내용 |
|---|---|
| schedule | `10 9 * * *` (UTC) = KST 18:10 매일 |
| 수동 트리거 | `workflow_dispatch` (Actions 탭에서 즉시 실행 가능) |
| 러너 | ubuntu-latest |
| Python | 3.11 고정 |
| 타임아웃 | 5분 |
| 실행 명령 | `python -m naver_investor_flow.collect` |
| 환경변수 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (GitHub Secrets) |

**cron 시각 산정 근거:**

| 시각 | 설명 |
|---|---|
| KST 09:00 | 한국 주식 개장 |
| KST 15:30 | 본장 마감 |
| KST 18:00 | 시간외 거래 종료 |
| **KST 18:10** | **cron 실행** — 시간외 종료 + 네이버 페이지 갱신 안정 마진 10분 |
| UTC 09:10 | GitHub Actions cron 표현식 기준 |

평일/주말 구분 없음: 주말에도 네이버가 직전 영업일 데이터를 반환하므로 메시지 1회 더 발송될 뿐 비용 사실상 0.

Secrets 없이도 cron은 정상 종료한다 (`collect.py`가 stdout만 출력하고 exit 0).

---

## Makefile 진입점

```bash
make [타겟] [변수=값 ...]
```

| 타겟 | 호출 명령 | 용도 |
|---|---|---|
| `help` | *(기본 타겟)* | 사용 가능한 명령 목록 출력 |
| `install-dev` | `uv pip install pytest` 또는 `pip install pytest` | pytest 설치 (uv 우선, fallback pip). 실행 자체에는 불필요. |
| `test` | `pytest tests/ -q --ignore=tests/test_live_smoke.py` | 단위 테스트 (mock + fixture, 네트워크 없음) |
| `test-live` | `pytest tests/ -q` | 라이브 호출 포함 전체 테스트 (네이버 직접 호출) |
| `test-cov` | `coverage run -m pytest ... && coverage report` | 커버리지 리포트 (coverage 패키지 필요) |
| `collect` | `python -m naver_investor_flow.collect` | 9콜 통합 수집 + 텔레그램 (cron 진입점과 동일) |
| `flow` | `python -m naver_investor_flow flow_day` | flow_day 단독 조회 (오늘 날짜 자동 주입) |
| `rank` | `python -m naver_investor_flow deal_rank --market ... --investor ... --side ...` | deal_rank 단독 조회 — `MARKET`, `INVESTOR`, `SIDE` 변수 필수. 미입력 시 exit 64 |
| `notify-test` | 인라인 Python | 텔레그램 헬로 메시지 1회 (환경변수 동작 확인) |
| `smoke-headers` | 인라인 Python | HTTP 헤더 라이브 점검 (UA·Referer·Accept-Language 실제 전송 확인) |
| `clean` | `find ... -exec rm -rf` | `__pycache__`·`.pytest_cache`·`htmlcov` 제거 |
| `version` | `python -c "from naver_investor_flow import __version__; print(__version__)"` | 패키지 버전 출력 |

**`make rank` 사용 예:**

```bash
make rank MARKET=kospi INVESTOR=foreign SIDE=buy
make rank MARKET=kosdaq INVESTOR=institution SIDE=sell | python3 -m json.tool
```

**[HARD] `deal_rank`에 `--bizdate` 옵션 신설 금지.** Makefile `rank` 타겟에도 `BIZDATE` 변수를 추가하지 않는다. (SPEC REQ-020.4)

---

## exit code 체계

| 코드 | 의미 | 발생 모듈 |
|---|---|---|
| 0 | 정상 (데이터 없는 empty 포함) | `cli.py`, `collect.py` |
| 1 | 수집 전체 실패 (flow_day + 모든 deal_rank 전부 실패) | `collect.py` |
| 2 | HTTP 오류 (4xx/5xx) | `cli.py` |
| 3 | HTML 파싱 오류 | `cli.py` |
| 4 | 네트워크 연결 실패 / 타임아웃 | `cli.py` |
| 5 | EUC-KR·UTF-8 모두 디코딩 실패 | `cli.py` |
| 64 | 사용법 오류 (인자 누락·오입력) | `cli.py`, `make rank` |

`collect.py`는 개별 호출 실패를 stderr에 출력하고 계속 진행한다. 텔레그램 전송 실패는 exit code 0 (collect 자체는 성공).

---

## 출처

- `naver_investor_flow/cli.py` — 서브커맨드·옵션·exit code 직접 확인
- `naver_investor_flow/collect.py` — `main()` 반환값·DEAL_RANK_COMBOS 직접 확인
- `.github/workflows/daily.yml` — cron 표현식·환경변수 직접 확인
- `Makefile` — 11개 타겟 직접 확인
- `HANDOFF.md` §2.3 (cron 결정), §3.2 (deal_rank bizdate 금지), §4.3 (Makefile 사용 패턴)
- `.moai/project/structure.md` 진입점 매핑 표
- `.moai/project/tech.md` §8 (에러 코드 체계), §6 (cron 시각 산정)
