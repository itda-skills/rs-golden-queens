# rs-golden-queens — market_flow 운영용 Makefile
#
# 사용:
#   make              # 명령 목록 (기본)
#   make install      # 의존성 설치 (yfinance, pandas, python-dotenv)
#   make daily-kr     # 한국장 매매동향 발송 (오늘)
#   make daily-us     # 미국장 마감 요약 발송 (최신 거래일)
#   make weekly       # 주간 리포트 발송
#   make notify-test  # 텔레그램 핑 (환경변수 검증)
#   make smoke-kr     # 네이버 fetch 단독 점검 (텔레그램 발송 없음)
#   make smoke-us     # yfinance fetch 단독 점검 (텔레그램 발송 없음)
#   make clean        # 캐시 정리
#
# Dry-run (텔레그램 발송 없이 stdout 출력):
#   make daily-kr DRY=1
#   make daily-us DRY=1 DATE=2026-05-22
#   make weekly DRY=1
#   make notify-test DRY=1
#
# 환경변수 (.env 또는 export):
#   GOLDENQUEENS_BOT_TOKEN  텔레그램 봇 토큰
#   GOLDENQUEENS_CHAT_ID    수신 chat_id (채널은 -100 으로 시작)

PY ?= python3
PKG_DIR := market_flow

# DRY=1 → 텔레그램 발송 없이 stdout 출력
ifeq ($(DRY),1)
export MARKET_FLOW_DRY_RUN := 1
endif

.DEFAULT_GOAL := help
.PHONY: help install daily-kr daily-us weekly notify-test smoke-kr smoke-us clean

help:  ## 사용 가능한 명령 목록
	@printf "rs-golden-queens — 사용 가능한 명령\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n환경변수:\n"
	@printf "  GOLDENQUEENS_BOT_TOKEN  텔레그램 봇 토큰\n"
	@printf "  GOLDENQUEENS_CHAT_ID    수신 chat_id (채널은 -100 으로 시작)\n"
	@printf "\n인자 예시:\n"
	@printf "  make daily-kr DATE=20260522\n"
	@printf "  make daily-us DATE=2026-05-22\n"

install:  ## 의존성 설치 (uv 우선, fallback pip)
	@if command -v uv >/dev/null 2>&1; then \
		uv pip install --system -r $(PKG_DIR)/requirements.txt; \
	else \
		$(PY) -m pip install -r $(PKG_DIR)/requirements.txt; \
	fi

daily-kr:  ## 한국장 매매동향 발송. DATE=YYYYMMDD 옵션
	cd $(PKG_DIR) && $(PY) daily_kr.py $(DATE)

daily-us:  ## 미국장 마감 요약 발송. DATE=YYYY-MM-DD 옵션
	cd $(PKG_DIR) && $(PY) daily_us.py $(DATE)

weekly:  ## 주간 리포트 발송
	cd $(PKG_DIR) && $(PY) weekly.py

notify-test:  ## 텔레그램 핑 메시지 1회 (환경변수 동작 확인)
	@cd $(PKG_DIR) && $(PY) -c "import datetime; \
	from telegram_push import send; \
	now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds'); \
	r = send(f'[rs-golden-queens] notify-test ping at {now} (KST)'); \
	print('OK' if r.get('ok') else r)"

smoke-kr:  ## 네이버 fetch 단독 점검 (텔레그램 발송 없음)
	@cd $(PKG_DIR) && $(PY) -c "from datetime import datetime; \
	from fetchers.naver_kr import fetch_today; \
	d = fetch_today(datetime.now().strftime('%Y%m%d')); \
	keys = list(d.keys()) if isinstance(d, dict) else type(d).__name__; \
	print('naver_kr OK:', keys)"

smoke-us:  ## yfinance fetch 단독 점검 (텔레그램 발송 없음)
	@cd $(PKG_DIR) && $(PY) -c "from fetchers.us_market import fetch_us_close; \
	d = fetch_us_close(); \
	keys = list(d.keys()) if isinstance(d, dict) else type(d).__name__; \
	print('us_market OK:', keys)"

clean:  ## __pycache__ 제거
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov
