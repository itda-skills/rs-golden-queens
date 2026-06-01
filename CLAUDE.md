# rs-golden-queens 지침

이 저장소에서 항상 필요한 최소 지침이다. 작업 절차는 사용자의 현재 요청과 필요 시 붙여넣는 작업별 지시가 우선한다.

rs-golden-queens는 한국장·미국장 마감 후 시장 매매동향 요약을 텔레그램으로 보내는 개인 투자 데이터 봇이다. Cloudflare cron-worker(`cron-worker/`)가 GitHub Actions `flow-*` 워크플로우를 `workflow_dispatch`로 호출한다.

## 기본

- 사용자 응답은 한국어 우선. 코드 식별자, 파일명, 공개 API 이름은 기존 영어 규칙을 유지한다.
- 작업 전 현재 작업트리 상태를 확인하고, 사용자 변경을 되돌리지 않는다.
- 큰 기능, 공개 계약 변경, 불명확한 설계는 목표·비목표·인수 조건부터 정리한다.
- 커밋, 브랜치 생성, 푸시, PR 생성은 사용자가 요청할 때만 한다.

## 탐색 지도

필요한 만큼만 읽는다.

1. 사용자 요청과 `git status --short`.
2. `README.md`, `market_flow/README.md`, `Makefile`.
3. 실행 흐름: `main.py`, `market_flow/daily_kr.py`, `market_flow/daily_us.py`, `market_flow/weekly.py`.
4. 공통 규칙: `market_flow/calendar_utils.py`, `market_flow/formatter.py`, `market_flow/telegram_push.py`.
5. 데이터·발행: `market_flow/fetchers/`, `market_flow/publisher.py`, `web/`, `.github/workflows/`.
6. 관련 테스트: `tests/`의 unit/integration/live 구분을 확인한다.

대용량 로그, 캐시, 로컬 출력물은 현재 작업에 직접 필요할 때만 본다.

## 도메인 불변성

- 사실 데이터만 출력한다. 투자 권유, 종목 추천, 매수·매도 시점 판단을 추가하지 않는다.
- 운영 수집 데이터는 디스크에 영구 저장하지 않는다. 명시적 dry-run/debug 출력과 `out/` 프리뷰만 예외다.
- KR/US 비거래일에는 해당 fetcher를 호출하지 않고 `[KR] ... 오늘은 휴장입니다` 또는 `[US] ... 오늘은 휴장입니다` 한 줄만 보낸다.
- 거래일, 휴장, 미국 DST 판단은 `calendar_utils.py`와 `daily_us.py` 경로를 사용한다. 계절별 시각이나 게이트를 하드코딩하지 않는다.
- 시장 날짜·시간 계산에는 시장별 timezone-aware `datetime`을 사용한다. naive datetime을 새로 늘리지 않는다.
- Telegram 전송은 `market_flow/telegram_push.py`를 통한다. `MARKET_FLOW_DRY_RUN=1`에서는 실제 발송하지 않는다.
- yfinance, 네이버, 텔레그램 같은 외부 호출은 fetcher/publisher 레이어에 둔다.
- 실패 시 침묵 종료하지 않는다. 시작/종료 마커와 에러가 stdout/stderr에 남아야 한다.
- `GOLDENQUEENS_*`, `TEST_GOLDENQUEENS_*`, `.env` 값은 출력하거나 커밋하지 않는다.

## 텔레그램이 원본, 웹은 종속 (Single Source of Truth)

텔레그램 메시지를 위한 데이터/포맷이 원본(source of truth)이다. 웹페이지는 그
원본에 맞춰 구성되는 종속 표현일 뿐이다. 따라서 **데이터/포맷이 바뀌면 웹도 함께
바뀌어야 하며, 그 역방향은 성립하지 않는다.**

- fetcher 반환 구조(`market_flow/fetchers/`)나 `formatter.py`, 발행 스키마
  (`publisher.py`, `schema_version`)를 바꾸면, 같은 변경 단위 안에서 웹
  (`web/src/lib/types.ts`, `data.ts`, 해당 페이지/컴포넌트)도 함께 갱신한다.
- 웹에 필요한 값은 **발행 스냅샷에 담아 내려보내는** 방식으로 추가한다. 웹에서
  새로 수집·계산하거나 시장 로직(거래일/휴장/색 의미)을 재구현하지 않는다.
- 스키마를 깨는 변경은 `schema_version`을 올리고, 웹 reader가 구버전을 안전하게
  처리(폴백 또는 명시적 분기)하도록 한다.
- 색 컨벤션(🔴▲상승 / 🔵▼하락)은 원본의 부호/값에서 파생한다. 웹은 이모지·색
  문자열을 저장하지 않고 값으로부터 재현한다.
- 변경 후에는 텔레그램 dry-run과 웹 빌드를 **모두** 통과시켜 원본·종속의 정합을
  확인한다.

## 검증 지도

- 설치: `make install`
- 전체 테스트: `pytest`
- 관련 단위 테스트: `pytest tests/test_calendar_utils.py tests/test_daily_us.py`
- dry-run: `make daily-kr DRY=1`, `make daily-us DRY=1 DATE=2026-05-22`, `make weekly DRY=1`
- 알림 점검: `make notify-test DRY=1`, 실제 테스트 채널은 `make notify-test TEST=1`
- 데이터 소스 스모크: `make smoke-kr`, `make smoke-us`
- 린트/포맷: `ruff check .`, `ruff format`

외부 네트워크나 실 텔레그램 발송이 필요한 검증은 실행 여부와 남은 공백을 분리해 보고한다.

## 금지선

- 비밀키, 토큰, `.env` 내용, 사용자 홈 설정을 커밋하거나 로그에 노출하지 않는다.
- `git reset --hard`, 강제 푸시, 루트 대상 `rm -rf`, 컨테이너/볼륨 삭제는 사용자가 명시적으로 요청하고 재확인한 경우에만 한다.
- 요청 범위 밖의 리팩토링과 정리는 별도 제안으로 분리한다.
