// 홈 overview 최상단 '오늘 시장 무드' 배지 행 — 의존성0 서버 렌더(차트 아님).
// 항상-존재 4배지(KR 외인·개인 순매수, US S&P500·VIX) + 조건부 2배지(하이일드 OAS,
// VIX 기간구조)로 구성한다. 조건부 지표는 schema_version 1 추가 키라 과거 스냅샷엔
// 없을 수 있어 '있을 때만' 렌더(빈 '–' 노출 안 함).
//
// 도메인 불변성: 추세 단정·주도주체 서사·인과·전망 표현 금지. 부호·값 순수 표기까지만
// (예: '외국인 -63,035 ▼'). 색은 format.colorClass 로 값 부호에서 파생(이모지·색
// 하드코딩 금지). 단위는 차트와 일치하도록 KR은 억원 원본 유지(조 단위 환산 안 함).

import type { ReactNode } from "react";
import { arrow, colorClass, signedAmount, signedPct } from "@/lib/format";
import { vixTermShape } from "@/lib/vix";
import type { HighYieldOas, KrInvestorFlow, UsQuote, UsSection } from "@/lib/types";

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-200 bg-neutral-50 px-2.5 py-1 text-xs tabular-nums dark:border-neutral-800 dark:bg-neutral-900/50">
      {children}
    </span>
  );
}

function Key({ children }: { children: ReactNode }) {
  return <span className="text-neutral-500 dark:text-neutral-400">{children}</span>;
}

// OAS 관측일(MM/DD) — T+1 지연으로 종가일과 다를 수 있어 표기(stale 위장 방지).
// RiskAxes 와 동일한 regex·월일 범위 검증.
function oasObsDate(date?: string): string | null {
  const m = date?.match(/^\d{4}-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const mo = +m[1];
  const dy = +m[2];
  return mo >= 1 && mo <= 12 && dy >= 1 && dy <= 31 ? `${mo}/${dy}` : null;
}

export function MoodStrip({
  kospi,
  spx,
  vix,
  volatility,
  oas,
}: {
  kospi: KrInvestorFlow;
  spx: UsQuote | null;
  vix: UsQuote | null;
  volatility: UsSection | null;
  oas?: HighYieldOas | null;
}) {
  const term = volatility ? vixTermShape(volatility) : null;
  const oasMd = oasObsDate(oas?.date);

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <Badge>
        <Key>🇰🇷 외국인</Key>
        <span className={`font-medium ${colorClass(kospi.foreign)}`}>
          {signedAmount(kospi.foreign)} {arrow(kospi.foreign)}
        </span>
      </Badge>
      <Badge>
        <Key>🇰🇷 개인</Key>
        <span className={`font-medium ${colorClass(kospi.personal)}`}>
          {signedAmount(kospi.personal)} {arrow(kospi.personal)}
        </span>
      </Badge>
      {spx && (
        <Badge>
          <Key>🇺🇸 S&P500</Key>
          <span className={`font-medium ${colorClass(spx.pct)}`}>
            {signedPct(spx.pct)} {arrow(spx.pct)}
          </span>
        </Badge>
      )}
      {vix && (
        <Badge>
          <Key>VIX</Key>
          <span className="font-medium text-neutral-700 dark:text-neutral-200">
            {vix.close.toFixed(2)}
          </span>
          <span className={colorClass(vix.pct)}>{signedPct(vix.pct)}</span>
        </Badge>
      )}
      {oas && oas.value != null && (
        <Badge>
          <Key>HY OAS{oasMd ? ` (${oasMd})` : ""}</Key>
          <span className="font-medium text-neutral-700 dark:text-neutral-200">
            {oas.value.toFixed(2)}%p
          </span>
          {oas.change != null && (
            <span className={colorClass(oas.change)}>
              {oas.change >= 0 ? "+" : ""}
              {oas.change.toFixed(2)}p
            </span>
          )}
        </Badge>
      )}
      {term && (
        <Badge>
          <Key>VIX 9D/30D</Key>
          <span className="font-medium text-neutral-700 dark:text-neutral-200">
            {term.shape}
          </span>
        </Badge>
      )}
    </div>
  );
}
