import {
  arrow,
  colorClass,
  price,
  shortDate,
  signedAmount,
  signedPct,
  volRatio,
} from "@/lib/format";
import type {
  KrDailyRow,
  KrForeignInst,
  KrForeignInstItem,
  KrInvestorFlow,
  KrMoneyFlow,
  KrMoneyFlowItem,
  KrMoneyFlowSellItem,
  KrSector,
  UsSection,
} from "@/lib/types";

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

// 한국 섹터 ETF (KIS, #10 P0-c) — 발행 순서 그대로 표시(정렬은 fetcher 가 소유:
// 등락 내림차순). 웹은 순서를 재계산하지 않는다(SoT: 시장 로직 재구현 금지).
export function SectorTable({ sectors }: { sectors: KrSector[] }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {sectors.map((s) => (
          <tr
            key={s.code}
            className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0"
          >
            <td className="py-1.5 text-neutral-700 dark:text-neutral-200">{s.label}</td>
            <td className={`py-1.5 text-right font-medium ${colorClass(s.pct)}`}>
              {signedPct(s.pct)} <span className="text-xs">{arrow(s.pct)}</span>
            </td>
            <td className="py-1.5 text-right text-xs text-neutral-400">
              {volRatio(s.vol_ratio)}
              {s.vol_ratio != null && s.vol_ratio >= 1.5 ? " 🔥" : ""}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 동적 수급 워치 한 그룹(ETF 또는 개별주) — 외인·기관 순매수(억원), 색은 값 부호에서 재현.
function MoneyFlowRows({ items }: { items: KrMoneyFlowItem[] }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {items.map((it) => (
          <tr
            key={it.code}
            className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0"
          >
            <td className="py-1.5 text-neutral-700 dark:text-neutral-200">
              {it.name}
              <span className="text-xs text-neutral-400 ml-1">{it.code}</span>
              <span className="text-xs text-neutral-400 ml-1">{it.grade}</span>
            </td>
            <td className={`py-1.5 text-right ${colorClass(it.foreign_eok)}`}>
              외{" "}
              {it.foreign_eok == null
                ? "–"
                : signedAmount(Math.round(it.foreign_eok))}
            </td>
            <td className={`py-1.5 text-right ${colorClass(it.orgn_eok)}`}>
              기{" "}
              {it.orgn_eok == null
                ? "–"
                : signedAmount(Math.round(it.orgn_eok))}
            </td>
            <td className="py-1.5 text-right">{it.both_buy ? "🔥" : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 오늘의 수급 Top (KIS money_flow, #10 P0-c) — ETF·개별주 분리 표시.
export function MoneyFlowTable({ mf }: { mf: KrMoneyFlow }) {
  return (
    <div className="space-y-3">
      {mf.etfs.length > 0 && (
        <div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-1">⭐ ETF Top</p>
          <MoneyFlowRows items={mf.etfs} />
        </div>
      )}
      {mf.stocks.length > 0 && (
        <div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-1">
            📈 개별주 Top
          </p>
          <MoneyFlowRows items={mf.stocks} />
        </div>
      )}
    </div>
  );
}

// 순매도 한 그룹 (I1, #10 P0-d) — 매수 라벨(grade·🔥) 미사용. 외인·기관 순매도(억원).
function MoneyFlowSellRows({ items }: { items: KrMoneyFlowSellItem[] }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {items.map((it) => (
          <tr
            key={it.code}
            className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0"
          >
            <td className="py-1.5 text-neutral-700 dark:text-neutral-200">
              {it.name}
              <span className="text-xs text-neutral-400 ml-1">{it.code}</span>
            </td>
            <td className={`py-1.5 text-right ${colorClass(it.foreign_eok)}`}>
              외{" "}
              {it.foreign_eok == null
                ? "–"
                : signedAmount(Math.round(it.foreign_eok))}
            </td>
            <td className={`py-1.5 text-right ${colorClass(it.orgn_eok)}`}>
              기{" "}
              {it.orgn_eok == null
                ? "–"
                : signedAmount(Math.round(it.orgn_eok))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 외인·기관 순매도 상위 (I1, #10 P0-d) — ETF·개별주 분리. 매수 편향 라벨 미사용.
export function MoneyFlowSellTable({ mf }: { mf: KrMoneyFlow }) {
  const etfsSell = mf.etfs_sell ?? [];
  const stocksSell = mf.stocks_sell ?? [];
  return (
    <div className="space-y-3">
      {etfsSell.length > 0 && (
        <div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-1">ETF</p>
          <MoneyFlowSellRows items={etfsSell} />
        </div>
      )}
      {stocksSell.length > 0 && (
        <div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-1">개별주</p>
          <MoneyFlowSellRows items={stocksSell} />
        </div>
      )}
    </div>
  );
}

// 외국인·기관 가집계 한 그룹 (I4, #10) — 장중 추정 금액(억원). 색은 값 부호에서 재현.
function ForeignInstRows({ items }: { items: KrForeignInstItem[] }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {items.map((it) => (
          <tr
            key={it.code}
            className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0"
          >
            <td className="py-1.5 text-neutral-700 dark:text-neutral-200">
              {it.name}
              <span className="text-xs text-neutral-400 ml-1">{it.code}</span>
            </td>
            <td className={`py-1.5 text-right ${colorClass(it.foreign_eok)}`}>
              외{" "}
              {it.foreign_eok == null
                ? "–"
                : signedAmount(Math.round(it.foreign_eok))}
            </td>
            <td className={`py-1.5 text-right ${colorClass(it.orgn_eok)}`}>
              기{" "}
              {it.orgn_eok == null ? "–" : signedAmount(Math.round(it.orgn_eok))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// 외국인·기관 가집계 (I4, #10) — 장중 추정(확정 아님). 순매수·순매도 분리.
export function ForeignInstTable({ fi }: { fi: KrForeignInst }) {
  return (
    <div className="space-y-3">
      {fi.buy.length > 0 && (
        <div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-1">
            순매수 상위
          </p>
          <ForeignInstRows items={fi.buy} />
        </div>
      )}
      {fi.sell.length > 0 && (
        <div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-1">
            순매도 상위
          </p>
          <ForeignInstRows items={fi.sell} />
        </div>
      )}
    </div>
  );
}
