import Link from "next/link";
import { Card, Container } from "@/components/Layout";
import { InvestorFlowTable, UsSectionTable } from "@/components/Tables";
import { getKrSnapshot, getLatest, getUsSnapshot, getWeeklySnapshot } from "@/lib/data";
import { longDate } from "@/lib/format";

export const revalidate = 600;

export default async function HomePage() {
  const latest = await getLatest();

  const kr = latest?.kr ? await getKrSnapshot(latest.kr.date) : null;
  const us = latest?.us ? await getUsSnapshot(latest.us.date) : null;
  const weekly = latest?.weekly ? await getWeeklySnapshot(latest.weekly.week!) : null;

  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">최신 시장 매매동향</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        한국·미국 시장 마감 후 요약. 사실 데이터만 제공합니다.
      </p>

      {kr?.payload && (
        <Card
          title={
            <Link href={`/kr/${kr.date}`} className="hover:underline">
              🇰🇷 코스피 — {longDate(kr.date)}
            </Link>
          }
          subtitle="투자자별 순매수 (억원)"
        >
          <InvestorFlowTable flow={kr.payload.kospi} />
          <Link
            href={`/kr/${kr.date}`}
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline mt-3 inline-block"
          >
            자세히 →
          </Link>
        </Card>
      )}

      {us?.payload && (
        <Card
          title={
            <Link href={`/us/${us.date}`} className="hover:underline">
              🇺🇸 미국 지수 — {longDate(us.date)}
            </Link>
          }
          subtitle="종가 / 등락"
        >
          <UsSectionTable section={us.payload.indices} />
          <Link
            href={`/us/${us.date}`}
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline mt-3 inline-block"
          >
            자세히 →
          </Link>
        </Card>
      )}

      {weekly?.payload && (
        <Card
          title={
            <Link href={`/weekly/${weekly.week}`} className="hover:underline">
              📅 주간 리포트 — {weekly.week}
            </Link>
          }
          subtitle="코스피 누적 + 워치 ETF 5일 등락"
        >
          <Link
            href={`/weekly/${weekly.week}`}
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline inline-block"
          >
            자세히 →
          </Link>
        </Card>
      )}

      {!kr && !us && !weekly && (
        <p className="text-sm text-neutral-500">아직 발행된 데이터가 없습니다.</p>
      )}

      <Link
        href="/calendar"
        className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
      >
        전체 거래일 캘린더 보기 →
      </Link>
    </Container>
  );
}
