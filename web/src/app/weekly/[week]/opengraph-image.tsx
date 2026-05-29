import { ImageResponse } from "next/og";
import { getWeeklySnapshot } from "@/lib/data";
import { signedPct } from "@/lib/format";

export const alt = "주간 리포트";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const UP = "#e11d48";
const DOWN = "#2563eb";

export default async function Image({
  params,
}: {
  params: Promise<{ week: string }>;
}) {
  const { week } = await params;
  const snap = await getWeeklySnapshot(week);
  const watch = [...(snap?.payload?.watch_5d ?? [])]
    .sort((a, b) => b.pct_5d - a.pct_5d)
    .slice(0, 5);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "#0a0a0a",
          color: "#fafafa",
          padding: 64,
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: 30, color: "#a3a3a3" }}>📅 주간 리포트</div>
        <div style={{ fontSize: 52, fontWeight: 700, marginTop: 8 }}>{week}</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 40 }}>
          {watch.map((w) => (
            <div key={w.ticker} style={{ display: "flex", fontSize: 38 }}>
              <div style={{ width: 200, color: "#d4d4d4" }}>{w.ticker}</div>
              <div style={{ color: w.pct_5d >= 0 ? UP : DOWN, fontWeight: 700 }}>
                {`${signedPct(w.pct_5d)} ${w.pct_5d >= 0 ? "▲" : "▼"}`}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: "auto", fontSize: 24, color: "#737373", display: "flex" }}>
          워치 ETF 5거래일 누적 등락 · Golden Queens
        </div>
      </div>
    ),
    size,
  );
}
