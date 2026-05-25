# 진입점 — rs-golden-queens

시스템에 진입할 수 있는 모든 경로와 그 파라미터를 정리한다.

모든 Python 진입점은 `market_flow/` 디렉터리에서 실행한다 (`Makefile`의 `cd $(PKG_DIR)` 참조).

---

## Python 스크립트 진입점

### `python daily_kr.py [YYYYMMDD]` — 한국장 일간 발송

```bash
# market_flow/ 디렉터리에서 실행
python daily_kr.py             # 오늘 KST 날짜 자동 사용
python daily_kr.py 20260522    # 특정일 지정
```

실행 흐름: `daily_kr.main()` → 휴장 게이트 → fetch → format → send

| 인자 | 타입 | 설명 |
|---|---|---|
| `YYYYMMDD` (선택) | 날짜 문자열 | 수집 기준 영업일. 미지정 시 오늘 KST 날짜 자동 사용. |

### `python daily_us.py [YYYY-MM-DD]` — 미국장 일간 발송

```bash
python daily_us.py              # 최신 거래일
python daily_us.py 2026-05-22   # 특정일 지정
```

실행 흐름: `daily_us.main()` → DST 게이트 → 휴장 게이트 → fetch → format → send

| 환경변수 | 값 | 설명 |
|---|---|---|
| `MARKET_SCHEDULE` | `edt` \| `est` | DST 이중 발송 방지 게이트. `flow-us.yml`이 자동 주입. 미설정 시 게이트 무시. |

### `python weekly.py` — 주간 리포트 발송

```bash
python weekly.py
```

실행 흐름: `weekly.main()` → 마지막 거래일 게이트 → fetch → format → send

인자 없음. 오늘이 그 주의 마지막 KR 거래일이 아니면 침묵 종료 (발송 없음).

### `python telegram_push.py "메시지"` — 텔레그램 직접 발송

```bash
python telegram_push.py "점검 메시지"   # 인자로 메시지 지정
python telegram_push.py                  # 기본 점검 메시지 사용
```

봇 토큰·chat_id 동작 확인용. `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID` 환경변수 필요.

---

## Makefile 타겟

```bash
make [타겟] [DRY=1] [DATE=...]
```

`DRY=1`을 붙이면 `MARKET_FLOW_DRY_RUN=1`이 자동 주입되어 텔레그램 발송 없이 stdout 출력.

| 타겟 | 실행 명령 | 용도 |
|---|---|---|
| `help` | *(기본 타겟)* | 사용 가능한 명령 목록 출력 |
| `install` | `pip install -r requirements.txt` (uv 우선, fallback pip) | 의존성 설치 |
| `daily-kr [DATE=YYYYMMDD]` | `python daily_kr.py [DATE]` | 한국장 매매동향 발송 |
| `daily-us [DATE=YYYY-MM-DD]` | `python daily_us.py [DATE]` | 미국장 마감 요약 발송 |
| `weekly` | `python weekly.py` | 주간 리포트 발송 |
| `notify-test` | 인라인 Python | 텔레그램 핑 메시지 (환경변수 동작 확인) |
| `smoke-kr` | 인라인 Python | 네이버 fetch 단독 점검 (텔레그램 발송 없음) |
| `smoke-us` | 인라인 Python | yfinance fetch 단독 점검 (텔레그램 발송 없음) |
| `clean` | `find ... -exec rm -rf` | `__pycache__`, `.pytest_cache`, `htmlcov` 제거 |

**사용 예:**

```bash
make daily-kr DRY=1               # 텔레그램 없이 한국장 리포트 stdout
make daily-kr DRY=1 DATE=20260522 # 특정일 dry-run
make daily-us DRY=1
make weekly DRY=1
make smoke-kr                     # 네이버 fetch 단독 점검
make smoke-us                     # yfinance fetch 단독 점검
make notify-test                  # 봇 연결 확인
```

---

## GitHub Actions 진입점

### `flow-kr.yml` — 한국장 일간 발송

| 항목 | 내용 |
|---|---|
| 트리거 | `cron '10 9 * * 1-5'` (평일 KST 18:10) + `workflow_dispatch` |
| 러너 | ubuntu-latest, Python 3.13 |
| 작업 디렉터리 | `market_flow` |
| 실행 명령 | `python daily_kr.py` |
| 환경변수 | `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`, `TZ=Asia/Seoul` |
| 타임아웃 | 5분 |

### `flow-us.yml` — 미국장 일간 발송 (DST 자동 반영)

| 항목 | 내용 |
|---|---|
| 트리거 (EDT) | `cron '30 20 * * 1-5'` (UTC 20:30 = NYSE 16:00 EDT + 30분) |
| 트리거 (EST) | `cron '30 21 * * 1-5'` (UTC 21:30 = NYSE 16:00 EST + 30분) |
| `workflow_dispatch` | 수동 트리거 지원 (MARKET_SCHEDULE 미설정, 게이트 무시) |
| 러너 | ubuntu-latest, Python 3.13 |
| 작업 디렉터리 | `market_flow` |
| 실행 명령 | `python daily_us.py` |
| 환경변수 | `MARKET_SCHEDULE` (`edt`/`est`, `github.event.schedule`로 자동 분기), `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`, `TZ=Asia/Seoul` |
| 타임아웃 | 5분 |

DST 게이트 동작: 두 cron이 모두 매일 트리거되지만, `MARKET_SCHEDULE` 값과 `is_us_in_dst()` 실제 판정이 불일치하면 즉시 `sys.exit(0)`. 한 시즌에 한 번만 발송.

### `flow-weekly.yml` — 주간 리포트 발송

| 항목 | 내용 |
|---|---|
| 트리거 | `cron '30 9 * * 1-5'` (평일 KST 18:30) + `workflow_dispatch` |
| 러너 | ubuntu-latest, Python 3.13 |
| 작업 디렉터리 | `market_flow` |
| 실행 명령 | `python weekly.py` |
| 환경변수 | `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`, `TZ=Asia/Seoul` |
| 타임아웃 | 5분 |
| 비고 | 스크립트 내부 `is_last_kr_trading_day_of_week()` 게이트가 발송 여부 결정. 금요일 휴장 시 직전 거래일에 이월. |

### `test.yml` — CI 품질 검증

| 항목 | 내용 |
|---|---|
| 트리거 | `push` (main), `pull_request` (main), `workflow_dispatch` |
| 러너 | ubuntu-latest 단일 OS |
| 매트릭스 | Python 3.10 / 3.11 / 3.12 (3잡) |
| 실행 | `pytest tests/ -q -m "not live"` |
| 옵션 | `fail-fast: false` |

---

## cron 시각 산정 근거

| 워크플로우 | cron (UTC) | KST 변환 | 근거 |
|---|---|---|---|
| `flow-kr.yml` | `10 9 * * 1-5` | 평일 18:10 | 네이버 18:03 갱신 + 7분 마진 |
| `flow-us.yml` EDT | `30 20 * * 1-5` | 익일 05:30 | NYSE 16:00 EDT + 30분 |
| `flow-us.yml` EST | `30 21 * * 1-5` | 익일 06:30 | NYSE 16:00 EST + 30분 |
| `flow-weekly.yml` | `30 9 * * 1-5` | 평일 18:30 | flow-kr 20분 후, 마지막 거래일 게이트 내장 |

---

## GitHub Secrets 등록 위치

```
Repository → Settings → Secrets and variables → Actions
  GOLDENQUEENS_BOT_TOKEN   (Telegram Bot 인증 토큰)
  GOLDENQUEENS_CHAT_ID     (수신 chat_id, 채널은 -100 시작)
```

두 값 모두 있어야 텔레그램 발송 활성화. 하나라도 없으면 `telegram_push.py`가 `RuntimeError` 발생.

---

## 출처

- `market_flow/daily_kr.py`, `daily_us.py`, `weekly.py`, `telegram_push.py` 직접 확인
- `.github/workflows/flow-kr.yml`, `flow-us.yml`, `flow-weekly.yml`, `test.yml` 직접 확인
- `Makefile` 직접 확인
- `.moai/project/structure.md` 진입점 매핑 표, Makefile 타겟 표
- `.moai/project/tech.md` §3 (cron 시각 산정), §4 (환경변수)
- SPEC-MF-SCHED-001 (DST 자동 반영 + 휴장 인지)
