#!/usr/bin/env node
/**
 * 로컬 수동 트리거 CLI.
 * NAS/CF 정시 트리거와 별개로, 손으로 워크플로를 쏠 때 쓴다(테스트·임시 발사).
 *
 *   GITHUB_PAT=github_pat_xxx node scripts/trigger.mjs kr
 *   GITHUB_PAT=github_pat_xxx node scripts/trigger.mjs flow-weekly.yml
 *   GITHUB_PAT=github_pat_xxx node scripts/trigger.mjs kr us weekly   # 여러 개 순차
 *
 * 토큰은 환경변수로만 받는다(GITHUB_PAT 또는 GH_TOKEN). 절대 인자/코드로 받지 않는다.
 * owner/repo/ref 는 환경변수로 덮어쓸 수 있고, 기본값은 이 저장소(origin)다.
 */
import { dispatchWorkflow, WORKFLOWS } from "../src/dispatch.js";

const OWNER = process.env.OWNER || "itda-skills";
const REPO = process.env.REPO || "rs-golden-queens";
const REF = process.env.REF || "main";
const token = process.env.GITHUB_PAT || process.env.GH_TOKEN;

const aliases = Object.keys(WORKFLOWS).join(", ");

function resolve(arg) {
  if (WORKFLOWS[arg]) return WORKFLOWS[arg]; // 별칭: kr, us, weekly, calendar
  if (arg.endsWith(".yml")) {
    // 파일명 직접 지정: 알려진 것이면 라벨을 붙이고, 아니면 파일명을 라벨로.
    const hit = Object.values(WORKFLOWS).find((w) => w.file === arg);
    return hit || { file: arg, label: arg };
  }
  return null;
}

const args = process.argv.slice(2);

if (!token) {
  console.error("✖ 토큰 없음. GITHUB_PAT 또는 GH_TOKEN 환경변수를 설정하세요.");
  console.error(`  예: GITHUB_PAT=github_pat_xxx node scripts/trigger.mjs kr`);
  process.exit(1);
}
if (args.length === 0) {
  console.error(`사용법: node scripts/trigger.mjs <별칭|파일.yml> [...]`);
  console.error(`별칭: ${aliases}`);
  process.exit(1);
}

let failed = 0;
for (const arg of args) {
  const wf = resolve(arg);
  if (!wf) {
    console.error(`✖ 알 수 없는 워크플로: "${arg}" (별칭: ${aliases})`);
    failed++;
    continue;
  }
  process.stdout.write(`▶ ${wf.label} (${wf.file}) 트리거 중... `);
  try {
    const r = await dispatchWorkflow({ token, owner: OWNER, repo: REPO, ref: REF, workflow: wf.file });
    console.log(`OK (${r.status})`);
  } catch (e) {
    console.log("실패");
    console.error(`  ${e.message}`);
    failed++;
  }
}

process.exit(failed ? 1 : 0);
