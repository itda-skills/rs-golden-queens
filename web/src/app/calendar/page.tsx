import { Card, Container } from "@/components/Layout";
import { CalendarGrid } from "@/components/CalendarGrid";
import { getCalendar, getIndex } from "@/lib/data";

export const revalidate = 600;
export const metadata = { title: "거래일 캘린더" };

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

  const krDays = new Set(cal.kr);
  const usDays = new Set(cal.us);
  const krPublished = new Set(index?.kr ?? []);
  const usPublished = new Set(index?.us ?? []);

  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">거래일 캘린더</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-4">
        KR/US 거래일·휴장. 발행된 날짜는 클릭하면 상세로 이동합니다.
      </p>
      <div className="flex gap-4 text-xs text-neutral-500 dark:text-neutral-400 mb-4">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" /> 한국 거래일
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> 미국 거래일
        </span>
      </div>
      <CalendarGrid
        krDays={krDays}
        usDays={usDays}
        krPublished={krPublished}
        usPublished={usPublished}
        start={cal.range.start}
        end={cal.range.end}
      />
      <p className="text-xs text-neutral-400 mt-4">
        거래일·휴장 판정 출처: 발행된 캘린더 스냅샷 (XKRX / NYSE).
      </p>
    </Container>
  );
}
