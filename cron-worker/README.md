# rs-golden-queens-cron

기존 **NAS 작업 스케줄러**가 하던 GitHub Actions `workflow_dispatch` 발사를 대체하는
Cloudflare Worker. 홈 네트워크 의존을 없애 트리거 신뢰성을 올린다.

이 워커는 **발사 장치일 뿐**이다. 실제 데이터 수집·텔레그램 발송·웹 발행은 그대로
GitHub Actions(`flow-*.yml`)에서 일어난다. DST/휴장/마지막 거래일 판정도 봇 내부가 한다 —
워커는 "무슨 요일 몇 시"만 안다.

## ⚠️ 전환이지 이중화가 아니다

텔레그램 발송은 비멱등이고 "오늘 이미 보냈는지" 게이트가 없다. **NAS 와 이 워커를 동시에
켜두면 같은 워크플로가 두 번 발사되어 중복 발송된다.** 검증이 끝나면 NAS 쪽 dispatch 작업을
반드시 끈다(아래 7단계).

## 스케줄 (UTC ↔ KST)

| 워크플로 | KST | UTC cron |
|---|---|---|
| `flow-kr.yml` | 월~금 18:10 | `10 9 * * mon-fri` |
| `flow-us.yml` | 화~토 07:00 | `0 22 * * mon-fri` (UTC 월~금 22:00) |
| `flow-weekly.yml` | 월~금 18:15 | `15 9 * * mon-fri` (내부 게이트가 마지막 거래일만 통과) |
| `flow-calendar.yml` | 일 09:00 (주 1회) | `0 0 * * sun` |

크론을 바꾸려면 `wrangler.toml` 의 `[triggers].crons` 와 `src/index.js` 의 `CRON_TO_WORKFLOW`
**양쪽을** 동일하게 고친다.

> ⚠️ **Cloudflare 요일은 `1=일요일 … 7=토요일`** 로 표준 cron(`0=일`)과 다르다. 숫자로 쓰면
> 하루씩 밀리고 `0`은 `invalid cron string` 에러가 난다. 요일은 약어(`mon-fri`, `sun`)로 쓴다.

## 사전 준비

1. **Cloudflare 계정** (무료 플랜으로 충분 — Cron Triggers 포함).
2. **Node 18+** 와 npm.
3. **GitHub Fine-grained PAT**
   - Repository access: `itda-skills/rs-golden-queens` 만 선택
   - Permissions → Repository → **Actions: Read and write** (이것만 있으면 됨)
   - Classic PAT 보다 권한이 좁아 안전하다. 만료일은 캘린더에 적어 두고 갱신.

## 배포

```bash
cd cron-worker
npm install
npx wrangler login                 # 브라우저로 Cloudflare 인증
npx wrangler secret put GH_TOKEN   # 위에서 만든 PAT 붙여넣기 (Enter)
npx wrangler deploy
```

`OWNER`/`REPO`/`REF` 는 `wrangler.toml` 의 `[vars]` 에 이미 들어 있다(`itda-skills` /
`rs-golden-queens` / `main`). 다르면 거기서 수정한다.

## 검증

배포 후 실제 정시를 기다리지 않고 확인하는 방법:

- **Cloudflare 대시보드** → Workers & Pages → `rs-golden-queens-cron` → Triggers 탭에서
  등록된 cron 4개 확인. "Trigger Cron" 으로 수동 발사 후 GitHub Actions 탭에 run 이 뜨는지 본다.
- **로그 실시간 확인**: `npm run tail` (= `wrangler tail`). 발사 시 `[dispatch] flow-kr.yml OK (204)`
  같은 줄이 보인다. 실패면 상태코드·본문이 `console.error` 로 남는다.
- **로컬 테스트**(GitHub 에 실제로 쏨, PAT 필요):
  ```bash
  cp .dev.vars.example .dev.vars   # .dev.vars 에 실제 PAT 기입
  npm run dev                      # 별도 터미널 유지
  curl "http://localhost:8787/__scheduled?cron=10+9+*+*+1-5"   # flow-kr 발사
  ```
  GitHub Actions 탭에 해당 워크플로 run 이 생기면 정상. (운영 채널로 실제 발송되니 주의 —
  테스트만 하려면 `flow-*-test.yml` 로 매핑을 잠시 바꾸거나 발송 대상 채널을 확인할 것.)

## 7단계: NAS 끄기 (중복 발송 방지)

검증이 끝나면 **NAS 작업 스케줄러에서 dispatch 작업들을 비활성화**한다. 그래야 워커와 NAS 가
같은 워크플로를 동시에 쏘는 중복 발송이 없다.

## 수동 트리거 (로컬 CLI)

정시 트리거와 별개로 손으로 워크플로를 쏠 때 쓴다(테스트·임시 발사). dispatch 로직은
`src/dispatch.js` 를 워커와 공유한다 — 토큰만 환경변수로 주입한다.

```bash
# 별칭(kr / us / weekly / calendar) 또는 파일명(flow-kr.yml) 사용
GITHUB_PAT=github_pat_xxx node scripts/trigger.mjs kr
GITHUB_PAT=github_pat_xxx node scripts/trigger.mjs flow-weekly.yml
GITHUB_PAT=github_pat_xxx node scripts/trigger.mjs kr us weekly   # 여러 개 순차
```

토큰은 `GITHUB_PAT`(또는 `GH_TOKEN`) 환경변수로만 받는다 — **인자나 코드에 토큰을 넣지 않는다.**
`OWNER`/`REPO`/`REF` 도 환경변수로 덮어쓸 수 있고 기본값은 이 저장소다. 운영 채널로 실제
발송되니 테스트만 하려면 `flow-*-test.yml` 을 직접 지정한다.

## 운영 메모

- 무료 플랜 한도(하루 10만 요청)에 한참 못 미친다 — cron 발사는 하루 몇 번뿐.
- 단일 트리거다. 누락이 걱정되면 `wrangler tail` 로그나 "발송 안 됨" 알림으로 감지한다.
  완전 이중화(백업 트리거)는 봇에 "오늘 이미 발송" 멱등 게이트를 먼저 넣어야 안전하다.
- 토큰·시크릿은 절대 커밋하지 않는다. `.dev.vars` 는 `.gitignore` 에 있다.
