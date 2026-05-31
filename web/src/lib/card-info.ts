// 실제 웹 카드 → ⓘ 툴팁(한 줄) + /guide 해당 섹션 앵커.
// 카드는 여러 지표를 묶으므로 카드 단위 요약 한 줄을 둔다(개별 항목 상세는 guide-content.ts).
// href 의 앵커(#group-key)는 web/src/app/guide/page.tsx 의 그룹 section id 와 일치한다.
// 도메인 불변성: 의미·관점만. 투자 권유·시점판단·전망 없음.

export interface CardInfo {
  tooltip: string;
  href: string;
}

export const CARD_INFO = {
  krKospiInvestors: {
    tooltip:
      "주체별 '매수−매도' 차액(억원). +는 순매수, −는 순매도. 외국인·기관이 같은 방향이면 흔히 '쌍끌이'라 부른다.",
    href: "/guide#kr-investors",
  },
  krKosdaqInvestors: {
    tooltip:
      "코스닥 주체별 순매수(억원). 코스피보다 개인 비중·변동성이 큰 시장이라는 점을 전제로 본다.",
    href: "/guide#kr-investors",
  },
  krProgram: {
    tooltip:
      "코스피 프로그램매매 순매수(억원). 차익은 KOSPI200 선물-현물 차익거래, 비차익은 15종목 이상 바스켓 매매로 모집단이 다르다.",
    href: "/guide#kr-program",
  },
  krDaily: {
    tooltip:
      "하루가 아니라 최근 거래일의 '흐름'으로 읽는 순매수 추이. 현물 기준이며 선물은 포함하지 않는다.",
    href: "/guide#kr-trend",
  },
  usIndices: {
    tooltip:
      "미국 대표 지수의 종가·등락률. 러셀2000은 중소형주라 경기·유동성에 민감한 편. 색은 한국식(빨강=상승).",
    href: "/guide#us-index-vol",
  },
  usVolatility: {
    tooltip:
      "VIX(9·30일)·VVIX·SKEW·금/유가 변동성. 시장 불안의 '크기'를 나타내는 동행·후행 지표이지 방향·예측이 아니다. 기간구조(9일 vs 30일): 콘탱고=30일>9일(우상향), 백워데이션=9일>30일(역전) — 곡선 형태 사실.",
    href: "/guide#us-index-vol",
  },
  usRisk: {
    tooltip:
      "HYG−IEF 갭(±0.2%p)으로 위험/안전 선호를 보고, VIX·달러(DXY)·금의 방향과 하이일드 OAS(신용 스프레드)를 보조 축으로 병기한다(VIX·달러·금은 하락=위험선호, OAS는 상승=스프레드 확대=안전자산). OAS는 T+1 지연이라 관측일을 함께 표기한다. 각 지표가 정의상 가리키는 방향일 뿐 종합 판단·예측이 아니다.",
    href: "/guide#us-risk-macro",
  },
  usMacro: {
    tooltip:
      "금리·달러·유가·금이 주식 매매동향에 주는 배경(레짐)을 보는 묶음. 단일 인과로 단정하지 않는다.",
    href: "/guide#us-risk-macro",
  },
  usSectors: {
    tooltip:
      "S&P 11섹터의 당일 등락률(막대)과 ^GSPC(S&P500) 대비 상대강도(vs ±%p)·거래량강도(×배수, 🔥=×1.5↑). 상대강도가 +면 시장보다 강했다는 사실일 뿐 자금 유입·권유가 아니다.",
    href: "/guide#us-sector-watch",
  },
  usWatch: {
    tooltip:
      "테마 ETF 8종의 종가·등락·거래량강도. 🔥(×1.5↑)는 거래량 급증일 뿐 매수세나 방향과는 무관하다.",
    href: "/guide#us-sector-watch",
  },
  weeklyKospi: {
    tooltip:
      "한 주 거래일별 코스피 외국인·기관·개인 순매수 추이(억원). 일별 노이즈를 줄여 '그 주의 방향'을 본다.",
    href: "/guide#weekly-common",
  },
  weeklyWatch: {
    tooltip:
      "워치 ETF의 가장 최근 종가 대 5거래일 전 종가 등락률(점대점). 매일 등락의 합이 아니다.",
    href: "/guide#weekly-common",
  },
} as const satisfies Record<string, CardInfo>;
