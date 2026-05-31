// 의존성 0 CSS 막대 차트 (서버 렌더 가능, 번들 증가 없음).
// 0선 기준 발산형: 양수=위(상승 빨강)·음수=아래(하락 파랑). 각 막대에 실제 수치 라벨.
// SVG preserveAspectRatio="none" 의 가로 찌그러짐/수치 미표시 문제를 피하려 flex+높이(px)로 구현.

import { colorClass, signedAmount, signedPct } from "@/lib/format";

export interface BarDatum {
  label: string; // x축 라벨 (일자/티커)
  value: number;
}

export interface HBarDatum {
  label: string;
  value: number | null; // 결측(null)은 막대 없이 '–' 로 표기
  note?: string; // 우측 보조 표기(예: 거래량강도 ×1.6 🔥)
}

// 수평 다이버징 막대 랭킹 — 0 중심, 양수=빨강(오른쪽)/음수=파랑(왼쪽).
// 라벨 | [중앙 0선 기준 좌우 막대] | 값(+선택 note). 등락률 랭킹(섹터 등) 표시용.
// 의존성 0, 서버 렌더. 색·길이는 값에서 파생(SoT: 이모지/색 문자열 미저장).
export function HBarChart({
  data,
  format = "pct",
  ariaLabel,
}: {
  data: HBarDatum[];
  format?: "amount" | "pct";
  ariaLabel?: string;
}) {
  if (!data.length) return null;
  const fmt = format === "pct" ? signedPct : signedAmount;
  // 유한값만으로 스케일을 잡는다 — 단일 NaN/null 이 max 를 오염시켜 전 행을 깨지 않도록.
  const finite = data
    .map((d) => d.value)
    .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  const max = Math.max(...finite.map(Math.abs), 1e-9);
  return (
    <figure aria-label={ariaLabel ?? "막대 차트"} className="w-full">
      <ul className="space-y-1.5">
        {data.map((d) => {
          const v =
            typeof d.value === "number" && Number.isFinite(d.value)
              ? d.value
              : null;
          const up = v != null && v >= 0;
          const w = v == null ? 0 : (Math.abs(v) / max) * 50; // 한쪽 최대 50%
          return (
            <li key={d.label} className="flex items-center gap-2 text-sm">
              <span className="w-16 shrink-0 truncate text-neutral-600 dark:text-neutral-300">
                {d.label}
              </span>
              <div className="relative h-4 min-w-0 flex-1">
                <div className="absolute inset-y-0 left-1/2 w-px bg-neutral-300 dark:bg-neutral-700" />
                {v != null && (
                  <div
                    className={`absolute inset-y-1 rounded ${up ? "bg-rose-500/85" : "bg-blue-500/85"}`}
                    style={
                      up
                        ? { left: "50%", width: `${w}%` }
                        : { right: "50%", width: `${w}%` }
                    }
                  />
                )}
              </div>
              <span
                className={`w-14 shrink-0 text-right font-medium tabular-nums ${colorClass(v)}`}
              >
                {fmt(v)}
              </span>
              {d.note != null && (
                <span className="w-14 shrink-0 truncate text-right text-xs text-neutral-400">
                  {d.note}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

export function BarChart({
  data,
  height = 120,
  format = "amount",
  ariaLabel,
}: {
  data: BarDatum[];
  height?: number;
  format?: "amount" | "pct";
  ariaLabel?: string;
}) {
  if (!data.length) return null;

  const fmt = format === "pct" ? signedPct : signedAmount;
  const max = Math.max(...data.map((d) => Math.abs(d.value)), 1);
  const half = height / 2; // 위/아래 각 영역 높이(px)
  // 막대와 수치 라벨은 같은 영역(half)을 공유한다. 막대 최대 높이를 half 그대로 두면
  // 값이 큰 막대가 영역을 꽉 채워 라벨이 들어갈 자리를 잃고 위/아래로 밀려난다.
  // 라벨 공간을 미리 빼서 막대가 라벨을 밀지 않도록 한다.
  const labelReserve = 14; // 9px 라벨 + 여백
  const barMax = Math.max(half - labelReserve, 8);

  return (
    <figure role="img" aria-label={ariaLabel ?? "막대 차트"} className="w-full">
      <div className="flex items-stretch gap-1" style={{ height }}>
        {data.map((d) => {
          const up = d.value >= 0;
          const barPx = Math.max((Math.abs(d.value) / max) * barMax, d.value === 0 ? 0 : 2);
          return (
            <div
              key={d.label}
              className="flex-1 flex flex-col items-center justify-center min-w-0"
              title={`${d.label}: ${fmt(d.value)}`}
            >
              {/* 위 영역 (양수) */}
              <div className="flex-1 min-h-0 w-full flex flex-col justify-end items-center">
                {up && (
                  <>
                    <span className="text-[9px] leading-none text-rose-600 dark:text-rose-400 mb-0.5 whitespace-nowrap">
                      {fmt(d.value)}
                    </span>
                    <div
                      className="w-full max-w-7 rounded-t bg-rose-500/85"
                      style={{ height: barPx }}
                    />
                  </>
                )}
              </div>
              {/* 0선 */}
              <div className="w-full h-px bg-neutral-300 dark:bg-neutral-700" />
              {/* 아래 영역 (음수) */}
              <div className="flex-1 min-h-0 w-full flex flex-col justify-start items-center">
                {!up && (
                  <>
                    <div
                      className="w-full max-w-7 rounded-b bg-blue-500/85"
                      style={{ height: barPx }}
                    />
                    <span className="text-[9px] leading-none text-blue-600 dark:text-blue-400 mt-0.5 whitespace-nowrap">
                      {fmt(d.value)}
                    </span>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {/* x축 라벨 */}
      <div
        className="grid text-[10px] text-neutral-400 mt-1"
        style={{ gridTemplateColumns: `repeat(${data.length}, 1fr)` }}
      >
        {data.map((d) => (
          <span key={d.label} className="text-center truncate px-0.5">
            {d.label}
          </span>
        ))}
      </div>
    </figure>
  );
}
