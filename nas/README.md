# 시놀러지 NAS — 상시 컨테이너 방식 (권장)

GitHub Actions cron 지연 문제를 회피하기 위한 NAS 운영 가이드.
`v*` 태그를 푸시하면 Docker Hub에 자동 빌드되는 **APScheduler 내장 이미지**를 사용합니다.

- **NAS는 이미지만 받아서 컨테이너 1개 띄우면 끝** — 디렉터리/파일 생성 없음
- **환경변수는 Container Manager GUI에서 입력** — `.env` 파일 불필요
- **DSM Task Scheduler 불필요** — 컨테이너 내부 APScheduler가 KST 정시 발화
- **DSM 7.2+의 자동 업데이트로 새 릴리스 자동 반영**

> 기존 `nas/run.sh` + DSM Task Scheduler 방식은 부록(§B)으로 유지합니다.

---

## 사전 요구

- DSM 7.2+ (Container Manager 자동 업데이트 기능)
- Container Manager 패키지 설치
- 인터넷 접근 (Yahoo Finance, Naver, Telegram, Docker Hub)

---

## 1. 새 버전 릴리스 (개발자 측 작업)

```bash
git tag v1.0.0
git push origin v1.0.0
```

→ GitHub Actions가 `.github/workflows/build-image.yml`을 실행:
- `linux/amd64` + `linux/arm64` 멀티 아키텍처 빌드
- **Docker Hub** (`allieus/rs-golden-queens`)에 푸시
- 생성되는 태그: `v1.0.0`, `1.0.0`, `1.0`, `1`, `latest`

수동 빌드: GitHub Actions 페이지 → "컨테이너 이미지 빌드 및 푸시" → **Run workflow**.

### 사전 시크릿 등록 (1회)

Repository **Settings** → **Secrets and variables** → **Actions**:

| 시크릿 이름 | 값 |
|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub 사용자명 |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token (Read & Write 권한) |

Docker Hub Access Token 발급: [hub.docker.com/settings/security](https://hub.docker.com/settings/security) → **New Access Token**.

Docker Hub에 미리 빈 public 저장소 `allieus/rs-golden-queens` 생성 권장 (자동 생성도 되지만 명시적 생성이 안전).

---

## 2. NAS 셋업 (1회)

### 2-1. 이미지 다운로드

**Container Manager** → **레지스트리** 탭 → 검색창에 `allieus/rs-golden-queens` 입력.

Container Manager는 기본적으로 Docker Hub에 연결되어 있으므로 별도 레지스트리 등록은 불필요합니다.

다운로드 클릭 → 태그 선택 시 `latest` 입력 (또는 특정 버전 `v1.0.0`).

### 2-2. 컨테이너 생성

**Container Manager** → **컨테이너** 탭 → **생성**

| 단계 | 입력 |
|---|---|
| 이미지 선택 | `allieus/rs-golden-queens:latest` |
| 컨테이너 이름 | `rs-golden-queens` |
| 자동 다시 시작 활성화 | ✅ |
| 리소스 제한 | 메모리 256MB 권장 (선택) |
| 자동 업데이트 활성화 | ✅ (DSM 7.2+, 매일 자정 새 이미지 확인) |

**고급 설정**:

- **포트 설정**: 매핑 없음 (외부 노출 불필요)
- **볼륨 설정**: 마운트 없음 (상태 무함)
- **네트워크**: 기본 `bridge`
- **환경 변수**: 4개 입력

| 변수 | 값 |
|---|---|
| `GOLDENQUEENS_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `GOLDENQUEENS_CHAT_ID` | 텔레그램 챗 ID |
| `MARKET_FLOW_RENDER` | `text` |
| `TZ` | `Asia/Seoul` |

**완료** → **적용** → 컨테이너 자동 시작.

---

## 3. 동작 확인

### 3-1. 로그 확인

**Container Manager** → **컨테이너** → `rs-golden-queens` 선택 → **로그** 탭

정상 동작 시 다음과 같이 출력:

```
INFO [scheduler] scheduler started (TZ=Asia/Seoul, misfire_grace=1800s)
INFO [scheduler]   job=daily-kr trigger=cron[day_of_week='mon-fri', hour='18', minute='10']
INFO [scheduler]   job=weekly trigger=cron[day_of_week='mon-fri', hour='18', minute='30']
INFO [scheduler]   job=daily-us trigger=cron[day_of_week='tue-sat', hour='7', minute='0']
INFO [apscheduler.scheduler] Scheduler started
```

### 3-2. 수동 테스트 (Telegram 핑)

**Container Manager** → **컨테이너** → `rs-golden-queens` 선택 → **세부 정보** → **터미널** → **명령 생성**

```
python /app/main.py notify-test
```

Telegram에 `[rs-golden-queens] notify-test ping at ...` 메시지가 도착하면 정상.

다른 명령도 같은 방식으로 즉시 검증:

```
python /app/main.py daily-kr
python /app/main.py daily-us
python /app/main.py weekly
```

### 3-3. 컨테이너 자체 상태

**컨테이너** 탭에서 `rs-golden-queens`의 상태가 **Running**(healthy) — 헬스체크는 1분 주기로 scheduler 프로세스 생존을 확인합니다.

---

## 4. 정기 발화 시각 (KST)

| 작업 | 요일 | 시각 | 비고 |
|---|---|---|---|
| `daily-kr` | 월~금 | 18:10 | 한국장 매매동향 |
| `weekly` | 월~금 | 18:30 | 스크립트가 "이번 주 마지막 거래일"만 발송 |
| `daily-us` | 화~토 | 07:00 | 미국장 마감 요약 (DST 시즌 무관 통합) |

NAS 재부팅 등으로 누락 시 **misfire_grace_time=30분** 이내 자동 보충.

### 스케줄 변경 방법

스케줄은 코드가 아니라 저장소 최상위의 **`schedule.toml`** 파일에 정의됩니다.

```toml
[[job]]
id = "daily-kr"
command = "daily-kr"
day_of_week = "mon-fri"
hour = 18
minute = 10
```

변경 절차:
1. `schedule.toml` 수정 + 커밋 + push
2. `v*` 태그 푸시 → GitHub Actions 자동 빌드 → Docker Hub
3. NAS 자동 업데이트 또는 §5의 수동 업데이트로 반영

지원 필드: `id`, `command`, `day_of_week`, `hour`, `minute`, `description`(선택), `env`(선택, 작업별 환경변수).

---

## 5. 업데이트 흐름

### 5-1. 자동 업데이트 (권장)

DSM 7.2+의 Container Manager는 매일 자정 새 이미지를 확인. `latest` 태그가 갱신되어 있으면 자동으로 컨테이너 재생성 → 재시작.

### 5-2. 수동 업데이트

**Container Manager** → **이미지** → `allieus/rs-golden-queens` 선택 → **다운로드** (새 버전 받기) → **컨테이너** 탭에서 `rs-golden-queens` 선택 → **작업** → **재설정**.

---

## 6. GitHub Actions schedule 정리

NAS 운영이 1주일 이상 안정적으로 검증되면 별도 PR로 `.github/workflows/flow-*.yml`의 `schedule` 블록 제거. `workflow_dispatch`는 비상용으로 유지.

---

## 7. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| 이미지 검색 실패 | 사용자명 오타 또는 Docker Hub 저장소가 private | Docker Hub에서 저장소가 public인지 확인 |
| GitHub Actions에서 `denied: requested access to the resource is denied` | `DOCKERHUB_TOKEN` 권한 부족 | Access Token을 **Read & Write** 권한으로 재발급 |
| 컨테이너 즉시 종료 | 필수 환경변수 누락 | 로그에 "필수 환경변수 누락" 메시지 확인 후 §2-2 환경변수 점검 |
| Telegram 미발송 | 토큰/챗ID 오류 또는 봇 차단 | `notify-test`로 분리 진단 |
| KST가 아닌 다른 시각 발화 | TZ 미설정 | 환경변수 `TZ=Asia/Seoul` 확인 |
| 헬스체크 unhealthy | scheduler 프로세스 사망 | 로그 확인 후 컨테이너 재시작 |

---

# 부록 A. 외부 모니터링 추가 (선택, 권장)

NAS 자체가 다운되면 위 구성은 감지 불가. [healthchecks.io](https://healthchecks.io) 같은 외부 모니터링으로 보완 가능.

1. healthchecks.io에 4개 check 생성 (cron schedule 동일하게 설정)
2. 발급받은 ping URL을 환경변수로 추가:

| 변수 | 값 |
|---|---|
| `HC_DAILY_KR` | `https://hc-ping.com/<uuid>` |
| `HC_DAILY_US` | `https://hc-ping.com/<uuid>` |
| `HC_WEEKLY` | `https://hc-ping.com/<uuid>` |

3. `scheduler.py`의 `run_command()`에 ping 호출 추가 (별도 PR 필요)

예정 시각에 ping이 안 오면 healthchecks.io가 메일/Slack/Telegram으로 알림.

---

# 부록 B. 기존 방식 (`nas/run.sh` + DSM Task Scheduler)

상시 컨테이너 방식 대신, 매 실행 시 git pull + pip install + main.py 실행하는 구성도 유지됩니다. 차이는 다음과 같습니다.

| 항목 | 상시 컨테이너 (본문) | nas/run.sh (이 부록) |
|---|---|---|
| 코드 갱신 반영 | 이미지 자동 업데이트 (일 1회) | git pull (매 실행 시) |
| NAS에 만들 파일 | 0개 | 6개 (.env, scheduler.sh, 4 디렉터리) |
| 스케줄러 | 컨테이너 내부 APScheduler | DSM Task Scheduler |
| 적합한 경우 | 일반적인 운영 | 환경 변수 변경이 잦거나 commit 단위로 즉시 반영하고 싶을 때 |

자세한 셋업은 `nas/run.sh`의 헤더 주석을 참고하세요. (이 부록은 의도적으로 간략화)
