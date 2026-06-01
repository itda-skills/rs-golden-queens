/**
 * rs-golden-queens 트리거 워커 (Cloudflare Cron Triggers)
 *
 * 역할: 정시에 GitHub Actions 의 workflow_dispatch 를 발사하는 "발사 장치".
 *       실제 데이터 수집·텔레그램 발송·웹 발행은 GitHub Actions(flow-*.yml)에서 일어난다.
 *       기존 NAS 작업 스케줄러의 dispatch 역할을 대체한다.
 *
 * DST 무관: 트리거는 "무슨 요일 몇 시"만 안다. 휴장/DST/마지막 거래일 판정은
 *           봇 내부(daily_us.py·calendar_utils.py 등)가 한다.
 *
 * 멱등성 주의: 발송은 비멱등이고 "오늘 이미 보냈는지" 게이트가 없다. NAS 와 이 워커를
 *             동시에 켜두면 같은 워크플로가 두 번 발사되어 중복 발송된다. 전환이지 이중화가 아니다.
 *
 * ⚠️ Cloudflare 요일 주의: Cloudflare 의 day-of-week 는 1=일요일 … 7=토요일 이다
 *    (표준 cron 의 0=일 과 다름!). 숫자로 쓰면 하루씩 밀리므로 요일은 약어(mon-fri / sun)로 쓴다.
 *
 * dispatch 로직은 src/dispatch.js 로 분리해 로컬 CLI(scripts/trigger.mjs)와 공유한다.
 */

import { dispatchWorkflow } from "./dispatch.js";

// UTC cron 표현식 → 발사할 워크플로 파일. wrangler.toml 의 [triggers].crons 와 일치해야 한다.
const CRON_TO_WORKFLOW = {
  "10 9 * * mon-fri": "flow-kr.yml", // KST 월~금 18:10
  "0 22 * * mon-fri": "flow-us.yml", // KST 화~토 07:00 (UTC 월~금 22:00)
  "15 9 * * mon-fri": "flow-weekly.yml", // KST 월~금 18:15 (내부 게이트가 마지막 거래일만 통과)
  "0 0 * * sun": "flow-calendar.yml", // KST 일 09:00 (UTC 일 00:00)
};

// event.cron 은 대소문자·공백이 등록값과 달라질 수 있으므로 정규화해서 느슨하게 매칭한다.
const norm = (s) => s.trim().toLowerCase().replace(/\s+/g, " ");
const TABLE = new Map(Object.entries(CRON_TO_WORKFLOW).map(([k, v]) => [norm(k), v]));

export default {
  async scheduled(event, env, ctx) {
    const workflow = TABLE.get(norm(event.cron));
    if (!workflow) {
      console.error(`[scheduled] 매핑 없는 cron: "${event.cron}" — wrangler.toml 과 index.js 불일치`);
      return;
    }
    console.log(`[scheduled] cron="${event.cron}" -> ${workflow}`);
    ctx.waitUntil(
      dispatchWorkflow({
        token: env.GH_TOKEN,
        owner: env.OWNER,
        repo: env.REPO,
        ref: env.REF || "main",
        workflow,
      })
        .then((r) => console.log(`[dispatch] ${r.workflow} OK (${r.status})`))
        .catch((e) => console.error(`[dispatch] ${e.message}`)),
    );
  },

  // 공개 HTTP 엔드포인트: 상태 확인 전용. 트리거 발사는 하지 않는다(공개 URL 오남용 방지).
  async fetch() {
    return new Response(
      "rs-golden-queens cron worker. Dispatch는 cron 스케줄로만 발사된다(HTTP 트리거 없음).\n",
      { status: 200, headers: { "content-type": "text/plain; charset=utf-8" } },
    );
  },
};
