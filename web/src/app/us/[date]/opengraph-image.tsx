import { ImageResponse } from "next/og";
import { getUsSnapshot } from "@/lib/data";
import { longDate, price, signedPct } from "@/lib/format";
import type { UsQuote } from "@/lib/types";

export const alt = "미국장 마감";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const UP = "#e11d48";
const DOWN = "#2563eb";
const FLAT = "#737373";

function color(v: number) {
  return v > 0 ? UP : v < 0 ? DOWN : FLAT;
}

export default async function Image({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const snap = await getUsSnapshot(date);
  const idx = snap?.payload?.indices ?? {};
  const rows = Object.values(idx)
    .filter((q): q is UsQuote => q != null)
    .slice(0, 4);

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
        <div style={{ fontSize: 30, color: "#a3a3a3" }}>🇺🇸 미국장 마감</div>
        <div style={{ fontSize: 52, fontWeight: 700, marginTop: 8 }}>
          {snap ? longDate(snap.date) : date}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 44 }}>
          {rows.map((q) => (
            <div key={q.label} style={{ display: "flex", fontSize: 40 }}>
              <div style={{ width: 280, color: "#d4d4d4" }}>{q.label}</div>
              <div style={{ width: 240, color: "#e5e5e5" }}>{price(q.close)}</div>
              <div style={{ color: color(q.pct), fontWeight: 700 }}>
                {`${signedPct(q.pct)} ${q.pct > 0 ? "▲" : q.pct < 0 ? "▼" : "–"}`}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: "auto", fontSize: 24, color: "#737373", display: "flex" }}>
          주요 지수 종가 / 등락 · Golden Queens
        </div>
      </div>
    ),
    size,
  );
}
