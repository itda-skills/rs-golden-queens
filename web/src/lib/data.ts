// 발행 데이터 reader.
// 데이터 저장소(itda-skills/rs-golden-queens-data)의 스냅샷을 읽는다.
// 채널 추상화: 현재는 GitHub raw content. 후속에 Blob/Supabase로 교체 시 이 파일만 수정.

import type {
  IndexFile,
  KrSnapshot,
  LatestFile,
  Snapshot,
  UsSnapshot,
  WeeklySnapshot,
} from "./types";

const DATA_REPO =
  process.env.NEXT_PUBLIC_DATA_REPO ?? "itda-skills/rs-golden-queens-data";
const DATA_BRANCH = process.env.NEXT_PUBLIC_DATA_BRANCH ?? "main";
const RAW_BASE = `https://raw.githubusercontent.com/${DATA_REPO}/${DATA_BRANCH}`;

// ISR: 발행은 거래일 마감 후 1회. 10분마다 재검증하면 충분.
const REVALIDATE_SECONDS = 600;

async function fetchJson<T>(path: string): Promise<T | null> {
  const url = `${RAW_BASE}/${path}`;
  try {
    const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function getIndex(): Promise<IndexFile | null> {
  return fetchJson<IndexFile>("snapshots/index.json");
}

export function getLatest(): Promise<LatestFile | null> {
  return fetchJson<LatestFile>("snapshots/latest.json");
}

export function getKrSnapshot(date: string): Promise<KrSnapshot | null> {
  return fetchJson<KrSnapshot>(`snapshots/kr/${date}.json`);
}

export function getUsSnapshot(date: string): Promise<UsSnapshot | null> {
  return fetchJson<UsSnapshot>(`snapshots/us/${date}.json`);
}

export function getWeeklySnapshot(week: string): Promise<WeeklySnapshot | null> {
  return fetchJson<WeeklySnapshot>(`snapshots/weekly/${week}.json`);
}

export function getSnapshotByPath(path: string): Promise<Snapshot | null> {
  return fetchJson<Snapshot>(path);
}

export { REVALIDATE_SECONDS };
