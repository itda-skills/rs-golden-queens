"use client";

import { useState, type ReactNode } from "react";

// 경량 React 툴팁 — 브라우저 기본 title 대비 즉시 표시 + 디자인 일관.
// hover/focus 시 표시. 의존성 없음.

export function Tooltip({
  label,
  children,
  side = "bottom",
  disabled = false,
  className,
}: {
  label: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
  // true 면 트리거(children)는 그대로 두고 말풍선만 띄우지 않는다 — 예: 잘리지
  // 않아 전체가 이미 보이는 종목명. 측정 결과에 따라 호출부가 토글한다.
  disabled?: boolean;
  // 래퍼 span 에 덧붙일 클래스 — flex 셀 안에서 min-w-0/flex-1 로 줄어들게 할 때.
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  const pos =
    side === "top"
      ? "bottom-full mb-1.5"
      : "top-full mt-1.5";

  return (
    <span
      className={`relative inline-flex ${className ?? ""}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      // 터치(탭)에도 열리게 — 모바일엔 hover 가 없다. 닫기는 blur(바깥 탭).
      onClick={() => setOpen(true)}
    >
      {children}
      {open && !disabled && (
        <span
          role="tooltip"
          className={`pointer-events-none absolute left-1/2 -translate-x-1/2 ${pos} z-30 w-max max-w-[16rem] whitespace-normal text-left leading-snug rounded-md bg-neutral-900 dark:bg-neutral-700 px-2.5 py-1.5 text-xs text-white shadow-lg`}
        >
          {label}
        </span>
      )}
    </span>
  );
}
