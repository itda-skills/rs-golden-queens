import { notFound } from "next/navigation";
import {
  Card,
  Container,
  HolidayNotice,
  SourceList,
} from "@/components/Layout";
import {
  InvestorFlowTable,
  KospiDailyTable,
  ProgramTable,
} from "@/components/Tables";
import { KospiTrendCharts } from "@/components/TrendCharts";
import { PrevNext } from "@/components/PrevNext";
import { adjacent } from "@/lib/adjacent";
import { getIndex, getKrSnapshot } from "@/lib/data";
import { longDate, shortDateWeekday } from "@/lib/format";

export const revalidate = 600;

export async function generateStaticParams() {
  const index = await getIndex();
  return (index?.kr ?? []).map((date) => ({ date }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  return { title: `코스피 ${date}` };
}

export default async function KrDetail({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const [snap, index] = await Promise.all([getKrSnapshot(date), getIndex()]);
  if (!snap) notFound();

  const { prev, next } = adjacent(index?.kr ?? [], date);

  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">🇰🇷 한국장 매매동향</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-4">
        {longDate(snap.date)}
      </p>

      <PrevNext
        prev={prev ? { href: `/kr/${prev}`, label: shortDateWeekday(prev) } : null}
        next={next ? { href: `/kr/${next}`, label: shortDateWeekday(next) } : null}
      />

      {snap.is_holiday ? (
        <HolidayNotice message={snap.message} />
      ) : (
        snap.payload && (
          <>
            <Card title="코스피 투자자별 순매수" subtitle="억원">
              <InvestorFlowTable flow={snap.payload.kospi} />
            </Card>
            <Card title="코스닥 투자자별 순매수" subtitle="억원">
              <InvestorFlowTable flow={snap.payload.kosdaq} />
            </Card>
            <Card title="코스피 프로그램매매" subtitle="억원">
              <ProgramTable flow={snap.payload.kospi} />
            </Card>
            <Card title="코스피 일별 추이" subtitle="최근 거래일 (억원)">
              <KospiTrendCharts rows={snap.payload.kospi_daily} />
            </Card>
            <Card title="일별 상세" subtitle="외국인 / 기관 / 개인 (억원)">
              <KospiDailyTable rows={snap.payload.kospi_daily} />
            </Card>
            <SourceList sources={snap.sources} />
          </>
        )
      )}
    </Container>
  );
}
