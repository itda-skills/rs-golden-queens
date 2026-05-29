// 발행 스냅샷 스키마 (schema_version 1)
// 원천: itda-skills/rs-golden-queens-data/SCHEMA.md
// 색·이모지 문자열은 저장되지 않는다 — 부호/값으로 색 컨벤션을 재현한다.

export type Market = "kr" | "us" | "weekly";

export interface SourceLink {
  label: string;
  url: string;
}

interface SnapshotBase {
  schema_version: number;
  market: Market;
  date: string; // YYYY-MM-DD (시장별 거래일)
  generated_at: string; // ISO +09:00
  is_holiday: boolean;
  sources: SourceLink[];
  message?: string; // 휴장 시 한 줄
}

// ── KR ──
export interface KrInvestorFlow {
  personal: number;
  foreign: number;
  institutional: number;
  program_arb: number;
  program_nonarb: number;
  program_total: number;
  bizdate?: string;
}

export interface KrDailyRow {
  date: string; // "26.05.29"
  personal: number;
  foreign: number;
  institutional: number;
  finance: number;
  insurance: number;
  trust: number;
  bank: number;
  other_fin: number;
  pension: number;
  other_corp: number;
}

export interface KrPayload {
  bizdate: string;
  kospi: KrInvestorFlow;
  kosdaq: KrInvestorFlow;
  kospi_daily: KrDailyRow[];
}

export interface KrSnapshot extends SnapshotBase {
  market: "kr";
  payload: KrPayload | null;
}

// ── US ──
export interface UsQuote {
  label: string;
  close: number;
  pct: number;
  vol_ratio: number | null;
  date: string;
}

export type UsSection = Record<string, UsQuote>;

export interface UsPayload {
  indices: UsSection;
  volatility: UsSection;
  risk_onoff: UsSection;
  macro: UsSection;
  sectors: UsSection;
  watch: UsSection;
}

export interface UsSnapshot extends SnapshotBase {
  market: "us";
  payload: UsPayload | null;
}

// ── Weekly ──
export interface Watch5d {
  ticker: string;
  pct_5d: number;
}

export interface WeeklyPayload {
  kospi_daily: KrDailyRow[];
  watch_5d: Watch5d[];
}

export interface WeeklySnapshot extends SnapshotBase {
  market: "weekly";
  week: string; // "2026-W22"
  payload: WeeklyPayload | null;
}

export type Snapshot = KrSnapshot | UsSnapshot | WeeklySnapshot;

// ── calendar ──
export interface CalendarSnapshot {
  schema_version: number;
  generated_at: string;
  range: { start: string; end: string };
  kr: string[]; // 거래일 ISO 날짜
  us: string[];
}

// ── index / latest ──
export interface IndexFile {
  schema_version: number;
  updated_at: string | null;
  kr: string[];
  us: string[];
  weekly: string[];
}

export interface LatestEntry {
  date: string;
  path: string;
  week?: string;
}

export interface LatestFile {
  schema_version: number;
  updated_at: string | null;
  kr: LatestEntry | null;
  us: LatestEntry | null;
  weekly: LatestEntry | null;
}
