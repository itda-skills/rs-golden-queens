import { notFound } from "next/navigation";
import {
  Card,
  Container,
  HolidayNotice,
  SourceList,
} from "@/components/Layout";
import { UsSectionTable } from "@/components/Tables";
import { HBarChart } from "@/components/BarChart";
import { PrevNext } from "@/components/PrevNext";
import { InfoTooltip } from "@/components/InfoTooltip";
import { adjacent } from "@/lib/adjacent";
import { CARD_INFO } from "@/lib/card-info";
import { getIndex, getUsSnapshot } from "@/lib/data";
import { longDate, shortDateWeekday } from "@/lib/format";

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
  const [snap, index] = await Promise.all([getUsSnapshot(date), getIndex()]);
  if (!snap) notFound();

  const { prev, next } = adjacent(index?.us ?? [], date);
  const p = snap.payload;
  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">🇺🇸 미국장 마감</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-4">
        {longDate(snap.date)}
      </p>

      <PrevNext
        prev={prev ? { href: `/us/${prev}`, label: shortDateWeekday(prev) } : null}
        next={next ? { href: `/us/${next}`, label: shortDateWeekday(next) } : null}
      />

      {snap.is_holiday ? (
        <HolidayNotice message={snap.message} />
      ) : (
        p && (
          <>
            <Card
              title="주요 지수"
              subtitle="종가 / 등락"
              info={<InfoTooltip {...CARD_INFO.usIndices} />}
            >
              <UsSectionTable section={p.indices} />
            </Card>
            <Card
              title="변동성·꼬리위험"
              subtitle="종가 / 등락"
              info={<InfoTooltip {...CARD_INFO.usVolatility} />}
            >
              <UsSectionTable section={p.volatility} />
            </Card>
            <Card
              title="위험선호 (Risk On/Off)"
              info={<InfoTooltip {...CARD_INFO.usRisk} />}
            >
              <UsSectionTable section={p.risk_onoff} />
            </Card>
            <Card
              title="매크로"
              subtitle="금리·환율·원자재"
              info={<InfoTooltip {...CARD_INFO.usMacro} />}
            >
              <UsSectionTable section={p.macro} />
            </Card>
            <Card
              title="섹터 (S&P 11)"
              subtitle="등락 기준 정렬"
              info={<InfoTooltip {...CARD_INFO.usSectors} />}
            >
              <HBarChart
                data={Object.values(p.sectors)
                  .filter(Boolean)
                  .map((q) => ({ label: q.label, value: q.pct }))
                  .sort((a, b) => b.value - a.value)}
                ariaLabel="S&P 11 섹터 등락"
              />
            </Card>
            <Card
              title="워치 ETF"
              subtitle="거래량강도 = 당일/5일평균 (×1.5↑ 거래 쏠림)"
              info={<InfoTooltip {...CARD_INFO.usWatch} />}
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
