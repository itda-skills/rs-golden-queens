import type { Metadata } from "next";
import "./globals.css";
import { DrawerProvider } from "@/components/DrawerContext";
import { Sidebar } from "@/components/Sidebar";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { getIndex, getWeeklySnapshot } from "@/lib/data";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://rs-golden-queens.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Golden Queens — 시장 매매동향 아카이브",
    template: "%s · Golden Queens",
  },
  description:
    "한국·미국 시장 마감 후 매매동향 요약 아카이브. 사실 데이터만 제공하며 투자 권유를 포함하지 않습니다.",
  alternates: {
    types: {
      "application/rss+xml": `${siteUrl}/rss.xml`,
    },
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // 사이드바 날짜 목록 — 발행 index 를 server 에서 fetch(ISR 600s)해 client 사이드바에
  // 넘긴다. SSG 페이지(/kr/[date] 등)는 그대로 정적 생성되고, 사이드바만 client island.
  const index = await getIndex();
  // 주간은 키(2026-W22)만으론 직관적이지 않아 '수집된 기준일'을 함께 넘긴다(최근 3개만).
  // 웹이 주차를 재계산하지 않고 발행 스냅샷의 date 를 그대로 라벨에 쓴다(SoT).
  const weeklyKeys = [...(index?.weekly ?? [])].sort().reverse().slice(0, 3);
  const weeklyDates: Record<string, string | null> = {};
  await Promise.all(
    weeklyKeys.map(async (w) => {
      weeklyDates[w] = (await getWeeklySnapshot(w))?.date ?? null;
    }),
  );
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
        <DrawerProvider>
          <SiteHeader />
          <div className="flex w-full flex-1">
            <Sidebar index={index} weeklyDates={weeklyDates} />
            <main className="min-w-0 flex-1">{children}</main>
          </div>
          <SiteFooter />
        </DrawerProvider>
      </body>
    </html>
  );
}
