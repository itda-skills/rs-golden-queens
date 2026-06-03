"use client";

// 좌측 날짜 사이드바 — 🇰🇷 코스피 / 🇺🇸 미국지수 / 📈 주간리포트 3섹션, 각 하위에
// 발행 날짜 링크. 데이터는 발행 index(getIndex)에서 layout 이 server fetch 해 넘긴다
// (웹은 새로 수집·계산하지 않는다). 현재 보는 날짜를 usePathname 으로 하이라이트하고,
// 모바일에선 헤더 ☰ 가 여는 드로어로 표시한다(DrawerContext 공유).

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useDrawer } from "./DrawerContext";
import { shortDateWeekday } from "@/lib/format";
import type { IndexFile } from "@/lib/types";

// 섹션별 표시 상한 — 최근 3일치만 노출하고 나머지는 캘린더로 유도(사이드바를 짧게).
const MAX_PER_SECTION = 3;

interface Section {
  key: string;
  label: string;
  emoji: string;
  base: string;
  dates: string[];
  fmt: (d: string) => string;
}

export function Sidebar({
  index,
  weeklyDates,
}: {
  index: IndexFile | null;
  // 주간 키("2026-W22") → 발행 기준일("2026-05-29") 매핑. layout 이 fetch 해 넘긴다.
  weeklyDates: Record<string, string | null>;
}) {
  const pathname = usePathname();
  const { open, setOpen } = useDrawer();
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // 드로어 열린 동안 ESC 로 닫기.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  const toggle = (k: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  const sections: Section[] = [
    { key: "kr", label: "코스피", emoji: "🇰🇷", base: "/kr", dates: index?.kr ?? [], fmt: shortDateWeekday },
    { key: "us", label: "미국지수", emoji: "🇺🇸", base: "/us", dates: index?.us ?? [], fmt: shortDateWeekday },
    {
      key: "weekly",
      label: "주간리포트",
      emoji: "📈",
      base: "/weekly",
      dates: index?.weekly ?? [],
      // 키(2026-W22) 대신 발행 '기준일'(수집된 날짜)을 코스피·미국과 같은 형식으로.
      fmt: (w) => {
        const d = weeklyDates[w];
        return d ? shortDateWeekday(d) : w;
      },
    },
  ];

  const renderNav = () => (
    <nav className="space-y-4 p-4 text-sm">
      {sections.map((s) => {
        const dates = [...s.dates].sort().reverse(); // 최신 먼저
        const shown = dates.slice(0, MAX_PER_SECTION);
        const more = dates.length - shown.length;
        const isCollapsed = collapsed.has(s.key);
        return (
          <div key={s.key}>
            <button
              type="button"
              onClick={() => toggle(s.key)}
              aria-expanded={!isCollapsed}
              className="flex w-full items-center justify-between rounded px-2 py-1.5 font-semibold text-neutral-700 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-neutral-800/60"
            >
              <span>
                {s.emoji} {s.label}
              </span>
              <span className="text-xs text-neutral-400">
                {isCollapsed ? "▸" : "▾"}
              </span>
            </button>
            {!isCollapsed && (
              <ul className="mt-1 space-y-0.5">
                {shown.length === 0 && (
                  <li className="px-2 py-1 text-xs text-neutral-400">
                    발행된 날짜가 없습니다
                  </li>
                )}
                {shown.map((date) => {
                  const href = `${s.base}/${date}`;
                  const active = pathname === href;
                  return (
                    <li key={date}>
                      <Link
                        href={href}
                        scroll={false}
                        onClick={() => setOpen(false)}
                        aria-current={active ? "page" : undefined}
                        className={`block rounded px-2 py-1 tabular-nums ${
                          active
                            ? "bg-neutral-200 font-medium text-neutral-900 dark:bg-neutral-700 dark:text-white"
                            : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800/60"
                        }`}
                      >
                        {s.fmt(date)}
                      </Link>
                    </li>
                  );
                })}
                {more > 0 && (
                  <li>
                    <Link
                      href="/calendar"
                      onClick={() => setOpen(false)}
                      className="block rounded px-2 py-1 text-xs text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600 dark:hover:bg-neutral-800/60"
                    >
                      + {more}개 더 · 캘린더에서 전체 보기
                    </Link>
                  </li>
                )}
              </ul>
            )}
          </div>
        );
      })}
    </nav>
  );

  return (
    <>
      {/* 데스크탑: 좌측 고정 (본문 스크롤에도 sticky 유지) */}
      <aside className="hidden w-64 shrink-0 border-r border-neutral-200 dark:border-neutral-800 lg:block">
        <div className="sticky top-0 max-h-screen overflow-y-auto">
          {renderNav()}
        </div>
      </aside>

      {/* 모바일: ☰ 가 여는 드로어(오버레이 + 좌측 패널) */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <aside className="absolute left-0 top-0 h-full w-72 max-w-[80%] overflow-y-auto border-r border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-950">
            <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3 dark:border-neutral-800">
              <span className="font-semibold">날짜</span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="닫기"
                className="rounded p-1 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                ✕
              </button>
            </div>
            {renderNav()}
          </aside>
        </div>
      )}
    </>
  );
}
