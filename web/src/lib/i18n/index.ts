// i18n 토대 (ko 기본, en 스텁).
// 라우팅 기반 다국어는 후속 — 지금은 메시지 사전 + 언어 상수 구조만 제공한다.
// 사용처에서 t(locale, key) 로 문자열을 조회하고, 미정의 키는 ko 폴백.

export const LOCALES = ["ko", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "ko";

type Messages = Record<string, string>;

const ko: Messages = {
  "site.title": "Golden Queens — 시장 매매동향 아카이브",
  "site.tagline": "한국·미국 시장 마감 후 요약. 사실 데이터만 제공합니다.",
  "nav.home": "홈",
  "nav.archive": "아카이브",
  "nav.calendar": "캘린더",
  "nav.search": "검색",
  "market.kr": "한국장",
  "market.us": "미국장",
  "market.weekly": "주간",
  "disclaimer.facts":
    "본 페이지는 사실 데이터만 제공합니다. 투자 권유·종목 추천·매매 시점 판단을 포함하지 않습니다.",
};

// en 스텁 — 핵심 키만, 나머지는 ko 폴백.
const en: Messages = {
  "site.title": "Golden Queens — Market Flow Archive",
  "site.tagline": "Post-close KR/US market summaries. Facts only.",
  "nav.home": "Home",
  "nav.archive": "Archive",
  "nav.calendar": "Calendar",
  "nav.search": "Search",
  "market.kr": "Korea",
  "market.us": "US",
  "market.weekly": "Weekly",
  "disclaimer.facts":
    "Facts only. No investment advice, stock recommendations, or timing calls.",
};

const TABLE: Record<Locale, Messages> = { ko, en };

export function t(locale: Locale, key: string): string {
  return TABLE[locale]?.[key] ?? TABLE[DEFAULT_LOCALE][key] ?? key;
}

export function isLocale(v: string): v is Locale {
  return (LOCALES as readonly string[]).includes(v);
}
