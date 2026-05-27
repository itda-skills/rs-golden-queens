# 시놀러지 NAS — Docker 기반 스케줄링 가이드

GitHub Actions의 cron 지연 문제를 회피하기 위해, 시놀러지 NAS의 DSM 작업 스케줄러가 분 단위 정확도로 컨테이너를 실행하는 구성입니다.

- **이미지 빌드 없음** — 공식 `python:3.13-slim`을 그대로 사용
- **매 실행 시 git pull** — 항상 최신 코드 반영
- **venv·pip cache 영구 보관** — 두 번째 실행부터 의존성 설치 생략
- **DSM 작업 스케줄러가 cron 역할** — 분 단위 정확

---

## 사전 요구

- 시놀러지 DSM 7.x + Container Manager 패키지
- SSH 활성화 (제어판 → 터미널 및 SNMP)
- 사용자 `admin` 또는 `root` sudo 권한

---

## 1. NAS 디렉터리 초기화 (1회)

SSH 접속 후 root로:

```bash
ROOT=/volume1/docker/rs-golden-queens
sudo mkdir -p "$ROOT"/{venv,pip-cache,logs}
cd "$ROOT"

# 1-1) 저장소 clone (alpine/git 컨테이너 사용 — NAS에 git 설치 불요)
sudo docker run --rm \
  -v "$ROOT":/work \
  -w /work \
  alpine/git clone https://github.com/itda-skills/rs-golden-queens.git repo

# 1-2) .env 작성
sudo tee "$ROOT/.env" > /dev/null <<'EOF'
GOLDENQUEENS_BOT_TOKEN=여기에_봇_토큰
GOLDENQUEENS_CHAT_ID=여기에_챗_ID
MARKET_FLOW_RENDER=text
EOF
sudo chmod 600 "$ROOT/.env"

# 1-3) scheduler.sh 작성 (Task Scheduler가 호출)
sudo tee "$ROOT/scheduler.sh" > /dev/null <<'SH'
#!/usr/bin/env bash
# Task Scheduler가 호출하는 래퍼.
# 사용: scheduler.sh <command> [args...]
#   ex) scheduler.sh daily-kr
#       MARKET_SCHEDULE=edt scheduler.sh daily-us

set -euo pipefail

ROOT=/volume1/docker/rs-golden-queens
DOCKER=/usr/local/bin/docker
LOGDIR="$ROOT/logs"
TS=$(date +%Y-%m-%dT%H:%M:%S%z)

CMD="${1:-}"
[ -z "$CMD" ] && { echo "usage: scheduler.sh <command> [args...]" >&2; exit 2; }
shift || true

# 명령별 로그 파일
LOG="$LOGDIR/${CMD}.log"
mkdir -p "$LOGDIR"

{
    echo "===== $TS scheduler.sh $CMD $* ====="

    # 1) git pull
    "$DOCKER" run --rm \
        -v "$ROOT/repo":/git \
        -w /git \
        alpine/git pull --rebase --quiet 2>&1 || echo "[scheduler] git pull 실패 — 기존 코드로 진행"

    # 2) python 실행
    "$DOCKER" run --rm \
        --name "flow-${CMD}-$$" \
        -v "$ROOT/repo":/app \
        -v "$ROOT/venv":/venv \
        -v "$ROOT/pip-cache":/root/.cache/pip \
        --env-file "$ROOT/.env" \
        -e TZ=Asia/Seoul \
        -e MARKET_SCHEDULE="${MARKET_SCHEDULE:-}" \
        -w /app \
        python:3.13-slim \
        bash nas/run.sh "$CMD" "$@"

    echo "===== $(date +%Y-%m-%dT%H:%M:%S%z) done ====="
    echo
} >> "$LOG" 2>&1
SH
sudo chmod +x "$ROOT/scheduler.sh"

# 1-4) 이미지 사전 pull (Task Scheduler 첫 실행 지연 방지)
sudo docker pull alpine/git
sudo docker pull python:3.13-slim
```

---

## 2. 수동 검증

스케줄러 등록 전 동작 확인:

```bash
# 한국장 푸시 (KST 18시 이후 KRX 데이터 확정된 시간에 수동 실행)
sudo /volume1/docker/rs-golden-queens/scheduler.sh daily-kr

# 로그 확인
tail -50 /volume1/docker/rs-golden-queens/logs/daily-kr.log

# 환경변수 ping (의존성 캐시 + Telegram 연결 검증)
sudo /volume1/docker/rs-golden-queens/scheduler.sh notify-test
```

첫 실행에서 venv 생성 + pip install로 1~2분 소요. **두 번째 실행부터는 5~10초**.

---

## 3. DSM 작업 스케줄러 등록

DSM → **제어판** → **작업 스케줄러** → **만들기** → **예약된 작업** → **사용자 정의 스크립트**

공통 설정:
- 사용자: `root`
- 알림: 작업 편집 → **알림** 탭에서 "오류가 발생한 경우에만 메일 보내기" 체크 (DSM 메일 설정 필요)

### 한국장

| 항목 | 값 |
|---|---|
| 작업 이름 | `flow-kr` |
| 스케줄 | 매주 월·화·수·목·금, 18:10 |
| 사용자 정의 스크립트 | `/volume1/docker/rs-golden-queens/scheduler.sh daily-kr` |

### 미국장 EDT 시즌 (3월 둘째 일요일 ~ 11월 첫째 일요일)

| 항목 | 값 |
|---|---|
| 작업 이름 | `flow-us-edt` |
| 스케줄 | 매주 화·수·목·금·토, 05:30 (전날 NYSE 마감 기준) |
| 사용자 정의 스크립트 | `MARKET_SCHEDULE=edt /volume1/docker/rs-golden-queens/scheduler.sh daily-us` |

### 미국장 EST 시즌

| 항목 | 값 |
|---|---|
| 작업 이름 | `flow-us-est` |
| 스케줄 | 매주 화·수·목·금·토, 06:30 |
| 사용자 정의 스크립트 | `MARKET_SCHEDULE=est /volume1/docker/rs-golden-queens/scheduler.sh daily-us` |

> EDT/EST 두 작업을 모두 등록해두면, `daily_us.py`의 DST 게이트가 시즌에 맞지 않는 트리거를 자동으로 skip합니다.

### 주간 리포트

| 항목 | 값 |
|---|---|
| 작업 이름 | `flow-weekly` |
| 스케줄 | 매주 금요일, 18:30 |
| 사용자 정의 스크립트 | `/volume1/docker/rs-golden-queens/scheduler.sh weekly` |

> 현 GitHub Actions의 `flow-weekly.yml`은 평일 매일 실행되지만, 주간 리포트는 보통 금요일 한 번이면 충분합니다. 매일 보내야 하면 스케줄을 평일 매일로 변경.

---

## 4. 로그 회전 (선택)

`/volume1/docker/rs-golden-queens/logs/*.log`가 누적되므로 매일 새벽 1회 정리:

| 항목 | 값 |
|---|---|
| 작업 이름 | `flow-log-rotate` |
| 스케줄 | 매일 03:00 |
| 사용자 정의 스크립트 | `find /volume1/docker/rs-golden-queens/logs -name "*.log" -mtime +30 -delete` |

---

## 5. GitHub Actions 정리

NAS 운영이 1주일 이상 안정적으로 검증되면, 기존 워크플로우의 `schedule` 블록을 제거합니다. `workflow_dispatch`는 비상용으로 남겨두는 것을 권장.

```yaml
# .github/workflows/flow-kr.yml (예)
on:
  workflow_dispatch:   # schedule 블록 제거
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `docker: command not found` | `docker` 경로가 다름 | `which docker` 확인 후 `scheduler.sh`의 `DOCKER=` 수정 |
| `permission denied` (Volume mount) | NAS 사용자/그룹 권한 | `sudo chown -R root:root /volume1/docker/rs-golden-queens` |
| venv 손상 (Python 버전 mismatch 등) | base image 업데이트 영향 | `sudo rm -rf /volume1/docker/rs-golden-queens/venv` 후 재실행 (자동 재생성) |
| pip install이 매번 실행됨 | venv 해시 파일 권한 문제 | `/volume1/docker/rs-golden-queens/venv/.requirements.sha256` 권한 확인 |
| `git pull` 실패 | 인증 필요 (private repo) | HTTPS PAT URL로 clone하거나 SSH 키 마운트 |

---

## 동작 흐름 요약

```
DSM Task Scheduler (정확한 시각에 발화)
    ↓
/volume1/docker/rs-golden-queens/scheduler.sh daily-kr
    ↓
docker run alpine/git pull            ← 코드 동기화 (~3초)
    ↓
docker run python:3.13-slim
    └─ bash nas/run.sh daily-kr
       ├─ venv 준비 (있으면 skip)
       ├─ requirements.txt 해시 변경 시만 pip install
       └─ python main.py daily-kr     ← 실제 작업
            ↓
        Telegram 푸시
```
