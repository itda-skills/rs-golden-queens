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

PKG_DIR := market_flow
VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python

# .venv 가 있으면 우선 사용, 없으면 시스템 python3
ifeq ($(wildcard $(VENV_PY)),$(VENV_PY))
PY ?= $(VENV_PY)
else
PY ?= python3
endif

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

install:  ## 의존성 설치 (.venv 기반, 없으면 생성 확인 후 진행)
	@if [ ! -x "$(VENV_PY)" ]; then \
		printf "'$(VENV_DIR)' 가상환경이 없습니다. 생성할까요? [y/N] "; \
		read ans; \
		case "$$ans" in \
			y|Y|yes|YES) ;; \
			*) echo "취소되었습니다."; exit 1 ;; \
		esac; \
		if command -v uv >/dev/null 2>&1; then \
			uv venv $(VENV_DIR); \
		else \
			python3 -m venv $(VENV_DIR); \
		fi; \
		echo "생성됨: $(VENV_DIR)"; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		uv pip install --python $(VENV_PY) -r $(PKG_DIR)/requirements.txt; \
	else \
		$(VENV_PY) -m pip install -r $(PKG_DIR)/requirements.txt; \
	fi
	@echo "설치 완료 → $(VENV_PY)"

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
