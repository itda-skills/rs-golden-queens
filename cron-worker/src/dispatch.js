/**
 * 공유 dispatch 로직.
 * Worker(src/index.js)와 로컬 CLI(scripts/trigger.mjs)가 함께 쓴다.
 *
 * 환경(Worker 시크릿 vs process.env)에 의존하지 않도록 순수 함수로 둔다 —
 * 토큰·owner·repo 는 호출부가 주입한다. 토큰을 이 파일에 하드코딩하지 않는다.
 */

// 워크플로 메타: 별칭 → { file, label }. CLI 사용성과 로그 라벨용.
export const WORKFLOWS = {
  kr: { file: "flow-kr.yml", label: "한국장 매매동향 푸시" },
  us: { file: "flow-us.yml", label: "미국장 마감 푸시" },
  weekly: { file: "flow-weekly.yml", label: "주간 리포트 푸시" },
  calendar: { file: "flow-calendar.yml", label: "거래일 캘린더 발행" },
};

/**
 * GitHub Actions 의 workflow_dispatch 를 1회 발사한다.
 * 성공 시 { workflow, status: 204 } 반환, 실패 시 본문을 담아 throw.
 */
export async function dispatchWorkflow({ token, owner, repo, ref = "main", workflow }) {
  if (!token) throw new Error("토큰 없음 (GH_TOKEN / GITHUB_PAT)");
  if (!owner || !repo) throw new Error("owner/repo 없음");
  if (!workflow) throw new Error("workflow 파일명 없음");

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "rs-golden-queens-cron",
    },
    body: JSON.stringify({ ref }),
  });

  // 성공 시 204 No Content. 실패는 응답 본문을 담아 throw(침묵 종료 금지).
  if (res.status !== 204) {
    const detail = await res.text();
    throw new Error(`dispatch ${workflow} 실패: ${res.status} ${detail}`);
  }
  return { workflow, status: res.status };
}
