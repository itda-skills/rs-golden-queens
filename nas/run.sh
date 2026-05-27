#!/usr/bin/env bash
# 시놀러지 NAS — 컨테이너 안에서 호출되는 진입점
#
# 호출 예 (NAS 호스트에서):
#   docker run --rm \
#     -v /volume1/docker/rs-golden-queens/repo:/app \
#     -v /volume1/docker/rs-golden-queens/venv:/venv \
#     -v /volume1/docker/rs-golden-queens/pip-cache:/root/.cache/pip \
#     --env-file /volume1/docker/rs-golden-queens/.env \
#     -e TZ=Asia/Seoul \
#     -w /app \
#     python:3.13-slim \
#     bash nas/run.sh daily-kr
#
# 동작:
#   1) /venv 없으면 venv 생성
#   2) requirements.txt 해시가 바뀌었으면 pip install
#   3) python main.py <command> <args...> 실행

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: run.sh <command> [args...]" >&2
    echo "  command: daily-kr | daily-us | weekly | notify-test" >&2
    exit 2
fi

VENV=/venv
REQ_HASH_FILE="$VENV/.requirements.sha256"

cd /app

# 1) venv 준비
if [ ! -x "$VENV/bin/python" ]; then
    echo "[run.sh] venv 생성: $VENV"
    python -m venv "$VENV"
    "$VENV/bin/pip" install -q --disable-pip-version-check --upgrade pip
fi

# 2) requirements 해시 비교 → 변경 시만 pip install
CURRENT_HASH=$(sha256sum requirements.txt | awk '{print $1}')
LAST_HASH=$(cat "$REQ_HASH_FILE" 2>/dev/null || echo "")

if [ "$CURRENT_HASH" != "$LAST_HASH" ]; then
    echo "[run.sh] requirements 변경 감지 → pip install"
    "$VENV/bin/pip" install -q --disable-pip-version-check -r requirements.txt
    echo "$CURRENT_HASH" > "$REQ_HASH_FILE"
else
    echo "[run.sh] requirements 동일 → pip install 생략"
fi

# 3) 실행
echo "[run.sh] python main.py $*"
exec "$VENV/bin/python" main.py "$@"
