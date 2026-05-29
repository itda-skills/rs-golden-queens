import { revalidatePath } from "next/cache";

// 발행 직후 on-demand revalidate.
// 발행 측(Actions)이 POST 로 호출하면 해당 경로 캐시를 무효화한다.
// 보호: REVALIDATE_SECRET 환경변수와 일치하는 토큰 필요.
//
// 사용 예 (발행 후):
//   curl -X POST "$WEB/api/revalidate" \
//     -H "content-type: application/json" \
//     -d '{"secret":"...","market":"kr","date":"2026-05-29"}'

interface Body {
  secret?: string;
  market?: "kr" | "us" | "weekly";
  id?: string; // date(kr/us) 또는 week(weekly)
  date?: string;
}

export async function POST(request: Request) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return Response.json({ ok: false, error: "not configured" }, { status: 503 });
  }

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ ok: false, error: "invalid json" }, { status: 400 });
  }

  if (body.secret !== secret) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const revalidated: string[] = [];

  // 홈·아카이브는 항상 갱신 (latest/index 반영)
  revalidatePath("/");
  revalidatePath("/archive");
  revalidated.push("/", "/archive");

  // 개별 상세 경로
  const id = body.id ?? body.date;
  if (body.market && id) {
    const path = `/${body.market}/${id}`;
    revalidatePath(path);
    revalidated.push(path);
  }

  return Response.json({ ok: true, revalidated });
}
