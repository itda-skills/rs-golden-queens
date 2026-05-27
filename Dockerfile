# syntax=docker/dockerfile:1.7
# rs-golden-queens — APScheduler 내장 상시 컨테이너
#
# 빌드: docker build -t rs-golden-queens .
# 실행:
#   docker run --rm \
#     -e GOLDENQUEENS_BOT_TOKEN=... \
#     -e GOLDENQUEENS_CHAT_ID=... \
#     -e MARKET_FLOW_RENDER=text \
#     rs-golden-queens
#
# 일회성 명령:
#   docker run --rm -e ... rs-golden-queens notify-test
#   docker run --rm -e ... rs-golden-queens daily-kr

FROM python:3.14.5-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Seoul

# tzdata (KST 정확도) + 로케일 최소 셋업
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

WORKDIR /app

# 의존성을 먼저 복사해서 레이어 캐시 활용
COPY requirements.txt .
RUN pip install -r requirements.txt

# 코드 + 진입점
COPY . .
RUN chmod +x /app/entrypoint.sh

# 헬스체크: scheduler 프로세스 생존 확인 (1분 주기)
HEALTHCHECK --interval=1m --timeout=10s --start-period=20s --retries=3 \
    CMD pgrep -f "python.*scheduler.py" >/dev/null || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["scheduler"]
