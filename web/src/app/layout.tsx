import type { Metadata } from "next";
import "./globals.css";
import { DrawerProvider } from "@/components/DrawerContext";
import { Sidebar } from "@/components/Sidebar";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { getIndex } from "@/lib/data";

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
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
        <DrawerProvider>
          <SiteHeader />
          <div className="flex w-full flex-1">
            <Sidebar index={index} />
            <main className="min-w-0 flex-1">{children}</main>
          </div>
          <SiteFooter />
        </DrawerProvider>
      </body>
    </html>
  );
}
