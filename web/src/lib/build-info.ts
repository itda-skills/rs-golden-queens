// 배포 빌드 정보 — 빌드 타임에 1회 평가된다.
// /deploy 페이지가 정적 프리렌더되므로, 이 값은 `next build` 가 도는 환경의
// git HEAD = 실제 배포된 커밋을 가리킨다. 런타임에 다시 읽지 않는다.
//
// 데이터 출처 우선순위:
//   - 커밋 해시: git → Vercel 시스템 env(VERCEL_GIT_COMMIT_SHA) 폴백
//   - 커밋 시각: git committer date(%cI, 타임존 오프셋 포함). git 불가 시 폴백 없음(null)
// 서버 전용. 클라이언트 컴포넌트에서 import 하지 말 것(child_process 포함).

import { execSync } from "node:child_process";

export interface BuildInfo {
  /** 전체 커밋 해시 (없으면 null) */
  sha: string | null;
  /** 표시용 짧은 해시 (앞 7자, 없으면 null) */
  shortSha: string | null;
  /** 커밋 시각 ISO 8601 (타임존 오프셋 포함, 없으면 null) */
  committedISO: string | null;
}

function git(args: string): string | null {
  try {
    return execSync(`git ${args}`, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

function read(): BuildInfo {
  // 해시 + committer date 를 한 번에. 탭 구분.
  const line = git("log -1 --format=%H%x09%cI");
  let sha: string | null = null;
  let committedISO: string | null = null;
  if (line) {
    const [h, iso] = line.split("\t");
    sha = h || null;
    committedISO = iso || null;
  }
  // git 이 막힌 환경(예: .git 부재) 폴백 — Vercel 은 시스템 env 로 해시를 노출한다.
  if (!sha) sha = process.env.VERCEL_GIT_COMMIT_SHA || null;

  return {
    sha,
    shortSha: sha ? sha.slice(0, 7) : null,
    committedISO,
  };
}

export const BUILD_INFO: BuildInfo = read();

const _KST_PARTS = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  weekday: "short",
});

// ISO 8601(오프셋 포함) → "2026-06-02 (월) 14:30:00 KST"
export function formatKST(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const p = Object.fromEntries(
    _KST_PARTS.formatToParts(d).map((x) => [x.type, x.value]),
  );
  return `${p.year}-${p.month}-${p.day} (${p.weekday}) ${p.hour}:${p.minute}:${p.second} KST`;
}
