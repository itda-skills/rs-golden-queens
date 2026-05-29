import { ImageResponse } from "next/og";

export const alt = "Golden Queens — 시장 매매동향 아카이브";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0a0a",
          color: "#fafafa",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: 80, fontWeight: 700 }}>📊 Golden Queens</div>
        <div style={{ fontSize: 34, color: "#a3a3a3", marginTop: 20 }}>
          한국·미국 시장 매매동향 아카이브
        </div>
        <div style={{ fontSize: 22, color: "#737373", marginTop: 48 }}>
          사실 데이터만 제공 · 투자 권유 없음
        </div>
      </div>
    ),
    size,
  );
}
