import type { Metadata } from "next";
import "./globals.css";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
        <SiteHeader />
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
