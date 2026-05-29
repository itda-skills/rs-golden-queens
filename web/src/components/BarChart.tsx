// 의존성 0 SVG 막대 차트 (서버 렌더 가능, 번들 증가 없음).
// 양수=상승(빨강)·음수=하락(파랑) 색 컨벤션. 0선 기준 발산형 막대.

import { signedAmount, signedPct } from "@/lib/format";

export interface BarDatum {
  label: string; // x축 라벨 (일자/티커)
  value: number;
}

const UP = "#e11d48"; // rose-600
const DOWN = "#2563eb"; // blue-600

export function BarChart({
  data,
  height = 140,
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
  const n = data.length;
  const W = 100; // viewBox 가로 (%) 비율
  const gap = 0.25; // 막대 간 간격 비율
  const slot = W / n;
  const barW = slot * (1 - gap);
  const midY = height / 2;
  const maxBar = midY - 14; // 라벨 영역 여백

  return (
    <figure
      role="img"
      aria-label={ariaLabel ?? "막대 차트"}
      className="w-full overflow-hidden"
    >
      <svg
        viewBox={`0 0 ${W} ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
      >
        {/* 0선 */}
        <line
          x1={0}
          y1={midY}
          x2={W}
          y2={midY}
          stroke="currentColor"
          strokeWidth={0.3}
          className="text-neutral-300 dark:text-neutral-700"
        />
        {data.map((d, i) => {
          const h = (Math.abs(d.value) / max) * maxBar;
          const x = i * slot + (slot - barW) / 2;
          const up = d.value >= 0;
          const y = up ? midY - h : midY;
          return (
            <g key={d.label}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={Math.max(h, 0.5)}
                fill={up ? UP : DOWN}
                rx={0.4}
              >
                <title>{`${d.label}: ${fmt(d.value)}`}</title>
              </rect>
            </g>
          );
        })}
      </svg>
      {/* x축 라벨 (SVG 밖, 정렬 유지) */}
      <figcaption className="grid text-[10px] text-neutral-400 mt-1" style={{ gridTemplateColumns: `repeat(${n}, 1fr)` }}>
        {data.map((d) => (
          <span key={d.label} className="text-center truncate px-0.5">
            {d.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
