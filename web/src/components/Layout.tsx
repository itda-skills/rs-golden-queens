import type { ReactNode } from "react";

// SiteHeader/SiteFooter 는 라우트별 폭 분기(usePathname)를 위해 클라이언트
// 컴포넌트(SiteChrome.tsx)로 분리했다. layout 은 그쪽에서 import 한다.

export function Container({
  children,
  width = "default",
}: {
  children: ReactNode;
  // KR 상세만 'wide'(max-w-6xl)로 멀티컬럼 대시보드. 그 외는 기본 max-w-3xl 유지.
  width?: "default" | "wide";
}) {
  const max = width === "wide" ? "max-w-6xl" : "max-w-3xl";
  return <main className={`mx-auto ${max} px-4 py-6 w-full`}>{children}</main>;
}

// 관련 카드들을 한 묶음으로 보여주는 헤더 래퍼(표시 전용). 내부 그리드 컬럼 수는
// 묶음마다 다르므로 호출부가 children 으로 grid div 를 직접 넘긴다(CardGroup 은 헤더만).
export function CardGroup({
  title,
  subtitle,
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-base font-semibold text-neutral-700 dark:text-neutral-300">
        {title}
        {subtitle && (
          <span className="ml-2 text-xs font-normal text-neutral-500 dark:text-neutral-400">
            {subtitle}
          </span>
        )}
      </h2>
      {children}
    </section>
  );
}

export function Card({
  title,
  subtitle,
  info,
  className,
  children,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  info?: ReactNode;
  // 그리드 셀 안에서는 카드 자체 mb-4 를 제거해야 한다(그리드 gap 이 간격을 줌).
  // 호출부가 className="!mb-0" 으로 확실히 덮는다(!important 로 mb-4 보다 우선).
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={`rounded-xl border border-neutral-200 dark:border-neutral-800 p-4 mb-4 ${className ?? ""}`}
    >
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
  className,
}: {
  title: ReactNode;
  info?: ReactNode;
  state: Exclude<SectionState, "ok">;
  // 정상적으로 이 자리에 표시되는 내용 ("~가 표시됩니다" 형태로 끝나는 절)
  normallyShows: string;
  // 수집 출처·시점 (명사구)
  collect: string;
  // 그리드 셀에서 자체 mb-4 제거용(Card 와 동일) — 호출부가 "!mb-0" 전달.
  className?: string;
}) {
  const reason =
    state === "legacy"
      ? "이 날짜를 발행한 시점에는 아직 이 지표를 수집·기록하지 않았습니다. 이후 발송분부터 표시됩니다."
      : state === "skipped"
        ? "과거 거래일 재발행분이라 이 지표가 포함되지 않았습니다 (KIS 지표는 거래일 당일에만 제공)."
        : "이 날짜에는 표시할 데이터가 없습니다.";
  return (
    <section
      className={`rounded-xl border border-dashed border-amber-300 dark:border-amber-700 bg-amber-50/50 dark:bg-amber-950/20 p-4 mb-4 ${className ?? ""}`}
    >
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
