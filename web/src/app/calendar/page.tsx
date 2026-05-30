import { Card, Container } from "@/components/Layout";
import { CalendarGrid } from "@/components/CalendarGrid";
import { getCalendar, getIndex, getKrSnapshot, getUsSnapshot } from "@/lib/data";
import type { CalendarOverviews } from "@/lib/types";

export const revalidate = 600;
export const metadata = { title: "거래일 캘린더" };

async function buildOverviews(
  krDates: string[],
  usDates: string[],
): Promise<CalendarOverviews> {
  const out: CalendarOverviews = {};
  // 발행된 날짜만 (소수) — 병렬 fetch
  const krSnaps = await Promise.all(krDates.map((d) => getKrSnapshot(d)));
  krSnaps.forEach((s, i) => {
    const k = s?.payload?.kospi;
    if (k) {
      out[krDates[i]] = {
        ...(out[krDates[i]] ?? {}),
        kr: {
          foreign: k.foreign,
          institutional: k.institutional,
          personal: k.personal,
        },
      };
    }
  });
  const usSnaps = await Promise.all(usDates.map((d) => getUsSnapshot(d)));
  usSnaps.forEach((s, i) => {
    const gspc = s?.payload?.indices?.["^GSPC"];
    const vix = s?.payload?.volatility?.["^VIX"];
    if (gspc) {
      out[usDates[i]] = {
        ...(out[usDates[i]] ?? {}),
        us: { sp500Pct: gspc.pct, vix: vix?.close ?? null },
      };
    }
  });
  return out;
}

export default async function CalendarPage() {
  const [cal, index] = await Promise.all([getCalendar(), getIndex()]);

  if (!cal) {
    return (
      <Container>
        <h1 className="text-xl font-bold mb-6">거래일 캘린더</h1>
        <Card>
          <p className="text-sm text-neutral-500">
            아직 캘린더 데이터가 발행되지 않았습니다.
          </p>
        </Card>
      </Container>
    );
  }

  const krPublished = index?.kr ?? [];
  const usPublished = index?.us ?? [];
  const overviews = await buildOverviews(krPublished, usPublished);

  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">거래일 캘린더</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-4">
        KR/US 거래일·휴장. 발행된 날짜(동그라미)를 클릭하면 한국장·미국장 데이터를
        선택해 볼 수 있습니다.
      </p>
      <div className="flex flex-wrap gap-4 text-xs text-neutral-500 dark:text-neutral-400 mb-4">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" /> 한국 거래일
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> 미국 거래일
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-blue-600 text-white text-[9px]">
            5
          </span>{" "}
          발행됨 (클릭하여 보기)
        </span>
      </div>
      <CalendarGrid
        krDays={cal.kr}
        usDays={cal.us}
        krPublished={krPublished}
        usPublished={usPublished}
        overviews={overviews}
        start={cal.range.start}
        end={cal.range.end}
      />
      <p className="text-xs text-neutral-400 mt-4">
        거래일·휴장 판정 출처: 발행된 캘린더 스냅샷 (XKRX / NYSE).
      </p>
    </Container>
  );
}
