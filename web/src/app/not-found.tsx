import Link from "next/link";
import { Container } from "@/components/Layout";

// 전역 not-found — 데이터 부재 시 notFound() 호출(kr/us/weekly [date] 등)과 매칭되지
// 않는 모든 경로가 공유한다. RootLayout(헤더·사이드바·푸터) 안에 렌더되므로 본문만 채운다.
// 휴장/미발행/오타를 한 화면에서 안내하고 홈·캘린더로 유도한다(전역이라 일반 문구).
export default function NotFound() {
  return (
    <Container>
      <div className="py-16 text-center">
        <p className="text-6xl font-bold tracking-tight text-neutral-200 dark:text-neutral-800">
          404
        </p>
        <h1 className="mt-4 text-xl font-bold">페이지를 찾을 수 없습니다</h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-neutral-500 dark:text-neutral-400">
          요청하신 데이터가 없습니다. 해당 날짜가 아직 발행되지 않았거나,
          휴장일이거나, 주소가 올바르지 않을 수 있습니다. 발행된 날짜는 캘린더에서
          확인하실 수 있습니다.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3 text-sm">
          <Link
            href="/"
            className="rounded-lg bg-neutral-900 px-4 py-2 font-medium text-white hover:bg-neutral-700 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200"
          >
            홈으로
          </Link>
          <Link
            href="/calendar"
            className="rounded-lg border border-neutral-300 px-4 py-2 font-medium text-neutral-700 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-200 dark:hover:bg-neutral-800"
          >
            발행 캘린더 보기
          </Link>
        </div>
      </div>
    </Container>
  );
}
