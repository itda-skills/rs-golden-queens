import { notFound } from "next/navigation";
import { Card, Container, SourceList } from "@/components/Layout";
import { KospiDailyTable } from "@/components/Tables";
import { KospiTrendCharts, Watch5dChart } from "@/components/TrendCharts";
import { PrevNext, adjacent } from "@/components/PrevNext";
import { arrow, colorClass, signedPct } from "@/lib/format";
import { getIndex, getWeeklySnapshot } from "@/lib/data";

export const revalidate = 600;

export async function generateStaticParams() {
  const index = await getIndex();
  return (index?.weekly ?? []).map((week) => ({ week }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ week: string }>;
}) {
  const { week } = await params;
  return { title: `주간 ${week}` };
}

export default async function WeeklyDetail({
  params,
}: {
  params: Promise<{ week: string }>;
}) {
  const { week } = await params;
  const [snap, index] = await Promise.all([getWeeklySnapshot(week), getIndex()]);
  if (!snap || !snap.payload) notFound();

  const { prev, next } = adjacent(index?.weekly ?? [], week);
  const watch = [...snap.payload.watch_5d].sort((a, b) => b.pct_5d - a.pct_5d);

  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">📅 주간 리포트</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-4">
        {snap.week} (기준일 {snap.date})
      </p>

      <PrevNext
        prev={prev ? { href: `/weekly/${prev}`, label: prev } : null}
        next={next ? { href: `/weekly/${next}`, label: next } : null}
      />

      <Card title="코스피 일별 추이" subtitle="이번 주 거래일 (억원)">
        <KospiTrendCharts rows={snap.payload.kospi_daily} />
      </Card>

      <Card title="일별 상세" subtitle="외국인 / 기관 / 개인 (억원)">
        <KospiDailyTable rows={snap.payload.kospi_daily} />
      </Card>

      <Card title="워치 ETF 5거래일 누적 등락">
        <div className="mb-4">
          <Watch5dChart items={snap.payload.watch_5d} />
        </div>
        <table className="w-full text-sm tabular-nums">
          <tbody>
            {watch.map((w) => (
              <tr
                key={w.ticker}
                className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0"
              >
                <td className="py-1.5 text-neutral-700 dark:text-neutral-200">
                  {w.ticker}
                </td>
                <td
                  className={`py-1.5 text-right font-medium ${colorClass(w.pct_5d)}`}
                >
                  {signedPct(w.pct_5d)}{" "}
                  <span className="text-xs">{arrow(w.pct_5d)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <SourceList sources={snap.sources} />
    </Container>
  );
}
