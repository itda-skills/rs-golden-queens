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
  HighYieldOas,
  KrDailyFlow,
  KrForeignInst,
  KrForeignInstItem,
  KrInvestorFlow,
  KrMoneyFlow,
  KrMoneyFlowItem,
  KrMoneyFlowSellItem,
  UsQuote,
  UsSection,
} from "@/lib/types";

// 투자자별 순매수 (외인/기관/개인) — 억원
export function InvestorFlowTable({ flow }: { flow: KrInvestorFlow }) {
  const rows: [string, number | null][] = [
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
  const rows: [string, number | null][] = [
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

// 일별 투자자 추이 (외인/기관/개인) — 코스피·코스닥 공용, 최신순
export function InvestorDailyTable({ rows }: { rows: KrDailyFlow[] }) {
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
  // 결측 티커(publisher 가 보통 제거하지만 구버전 스냅샷 방어)는 null — 필터링한다.
  let entries = Object.entries(section).filter(
    (e): e is [string, UsQuote] => e[1] != null,
  );
  if (sortByPct) entries = entries.sort((a, b) => b[1].pct - a[1].pct);
  // 그 외에는 발행값의 catalog 순서(order)로 렌더 — sort_keys 알파벳 대신 텔레그램 정합(#10).
  else entries = entries.sort((a, b) => (a[1].order ?? 0) - (b[1].order ?? 0));
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

// VIX 기간구조 (I7, #10) — 9일 vs 30일 곡선 형태(콘탱고/백워데이션). 발행 스냅샷의
// 종가값에서 파생. 곡선 형태 사실이지 판단·예측 아님 — 세 상태 모두 중립색(경고색 미사용).
export function VixTermStructure({ volatility }: { volatility: UsSection }) {
  const short = volatility["^VIX9D"]?.close ?? null;
  const long = volatility["^VIX"]?.close ?? null;
  if (short == null || long == null) return null;
  const spread = long - short;
  // 표시 단위(소수 2자리)로 반올림해 분류 — 텔레그램 round(spread,2) 와 동일 임계(SoT 정합).
  const s = Math.round(spread * 100) / 100;
  const shape = s > 0.3 ? "콘탱고" : s < -0.3 ? "백워데이션" : "평탄";
  return (
    <p className="mt-2 text-xs text-neutral-500 dark:text-neutral-400 tabular-nums">
      VIX 기간구조: 9일 {short.toFixed(2)} / 30일 {long.toFixed(2)} →{" "}
      <span className="font-medium text-neutral-700 dark:text-neutral-200">
        {shape}
      </span>{" "}
      ({spread >= 0 ? "+" : ""}
      {spread.toFixed(2)}p)
    </p>
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

// 위험선호 다축 (I6, #10) — 각 지표가 정의상 가리키는 쪽(위험선호/안전자산)을 사실로
// 나열. 종합 점수·예측 아님. inverse=true(하락=위험선호)는 VIX·달러·금에 적용.
function riskLean(value: number | null, inverse: boolean, tol = 0.05): string {
  if (value == null) return "—";
  if (Math.abs(value) < tol) return "중립";
  const riskOnWhenUp = !inverse;
  return value > 0 === riskOnWhenUp ? "위험선호" : "안전자산";
}

const LEAN_CLASS: Record<string, string> = {
  위험선호: "text-rose-600 dark:text-rose-400",
  안전자산: "text-blue-600 dark:text-blue-400",
  중립: "text-neutral-500 dark:text-neutral-400",
  "—": "text-neutral-400",
};

// HYG−IEF 갭(±0.2%p 임계 — 텔레그램 라벨과 동일) + VIX·달러·금. 발행 스냅샷 값에서 파생.
export function RiskAxes({
  riskOnoff,
  volatility,
  macro,
  oas,
}: {
  riskOnoff: UsSection;
  volatility: UsSection;
  macro: UsSection;
  oas?: HighYieldOas | null;
}) {
  const hyg = riskOnoff["HYG"]?.pct ?? null;
  const ief = riskOnoff["IEF"]?.pct ?? null;
  const rows: {
    label: string;
    valueStr: string;
    value: number | null;
    lean: string;
  }[] = [];
  if (hyg != null && ief != null) {
    const gap = hyg - ief;
    rows.push({
      label: "HYG−IEF 갭",
      valueStr: `${gap >= 0 ? "+" : ""}${gap.toFixed(2)}%p`,
      value: gap,
      // 텔레그램 primary 와 동일 strict 경계(>0.2 / <-0.2, 0.20 은 중립)
      lean: gap > 0.2 ? "위험선호" : gap < -0.2 ? "안전자산" : "중립",
    });
  }
  const inverse: [string, number | null][] = [
    ["VIX", volatility["^VIX"]?.pct ?? null],
    ["달러(DXY)", macro["DX-Y.NYB"]?.pct ?? null],
    ["금", macro["GC=F"]?.pct ?? null],
  ];
  for (const [label, pct] of inverse) {
    if (pct != null) {
      rows.push({
        label,
        valueStr: signedPct(pct),
        value: pct,
        lean: riskLean(pct, true),
      });
    }
  }
  // 하이일드 OAS(#10 I6 2nd): 절대 스프레드 + 전일대비. 상승=확대=안전자산(inverse).
  // 색은 전일대비(change) 부호에서, 의미(lean)는 별도 — 텔레그램 발행값과 정합.
  // T+1 지연으로 종가일과 다를 수 있어 관측일(MM/DD)을 라벨에 명시(stale 위장 방지).
  // change 는 발행 시점에 소수 2자리로 확정됨 — 웹은 재반올림하지 않는다(AGENTS SoT:
  // round 방식 차이가 텔레그램과 값/분류를 어긋나게 하지 않도록). date 는 regex 로 검증.
  if (oas && oas.value != null) {
    const ch = oas.change;
    const m = oas.date?.match(/^\d{4}-(\d{2})-(\d{2})$/);
    const mo = m ? +m[1] : 0;
    const dy = m ? +m[2] : 0;
    // 월/일 범위까지 확인해 13/99 같은 malformed 를 거른다(formatter strptime 과 정합).
    const md = mo >= 1 && mo <= 12 && dy >= 1 && dy <= 31 ? `${mo}/${dy}` : null;
    rows.push({
      label: md ? `하이일드 OAS (${md})` : "하이일드 OAS",
      valueStr:
        ch != null
          ? `${oas.value.toFixed(2)}%p (${ch >= 0 ? "+" : ""}${ch.toFixed(2)}p)`
          : `${oas.value.toFixed(2)}%p`,
      value: ch,
      lean: riskLean(ch, true, 0.01),
    });
  }
  if (!rows.length) return null;
  return (
    <table className="w-full text-sm tabular-nums">
      <tbody>
        {rows.map((r) => (
          <tr
            key={r.label}
            className="border-b border-neutral-100 dark:border-neutral-800/60 last:border-0"
          >
            <td className="py-1.5 text-neutral-700 dark:text-neutral-200">
              {r.label}
            </td>
            <td className={`py-1.5 text-right ${colorClass(r.value)}`}>
              {r.valueStr}
            </td>
            <td className={`py-1.5 text-right text-xs ${LEAN_CLASS[r.lean]}`}>
              {r.lean}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
