import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Container } from "@/components/Layout";
import { GUIDE_GROUPS } from "@/lib/guide-content";

export const metadata: Metadata = {
  title: "지표 읽는 법 — 해석 가이드",
  description:
    "화면의 각 시장 데이터를 어떤 관점에서 보면 좋은지 설명하는 가이드. 지표의 의미와 해석 관점만 제공하며, 투자 권유·종목 추천·매매 시점 판단이 아닙니다.",
};

function Block({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="mt-3 first:mt-0">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400 dark:text-neutral-500 mb-1">
        {label}
      </p>
      <div className="text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed">
        {children}
      </div>
    </div>
  );
}

function UpcomingBadge() {
  return (
    <span className="ml-2 align-middle rounded-full border border-amber-400/60 bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-400">
      향후 추가 예정 · 현재 미표시
    </span>
  );
}

export default function GuidePage() {
  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">지표 읽는 법</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-5 leading-relaxed">
        화면의 각 데이터를 어떤 관점에서 보면 좋은지 설명합니다. 지표의 의미와
        해석 관점만 제공하며, 투자 권유·종목 추천·매매 시점 판단이 아닙니다.
      </p>

      {/* 목차 */}
      <nav
        aria-label="목차"
        className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4 mb-8"
      >
        <p className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 mb-2">
          목차
        </p>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
          {GUIDE_GROUPS.map((g) => (
            <li key={g.key}>
              <a
                href={`#${g.key}`}
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                {g.title}
              </a>
              {g.upcoming && (
                <span className="ml-1 text-[11px] text-amber-600 dark:text-amber-400">
                  (향후)
                </span>
              )}
            </li>
          ))}
        </ul>
      </nav>

      {GUIDE_GROUPS.map((group) => (
        <section
          key={group.key}
          id={group.key}
          className="mb-10 scroll-mt-20"
        >
          <h2 className="text-lg font-bold mb-3 pb-1.5 border-b border-neutral-200 dark:border-neutral-800">
            {group.title}
            {group.upcoming && <UpcomingBadge />}
          </h2>

          {group.upcoming && (
            <p className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 rounded-lg px-3 py-2 mb-4 leading-relaxed">
              아래 항목은 아직 화면·발행 데이터에 없는, 향후 추가를 검토 중인
              지표의 해석 가이드입니다. 봇이 파생값을 스냅샷에 담은 뒤 정식
              지표로 편입됩니다.
            </p>
          )}

          <div className="space-y-4">
            {group.items.map((item) => (
              <article
                key={item.key}
                id={item.key}
                className={`scroll-mt-20 rounded-xl border p-4 ${
                  item.upcoming
                    ? "border-dashed border-neutral-300 dark:border-neutral-700 bg-neutral-50/50 dark:bg-neutral-900/30"
                    : "border-neutral-200 dark:border-neutral-800"
                }`}
              >
                <h3 className="font-semibold mb-1">{item.indicator}</h3>
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-2 italic">
                  {item.tooltip}
                </p>
                <Block label="무엇인지">{item.what}</Block>
                <Block label="이렇게 보면 좋습니다">
                  <ul className="list-disc pl-4 space-y-1">
                    {item.howToRead.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                </Block>
                <Block label="흔한 오해">{item.misread}</Block>
              </article>
            ))}
          </div>
        </section>
      ))}

      <p className="text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed border-t border-neutral-200 dark:border-neutral-800 pt-4">
        본 가이드는 지표의 의미와 해석 관점을 설명하는 교육 자료입니다. 어떤
        지표도 매수·매도 신호나 추천으로 해석되지 않으며, 모든 수치는 출처·기준일에
        따라 지연·오류가 있을 수 있습니다. 색 컨벤션은 한국 증시 관례(🔴빨강=상승·순매수
        / 🔵파랑=하락·순매도)를 따릅니다.
      </p>
    </Container>
  );
}
