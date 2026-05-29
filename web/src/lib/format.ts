// 색 컨벤션 + 숫자 포맷 (한국 증시 관례)
// 양수=상승(빨강), 음수=하락(파랑), 0=보합(중립). 이모지는 스냅샷에 없으므로 여기서 재현.

export type Direction = "up" | "down" | "flat";

export function direction(v: number | null | undefined): Direction {
  if (v == null || v === 0) return "flat";
  return v > 0 ? "up" : "down";
}

// Tailwind 텍스트 색 클래스 (한국 관례: 상승 빨강 / 하락 파랑)
export function colorClass(v: number | null | undefined): string {
  const d = direction(v);
  if (d === "up") return "text-rose-600 dark:text-rose-400";
  if (d === "down") return "text-blue-600 dark:text-blue-400";
  return "text-neutral-500 dark:text-neutral-400";
}

export function arrow(v: number | null | undefined): string {
  const d = direction(v);
  if (d === "up") return "▲";
  if (d === "down") return "▼";
  return "–";
}

// 순매수 억원: 부호 + 천단위 콤마
export function signedAmount(v: number | null | undefined): string {
  if (v == null) return "–";
  const sign = v > 0 ? "+" : v < 0 ? "" : "";
  return `${sign}${v.toLocaleString("ko-KR")}`;
}

// 등락률 %: 부호 + 소수 2자리
export function signedPct(v: number | null | undefined): string {
  if (v == null) return "–";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

// 종가: 천단위 콤마 (소수 자리는 값 크기에 따라)
export function price(v: number | null | undefined): string {
  if (v == null) return "–";
  const digits = Math.abs(v) >= 1000 ? 2 : v % 1 === 0 ? 0 : 2;
  return v.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

// 거래량강도 ×배수
export function volRatio(v: number | null | undefined): string {
  if (v == null) return "";
  return `×${v.toFixed(2)}`;
}

// "26.05.29" → "05/29" 표시용
export function shortDate(yymmdd: string): string {
  const parts = yymmdd.split(".");
  if (parts.length === 3) return `${parts[1]}/${parts[2]}`;
  return yymmdd;
}

// "2026-05-29" → "2026년 5월 29일 (금)"
const WEEKDAY_KR = ["일", "월", "화", "수", "목", "금", "토"];
export function longDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  const wd = WEEKDAY_KR[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${y}년 ${m}월 ${d}일 (${wd})`;
}

// "2026-05-29" → "5/29 (금)" — prev/next 버튼용 짧은 표기
export function shortDateWeekday(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  const wd = WEEKDAY_KR[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${m}/${d} (${wd})`;
}
