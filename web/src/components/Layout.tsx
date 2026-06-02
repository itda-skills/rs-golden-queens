import Link from "next/link";
import type { ReactNode } from "react";

const NAV_LINKS = [
  { href: "/", label: "홈" },
  { href: "/calendar", label: "캘린더" },
  { href: "/guide", label: "가이드" },
];

export function SiteHeader() {
  // 좁은 화면(iPhone)에서 메뉴명이 2줄로 접히던 문제: 링크는 항상 1줄
  // (whitespace-nowrap·shrink-0)로 두고, 모바일은 로고/nav 를 세로 스택해 nav 가
  // 전체 폭을 쓰게 한다. sm+ 는 가로 배치. 넘치면 nav 가 가로 스크롤(안전망).
  return (
    <header className="border-b border-neutral-200 dark:border-neutral-800">
      <div className="mx-auto flex max-w-3xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:py-4">
        <Link
          href="/"
          className="shrink-0 whitespace-nowrap text-lg font-bold tracking-tight"
        >
          📊 Golden Queens
        </Link>
        <nav className="-mx-4 flex gap-4 overflow-x-auto whitespace-nowrap px-4 text-sm text-neutral-600 dark:text-neutral-300 sm:mx-0 sm:px-0">
          {NAV_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="shrink-0 hover:text-neutral-900 dark:hover:text-white"
            >
              {l.label}
            </Link>
          ))}
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
  info,
  children,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  info?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4 mb-4">
      {title && (
        <div className="mb-3">
          <h2 className="font-semibold flex items-center gap-1.5">
            <span>{title}</span>
            {info}
          </h2>
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

// 조건부 섹션이 비었을 때, 그냥 숨기는 대신 "왜 비었고 / 정상적으로는 무엇이
// 보이며 / 어떻게 수집되는지"를 같은 자리에 안내한다(데이터 부재 ≠ 결함).
// 사유는 발행 스냅샷의 키 상태로 구분한다:
//   legacy  — payload 에 키 자체가 없음(그 지표 도입 전 발행분, 과거라 보정 불가)
//   skipped — 값이 null(과거일 재발행 KIS 스킵 또는 당일 수집 실패)
//   empty   — 키·구조는 있으나 항목 0건(당일 조건에 맞는 데이터 없음)
export type SectionState = "ok" | "legacy" | "skipped" | "empty";

// raw: 스냅샷의 해당 키 값(undefined=키 부재, null=스킵), hasData: 표시할 항목 유무
export function sectionState(raw: unknown, hasData: boolean): SectionState {
  if (raw === undefined) return "legacy";
  if (raw === null) return "skipped";
  return hasData ? "ok" : "empty";
}

export function SectionPlaceholder({
  title,
  info,
  state,
  normallyShows,
  collect,
}: {
  title: ReactNode;
  info?: ReactNode;
  state: Exclude<SectionState, "ok">;
  // 정상적으로 이 자리에 표시되는 내용 ("~가 표시됩니다" 형태로 끝나는 절)
  normallyShows: string;
  // 수집 출처·시점 (명사구)
  collect: string;
}) {
  const reason =
    state === "legacy"
      ? "이 날짜를 발행한 시점에는 아직 이 지표를 수집·기록하지 않았습니다. 이후 발송분부터 표시됩니다."
      : state === "skipped"
        ? "과거 거래일 재발행분이라 이 지표가 포함되지 않았습니다 (KIS 지표는 거래일 당일에만 제공)."
        : "이 날짜에는 표시할 데이터가 없습니다.";
  return (
    <section className="rounded-xl border border-dashed border-amber-300 dark:border-amber-700 bg-amber-50/50 dark:bg-amber-950/20 p-4 mb-4">
      <h2 className="font-semibold flex items-center gap-1.5 text-neutral-600 dark:text-neutral-300">
        <span>{title}</span>
        {info}
      </h2>
      <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400 leading-relaxed">
        <span className="mr-1">ℹ️</span>
        {reason}
      </p>
      <p className="mt-2 text-xs text-neutral-500 leading-relaxed">
        이 자리에는 보통 {normallyShows}. 수집: {collect}.
      </p>
    </section>
  );
}

export function HolidayNotice({ message }: { message?: string }) {
  return (
    <div className="rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30 p-4 text-sm">
      🏖️ {message ?? "휴장일입니다."}
    </div>
  );
}
