"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { colorClass, signedAmount, signedPct } from "@/lib/format";
import type { CalendarOverviews } from "@/lib/types";

// 거래일/휴장 캘린더 (표시 전용 — 판정은 발행된 calendar 스냅샷에 위임).
// 발행일 셀 클릭 시 팝오버: KR/US 각각의 링크 + 간략 overview.

const WD = ["일", "월", "화", "수", "목", "금", "토"];

function ymKey(y: number, m: number) {
  return `${y}-${String(m).padStart(2, "0")}`;
}

function iso(d: Date) {
  return d.toISOString().slice(0, 10);
}

// ISO week "YYYY-Www" → 그 주 목요일이 속한 [year, month]. 순수 ISO 8601 캘린더
// 산술이다(거래일/휴장 같은 시장 로직 아님). 목요일은 ISO 주의 대표일이라
// 월 경계에 걸친 주도 다수가 속한 달로 안정 귀속된다.
function isoWeekToYearMonth(weekStr: string): [number, number] | null {
  const m = /^(\d{4})-W(\d{2})$/.exec(weekStr);
  if (!m) return null;
  const year = Number(m[1]);
  const week = Number(m[2]);
  const jan4Dow = new Date(Date.UTC(year, 0, 4)).getUTCDay() || 7; // 1(월)~7(일)
  const thu = new Date(Date.UTC(year, 0, 4 - (jan4Dow - 1) + 3 + (week - 1) * 7));
  return [thu.getUTCFullYear(), thu.getUTCMonth() + 1];
}

export interface CalendarGridProps {
  krDays: string[];
  usDays: string[];
  krPublished: string[];
  usPublished: string[];
  overviews: CalendarOverviews;
  weekly: string[];
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
  overview,
  onClose,
}: {
  id: string;
  hasKr: boolean;
  hasUs: boolean;
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
    </div>
  );
}

function MonthCard({
  year,
  month,
  krSet,
  usSet,
  krPubSet,
  usPubSet,
  overviews,
  weeklyList,
  openId,
  setOpenId,
}: {
  year: number;
  month: number;
  krSet: Set<string>;
  usSet: Set<string>;
  krPubSet: Set<string>;
  usPubSet: Set<string>;
  overviews: CalendarOverviews;
  weeklyList: string[];
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
          const isKr = krSet.has(id);
          const isUs = usSet.has(id);
          const trading = isKr || isUs;
          const day = d.getUTCDate();
          const hasKr = krPubSet.has(id);
          const hasUs = usPubSet.has(id);
          const published = hasKr || hasUs;

          const dayClass = published
            ? "inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white font-semibold"
            : trading
              ? "inline-flex items-center justify-center w-6 h-6 text-neutral-800 dark:text-neutral-100"
              : "inline-flex items-center justify-center w-6 h-6 text-neutral-300 dark:text-neutral-700";

          const inner = (
            <>
              <span className={dayClass}>{day}</span>
              <div className="flex justify-center gap-0.5 h-1.5 mt-0.5">
                {isKr && <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />}
                {isUs && <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />}
              </div>
            </>
          );

          if (!published) {
            return (
              <div
                key={id}
                className="py-1"
                title={trading ? `${id} 거래일` : `${id} 휴장`}
              >
                {inner}
              </div>
            );
          }

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
                title={`${id} — 데이터 보기`}
              >
                {inner}
              </button>
              {open && (
                <Popover
                  id={id}
                  hasKr={hasKr}
                  hasUs={hasUs}
                  overview={overviews[id]}
                  onClose={() => setOpenId(null)}
                />
              )}
            </div>
          );
        })}
      </div>
      {weeklyList.length > 0 && (
        <div className="mt-2.5 pt-2.5 border-t border-neutral-100 dark:border-neutral-800">
          <div className="text-[10px] font-medium text-neutral-400 dark:text-neutral-500 mb-1.5">
            주간 리포트
          </div>
          <div className="flex flex-wrap gap-1.5">
            {weeklyList.map((w) => (
              <Link
                key={w}
                href={`/weekly/${w}`}
                title={w}
                className="text-[11px] px-2 py-0.5 rounded-md border border-neutral-200 dark:border-neutral-800 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400"
              >
                📅 {w.slice(5)}
              </Link>
            ))}
          </div>
        </div>
      )}
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

  const krSet = new Set(props.krDays);
  const usSet = new Set(props.usDays);
  const krPubSet = new Set(props.krPublished);
  const usPubSet = new Set(props.usPublished);
  // 최신 월을 먼저 — 2열 그리드에서 최신이 좌상단으로 온다.
  const months = [...monthsBetween(props.start, props.end)].reverse();

  // 주간 리포트를 ISO week 목요일이 속한 월에 귀속(ISO 8601). props.weekly 는
  // 이미 최신순이라 월별 리스트도 최신순을 유지한다.
  const weeklyByMonth = new Map<string, string[]>();
  for (const w of props.weekly) {
    const ym = isoWeekToYearMonth(w);
    if (!ym) continue;
    const key = ymKey(ym[0], ym[1]);
    const list = weeklyByMonth.get(key);
    if (list) list.push(w);
    else weeklyByMonth.set(key, [w]);
  }

  return (
    <div className="grid sm:grid-cols-2 gap-3">
      {months.map(([y, m]) => (
        <MonthCard
          key={ymKey(y, m)}
          year={y}
          month={m}
          krSet={krSet}
          usSet={usSet}
          krPubSet={krPubSet}
          usPubSet={usPubSet}
          overviews={props.overviews}
          weeklyList={weeklyByMonth.get(ymKey(y, m)) ?? []}
          openId={openId}
          setOpenId={setOpenId}
        />
      ))}
    </div>
  );
}
