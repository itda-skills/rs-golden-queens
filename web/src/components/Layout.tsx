import Link from "next/link";
import type { ReactNode } from "react";

export function SiteHeader() {
  return (
    <header className="border-b border-neutral-200 dark:border-neutral-800">
      <div className="mx-auto max-w-3xl px-4 py-4 flex items-center justify-between">
        <Link href="/" className="font-bold text-lg tracking-tight">
          📊 Golden Queens
        </Link>
        <nav className="flex gap-4 text-sm text-neutral-600 dark:text-neutral-300">
          <Link href="/" className="hover:text-neutral-900 dark:hover:text-white">
            홈
          </Link>
          <Link
            href="/archive"
            className="hover:text-neutral-900 dark:hover:text-white"
          >
            아카이브
          </Link>
          <Link
            href="/calendar"
            className="hover:text-neutral-900 dark:hover:text-white"
          >
            캘린더
          </Link>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-neutral-200 dark:border-neutral-800">
      <div className="mx-auto max-w-3xl px-4 py-6 text-xs text-neutral-500 dark:text-neutral-400 space-y-1">
        <p>
          본 페이지는 한국·미국 시장 마감 후의 <strong>사실 데이터</strong>만
          제공합니다. 투자 권유·종목 추천·매매 시점 판단을 포함하지 않습니다.
        </p>
        <p>
          데이터 출처: 네이버 금융, Yahoo Finance, 한국투자증권 등. 지연·오류가
          있을 수 있으며 투자 판단의 근거로 삼지 마십시오.
        </p>
      </div>
    </footer>
  );
}

export function Container({ children }: { children: ReactNode }) {
  return <main className="mx-auto max-w-3xl px-4 py-6 w-full">{children}</main>;
}

export function Card({
  title,
  subtitle,
  children,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4 mb-4">
      {title && (
        <div className="mb-3">
          <h2 className="font-semibold">{title}</h2>
          {subtitle && (
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {subtitle}
            </p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}

export function SourceList({
  sources,
}: {
  sources: { label: string; url: string }[];
}) {
  if (!sources?.length) return null;
  return (
    <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-4">
      출처:{" "}
      {sources.map((s, i) => (
        <span key={s.url}>
          {i > 0 && " · "}
          <a
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-neutral-700 dark:hover:text-neutral-200"
          >
            {s.label}
          </a>
        </span>
      ))}
    </p>
  );
}

export function HolidayNotice({ message }: { message?: string }) {
  return (
    <div className="rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30 p-4 text-sm">
      🏖️ {message ?? "휴장일입니다."}
    </div>
  );
}
