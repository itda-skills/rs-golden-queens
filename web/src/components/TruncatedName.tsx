"use client";

import { useEffect, useRef, useState } from "react";
import { Tooltip } from "./Tooltip";

// 종목명 셀. 좁은 카드에서 이름이 셀 폭을 넘으면 …로 자르고(truncate), 잘린
// 경우에만 React 툴팁으로 전체 이름을 노출한다(hover·키보드 focus·터치 탭).
// 값(외/기)은 호출부에서 nowrap·고정폭으로 두므로, 폭 양보는 이 이름만 한다.
//
// 자름 여부는 렌더 후에야 알 수 있어(scrollWidth>clientWidth) client 컴포넌트로
// 측정한다. 폭이 바뀌면(반응형/3열↔1열) ResizeObserver 로 다시 판정한다.
export function TruncatedName({ name }: { name: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [truncated, setTruncated] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setTruncated(el.scrollWidth > el.clientWidth + 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [name]);

  return (
    <Tooltip label={name} disabled={!truncated} className="min-w-0 flex-1">
      <span
        ref={ref}
        tabIndex={truncated ? 0 : -1}
        className={`block w-full truncate ${truncated ? "cursor-help" : ""}`}
      >
        {name}
      </span>
    </Tooltip>
  );
}
