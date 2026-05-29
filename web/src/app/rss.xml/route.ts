import { getIndex } from "@/lib/data";

// 최신 발행물 RSS 피드. 사실 요약만 포함 — 투자 권유 없음.
// index.json 의 날짜 목록을 항목으로 변환한다.

const SITE =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://rs-golden-queens.vercel.app";

export const revalidate = 600;

interface Item {
  title: string;
  link: string;
  guid: string;
  date: string; // YYYY-MM-DD or YYYY-Www
  desc: string;
}

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// YYYY-MM-DD → RFC822 (정오 KST 기준, 안정적 pubDate)
function rfc822(dateOrWeek: string): string {
  let y: number, mo: number, d: number;
  const wk = dateOrWeek.match(/^(\d{4})-W(\d{2})$/);
  if (wk) {
    // ISO week → 그 주 목요일 근사 (간단히 1월 1일 + (week-1)*7)
    const jan1 = Date.UTC(Number(wk[1]), 0, 1);
    const ms = jan1 + (Number(wk[2]) - 1) * 7 * 86400000;
    const dt = new Date(ms);
    y = dt.getUTCFullYear();
    mo = dt.getUTCMonth();
    d = dt.getUTCDate();
  } else {
    [y, mo, d] = dateOrWeek.split("-").map(Number);
    mo -= 1;
  }
  // 03:00 UTC = 12:00 KST
  return new Date(Date.UTC(y, mo, d, 3, 0, 0)).toUTCString();
}

export async function GET() {
  const index = await getIndex();
  const items: Item[] = [];

  for (const date of index?.kr ?? []) {
    items.push({
      title: `한국장 매매동향 — ${date}`,
      link: `${SITE}/kr/${date}`,
      guid: `kr-${date}`,
      date,
      desc: "코스피·코스닥 투자자별 매매동향, 프로그램매매, 일별 추이 (사실 데이터).",
    });
  }
  for (const date of index?.us ?? []) {
    items.push({
      title: `미국장 마감 — ${date}`,
      link: `${SITE}/us/${date}`,
      guid: `us-${date}`,
      date,
      desc: "지수·변동성·매크로·섹터·워치 ETF 종가 및 등락 (사실 데이터).",
    });
  }
  for (const week of index?.weekly ?? []) {
    items.push({
      title: `주간 리포트 — ${week}`,
      link: `${SITE}/weekly/${week}`,
      guid: `weekly-${week}`,
      date: week,
      desc: "코스피 누적 매매동향, 워치 ETF 5거래일 등락 (사실 데이터).",
    });
  }

  // 최신순 정렬 (date 문자열 역순; 주차는 그 안에서 자연 정렬)
  items.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  const top = items.slice(0, 50);

  const lastBuild = new Date().toUTCString();
  const xmlItems = top
    .map(
      (it) => `    <item>
      <title>${esc(it.title)}</title>
      <link>${esc(it.link)}</link>
      <guid isPermaLink="false">${esc(it.guid)}</guid>
      <pubDate>${rfc822(it.date)}</pubDate>
      <description>${esc(it.desc)}</description>
    </item>`,
    )
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Golden Queens — 시장 매매동향 아카이브</title>
    <link>${SITE}</link>
    <description>한국·미국 시장 마감 후 매매동향 요약. 사실 데이터만 제공하며 투자 권유를 포함하지 않습니다.</description>
    <language>ko</language>
    <lastBuildDate>${lastBuild}</lastBuildDate>
${xmlItems}
  </channel>
</rss>
`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
    },
  });
}
