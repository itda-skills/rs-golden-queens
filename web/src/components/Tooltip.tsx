"use client";

import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

// 경량 React 툴팁 — 브라우저 기본 title 대비 즉시 표시 + 디자인 일관. 의존성 없음.
// 마우스: hover 로 열고 닫음. 키보드: focus/blur + Esc. 터치/펜: 탭 토글 + 바깥 탭
// 닫기(트리거가 포커스 불가 요소여도 닫히도록 document 레벨에서 처리).

export function Tooltip({
  label,
  children,
  side = "bottom",
  disabled = false,
  className,
  as = "span",
  tone = "flat",
}: {
  label: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
  // true 면 트리거(children)는 그대로 두고 말풍선만 띄우지 않는다 — 예: 잘리지
  // 않아 전체가 이미 보이는 종목명. 측정 결과에 따라 호출부가 토글한다.
  disabled?: boolean;
  // 래퍼 span 에 덧붙일 클래스 — flex 셀 안에서 min-w-0/flex-1 로 줄어들게 할 때.
  className?: string;
  // 래퍼 요소. 기본 span(phrasing). 차트 막대처럼 block(div) 자식을 감쌀 땐 "div"
  // 로 줘 div-in-span 부적합을 피한다. 기존 호출부는 기본값 span 그대로.
  as?: "span" | "div";
  // 말풍선 배경 톤 — 수치 부호에서 파생(상승 빨강 / 하락 파랑 / 보합·무값 검정).
  // 기본 flat 은 기존 검정. format.direction() 의 반환값을 그대로 넘기면 된다.
  tone?: "up" | "down" | "flat";
}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLElement | null>(null);
  // 마지막 포인터 종류 — 마우스는 hover 가 담당하므로 onClick 토글에서 제외하고,
  // 터치/펜 탭만 토글한다. onClick 엔 pointerType 이 없어 pointerdown 에서 기록한다.
  const pointerTypeRef = useRef<string>("mouse");

  const showing = open && !disabled;

  // 표시 중일 때만: 바깥 탭/클릭 → 닫기(차트 막대처럼 포커스 불가라 blur 로 못 닫는
  // 경우 대비), Esc → 닫기.
  useEffect(() => {
    if (!showing) return;
    const onDocPointerDown = (e: PointerEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onDocPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onDocPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [showing]);

  const pos = side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5";

  // 한국 색 컨벤션(상승 빨강 / 하락 파랑). 흰 글자 가독성 위해 진한 600 단계.
  const toneBg =
    tone === "up"
      ? "bg-rose-600"
      : tone === "down"
        ? "bg-blue-600"
        : "bg-neutral-900 dark:bg-neutral-700";

  const handlers = {
    // 마우스만 hover 로 열고 닫는다. 터치 pointerenter 는 무시 → 탭 토글로만 동작.
    onPointerEnter: (e: ReactPointerEvent) => {
      if (e.pointerType === "mouse") setOpen(true);
    },
    onPointerLeave: (e: ReactPointerEvent) => {
      if (e.pointerType === "mouse") setOpen(false);
    },
    onPointerDown: (e: ReactPointerEvent) => {
      pointerTypeRef.current = e.pointerType;
    },
    // 터치/펜 탭 = 토글(다시 탭하면 닫힘). 마우스 클릭은 hover 가 담당하므로 무시.
    onClick: () => {
      if (pointerTypeRef.current !== "mouse") setOpen((o) => !o);
    },
    onFocus: () => setOpen(true),
    onBlur: () => setOpen(false),
  };

  const wrapperClassName = `relative inline-flex ${className ?? ""}`;

  const inner = (
    <>
      {children}
      {showing && (
        <span
          role="tooltip"
          className={`pointer-events-none absolute left-1/2 -translate-x-1/2 ${pos} z-30 w-max max-w-[16rem] whitespace-normal text-left leading-snug rounded-md ${toneBg} px-2.5 py-1.5 text-xs text-white shadow-lg`}
        >
          {label}
        </span>
      )}
    </>
  );

  if (as === "div") {
    return (
      <div
        ref={(el) => {
          wrapperRef.current = el;
        }}
        className={wrapperClassName}
        {...handlers}
      >
        {inner}
      </div>
    );
  }
  return (
    <span
      ref={(el) => {
        wrapperRef.current = el;
      }}
      className={wrapperClassName}
      {...handlers}
    >
      {inner}
    </span>
  );
}
