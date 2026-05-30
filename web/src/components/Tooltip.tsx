"use client";

import { useState, type ReactNode } from "react";

// 경량 React 툴팁 — 브라우저 기본 title 대비 즉시 표시 + 디자인 일관.
// hover/focus 시 표시. 의존성 없음.

export function Tooltip({
  label,
  children,
  side = "bottom",
}: {
  label: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
}) {
  const [open, setOpen] = useState(false);

  const pos =
    side === "top"
      ? "bottom-full mb-1.5"
      : "top-full mt-1.5";

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          className={`pointer-events-none absolute left-1/2 -translate-x-1/2 ${pos} z-30 whitespace-nowrap rounded-md bg-neutral-900 dark:bg-neutral-700 px-2 py-1 text-xs text-white shadow-lg`}
        >
          {label}
        </span>
      )}
    </span>
  );
}
