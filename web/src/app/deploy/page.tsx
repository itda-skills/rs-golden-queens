import type { Metadata } from "next";
import { Container, Card } from "@/components/Layout";
import { BUILD_INFO, formatKST } from "@/lib/build-info";

// nav 에는 노출하지 않는 페이지(Layout 의 NAV_LINKS 미등록). 직접 URL 로만 접근.
// 빌드 타임 git HEAD = 배포된 커밋을 정적으로 박아 보여준다.
export const metadata: Metadata = {
  title: "배포 정보",
  description: "현재 배포된 사이트의 마지막 커밋 해시와 커밋 시각(KST).",
  robots: { index: false, follow: false },
};

export default function DeployPage() {
  const { sha, shortSha, committedISO } = BUILD_INFO;
  const committedKST = formatKST(committedISO);

  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">배포 정보</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-5 leading-relaxed">
        현재 배포된 사이트가 빌드된 시점의 마지막 커밋입니다.
      </p>

      <Card title="마지막 커밋">
        <dl className="text-sm space-y-3">
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400 dark:text-neutral-500 mb-1">
              커밋 해시
            </dt>
            <dd className="font-mono break-all text-neutral-800 dark:text-neutral-200">
              {sha ? (
                <>
                  <span className="font-semibold">{shortSha}</span>
                  <span className="text-neutral-400 dark:text-neutral-500">
                    {" "}
                    ({sha})
                  </span>
                </>
              ) : (
                "–"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400 dark:text-neutral-500 mb-1">
              커밋 시각 (KST)
            </dt>
            <dd className="font-mono text-neutral-800 dark:text-neutral-200">
              {committedKST ?? "–"}
            </dd>
          </div>
        </dl>
      </Card>
    </Container>
  );
}
