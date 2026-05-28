# rs-golden-queens — 작업 규약

한국장·미국장 마감 후 텔레그램 채널로 매매동향 요약을 자동 푸시하는 개인 투자 데이터 봇.
NAS 작업 스케줄러가 GitHub Actions의 `flow-*` 워크플로우를 `workflow_dispatch`로 호출한다.
운영 수집 데이터는 영구 저장하지 않고 즉시 발송한다.

## 언어·톤

- 사용자 응답은 한국어. 코드/식별자/파일명은 영어.
- 커밋 메시지·코드 주석·문서는 한국어 허용.

## 프로젝트 레이아웃

```
market_flow/           # 메인 패키지 (KR/US 매매동향, 주간 리포트)
  daily_kr.py          # 한국장 매매동향 진입점
  daily_us.py          # 미국장 마감 요약 진입점
  weekly.py            # 주간 리포트 진입점
  calendar_utils.py    # DST·거래일·마지막 거래일 판정
  formatter.py         # 색 컨벤션 (🔴▲ 상승 / 🔵▼ 하락)
  telegram_push.py     # Telegram sendMessage/sendPhoto + DRY_RUN 분기
  fetchers/, render/   # 데이터 수집·렌더링
naver_investor_flow/   # 네이버 투자자 동향 (보조 데이터 소스)
tests/                 # pytest (unit/integration/live)
main.py                # 로컬·GitHub Actions CLI 진입점
.github/workflows/     # GitHub Actions (flow-* dispatch 대상, test CI)
```

진입점 세부는 `README.md`, `market_flow/README.md` 참조. 정시 호출 스케줄은 repo 밖의 NAS 작업 스케줄러에서 관리한다.

## 도메인 규약

- **사실 데이터만** — 투자 권유·종목 추천·매수/매도 시점 판단을 출력하지 않는다.
- **저장 금지** — 운영 수집 데이터는 디스크에 영구 저장하지 않고 텔레그램으로만 전송. 명시적인 DRY_RUN/debug 산출물만 예외.
- **휴장 처리** — KR/US 비거래일에는 "[KR/US] 오늘은 휴장입니다" 한 줄 발송. 캘린더 판단은 `calendar_utils.py` 경유.
- **DST 자동 반영** — 미국장 날짜·휴장·DST 판단은 `calendar_utils.py`/`daily_us.py` 경유. 계절별 시각·게이트 하드코딩 금지.
- **발송 단일 경로** — Telegram 전송은 반드시 `telegram_push.py` 를 통한다. `MARKET_FLOW_DRY_RUN=1` 은 실제 발송하지 않으며, 텍스트는 stdout 출력·이미지는 `out/` 프리뷰 저장으로 처리한다.

## 개발 워크플로우

- 의존성: `make install` (가능하면 `.venv` 안에서)
- 로컬 검증: `make daily-kr DRY=1`, `make daily-us DRY=1 DATE=2026-05-22`, `make weekly DRY=1`
- 텔레그램 핑 점검: `make notify-test DRY=1`
- 데이터 소스 단독 점검: `make smoke-kr`, `make smoke-us`
- 테스트: `pytest` (unit/integration/live 분리; live는 외부 API 호출)
- 린트: `ruff check .`, 포맷은 `ruff format` 또는 기존 스타일을 따른다.

## 작업 안전 규칙

1. **계획 우선** — 3개 이상 파일을 수정해야 하는 작업은 변경 범위와 순서를 먼저 공유하고 동의를 받은 뒤 진행한다.
2. **버그 수정 전 재현** — 가능한 한 실패하는 테스트를 먼저 추가하고 수정한다 (특히 캘린더·DST·휴장 로직).
3. **시간 처리** — 날짜/시간 계산은 `calendar_utils.py` 의 함수를 우선 사용. tzinfo 없는 naive datetime 사용 지양.
4. **외부 호출 격리** — yfinance·네이버·텔레그램 API 호출은 fetcher·publisher 레이어 안에 둔다. 비즈니스 로직과 섞지 않는다.
5. **비밀키 금지** — `GOLDENQUEENS_BOT_TOKEN`, `GOLDENQUEENS_CHAT_ID`, `.env` 내용을 커밋·로그·메시지에 노출하지 않는다.
6. **파괴적 명령 사전 확인** — `git push --force`, `git reset --hard`, `rm -rf`, 컨테이너/볼륨 삭제는 실행 전에 한 번 더 확인한다.
7. **요청 범위 준수** — 요청 범위 밖의 리팩토링·정리는 별도 제안으로 분리한다.

## 통신·운영

- 발송 대상은 `GOLDENQUEENS_CHAT_ID` (다중 chat_id 쉼표 구분 지원, `,` 로 split). 채널은 `-100` 으로 시작.
- 실패 시 침묵 종료 금지 — 시작/종료 마커와 에러를 stdout/stderr 로 노출한다 (기존 관측성 커밋 방향 유지).
- GitHub Actions cron 은 제거됨. NAS 작업 스케줄러가 GitHub API/CLI로 `flow-*` 워크플로우의 `workflow_dispatch`를 호출한다.

## 도구 사용 (Claude Code 기준)

- 파일 탐색: `Glob` → `Grep` → `Read` 순서. `find`/`grep` 셸 호출 지양.
- 파일 편집은 `Edit` 우선, 신규 파일만 `Write`.
- 큰 PDF/로그는 페이지·라인 범위 지정해서 읽는다.
