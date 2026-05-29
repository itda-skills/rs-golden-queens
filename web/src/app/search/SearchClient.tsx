"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

export interface SearchEntry {
  id: string; // date or week
  market: "kr" | "us" | "weekly";
  label: string; // 표시용 (예: "한국장 2026-05-29")
  href: string;
  keywords: string; // 검색 대상 텍스트
}

const MARKET_LABEL: Record<string, string> = {
  kr: "한국장",
  us: "미국장",
  weekly: "주간",
};

export function SearchClient({ entries }: { entries: SearchEntry[] }) {
  const [q, setQ] = useState("");
  const [market, setMarket] = useState<"all" | "kr" | "us" | "weekly">("all");

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return entries.filter((e) => {
      if (market !== "all" && e.market !== market) return false;
      if (!needle) return true;
      return e.keywords.toLowerCase().includes(needle);
    });
  }, [q, market, entries]);

  return (
    <div>
      <div className="flex flex-col sm:flex-row gap-2 mb-4">
        <input
          type="search"
          inputMode="search"
          placeholder="날짜 또는 키워드 (예: 2026-05, 한국장)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="flex-1 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-400"
        />
        <select
          value={market}
          onChange={(e) => setMarket(e.target.value as typeof market)}
          className="rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm"
        >
          <option value="all">전체</option>
          <option value="kr">한국장</option>
          <option value="us">미국장</option>
          <option value="weekly">주간</option>
        </select>
      </div>

      <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-3">
        {results.length}건
      </p>

      <ul className="flex flex-col gap-1.5">
        {results.map((e) => (
          <li key={`${e.market}-${e.id}`}>
            <Link
              href={e.href}
              className="flex items-center gap-2 rounded-lg border border-neutral-200 dark:border-neutral-800 px-3 py-2 text-sm hover:border-blue-400"
            >
              <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300">
                {MARKET_LABEL[e.market]}
              </span>
              <span>{e.id}</span>
            </Link>
          </li>
        ))}
        {!results.length && (
          <li className="text-sm text-neutral-500">검색 결과가 없습니다.</li>
        )}
      </ul>
    </div>
  );
}
