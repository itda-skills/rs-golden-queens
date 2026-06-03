"use client";

// 사이트 헤더/푸터 — 좌측 날짜 사이드바와 함께 쓰는 상단 바/하단 바(전체 폭).
// 모바일에선 헤더 ☰ 로 사이드바 드로어를 연다(DrawerContext 공유). 데스크탑은
// 사이드바가 늘 고정이라 ☰ 를 숨긴다. 본문 폭 분기(usePathname)는 사이드바 도입으로
// 더는 필요 없어 제거했다 — 본문은 main 안 Container 가 자체 max-w 로 정렬한다.

import Link from "next/link";
import { useDrawer } from "./DrawerContext";

const NAV_LINKS = [
  { href: "/", label: "홈" },
  { href: "/calendar", label: "캘린더" },
  { href: "/guide", label: "가이드" },
];

export function SiteHeader() {
  const { setOpen } = useDrawer();
  return (
    <header className="border-b border-neutral-200 dark:border-neutral-800">
      <div className="flex items-center gap-2 px-4 py-3 sm:py-4">
        {/* 모바일 햄버거 — 사이드바 드로어 토글. lg+ 에선 사이드바가 고정이라 숨김. */}
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="날짜 메뉴 열기"
          className="-ml-1 rounded p-1.5 text-neutral-600 hover:bg-neutral-100 lg:hidden dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          <span className="block text-lg leading-none">☰</span>
        </button>
        <Link
          href="/"
          className="shrink-0 whitespace-nowrap text-lg font-bold tracking-tight"
        >
          📊 Golden Queens
        </Link>
        <nav className="-mr-1 ml-auto flex gap-4 overflow-x-auto whitespace-nowrap px-1 text-sm text-neutral-600 dark:text-neutral-300">
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
      <div className="space-y-1 px-4 py-6 text-xs text-neutral-500 dark:text-neutral-400">
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
