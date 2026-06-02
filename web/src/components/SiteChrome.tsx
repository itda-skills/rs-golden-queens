"use client";

// 사이트 헤더/푸터 — 라우트별 본문 폭(KR 상세 max-w-5xl, 그 외 max-w-3xl)에
// 맞춰 좌우 정렬을 일치시키려 usePathname 으로 폭을 분기한다(클라이언트 컴포넌트).
// layout 에서 headers() 로 라우트를 읽으면 KR 의 정적 생성(ISR)이 동적으로
// 전환되므로, 폭 분기는 이 작은 chrome 만 클라이언트로 두어 처리한다.

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/", label: "홈" },
  { href: "/calendar", label: "캘린더" },
  { href: "/guide", label: "가이드" },
];

// KR 상세(/kr/<date>)만 본문이 넓어진다 → 헤더/푸터도 같은 폭으로 정렬.
function shellMax(pathname: string | null): string {
  return pathname?.startsWith("/kr/") ? "max-w-5xl" : "max-w-3xl";
}

export function SiteHeader() {
  const max = shellMax(usePathname());
  // 좁은 화면(iPhone)에서 메뉴명이 2줄로 접히던 문제: 링크는 항상 1줄
  // (whitespace-nowrap·shrink-0)로 두고, 모바일은 로고/nav 를 세로 스택해 nav 가
  // 전체 폭을 쓰게 한다. sm+ 는 가로 배치. 넘치면 nav 가 가로 스크롤(안전망).
  return (
    <header className="border-b border-neutral-200 dark:border-neutral-800">
      <div className={`mx-auto flex ${max} flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:py-4`}>
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
  const max = shellMax(usePathname());
  return (
    <footer className="mt-auto border-t border-neutral-200 dark:border-neutral-800">
      <div className={`mx-auto ${max} px-4 py-6 text-xs text-neutral-500 dark:text-neutral-400 space-y-1`}>
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
