"use client";

import { Children, useState, type ReactNode } from "react";

// 표의 기본 N개만 먼저 보여주고, 초과분은 '더 보기'로 같은 자리에 펼친다(인라인).
// 항목이 initial 이하면 버튼을 숨긴다(기존 5개 스냅샷도 그대로 동작 — 하위 호환).
// 행 렌더는 호출부(server)가 children 으로 넘기고, 여기선 펼침 상태만 관리한다
// (데이터 재수집 없음 — 스냅샷이 이미 담은 행을 펼칠 뿐).
export function Expandable({
  children,
  initial = 5,
}: {
  children: ReactNode;
  initial?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const rows = Children.toArray(children);
  const hasMore = rows.length > initial;
  const shown = expanded ? rows : rows.slice(0, initial);

  return (
    <>
      {shown}
      {hasMore && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-2 w-full text-center text-xs text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200"
        >
          {expanded ? "⌃ 접기" : `⌄ ${rows.length - initial}개 더 보기`}
        </button>
      )}
    </>
  );
}
