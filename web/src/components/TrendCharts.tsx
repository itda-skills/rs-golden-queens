// 발행 스냅샷 시계열을 막대 차트로. 표시 전용 — 신규 계산 없음.

import { BarChart, type BarDatum } from "./BarChart";
import { shortDate } from "@/lib/format";
import type { KrDailyRow, Watch5d } from "@/lib/types";

// kospi_daily 는 최신순 → 차트는 시간순(오래된 것 왼쪽)으로
function toChrono(rows: KrDailyRow[]): KrDailyRow[] {
  return [...rows].reverse();
}

const SERIES: { key: keyof KrDailyRow; label: string }[] = [
  { key: "foreign", label: "외국인" },
  { key: "institutional", label: "기관" },
  { key: "personal", label: "개인" },
];

export function KospiTrendCharts({ rows }: { rows: KrDailyRow[] }) {
  const chrono = toChrono(rows);
  return (
    <div className="space-y-5">
      {SERIES.map(({ key, label }) => {
        const data: BarDatum[] = chrono.map((r) => ({
          label: shortDate(r.date),
          value: r[key] as number,
        }));
        return (
          <div key={key}>
            <div className="text-xs text-neutral-500 dark:text-neutral-400 mb-1">
              {label} 일별 순매수 (억원)
            </div>
            <BarChart data={data} ariaLabel={`${label} 일별 순매수 추이`} />
          </div>
        );
      })}
    </div>
  );
}

export function Watch5dChart({ items }: { items: Watch5d[] }) {
  // 등락률 내림차순
  const data: BarDatum[] = [...items]
    .sort((a, b) => b.pct_5d - a.pct_5d)
    .map((w) => ({ label: w.ticker, value: w.pct_5d }));
  return (
    <BarChart data={data} format="pct" ariaLabel="워치 ETF 5거래일 누적 등락" />
  );
}
