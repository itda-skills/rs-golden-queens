// VIX 9일 vs 30일 기간구조 분류 — 표시 단위(소수 2자리)로 반올림해 ±0.3p 임계로
// 콘탱고/백워데이션/평탄 판정. 텔레그램 round(spread, 2) 와 동일 임계(SoT: 임계 단일
// 출처). Tables.VixTermStructure 와 MoodStrip 이 이 함수를 공유한다. 결측이면 null.

import type { UsSection } from "./types";

export interface VixTerm {
  short: number; // ^VIX9D 종가
  long: number; // ^VIX 종가
  spread: number; // long - short
  shape: "콘탱고" | "백워데이션" | "평탄";
}

export function vixTermShape(volatility: UsSection): VixTerm | null {
  const short = volatility["^VIX9D"]?.close ?? null;
  const long = volatility["^VIX"]?.close ?? null;
  if (short == null || long == null) return null;
  const spread = long - short;
  const s = Math.round(spread * 100) / 100;
  const shape = s > 0.3 ? "콘탱고" : s < -0.3 ? "백워데이션" : "평탄";
  return { short, long, spread, shape };
}
