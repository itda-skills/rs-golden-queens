"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

// 상세 페이지 이전/다음 이동 + 키보드 단축키(←/→).
// 발행 목록(index)은 최신순(내림차순) — 왼쪽=이전(과거), 오른쪽=다음(미래).

export interface NavItem {
  href: string;
  label: string; // 예: "5/28 (목)"
}

export function adjacent(
  ids: string[],
  current: string,
): { prev: string | null; next: string | null } {
  const i = ids.indexOf(current);
  if (i === -1) return { prev: null, next: null };
  // ids 내림차순: i+1 = 더 과거(prev), i-1 = 더 미래(next)
  return {
    prev: i + 1 < ids.length ? ids[i + 1] : null,
    next: i - 1 >= 0 ? ids[i - 1] : null,
  };
}

export function PrevNext({
  prev,
  next,
}: {
  prev: NavItem | null;
  next: NavItem | null;
}) {
  const router = useRouter();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // 입력 요소에 포커스가 있으면 무시
      const el = e.target as HTMLElement | null;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "ArrowLeft" && prev) {
        router.push(prev.href);
      } else if (e.key === "ArrowRight" && next) {
        router.push(next.href);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prev, next, router]);

  return (
    <nav className="flex items-center justify-between gap-2 mt-2 mb-6">
      {prev ? (
        <Link
          href={prev.href}
          title="이전 (← 방향키)"
          className="flex items-center gap-1 text-sm rounded-lg border border-neutral-200 dark:border-neutral-800 px-3 py-2 hover:border-blue-400"
        >
          <kbd className="text-[10px] px-1 rounded border border-neutral-300 dark:border-neutral-600">
            ←
          </kbd>
          <span className="text-neutral-500 dark:text-neutral-400">이전</span>
          <span className="font-medium">{prev.label}</span>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link
          href={next.href}
          title="다음 (→ 방향키)"
          className="flex items-center gap-1 text-sm rounded-lg border border-neutral-200 dark:border-neutral-800 px-3 py-2 hover:border-blue-400"
        >
          <span className="font-medium">{next.label}</span>
          <span className="text-neutral-500 dark:text-neutral-400">다음</span>
          <kbd className="text-[10px] px-1 rounded border border-neutral-300 dark:border-neutral-600">
            →
          </kbd>
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
