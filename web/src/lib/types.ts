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

// 섹터 ETF (KIS, #10 P0-c) — 색·이모지 없는 값만. 웹이 pct 부호로 색을 재현한다.
export interface KrSector {
  code: string;
  label: string;
  // 발행 키는 항상 존재하되 결측(NaN)은 null 로 정규화됨 → number | null.
  close: number | null;
  pct: number | null;
  vol_ratio: number | null;
  trade_value_eok: number | null;
  date: string;
}

// 동적 수급 워치 항목 (KIS money_flow, #10 P0-c) — 표시 필드만(내부 점수 제외).
export interface KrMoneyFlowItem {
  code: string;
  name: string;
  grade: string;
  // 발행 화이트리스트가 항상 키를 담되 결측(NaN)은 null 로 정규화 → number | null.
  price: number | null;
  ret_5: number | null;
  trade_value_eok: number | null;
  // 외인·기관 합산도 동일 — 값에서 색·부호 재현(이모지/색 문자열 미저장).
  foreign_eok: number | null;
  orgn_eok: number | null;
  combined_eok: number | null;
  both_buy: boolean;
}

// 순매도 항목 (I1, #10 P0-d) — 매수 개념(grade·both_buy) 미포함, 사실 금액만.
export interface KrMoneyFlowSellItem {
  code: string;
  name: string;
  price: number | null;
  ret_5: number | null;
  trade_value_eok: number | null;
  foreign_eok: number | null;
  orgn_eok: number | null;
  combined_eok: number | null;
}

export interface KrMoneyFlow {
  etfs: KrMoneyFlowItem[];
  stocks: KrMoneyFlowItem[];
  // I1: 외인·기관 순매도 상위. schema_version 1 추가 키이므로 구버전 스냅샷엔
  // 없을 수 있어 optional (없으면 순매도 블록 미표시).
  etfs_sell?: KrMoneyFlowSellItem[];
  stocks_sell?: KrMoneyFlowSellItem[];
}

// 외국인·기관 가집계 항목 (KIS FHPTJ04400000, #10 I4) — 장중 추정 금액(억원), 사실값만.
export interface KrForeignInstItem {
  code: string;
  name: string;
  foreign_eok: number | null;
  orgn_eok: number | null;
  combined_eok: number | null;
}

export interface KrForeignInst {
  buy: KrForeignInstItem[];
  sell: KrForeignInstItem[];
}

export interface KrPayload {
  bizdate: string;
  kospi: KrInvestorFlow;
  kosdaq: KrInvestorFlow;
  kospi_daily: KrDailyRow[];
  // P0-c: 텔레그램과 동일한 섹터·수급 섹션. schema_version 1 의 추가 키이므로
  // 구버전 스냅샷엔 없을 수 있어 optional (없으면 카드 미표시).
  sectors?: KrSector[] | null;
  money_flow?: KrMoneyFlow | null;
  // I4: 외국인·기관 매매종목 가집계(장중 추정). optional — 없으면 카드 미표시.
  foreign_inst?: KrForeignInst | null;
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

// 결측 티커(_fetch_yf → None)는 publisher 가 발행 전 제거하지만, 구버전 스냅샷·방어를
// 위해 null 을 허용한다(UsSectionTable 이 필터링). 소비처는 옵셔널 체이닝으로 접근.
export type UsSection = Record<string, UsQuote | null>;

// 하이일드 OAS(#10 I6) — FRED 신용 스프레드 사실값. 단일 관측(섹션 dict 아님).
export interface HighYieldOas {
  series: string;
  date: string;
  value: number;
  prev: number | null;
  change: number | null;
}

export interface UsPayload {
  indices: UsSection;
  volatility: UsSection;
  risk_onoff: UsSection;
  macro: UsSection;
  sectors: UsSection;
  watch: UsSection;
  // 추가 키라 구버전 스냅샷엔 없을 수 있어 옵셔널(reader 가 null 폴백).
  high_yield_oas?: HighYieldOas | null;
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

// 캘린더 팝오버용 간략 overview (발행된 스냅샷에서 추출)
export interface DayOverview {
  kr?: { foreign: number; institutional: number; personal: number };
  us?: { sp500Pct: number | null; vix: number | null };
}
export type CalendarOverviews = Record<string, DayOverview>;

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
