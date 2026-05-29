import { notFound } from "next/navigation";
import {
  Card,
  Container,
  HolidayNotice,
  SourceList,
} from "@/components/Layout";
import { UsSectionTable } from "@/components/Tables";
import { getIndex, getUsSnapshot } from "@/lib/data";
import { longDate } from "@/lib/format";

export const revalidate = 600;

export async function generateStaticParams() {
  const index = await getIndex();
  return (index?.us ?? []).map((date) => ({ date }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  return { title: `미국장 ${date}` };
}

export default async function UsDetail({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const snap = await getUsSnapshot(date);
  if (!snap) notFound();

  const p = snap.payload;
  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">🇺🇸 미국장 마감</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
        {longDate(snap.date)}
      </p>

      {snap.is_holiday ? (
        <HolidayNotice message={snap.message} />
      ) : (
        p && (
          <>
            <Card title="주요 지수" subtitle="종가 / 등락">
              <UsSectionTable section={p.indices} />
            </Card>
            <Card title="변동성·꼬리위험" subtitle="종가 / 등락">
              <UsSectionTable section={p.volatility} />
            </Card>
            <Card title="위험선호 (Risk On/Off)">
              <UsSectionTable section={p.risk_onoff} />
            </Card>
            <Card title="매크로" subtitle="금리·환율·원자재">
              <UsSectionTable section={p.macro} />
            </Card>
            <Card title="섹터 (S&P 11)" subtitle="등락 기준 정렬">
              <UsSectionTable section={p.sectors} sortByPct />
            </Card>
            <Card
              title="워치 ETF"
              subtitle="거래량강도 = 당일/5일평균 (×1.5↑ 자금 쏠림)"
            >
              <UsSectionTable section={p.watch} showVol sortByPct />
            </Card>
            <SourceList sources={snap.sources} />
          </>
        )
      )}
    </Container>
  );
}
