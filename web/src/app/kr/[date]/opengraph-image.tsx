import { ImageResponse } from "next/og";
import { getKrSnapshot } from "@/lib/data";
import { longDate, signedAmount } from "@/lib/format";

export const alt = "한국장 매매동향";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const UP = "#e11d48";
const DOWN = "#2563eb";
const FLAT = "#737373";

function color(v: number | null) {
  if (v == null) return FLAT;
  return v > 0 ? UP : v < 0 ? DOWN : FLAT;
}

export default async function Image({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const snap = await getKrSnapshot(date);
  const k = snap?.payload?.kospi;
  const rows: [string, number | null][] = k
    ? [
        ["외국인", k.foreign],
        ["기관", k.institutional],
        ["개인", k.personal],
      ]
    : [];

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
        <div style={{ fontSize: 30, color: "#a3a3a3" }}>🇰🇷 한국장 매매동향</div>
        <div style={{ fontSize: 52, fontWeight: 700, marginTop: 8 }}>
          {snap ? longDate(snap.date) : date}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 48 }}>
          {rows.map(([label, v]) => (
            <div key={label} style={{ display: "flex", fontSize: 44 }}>
              <div style={{ width: 240, color: "#d4d4d4" }}>{label}</div>
              <div style={{ color: color(v), fontWeight: 700 }}>
                {`${signedAmount(v)} ${(v ?? 0) > 0 ? "▲" : (v ?? 0) < 0 ? "▼" : "–"}`}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: "auto", fontSize: 24, color: "#737373", display: "flex" }}>
          코스피 투자자별 순매수 (억원) · Golden Queens
        </div>
      </div>
    ),
    size,
  );
}
