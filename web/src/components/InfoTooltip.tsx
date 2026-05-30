import Link from "next/link";
import { Tooltip } from "./Tooltip";

// 카드 제목 옆 ⓘ — hover/focus 시 한 줄 설명, 클릭 시 /guide 해당 섹션으로 이동.
// 해석 가이드는 정적 콘텐츠(권유·시점판단 없음). 텍스트는 guide-content.ts 원본을 참조.

function Dot() {
  return (
    <span
      aria-hidden
      className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-neutral-300 dark:border-neutral-600 text-[10px] font-semibold leading-none text-neutral-400 dark:text-neutral-500 transition-colors group-hover:text-neutral-600 dark:group-hover:text-neutral-300"
    >
      i
    </span>
  );
}

export function InfoTooltip({ tooltip, href }: { tooltip: string; href?: string }) {
  const trigger = href ? (
    <Link
      href={href}
      aria-label={`${tooltip} — 가이드에서 자세히 보기`}
      className="group inline-flex cursor-help align-middle"
    >
      <Dot />
    </Link>
  ) : (
    <span
      role="note"
      tabIndex={0}
      aria-label={tooltip}
      className="group inline-flex cursor-help align-middle"
    >
      <Dot />
    </span>
  );

  return <Tooltip label={tooltip}>{trigger}</Tooltip>;
}
