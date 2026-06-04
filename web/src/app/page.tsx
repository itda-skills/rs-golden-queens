import Link from "next/link";
import { BarChart, HBarChart } from "@/components/BarChart";
import { Card, Container } from "@/components/Layout";
import { MoodStrip } from "@/components/MoodStrip";
import { UsSectionTable } from "@/components/Tables";
import { Watch5dChart } from "@/components/TrendCharts";
import {
  getKrSnapshot,
  getLatest,
  getUsSnapshot,
  getWeeklySnapshot,
} from "@/lib/data";
import { shortDate, shortDateWeekday } from "@/lib/format";

export const revalidate = 600;

const moreLink =
  "mt-3 inline-block text-xs text-blue-600 dark:text-blue-400 hover:underline";

export default async function HomePage() {
  const latest = await getLatest();

  const kr = latest?.kr ? await getKrSnapshot(latest.kr.date) : null;
  const us = latest?.us ? await getUsSnapshot(latest.us.date) : null;
  const weekly = latest?.weekly
    ? await getWeeklySnapshot(latest.weekly.week!)
    : null;

  const kp = kr?.payload ?? null;
  const up = us?.payload ?? null;
  const wp = weekly?.payload ?? null;

  // A: 한국 외국인 일별 순매수 — 코스피·코스닥. 스냅샷은 최신순이라 시간순(오래된 것
  // 왼쪽)으로 뒤집는다. 코스닥 일별은 2026-06-02 발송분부터 제공(없으면 코스피만 표시).
  const toForeignBars = (rows: { date: string; foreign: number }[]) =>
    rows
      .slice()
      .reverse()
      .map((r) => ({ label: shortDate(r.date), value: r.foreign }));
  const kospiForeign = toForeignBars(kp?.kospi_daily ?? []);
  const kosdaqForeign = toForeignBars(kp?.kosdaq_daily ?? []);

  // B: 미국 섹터 등락 랭킹 — pct 내림차순, note=거래량강도(×, 🔥). vs S&P 상대강도는 상세에.
  const usSectors = up
    ? Object.values(up.sectors)
        .filter((q): q is NonNullable<typeof q> => q != null)
        .map((q) => ({
          label: q.label,
          value: q.pct,
          note:
            q.vol_ratio != null
              ? `×${q.vol_ratio.toFixed(2)}${q.vol_ratio >= 1.5 ? " 🔥" : ""}`
              : undefined,
        }))
        .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
    : [];

  // D: 주간 워치 ETF 5거래일 누적 등락
  const watch = wp?.watch_5d ?? [];

  // A: 한국 외국인 일별(코스피 + 코스닥)
  const krCard = kr && (kospiForeign.length > 0 || kosdaqForeign.length > 0) && (
    <Card
      title={
        <Link href={`/kr/${kr.date}`} className="hover:underline">
          🇰🇷 외국인 일별 순매수 — 코스피·코스닥
        </Link>
      }
      subtitle="최근 거래일 (억원)"
      className="!mb-0"
    >
      {kospiForeign.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-neutral-500 dark:text-neutral-400">
            코스피
          </div>
          <BarChart data={kospiForeign} ariaLabel="코스피 외국인 일별 순매수 추이" />
        </div>
      )}
      {kosdaqForeign.length > 0 && (
        <div className="mt-4">
          <div className="mb-1 text-xs text-neutral-500 dark:text-neutral-400">
            코스닥
          </div>
          <BarChart
            data={kosdaqForeign}
            ariaLabel="코스닥 외국인 일별 순매수 추이"
          />
        </div>
      )}
      <Link href={`/kr/${kr.date}`} className={moreLink}>
        코스피·코스닥 전체 추이 (기관·개인 포함) 자세히 →
      </Link>
    </Card>
  );

  // C: 미국 지수 4종(단일일 표 — US 일별 시계열은 스냅샷에 없어 상세로 위임)
  const usIndexCard = us && up && (
    <Card
      title={
        <Link href={`/us/${us.date}`} className="hover:underline">
          🇺🇸 미국 지수
        </Link>
      }
      subtitle="종가 / 등락 · 일별 추이는 상세에"
      className="!mb-0"
    >
      <UsSectionTable section={up.indices} />
      <Link href={`/us/${us.date}`} className={moreLink}>
        미국장 자세히 →
      </Link>
    </Card>
  );

  // B: 미국 섹터 11 등락 랭킹
  const usSectorCard = us && usSectors.length > 0 && (
    <Card
      title={
        <Link href={`/us/${us.date}`} className="hover:underline">
          🇺🇸 미국 섹터 등락 (S&P 11)
        </Link>
      }
      subtitle="당일 등락률 · 거래량강도"
      className="!mb-0"
    >
      <HBarChart data={usSectors} ariaLabel="미국 섹터 등락 랭킹" />
      <Link href={`/us/${us.date}`} className={moreLink}>
        미국장 전체 (지수·변동성·위험선호) 자세히 →
      </Link>
    </Card>
  );

  // D: 주간 워치 ETF 5일 누적
  const weeklyCard = weekly && watch.length > 0 && (
    <Card
      title={
        <Link href={`/weekly/${weekly.week}`} className="hover:underline">
          📅 주간 워치 ETF 5일 누적
        </Link>
      }
      subtitle="5거래일 누적 등락률"
      className="!mb-0"
    >
      <Watch5dChart items={watch} />
      <Link href={`/weekly/${weekly.week}`} className={moreLink}>
        주간 리포트 자세히 →
      </Link>
    </Card>
  );

  return (
    <Container width="wide">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h1 className="text-xl font-bold">최신 시장 매매동향</h1>
        <p className="text-xs tabular-nums text-neutral-500 dark:text-neutral-400">
          {kr && <>🇰🇷 {shortDateWeekday(kr.date)}</>}
          {us && <> · 🇺🇸 {shortDateWeekday(us.date)}</>}
          {weekly?.date && <> · 📅 주간 {shortDateWeekday(weekly.date)}</>}
        </p>
      </div>
      <p className="mb-4 text-sm text-neutral-500 dark:text-neutral-400">
        한국·미국 시장 마감 후 요약 — 사실 데이터만, 투자권유·시점판단 없음.
      </p>

      {kp && (
        <MoodStrip
          kospi={kp.kospi}
          spx={up?.indices?.["^GSPC"] ?? null}
          vix={up?.volatility?.["^VIX"] ?? null}
          volatility={up?.volatility ?? null}
          oas={up?.high_yield_oas ?? null}
        />
      )}

      {/* 좌열(A 한국 외인 → C 미국 지수) / 우열(B 미국 섹터 → D 주간) 독립 스택 — A·B
          높이 불균형으로 생기던 빈 공간을 제거(masonry). 모바일은 1열 A→C→B→D. */}
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          {krCard}
          {usIndexCard}
        </div>
        <div className="flex flex-col gap-4">
          {usSectorCard}
          {weeklyCard}
        </div>
      </div>

      {!kr && !us && !weekly && (
        <p className="mt-4 text-sm text-neutral-500">
          아직 발행된 데이터가 없습니다.
        </p>
      )}

      <Link
        href="/calendar"
        className="mt-6 inline-block text-sm text-blue-600 dark:text-blue-400 hover:underline"
      >
        전체 발행 캘린더 보기 →
      </Link>
    </Container>
  );
}
