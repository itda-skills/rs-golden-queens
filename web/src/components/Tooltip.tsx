"use client";

import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

// 경량 React 툴팁 — 브라우저 기본 title 대비 즉시 표시 + 디자인 일관. 의존성 없음.
// 마우스: hover 로 열고 닫음. 키보드: focus/blur + Esc. 터치/펜: 탭 토글 + 바깥 탭
// 닫기(트리거가 포커스 불가 요소여도 닫히도록 document 레벨에서 처리).
//
// follow=true: 말풍선이 커서를 따라다닌다(차트 막대용). body 로 포털 + position:fixed
// 라 차트의 overflow/transform 에 클리핑되지 않고, 세로 막대처럼 트리거가 큰 경우
// '컬럼 맨 아래'가 아니라 커서(=막대) 바로 옆에 뜬다. 터치는 탭 지점에 고정.

type Tone = "up" | "down" | "flat" | "dark";

// 톤별 배경/기본 글자색. 차트 값은 부호에서 파생(상승 빨강 / 하락 파랑 / 보합 회색,
// 모두 연한 파스텔). dark(기본)는 정보성 툴팁용 검정 — 종목명·ⓘ 등 기존 그대로.
const TONE_CLASS: Record<Tone, string> = {
  up: "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-200",
  down: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-200",
  flat: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200",
  dark: "bg-neutral-900 text-white dark:bg-neutral-700",
};

export function Tooltip({
  label,
  children,
  side = "bottom",
  disabled = false,
  className,
  as = "span",
  tone = "dark",
  follow = false,
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
  // 말풍선 톤. 기본 dark=검정(정보성). 차트는 format.direction() 값(up/down/flat)을
  // 그대로 넘겨 부호별 파스텔 색으로 표시한다.
  tone?: Tone;
  // true 면 말풍선이 커서를 따라다닌다(차트용). 기본은 트리거에 앵커.
  follow?: boolean;
}) {
  const [open, setOpen] = useState(false);
  // follow 시 말풍선 위치(뷰포트 좌표). null 이면 아직 좌표 없음(키보드 등) → 미표시.
  const [coords, setCoords] = useState<{ x: number; y: number } | null>(null);
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

  const sidePos = side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5";
  const bubbleBase = `pointer-events-none z-30 w-max max-w-[16rem] whitespace-normal text-left leading-snug rounded-md ${TONE_CLASS[tone]} px-2.5 py-1.5 text-xs shadow-lg`;

  const handlers = {
    // 마우스만 hover 로 열고 닫는다. 터치 pointerenter 는 무시 → 탭 토글로만 동작.
    onPointerEnter: (e: ReactPointerEvent) => {
      if (e.pointerType !== "mouse") return;
      if (follow) setCoords({ x: e.clientX, y: e.clientY });
      setOpen(true);
    },
    onPointerMove: (e: ReactPointerEvent) => {
      if (follow && e.pointerType === "mouse")
        setCoords({ x: e.clientX, y: e.clientY });
    },
    onPointerLeave: (e: ReactPointerEvent) => {
      if (e.pointerType === "mouse") setOpen(false);
    },
    onPointerDown: (e: ReactPointerEvent) => {
      pointerTypeRef.current = e.pointerType;
      // 터치/펜 탭은 탭 지점에 말풍선을 고정한다(따라다닐 커서가 없으므로).
      if (follow && e.pointerType !== "mouse")
        setCoords({ x: e.clientX, y: e.clientY });
    },
    // 터치/펜 탭 = 토글(다시 탭하면 닫힘). 마우스 클릭은 hover 가 담당하므로 무시.
    onClick: () => {
      if (pointerTypeRef.current !== "mouse") setOpen((o) => !o);
    },
    onFocus: () => setOpen(true),
    onBlur: () => setOpen(false),
  };

  const wrapperClassName = `relative inline-flex ${className ?? ""}`;

  let bubble: ReactNode = null;
  if (showing) {
    if (follow) {
      // 커서 추적 말풍선 — body 포털 + fixed. 화면 가장자리에선 반대쪽으로 플립.
      if (coords && typeof document !== "undefined") {
        const vw = typeof window !== "undefined" ? window.innerWidth : 0;
        const vh = typeof window !== "undefined" ? window.innerHeight : 0;
        const flipX = vw > 0 && coords.x > vw - 280;
        const flipY = vh > 0 && coords.y > vh - 140;
        const tx = flipX ? "calc(-100% - 14px)" : "14px";
        const ty = flipY ? "calc(-100% - 14px)" : "16px";
        bubble = createPortal(
          <span
            role="tooltip"
            className={`fixed ${bubbleBase}`}
            style={{ left: coords.x, top: coords.y, transform: `translate(${tx}, ${ty})` }}
          >
            {label}
          </span>,
          document.body,
        );
      }
    } else {
      bubble = (
        <span
          role="tooltip"
          className={`absolute left-1/2 -translate-x-1/2 ${sidePos} ${bubbleBase}`}
        >
          {label}
        </span>
      );
    }
  }

  const inner = (
    <>
      {children}
      {bubble}
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
