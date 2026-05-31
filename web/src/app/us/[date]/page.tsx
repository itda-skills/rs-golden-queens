import { notFound } from "next/navigation";
import {
  Card,
  Container,
  HolidayNotice,
  SourceList,
} from "@/components/Layout";
import { RiskAxes, UsSectionTable, VixTermStructure } from "@/components/Tables";
import { HBarChart } from "@/components/BarChart";
import { PrevNext } from "@/components/PrevNext";
import { InfoTooltip } from "@/components/InfoTooltip";
import { adjacent } from "@/lib/adjacent";
import { CARD_INFO } from "@/lib/card-info";
import { getIndex, getUsSnapshot } from "@/lib/data";
import { longDate, shortDateWeekday } from "@/lib/format";
import type { UsPayload, UsQuote } from "@/lib/types";

// US 섹터: 등락률 막대 + 우측 note 에 ^GSPC 대비 상대강도(%p)·거래량강도(×, 🔥) 병기.
// 모두 발행 스냅샷 값에서 파생(상대치 = 섹터pct − S&P500pct). 등락 내림차순.
function usSectorBars(p: UsPayload) {
  const sp = p.indices?.["^GSPC"]?.pct ?? null;
  return Object.values(p.sectors)
    .filter((q): q is UsQuote => q != null)
    .map((q) => {
      const rel = sp != null && q.pct != null ? q.pct - sp : null;
      const relStr = rel != null ? `vs${rel >= 0 ? "+" : ""}${rel.toFixed(2)}` : "";
      const vr = q.vol_ratio;
      const vrStr = vr != null ? `×${vr.toFixed(2)}${vr >= 1.5 ? "🔥" : ""}` : "";
      return {
        label: q.label,
        value: q.pct,
        note: [relStr, vrStr].filter(Boolean).join(" "),
      };
    })
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
}

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
              <VixTermStructure volatility={p.volatility} />
            </Card>
            <Card
              title="위험선호 (Risk On/Off)"
              subtitle="HYG−IEF 갭 · VIX·달러·금이 가리키는 쪽 (종합 판단 아님)"
              info={<InfoTooltip {...CARD_INFO.usRisk} />}
            >
              <RiskAxes
                riskOnoff={p.risk_onoff}
                volatility={p.volatility}
                macro={p.macro}
              />
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
              subtitle="등락 정렬 · vs S&P500 · 거래량강도"
              info={<InfoTooltip {...CARD_INFO.usSectors} />}
            >
              <HBarChart
                data={usSectorBars(p)}
                ariaLabel="S&P 11 섹터 등락 (vs S&P500 · 거래량강도)"
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
