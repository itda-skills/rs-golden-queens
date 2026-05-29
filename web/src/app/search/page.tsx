import { Container } from "@/components/Layout";
import { getIndex } from "@/lib/data";
import { SearchClient, type SearchEntry } from "./SearchClient";

export const revalidate = 600;
export const metadata = { title: "검색" };

export default async function SearchPage() {
  const index = await getIndex();
  const entries: SearchEntry[] = [];

  for (const date of index?.kr ?? []) {
    entries.push({
      id: date,
      market: "kr",
      label: `한국장 ${date}`,
      href: `/kr/${date}`,
      keywords: `한국장 코스피 코스닥 kr ${date}`,
    });
  }
  for (const date of index?.us ?? []) {
    entries.push({
      id: date,
      market: "us",
      label: `미국장 ${date}`,
      href: `/us/${date}`,
      keywords: `미국장 us sp500 나스닥 ${date}`,
    });
  }
  for (const week of index?.weekly ?? []) {
    entries.push({
      id: week,
      market: "weekly",
      label: `주간 ${week}`,
      href: `/weekly/${week}`,
      keywords: `주간 weekly ${week}`,
    });
  }

  // 최신순
  entries.sort((a, b) => (a.id < b.id ? 1 : a.id > b.id ? -1 : 0));

  return (
    <Container>
      <h1 className="text-xl font-bold mb-1">검색</h1>
      <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-4">
        발행된 리포트를 날짜·시장·키워드로 찾습니다.
      </p>
      <SearchClient entries={entries} />
    </Container>
  );
}
