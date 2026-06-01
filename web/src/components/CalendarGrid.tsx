"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { colorClass, signedAmount, signedPct } from "@/lib/format";
import type { CalendarOverviews } from "@/lib/types";

// 발행 캘린더 (표시 전용 — 판정은 발행된 calendar 스냅샷에 위임).
// 발행(데이터 있는) 날짜만 마커·클릭을 노출한다. 셀 클릭 시 팝오버:
// KR/US 링크 + 그 주 주간 리포트 링크 + 간략 overview.

const WD = ["일", "월", "화", "수", "목", "금", "토"];

function ymKey(y: number, m: number) {
  return `${y}-${String(m).padStart(2, "0")}`;
}

function iso(d: Date) {
  return d.toISOString().slice(0, 10);
}

export interface CalendarGridProps {
  krPublished: string[];
  usPublished: string[];
  overviews: CalendarOverviews;
  // 주간 리포트 기준일(snap.date) → ISO week. 그 셀에 주간 마커·링크를 배치한다.
  weeklyByDate: Record<string, string>;
  start: string;
  end: string;
}

function* monthsBetween(start: string, end: string) {
  const [sy, sm] = start.split("-").map(Number);
  const [ey, em] = end.split("-").map(Number);
  let y = sy;
  let m = sm;
  while (y < ey || (y === ey && m <= em)) {
    yield [y, m] as [number, number];
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
}

function Popover({
  id,
  hasKr,
  hasUs,
  week,
  overview,
  onClose,
}: {
  id: string;
  hasKr: boolean;
  hasUs: boolean;
  week?: string;
  overview?: CalendarOverviews[string];
  onClose: () => void;
}) {
  return (
    <div
      className="absolute z-20 left-1/2 -translate-x-1/2 top-full mt-1 w-44 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 shadow-lg p-2 text-left"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="text-[11px] font-semibold text-neutral-500 dark:text-neutral-400 mb-1.5">
        {id}
      </div>
      {hasKr && (
        <Link
          href={`/kr/${id}`}
          onClick={onClose}
          className="block rounded-md px-2 py-1.5 mb-1 hover:bg-rose-50 dark:hover:bg-rose-950/30"
        >
          <div className="text-xs font-medium text-rose-600 dark:text-rose-400">
            🇰🇷 한국장 →
          </div>
          {overview?.kr && (
            <div className="text-[10px] text-neutral-500 dark:text-neutral-400 mt-0.5">
              외인{" "}
              <span className={colorClass(overview.kr.foreign)}>
                {signedAmount(overview.kr.foreign)}
              </span>{" "}
              · 기관{" "}
              <span className={colorClass(overview.kr.institutional)}>
                {signedAmount(overview.kr.institutional)}
              </span>
            </div>
          )}
        </Link>
      )}
      {hasUs && (
        <Link
          href={`/us/${id}`}
          onClick={onClose}
          className="block rounded-md px-2 py-1.5 hover:bg-blue-50 dark:hover:bg-blue-950/30"
        >
          <div className="text-xs font-medium text-blue-600 dark:text-blue-400">
            🇺🇸 미국장 →
          </div>
          {overview?.us && (
            <div className="text-[10px] text-neutral-500 dark:text-neutral-400 mt-0.5">
              S&amp;P{" "}
              <span className={colorClass(overview.us.sp500Pct)}>
                {signedPct(overview.us.sp500Pct)}
              </span>
              {overview.us.vix != null && <> · VIX {overview.us.vix.toFixed(2)}</>}
            </div>
          )}
        </Link>
      )}
      {week && (
        <Link
          href={`/weekly/${week}`}
          onClick={onClose}
          className={`block rounded-md px-2 py-1.5 hover:bg-amber-50 dark:hover:bg-amber-950/30${
            hasKr || hasUs
              ? " mt-1 pt-2 border-t border-neutral-100 dark:border-neutral-800"
              : ""
          }`}
        >
          <div className="text-xs font-medium text-amber-600 dark:text-amber-500">
            📅 주간 리포트 →
          </div>
          <div className="text-[10px] text-neutral-500 dark:text-neutral-400 mt-0.5">
            {week}
          </div>
        </Link>
      )}
    </div>
  );
}

function MonthCard({
  year,
  month,
  krPubSet,
  usPubSet,
  overviews,
  weeklyByDate,
  openId,
  setOpenId,
}: {
  year: number;
  month: number;
  krPubSet: Set<string>;
  usPubSet: Set<string>;
  overviews: CalendarOverviews;
  weeklyByDate: Record<string, string>;
  openId: string | null;
  setOpenId: (id: string | null) => void;
}) {
  const first = new Date(Date.UTC(year, month - 1, 1));
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const leading = first.getUTCDay();
  const cells: (Date | null)[] = [];
  for (let i = 0; i < leading; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++)
    cells.push(new Date(Date.UTC(year, month - 1, d)));

  return (
    <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-3">
      <div className="font-semibold text-sm mb-2">
        {year}년 {month}월
      </div>
      <div className="grid grid-cols-7 gap-0.5 text-center text-[11px]">
        {WD.map((w, i) => (
          <div
            key={w}
            className={`py-1 ${i === 0 ? "text-rose-500" : i === 6 ? "text-blue-500" : "text-neutral-400"}`}
          >
            {w}
          </div>
        ))}
        {cells.map((d, i) => {
          if (!d) return <div key={`e${i}`} />;
          const id = iso(d);
          const day = d.getUTCDate();
          const hasKr = krPubSet.has(id);
          const hasUs = usPubSet.has(id);
          const week = weeklyByDate[id];
          const hasWeekly = !!week;
          // 발행(데이터 있는) 날짜만 마커·클릭을 노출한다.
          const clickable = hasKr || hasUs || hasWeekly;

          const dayClass = clickable
            ? "inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white font-semibold"
            : "inline-flex items-center justify-center w-6 h-6 text-neutral-300 dark:text-neutral-600";

          if (!clickable) {
            return (
              <div key={id} className="py-1">
                <span className={dayClass}>{day}</span>
              </div>
            );
          }

          // KR/US 마커와 동일한 점(dot) 방식으로 주간 리포트도 표시(amber).
          const inner = (
            <>
              <span className={dayClass}>{day}</span>
              <div className="flex justify-center gap-0.5 h-1.5 mt-0.5">
                {hasKr && <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />}
                {hasUs && <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />}
                {hasWeekly && (
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                )}
              </div>
            </>
          );

          const open = openId === id;
          return (
            <div key={id} className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpenId(open ? null : id);
                }}
                className={`w-full py-1 rounded cursor-pointer ${open ? "bg-blue-50 dark:bg-blue-950/40" : "hover:bg-blue-50 dark:hover:bg-blue-950/40"}`}
                aria-expanded={open}
                title={
                  hasWeekly ? `${id} — 데이터·주간 리포트 보기` : `${id} — 데이터 보기`
                }
              >
                {inner}
              </button>
              {open && (
                <Popover
                  id={id}
                  hasKr={hasKr}
                  hasUs={hasUs}
                  week={week}
                  overview={overviews[id]}
                  onClose={() => setOpenId(null)}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function CalendarGrid(props: CalendarGridProps) {
  const [openId, setOpenId] = useState<string | null>(null);

  // 바깥 클릭/ESC 시 팝오버 닫기
  useEffect(() => {
    if (!openId) return;
    const close = () => setOpenId(null);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpenId(null);
    document.addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [openId]);

  const krPubSet = new Set(props.krPublished);
  const usPubSet = new Set(props.usPublished);
  // 최신 월을 먼저 — 2열 그리드에서 최신이 좌상단으로 온다.
  const months = [...monthsBetween(props.start, props.end)].reverse();

  return (
    <div className="grid sm:grid-cols-2 gap-3">
      {months.map(([y, m]) => (
        <MonthCard
          key={ymKey(y, m)}
          year={y}
          month={m}
          krPubSet={krPubSet}
          usPubSet={usPubSet}
          overviews={props.overviews}
          weeklyByDate={props.weeklyByDate}
          openId={openId}
          setOpenId={setOpenId}
        />
      ))}
    </div>
  );
}
