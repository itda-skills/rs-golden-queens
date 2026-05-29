import {
  arrow,
  colorClass,
  price,
  shortDate,
  signedAmount,
  signedPct,
  volRatio,
} from "@/lib/format";
import type { KrDailyRow, KrInvestorFlow, UsSection } from "@/lib/types";

// 투자자별 순매수 (외인/기관/개인) — 억원
export function InvestorFlowTable({ flow }: { flow: KrInvestorFlow }) {
  const rows: [string, number][] = [
    ["외국인", flow.foreign],
    ["기관", flow.institutional],
    ["개인", flow.personal],
  ];
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {rows.map(([label, v]) => (
          <tr key={label} className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0">
            <td className="py-1.5 text-neutral-600 dark:text-neutral-300">{label}</td>
            <td className={`py-1.5 text-right font-medium ${colorClass(v)}`}>
              {signedAmount(v)} <span className="text-xs">{arrow(v)}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 프로그램매매 (차익/비차익/합계)
export function ProgramTable({ flow }: { flow: KrInvestorFlow }) {
  const rows: [string, number][] = [
    ["차익", flow.program_arb],
    ["비차익", flow.program_nonarb],
    ["합계", flow.program_total],
  ];
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {rows.map(([label, v]) => (
          <tr key={label} className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0">
            <td className="py-1.5 text-neutral-600 dark:text-neutral-300">{label}</td>
            <td className={`py-1.5 text-right font-medium ${colorClass(v)}`}>
              {signedAmount(v)} <span className="text-xs">{arrow(v)}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 코스피 일별 추이 (외인/기관/개인) — 최신순
export function KospiDailyTable({ rows }: { rows: KrDailyRow[] }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <thead>
        <tr className="text-xs text-neutral-500 dark:text-neutral-400 border-b border-neutral-200 dark:border-neutral-800">
          <th className="py-1.5 text-left font-normal">일자</th>
          <th className="py-1.5 text-right font-normal">외국인</th>
          <th className="py-1.5 text-right font-normal">기관</th>
          <th className="py-1.5 text-right font-normal">개인</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.date} className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0">
            <td className="py-1.5 text-neutral-600 dark:text-neutral-300">{shortDate(r.date)}</td>
            <td className={`py-1.5 text-right ${colorClass(r.foreign)}`}>{signedAmount(r.foreign)}</td>
            <td className={`py-1.5 text-right ${colorClass(r.institutional)}`}>{signedAmount(r.institutional)}</td>
            <td className={`py-1.5 text-right ${colorClass(r.personal)}`}>{signedAmount(r.personal)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// US 섹션 표 (종목/종가/등락/거래량강도)
export function UsSectionTable({
  section,
  showVol = false,
  sortByPct = false,
}: {
  section: UsSection;
  showVol?: boolean;
  sortByPct?: boolean;
}) {
  let entries = Object.entries(section);
  if (sortByPct) entries = entries.sort((a, b) => b[1].pct - a[1].pct);
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {entries.map(([ticker, q]) => (
          <tr key={ticker} className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0">
            <td className="py-1.5 text-neutral-700 dark:text-neutral-200">
              {q.label}
              <span className="text-xs text-neutral-400 ml-1">{ticker.replace("^", "")}</span>
            </td>
            <td className="py-1.5 text-right text-neutral-600 dark:text-neutral-300">{price(q.close)}</td>
            <td className={`py-1.5 text-right font-medium ${colorClass(q.pct)}`}>
              {signedPct(q.pct)} <span className="text-xs">{arrow(q.pct)}</span>
            </td>
            {showVol && (
              <td className="py-1.5 text-right text-xs text-neutral-400">{volRatio(q.vol_ratio)}</td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
