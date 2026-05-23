# rs-golden-queens — 네이버 투자자 매매동향 일일 수집 자동화
#
# 사용:
#   make             # 명령 목록 (기본)
#   make collect     # cron 진입점과 동일 실행
#   make test        # 단위 테스트 (네트워크 없음)
#   make notify-test # 텔레그램 봇·chat 동작 확인 (헬로 메시지 1회)
#
# 의도적으로 stdlib only. install-dev만 pytest 설치 — 실행에는 불필요.

PY ?= python3
PKG := naver_investor_flow

.DEFAULT_GOAL := help
.PHONY: help install-dev test test-live test-cov collect flow rank notify-test smoke-headers clean version

help:  ## 사용 가능한 명령 목록
	@printf "rs-golden-queens — 사용 가능한 명령\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[1m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n환경변수:\n"
	@printf "  TELEGRAM_BOT_TOKEN  봇 토큰 (없으면 텔레그램 no-op)\n"
	@printf "  TELEGRAM_CHAT_ID    수신 chat ID\n"

install-dev:  ## pytest 설치 (uv 우선, fallback pip)
	@if command -v uv >/dev/null 2>&1; then \
		uv pip install --system pytest; \
	else \
		$(PY) -m pip install --upgrade pytest; \
	fi

test:  ## 단위 테스트 (mock + fixture만, 네트워크 없음)
	$(PY) -m pytest tests/ -q --ignore=tests/test_live_smoke.py

test-live:  ## 라이브 호출 포함 전체 테스트 (네이버 직접 호출)
	$(PY) -m pytest tests/ -q

test-cov:  ## 커버리지 리포트 (coverage 패키지 필요)
	$(PY) -m coverage run -m pytest tests/ --ignore=tests/test_live_smoke.py
	$(PY) -m coverage report -m
	@printf "\nHTML 리포트: htmlcov/index.html\n"
	@$(PY) -m coverage html >/dev/null 2>&1 || true

collect:  ## 9콜 통합 수집 + 텔레그램 알림 (cron 진입점과 동일)
	@$(PY) -m $(PKG).collect

flow:  ## flow_day 단독 조회 (오늘 자동 주입)
	@$(PY) -m $(PKG) flow_day

rank:  ## deal_rank 단독 — MARKET/INVESTOR/SIDE 인자 필요. 예: make rank MARKET=kospi INVESTOR=foreign SIDE=buy
	@if [ -z "$(MARKET)" ] || [ -z "$(INVESTOR)" ] || [ -z "$(SIDE)" ]; then \
		printf "사용법: make rank MARKET=kospi INVESTOR=foreign SIDE=buy\n"; \
		printf "  MARKET   = kospi | kosdaq\n"; \
		printf "  INVESTOR = foreign | institution\n"; \
		printf "  SIDE     = buy | sell\n"; \
		exit 64; \
	fi
	@$(PY) -m $(PKG) deal_rank --market $(MARKET) --investor $(INVESTOR) --side $(SIDE)

notify-test:  ## 텔레그램 헬로 메시지 1회 (환경변수 동작 확인)
	@$(PY) -c "import os, sys, datetime; \
	from naver_investor_flow.notify_telegram import TelegramConfig, send_message; \
	cfg = TelegramConfig.from_env(); \
	sys.exit('TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다.\nexport TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... 후 다시 시도하세요.') if not cfg.enabled else None; \
	now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds'); \
	ok = send_message(f'[rs-golden-queens] notify-test ping at {now} (KST)', config=cfg); \
	sys.exit(0 if ok else 1)"

smoke-headers:  ## HTTP 헤더 라이브 점검 — UA·Referer·Accept-Language 실제 전송 확인
	@$(PY) -c "from naver_investor_flow import http_client; \
	import urllib.request as ur; \
	captured = []; orig = ur.urlopen; \
	ur.urlopen = lambda req, timeout=None: (captured.append(dict(req.headers)), orig(req, timeout=timeout))[1]; \
	http_client.fetch_html('https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=01&investor_gubun=9000&type=buy', referer='https://finance.naver.com/sise/sise_deal_rank.naver'); \
	import json; print(json.dumps(captured[0], ensure_ascii=False, indent=2))"

clean:  ## __pycache__·.pytest_cache·htmlcov 제거
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache htmlcov .coverage

version:  ## 패키지 버전 출력
	@$(PY) -c "from naver_investor_flow import __version__; print(__version__)"
