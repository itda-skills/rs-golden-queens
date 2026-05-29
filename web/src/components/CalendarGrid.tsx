import Link from "next/link";

// 거래일/휴장 캘린더 (표시 전용 — 판정은 발행된 calendar 스냅샷에 위임).
// kr/us 거래일 집합을 받아 월별 그리드로 표시. 발행된 날짜는 상세로 링크.

const WD = ["일", "월", "화", "수", "목", "금", "토"];

function ymKey(d: Date) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function iso(d: Date) {
  return d.toISOString().slice(0, 10);
}

export interface CalendarGridProps {
  krDays: Set<string>;
  usDays: Set<string>;
  krPublished: Set<string>;
  usPublished: Set<string>;
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

function MonthCard({
  year,
  month,
  krDays,
  usDays,
  krPublished,
  usPublished,
}: {
  year: number;
  month: number;
} & Omit<CalendarGridProps, "start" | "end">) {
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
          const isKr = krDays.has(id);
          const isUs = usDays.has(id);
          const trading = isKr || isUs;
          const day = d.getUTCDate();
          const krLink = krPublished.has(id) ? `/kr/${id}` : null;
          // US 발행일은 미국 거래일 기준이라 같은 날짜로 링크
          const usLink = usPublished.has(id) ? `/us/${id}` : null;
          const link = krLink ?? usLink;
          const published = !!link;

          // 발행일이면 날짜 숫자에 동그라미 강조 (클릭 가능 단서)
          const dayClass = published
            ? "inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white font-semibold"
            : trading
              ? "inline-flex items-center justify-center w-6 h-6 text-neutral-800 dark:text-neutral-100"
              : "inline-flex items-center justify-center w-6 h-6 text-neutral-300 dark:text-neutral-700";

          const content = (
            <div
              className={`py-1 rounded ${published ? "hover:bg-blue-50 dark:hover:bg-blue-950/40" : ""}`}
            >
              <span className={dayClass}>{day}</span>
              <div className="flex justify-center gap-0.5 h-1.5 mt-0.5">
                {isKr && <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />}
                {isUs && <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />}
              </div>
            </div>
          );

          return link ? (
            <Link key={id} href={link} title={`${id} — 데이터 보기`}>
              {content}
            </Link>
          ) : (
            <div key={id} title={trading ? `${id} 거래일` : `${id} 휴장`}>
              {content}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function CalendarGrid(props: CalendarGridProps) {
  const months = [...monthsBetween(props.start, props.end)];
  return (
    <div className="grid sm:grid-cols-2 gap-3">
      {months.map(([y, m]) => (
        <MonthCard key={ymKey(new Date(Date.UTC(y, m - 1, 1)))} year={y} month={m} {...props} />
      ))}
    </div>
  );
}
