import Link from "next/link";
import { Card, Container } from "@/components/Layout";
import { getIndex } from "@/lib/data";

export const revalidate = 600;
export const metadata = { title: "아카이브" };

function DateList({
  title,
  base,
  items,
}: {
  title: string;
  base: string;
  items: string[];
}) {
  if (!items.length)
    return (
      <Card title={title}>
        <p className="text-sm text-neutral-500">발행된 데이터가 없습니다.</p>
      </Card>
    );
  return (
    <Card title={`${title} (${items.length})`}>
      <ul className="flex flex-wrap gap-2">
        {items.map((id) => (
          <li key={id}>
            <Link
              href={`${base}/${id}`}
              className="text-sm px-2.5 py-1 rounded-lg border border-neutral-200 dark:border-neutral-800 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400"
            >
              {id}
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default async function ArchivePage() {
  const index = await getIndex();
  return (
    <Container>
      <h1 className="text-xl font-bold mb-6">아카이브</h1>
      <DateList title="🇰🇷 한국장" base="/kr" items={index?.kr ?? []} />
      <DateList title="🇺🇸 미국장" base="/us" items={index?.us ?? []} />
      <DateList title="📅 주간" base="/weekly" items={index?.weekly ?? []} />
    </Container>
  );
}
