import { notFound } from "next/navigation";
import {
  Card,
  Container,
  HolidayNotice,
  SourceList,
} from "@/components/Layout";
import {
  ForeignInstTable,
  InvestorFlowTable,
  InvestorDailyTable,
  MoneyFlowSellTable,
  MoneyFlowTable,
  ProgramTable,
} from "@/components/Tables";
import { HBarChart } from "@/components/BarChart";
import { InvestorTrendCharts } from "@/components/TrendCharts";
import { PrevNext } from "@/components/PrevNext";
import { InfoTooltip } from "@/components/InfoTooltip";
import { adjacent } from "@/lib/adjacent";
import { CARD_INFO } from "@/lib/card-info";
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
            <Card
              title="코스피 투자자별 순매수"
              subtitle="억원"
              info={<InfoTooltip {...CARD_INFO.krKospiInvestors} />}
            >
              <InvestorFlowTable flow={snap.payload.kospi} />
            </Card>
            <Card
              title="코스닥 투자자별 순매수"
              subtitle="억원"
              info={<InfoTooltip {...CARD_INFO.krKosdaqInvestors} />}
            >
              <InvestorFlowTable flow={snap.payload.kosdaq} />
            </Card>
            <Card
              title="코스피 프로그램매매"
              subtitle="억원"
              info={<InfoTooltip {...CARD_INFO.krProgram} />}
            >
              <ProgramTable flow={snap.payload.kospi} />
            </Card>
            {snap.payload.sectors && snap.payload.sectors.length > 0 && (
              <Card
                title="섹터 ETF"
                subtitle="당일 등락률 · 거래량강도 (KIS)"
                info={
                  <InfoTooltip tooltip="KIS 제공 섹터 대표 ETF의 당일 등락률과 거래량강도. '가격이 올랐다'이지 '그 섹터로 순매수가 들어왔다'가 아니다. 🔥(×1.5↑)는 거래량 급증 표시일 뿐 방향·권유가 아니다." />
                }
              >
                <HBarChart
                  data={snap.payload.sectors.map((s) => ({
                    label: s.label,
                    value: s.pct,
                    note:
                      s.vol_ratio != null
                        ? `×${s.vol_ratio.toFixed(2)}${
                            s.vol_ratio >= 1.5 ? " 🔥" : ""
                          }`
                        : undefined,
                  }))}
                  ariaLabel="KR 섹터 ETF 등락"
                />
              </Card>
            )}
            {snap.payload.money_flow &&
              (snap.payload.money_flow.etfs.length > 0 ||
                snap.payload.money_flow.stocks.length > 0) && (
                <Card
                  title="오늘의 수급 Top"
                  subtitle="외국인·기관 순매수 (억원 · 환산 추정)"
                  info={
                    <InfoTooltip tooltip="외국인·기관의 당일 순매수 상위 종목. 금액은 순매수 '수량'을 대표가격(고+저+종)/3으로 환산한 추정치(억원)다. 외인·기관이 같은 방향이면 🔥. 규모일 뿐 향후 방향·권유가 아니다." />
                  }
                >
                  <MoneyFlowTable mf={snap.payload.money_flow} />
                </Card>
              )}
            {snap.payload.money_flow &&
              ((snap.payload.money_flow.etfs_sell?.length ?? 0) > 0 ||
                (snap.payload.money_flow.stocks_sell?.length ?? 0) > 0) && (
                <Card
                  title="외인·기관 순매도 상위"
                  subtitle="외국인·기관 합산이 음수인 종목 (억원 · 환산 추정)"
                  info={
                    <InfoTooltip tooltip="외국인·기관이 당일 가장 많이 순매도한(합산 음수) 종목. 금액은 순매수 '수량'을 대표가격(고+저+종)/3으로 환산한 추정치(억원)다. 순매수 Top만 보면 놓치는 순매도를 함께 보여줄 뿐, 향후 방향·권유가 아니다." />
                  }
                >
                  <MoneyFlowSellTable mf={snap.payload.money_flow} />
                </Card>
              )}
            {snap.payload.foreign_inst &&
              ((snap.payload.foreign_inst.buy?.length ?? 0) > 0 ||
                (snap.payload.foreign_inst.sell?.length ?? 0) > 0) && (
                <Card
                  title="외국인·기관 가집계"
                  subtitle="장중 추정 · 증권사 입력 누계 (억원)"
                  info={
                    <InfoTooltip tooltip="증권사가 장중 집계·입력한 외국인·기관 순매수/순매도 누계(최종 ~14:30 추정치, 확정 아님). 금액(억원) 사실값일 뿐 향후 방향·권유가 아니다." />
                  }
                >
                  <ForeignInstTable fi={snap.payload.foreign_inst} />
                </Card>
              )}
            <Card
              title="코스피 일별 추이"
              subtitle="최근 거래일 (억원)"
              info={<InfoTooltip {...CARD_INFO.krDaily} />}
            >
              <InvestorTrendCharts rows={snap.payload.kospi_daily} />
            </Card>
            <Card
              title="일별 상세"
              subtitle="외국인 / 기관 / 개인 (억원)"
              info={<InfoTooltip {...CARD_INFO.krDaily} />}
            >
              <InvestorDailyTable rows={snap.payload.kospi_daily} />
            </Card>
            {snap.payload.kosdaq_daily && snap.payload.kosdaq_daily.length > 0 && (
              <>
                <Card
                  title="코스닥 일별 추이"
                  subtitle="최근 거래일 (억원)"
                  info={<InfoTooltip {...CARD_INFO.krDaily} />}
                >
                  <InvestorTrendCharts rows={snap.payload.kosdaq_daily} />
                </Card>
                <Card
                  title="코스닥 일별 상세"
                  subtitle="외국인 / 기관 / 개인 (억원)"
                  info={<InfoTooltip {...CARD_INFO.krDaily} />}
                >
                  <InvestorDailyTable rows={snap.payload.kosdaq_daily} />
                </Card>
              </>
            )}
            <SourceList sources={snap.sources} />
          </>
        )
      )}
    </Container>
  );
}
