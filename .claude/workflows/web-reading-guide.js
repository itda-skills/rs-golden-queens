// ── 재사용 워크플로우: 웹 지표 해석 가이드 작성 ──────────────────────────
// 8개 데이터 그룹별 해석 가이드 작성 → 불변성·사실정확성·SoT 3축 적대 검증
// → 종합 → 불변성 최종감사 → 최종화. (약 19개 에이전트)
//
// 실행:  Workflow({ name: 'web-reading-guide' })
//        다른 경로/CI:  Workflow({ name: 'web-reading-guide', args: { root: '/abs/path' } })
// 산출:  { final: { title, summary, top_priorities, body_markdown, labels },
//          verifiedAll, critique, stats }
//        도메인 불변성(투자 권유·시점판단·전망 금지) + SoT(정적 콘텐츠) 준수 콘텐츠.
// ───────────────────────────────────────────────────────────────────────────
export const meta = {
  name: 'web-reading-guide',
  description: 'rs-golden-queens 웹 각 지표의 해석 가이드(어떤 관점에서 보는가)를 작성·적대검증하고 GitHub 이슈로 종합',
  phases: [
    { title: '작성', detail: '8개 데이터 그룹별 해석 가이드 작성' },
    { title: '검증', detail: '불변성·사실정확성·SoT 3축 적대 검증' },
    { title: '종합', detail: '툴팁 마이크로카피 + /guide 콘텐츠 + 구현 가이드' },
    { title: '불변성비평', detail: '권유·시점판단·사실오류 최종 점검' },
    { title: '최종화', detail: '비평 반영 최종 이슈 본문' },
  ],
}

// 기본은 이 저장소의 로컬 경로. 다른 위치/CI에서는 args.root 로 주입한다.
const ROOT = (args && typeof args === 'object' && args.root) || '/Users/allieus/Apps/itda-skills/rs-golden-queens'

const CTX = `
# 대상: rs-golden-queens 웹 (매매동향 봇의 읽기 전용 종속 표현)

웹(Next.js)은 텔레그램 봇이 발행한 스냅샷을 읽어 한국장·미국장·주간 매매동향 데이터를 **값만** 표로 보여준다.
문제: 방문자가 각 숫자를 "어떤 관점에서 봐야 하는지" 모른 채 데이터만 본다. 이 작업은 각 지표에
**"어떻게 읽는가(해석 관점)" 가이드 콘텐츠**를 만든다. 카드마다 ⓘ 툴팁(한 줄) + 별도 /guide 페이지(상세) 형태로 제공할 예정.

## 절대 준수 — 도메인 불변성 (위반 시 검증에서 reject)
- **사실 데이터/지표의 의미와 관점만** 설명한다. 투자 권유·종목 추천·매수/매도 시점 판단·전망을 절대 넣지 않는다.
- 금지 표현: "사세요/파세요", "지금이 기회", "강세 전환 임박", "비중 확대", "주목할 종목", "~할 때다".
- 허용: "이 지표는 X를 뜻한다", "Y와 함께 보면 Z 관점에서 해석한다", "하루 수치만으로 단정하기 어렵다", "흔한 오해는 ~".
- 특정 값에 대한 동적 판단("오늘은 강세")도 금지 — 가이드는 일반적·교육적 설명이어야 한다.

## SoT(Single Source of Truth) 제약 (web/AGENTS.md)
- 웹은 스냅샷 값을 표시만 하고 데이터를 새로 수집·계산하거나 시장 로직(거래일/휴장/색 의미)을 재구현하지 않는다.
- 따라서 해석 가이드는 **정적 콘텐츠**(지표를 읽는 고정된 방법)여야 한다. "오늘 3일 연속 순매수" 같은 동적 자동 코멘트는
  스냅샷에 파생값이 있어야 하므로 이 작업의 범위 밖(이슈 #10의 O-reuse 이후 확장)으로 분리한다.

## 웹이 실제로 보여주는 데이터 (해석 가이드 대상)
### 한국 (KR 상세 페이지)
- 코스피/코스닥 투자자별 순매수: 외국인 / 기관 / 개인 (단위: 억원, 순매수=매수-매도)
- 코스피 프로그램매매: 차익(arb) / 비차익(nonarb) / 합계
- 코스피 일별 추이(차트) + 일별 상세 표(외국인/기관/개인, 최근 거래일들)
  - (스냅샷엔 기관세부 7종 finance/insurance/trust/bank/other_fin/pension/other_corp도 있으나 현재 표엔 미표시)
- 색 컨벤션: 🔴 빨강=상승/순매수(양수), 🔵 파랑=하락/순매도(음수) — **한국 증시식(미국과 반대)**
### 미국 (US 상세 페이지) — 각 항목 종가/등락률(/일부 거래량강도)
- 주요 지수: S&P500(^GSPC) / 나스닥(^IXIC) / 다우(^DJI) / 러셀2000(^RUT, 중소형)
- 변동성·꼬리위험: VIX / VVIX(VIX의 변동성) / SKEW(꼬리위험)
- 위험선호(Risk On/Off): HYG(하이일드채) vs IEF(7-10Y국채) — 갭으로 위험선호/안전선호 판정
- 매크로: 10Y/30Y 금리(^TNX/^TYX) / DXY(달러지수) / 원달러(KRW=X) / WTI(유가) / 금
- 섹터 (S&P 11, SPDR): 등락률 기준 정렬
- 워치 ETF (QQQ/SMH/NLR/XLE/GLD/SLV/ITA/XOVR): 종가/등락 + 거래량강도(vol_ratio=당일/5일평균, ×1.5↑ '쏠림')
### 주간 (Weekly)
- 코스피 5거래일 누적 (외인/기관/개인) + 워치 ETF 5거래일 등락
### 공통 개념
- 단위(억원 vs USD/%), 색 컨벤션(한국식), vol_ratio(거래량강도)의 의미

## 흔한 오해(반드시 각 지표 가이드에 반영할 '함정' — 이슈 #10에서 검증된 사실)
- vol_ratio(거래량강도) 🔥는 **거래량 급증일 뿐 방향(매수/매도) 무관** — 폭락+거래폭증도 ×1.5↑가 된다.
- 프로그램 차익(arb)은 **KOSPI200 선물-현물 차익**이라, '시장 전체 현물' 외국인 순매수와 다른 유니버스(시총 커버리지)다.
- 외국인 순매수는 **현물만** — 외국인이 현물 순매도 + 선물 순매수(헤지)면 방향을 정반대로 오독할 수 있다(선물 데이터는 현재 없음).
- 섹터 '등락률 정렬'은 **가격 등락**이지 '그 섹터에 자금이 들어왔다'(투자자 순매수)가 아니다.
- VIX 등 변동성지수는 **동행/후행** 성격(시장 불안의 반영)이지 미래 예측이 아니다.
- 색이 한국식(빨강=상승)이라 미국 데이터도 같은 컨벤션 — 미국 현지(초록=상승)와 반대임에 유의.

## 참고 파일 (필요 시 Read; 정확 표시 항목·라벨 확인용)
- ${ROOT}/web/src/lib/types.ts (스냅샷 스키마)
- ${ROOT}/web/src/components/Tables.tsx (KR/US 표 렌더)
- ${ROOT}/web/src/app/kr/[date]/page.tsx · ${ROOT}/web/src/app/us/[date]/page.tsx (카드 구성)
- ${ROOT}/web/src/components/Tooltip.tsx (재활용할 툴팁 컴포넌트)
- ${ROOT}/web/AGENTS.md (SoT 제약)
`.trim()

// 8개 데이터 그룹 (가이드 작성 단위)
const GROUPS = [
  {
    key: 'kr-investors',
    title: '한국 투자자 주체 (외국인·기관·개인)',
    focus: `코스피/코스닥의 외국인·기관·개인 순매수 각각이 무엇을 뜻하는지, '쌍끌이(외인+기관 동반 순매수)'·'개인은 보통 반대편'·
'외인+기관+개인+기타법인 합이 ≈0인 제로섬 구조'를 어떤 관점에서 보는지. 코스피와 코스닥의 주체별 성격 차이(코스닥은 개인 비중·변동성이 큼).
순매수(억원)가 매수-매도 차액이라는 기본 정의도. 함정: 외국인은 현물 순매수만이라 선물 헤지를 못 본다, 하루 수치≠추세.`,
  },
  {
    key: 'kr-program',
    title: '한국 프로그램매매 (차익·비차익·합계)',
    focus: `프로그램매매 차익(arb)/비차익(nonarb)/합계 각각의 의미. 차익=KOSPI200 선물-현물 가격차를 이용한 차익거래 흔적,
비차익=다수 종목 바스켓 동시 매매(기관·외국인 자금 흐름 성격). 어떤 관점에서 보는지(예: 비차익 대량 순매수는 바스켓 유입 신호로 읽되 단정 금지).
함정: 차익은 KOSPI200 유니버스라 '시장 전체 현물 외국인 순매수'와 모집단이 다르다 — 같은 화면의 두 수치를 합산·동일시하면 오독.`,
  },
  {
    key: 'kr-trend',
    title: '한국 일별 추이 + 시계열 관점',
    focus: `일별 추이(최근 거래일 외인/기관/개인)를 '하루'가 아니라 '흐름'으로 읽는 관점: 연속 순매수/순매도일수, 추세 전환(순매도→순매수),
순매수 규모의 증감(가속/감속), 5거래일 누적의 의미. 기관세부 7종(금융투자/보험/투신/은행/기타금융/연기금/기타법인)의 성격 차이
(연기금=장기 수급, 금융투자=증권사 자기매매, 투신=펀드 자금)도 — 단, 현재 웹 표엔 외인/기관/개인만 표시되므로 '일별 표를 흐름으로 읽기'에 무게.
함정: 단일일 급변은 만기·배당·MSCI 리밸런싱 등 이벤트성일 수 있다(추세와 구분).`,
  },
  {
    key: 'us-index-vol',
    title: '미국 지수 + 변동성·꼬리위험',
    focus: `4개 지수의 성격(S&P500=대형주 전반, 나스닥=기술주, 다우=30 우량주, 러셀2000=중소형주→경기·유동성 민감). 지수 간 괴리를 보는 관점
(러셀 약세=위험회피, 나스닥 독주=기술 쏠림). VIX(S&P 옵션 내재변동성=공포지수)/VVIX(VIX의 변동성)/SKEW(급락 꼬리위험)의 의미와 함께 보는 법.
함정: 변동성지수는 동행·후행(불안의 반영)이지 예측이 아니다, VIX 하락=무조건 안전은 단정.`,
  },
  {
    key: 'us-risk-macro',
    title: '미국 위험선호 + 매크로',
    focus: `위험선호(HYG 하이일드채 vs IEF 국채): 위험자산 선호면 HYG가 IEF보다 강함, 갭의 의미. 매크로가 주식 매매동향에 주는 맥락:
10Y/30Y 금리(상승=할인율↑ 성장주 부담, 장단기), DXY 달러지수·원달러(달러 강세=외국인 한국 순매도 압력 경향), WTI(에너지·인플레), 금(안전자산·실질금리 역상관).
어떤 관점에서 '레짐'을 읽는지. 함정: HYG-IEF는 채권 가격차 프록시지 실제 자금흐름(fund flow)이 아니다, 상관은 시기마다 달라진다.`,
  },
  {
    key: 'us-sector-watch',
    title: '미국 섹터 + 워치ETF + 거래량강도',
    focus: `S&P 11섹터 등락률 정렬을 '섹터 로테이션' 관점에서 보는 법(경기방어 XLP/XLU vs 경기민감 XLK/XLY 상대강도). 워치 ETF(QQQ/SMH/NLR/XLE/GLD/SLV/ITA/XOVR) 테마.
거래량강도(vol_ratio=당일/5일평균)의 의미: 관심·참여 급증. 함정(중요): vol_ratio 🔥는 '거래량 급증'일 뿐 매수/매도 방향 무관(폭락+거래폭증도 🔥),
섹터 '등락률 정렬'은 가격이지 투자자 순매수(자금 유입)가 아니다(섹터별 수급 데이터는 현재 없음).`,
  },
  {
    key: 'weekly-common',
    title: '주간 누적 + 공통 개념(색·단위·거래량강도)',
    focus: `주간: 코스피 5거래일 누적 순매수가 '한 주 동안 주체별 방향'을 일별 노이즈를 줄여 보는 관점인 점, 워치 ETF 5일 등락의 의미.
공통 개념 가이드: 색 컨벤션(🔴빨강=상승/순매수, 🔵파랑=하락/순매도 — 한국 증시식이라 미국 현지 초록=상승과 반대), 단위(한국=억원 순매수, 미국=USD 종가/% 등락),
거래량강도의 일반 정의. 함정: 누적은 상쇄(매수일+매도일)되어 큰 일중 변동을 숨길 수 있다, 색이 현지와 반대라 미국 데이터 오독 주의.`,
  },
  {
    key: 'future-breadth',
    title: '(향후·#10 연계) 시장 폭 + 추세 신호 가이드',
    focus: `이슈 #10이 제안한 '추가 호출 0' 신규 지표가 웹에 들어올 때를 대비한 가이드 초안: 시장 폭(등락종목수 breadth — 상승종목≪하락종목이면 지수 상승도 내부는 약세),
연속 순매수일수/추세 전환(코스피 10일 시계열 파생). 이들을 어떤 관점에서 읽는지. **주의: 이 그룹은 '향후 추가 시 가이드'로 명확히 분리** — 현재 웹엔 없는 데이터이고,
동적 파생값은 스냅샷에 담겨야(SoT) 한다는 점을 함께 적는다. 함정: breadth는 지수 방향과 어긋날 수 있다(지수 상승+폭 악화=소수 주도).`,
  },
]

// ── 스키마 ──
const GUIDE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['group', 'items'],
  properties: {
    group: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['key', 'indicator', 'tooltip_oneline', 'what_it_is', 'how_to_read', 'common_misread'],
        properties: {
          key: { type: 'string', description: 'kebab-case 식별자' },
          indicator: { type: 'string', description: '지표/카드명 (웹 표기와 일치)' },
          tooltip_oneline: { type: 'string', description: '카드 ⓘ 툴팁용 한 줄 (간결, 50자 내외, 권유 금지)' },
          what_it_is: { type: 'string', description: '무엇인지 — 정의와 의미 (사실)' },
          how_to_read: { type: 'array', items: { type: 'string' }, description: '함께 보면 좋은 관점 2~4개 (중립·교육적)' },
          common_misread: { type: 'string', description: '흔한 오해/함정 (도메인 불변성 강화)' },
        },
      },
    },
  },
}

const VERIFIED_GUIDE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['group', 'items'],
  properties: {
    group: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['key', 'indicator', 'tooltip_oneline', 'what_it_is', 'how_to_read', 'common_misread', 'verdict', 'check_note'],
        properties: {
          key: { type: 'string' },
          indicator: { type: 'string' },
          tooltip_oneline: { type: 'string', description: '검증·수정 후 최종 한 줄' },
          what_it_is: { type: 'string', description: '검증·수정 후 최종' },
          how_to_read: { type: 'array', items: { type: 'string' } },
          common_misread: { type: 'string' },
          verdict: { type: 'string', enum: ['ok', 'revised', 'rejected'], description: 'ok=원안 정확, revised=사실/톤 수정함, rejected=불변성위반·부정확으로 제외' },
          check_note: { type: 'string', description: '검증 결과 — 무엇을 확인/수정했는지 (불변성·사실·SoT 축)' },
        },
      },
    },
  },
}

const ISSUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['title', 'summary', 'top_priorities', 'body_markdown', 'labels'],
  properties: {
    title: { type: 'string' },
    summary: { type: 'string', description: '사용자에게 보여줄 3-5문장 요약' },
    top_priorities: { type: 'array', items: { type: 'string' } },
    body_markdown: { type: 'string', description: 'GitHub 이슈 본문 전체 (한국어 마크다운)' },
    labels: { type: 'array', items: { type: 'string' } },
  },
}

const CRITIQUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['violations', 'factual_errors', 'missing', 'verdict'],
  properties: {
    violations: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['where', 'kind', 'detail'],
        properties: {
          where: { type: 'string', description: '문제 항목 (indicator/key)' },
          kind: { type: 'string', enum: ['recommendation', 'timing', 'forecast', 'sot'], description: '권유/시점판단/전망/SoT위반' },
          detail: { type: 'string' },
        },
      },
    },
    factual_errors: { type: 'array', items: { type: 'string' }, description: '사실 오류 (틀린 지표 설명)' },
    missing: { type: 'array', items: { type: 'string' }, description: '빠진 중요 지표·관점' },
    verdict: { type: 'string', enum: ['solid', 'needs_revision'] },
  },
}

// ───────────────────────────────────────────────
//  실행
// ───────────────────────────────────────────────

log(`웹 해석 가이드 작성 시작 — ${GROUPS.length}개 데이터 그룹`)

// Phase 작성 → 검증 (pipeline)
const reviewed = await pipeline(
  GROUPS,
  (g) =>
    agent(
      `${CTX}\n\n---\n\n# 당신의 역할: 숙련된 시장 데이터 해설가 (담당 그룹: ${g.title})\n\n${g.focus}\n\n` +
        `이 그룹에 속한 각 지표/항목마다 해석 가이드를 작성하라. 각 항목: 카드 툴팁용 한 줄(tooltip_oneline), 무엇인지(what_it_is), 함께 보는 관점(how_to_read 2~4개), 흔한 오해(common_misread).\n` +
        `**정확성이 최우선** — 틀린 설명은 검증에서 걸러진다. 모호하면 WebSearch로 사실을 확인하라.\n` +
        `**도메인 불변성 절대 준수** — 권유·시점판단·전망 표현을 쓰지 마라. '관점 제시'와 '권유'의 경계를 항상 의식하라.\n` +
        `웹 표기와 라벨이 헷갈리면 참고 파일을 Read로 확인하라. 초보 방문자도 이해할 평이한 한국어로.`,
      { label: `작성:${g.key}`, phase: '작성', schema: GUIDE_SCHEMA }
    ),
  (drafted, g) => {
    if (!drafted || !drafted.items || !drafted.items.length) return { group: g.title, items: [] }
    return agent(
      `${CTX}\n\n---\n\n# 당신의 역할: 적대적 검증가 (대상 그룹: ${g.title})\n\n` +
        `아래는 "${g.title}" 가이드 초안(JSON)이다. 각 항목을 **3개 축으로 엄격히 검증**하고 필요하면 직접 고쳐라:\n` +
        `1. **도메인 불변성:** 권유/시점판단/전망 표현이 있으면 제거(revised) 또는 제외(rejected). '관점 제시'를 가장한 권유도 잡아라.\n` +
        `2. **사실 정확성:** 지표 정의·메커니즘이 틀리면 수정. 의심되면 WebSearch로 확인. (예: SKEW의 의미, HYG-IEF 해석, vol_ratio가 방향무관인지)\n` +
        `3. **SoT 제약:** 동적 자동 판단('오늘은 ~')을 요구하는 설명이면 정적 표현으로 고치거나 '향후(#10)'로 분리.\n` +
        `각 항목에 verdict(ok/revised/rejected)와 check_note를 달고, revised면 수정된 본문을 반환하라. tooltip_oneline은 간결·중립을 유지하라.\n\n` +
        `## 검증 대상\n\`\`\`json\n${JSON.stringify(drafted, null, 2)}\n\`\`\``,
      { label: `검증:${g.key}`, phase: '검증', schema: VERIFIED_GUIDE_SCHEMA }
    )
  }
)

const verifiedAll = (reviewed || []).filter(Boolean)
const okItems = verifiedAll.reduce((acc, r) => acc + (r.items || []).filter((i) => i.verdict !== 'rejected').length, 0)
const rejected = verifiedAll.reduce((acc, r) => acc + (r.items || []).filter((i) => i.verdict === 'rejected').length, 0)
log(`검증 완료 — 채택 ${okItems}개 항목, 불변성/부정확 제외 ${rejected}개. 종합 시작.`)

const SYNTH_GUIDE = `
# 종합 지침 — GitHub 이슈 본문(body_markdown)

verdict=rejected 항목은 제외한다. 채택 항목으로 다음 구조의 한국어 마크다운을 작성하라:

## 배경 / 목적
웹이 데이터를 값만 보여줘 방문자가 '어떻게 읽는지' 모른다는 문제. 이 이슈가 제공하는 것(카드 ⓘ 툴팁 + /guide 상세).
데이터 수집 개선(#10)과 별개의 '표현/교육' 레이어임을 명시하고 #10을 교차참조.

## 설계 원칙 (반드시 명시)
- 도메인 불변성: 지표의 '의미와 관점'만, 투자 권유·시점판단·전망 금지. (관점 제시 ⭕ / 권유 ❌ 경계)
- SoT: 정적 교육 콘텐츠라 스냅샷 데이터·시장 로직과 무관. 동적 자동 해석('오늘 3일 연속 순매수')은 파생값이 스냅샷에 필요하므로 #10(O-reuse) 이후로 분리.
- 표현: 각 카드 제목 옆 ⓘ(기존 Tooltip.tsx 재활용) 한 줄 + 전체 상세는 /guide 페이지. 색·단위 컨벤션도 가이드에 포함.

## 카드 ⓘ 툴팁 마이크로카피
표: | 페이지 | 카드/지표 | 툴팁 한 줄 | — 채택 항목의 tooltip_oneline 정리.

## /guide 페이지 콘텐츠 (상세)
그룹별 섹션. 각 지표: **무엇인지** / **이렇게 보면 좋습니다**(관점 목록) / **흔한 오해**. 평이한 한국어. 향후(#10 연계) 지표는 별도 '예고' 섹션으로.

## 구현 가이드
- 컴포넌트: Tooltip.tsx 재활용(또는 ⓘ 아이콘 래퍼 추가), Card 제목에 옵션 prop으로 툴팁 주입.
- /guide 라우트 신설(app/guide/page.tsx) — 정적 페이지. 콘텐츠는 상수/MDX 등.
- i18n(src/lib/i18n) 구조 고려, web/AGENTS.md 준수: 데이터 재계산 없음, npm run build + eslint 통과.
- 콘텐츠는 코드가 아닌 데이터(상수)로 분리해 유지보수 용이하게.

## 후속/확장 (#10 연계)
동적 해석(연속 순매수일수·breadth 자동 코멘트)은 #10의 파생값 발행 후. 교차참조 링크.

전체: 구체적이고, 도메인 불변성을 지키며, 카피는 그대로 붙여넣어 쓸 수 있는 완성도로.
`.trim()

phase('종합')
const draft = await agent(
  `${CTX}\n\n---\n\n# 당신의 역할: 콘텐츠 리드 — 종합 및 이슈 작성\n\n` +
    `검증 통과한 해석 가이드를 하나의 GitHub 이슈로 종합하라. 이슈 #10(데이터 수집 개선)과 교차참조하되 이건 '웹 표현/교육' 레이어다.\n\n` +
    `${SYNTH_GUIDE}\n\n` +
    `## 입력: 검증된 가이드 (그룹별)\n\`\`\`json\n${JSON.stringify(verifiedAll, null, 2)}\n\`\`\``,
  { label: '종합:이슈초안', phase: '종합', schema: ISSUE_SCHEMA }
)

phase('불변성비평')
const critique = await agent(
  `${CTX}\n\n---\n\n# 당신의 역할: 불변성·정확성 최종 감사관\n\n` +
    `아래 이슈 초안의 모든 가이드 문구를 마지막으로 점검하라. 특히 **단 하나의 권유·시점판단·전망도 남아선 안 된다.**\n` +
    `1. 권유(recommendation)/시점판단(timing)/전망(forecast)/SoT위반 표현을 모두 찾아라.\n` +
    `2. 사실 오류(틀린 지표 설명)를 찾아라 — 의심되면 WebSearch.\n` +
    `3. 빠진 중요 지표·관점.\n` +
    `엄격하게. 통과 기준은 '초보자가 읽어도 매수/매도 신호로 오해할 여지가 없음'이다.\n\n` +
    `## 이슈 초안\n제목: ${draft.title}\n\n${draft.body_markdown}`,
  { label: '불변성비평', phase: '불변성비평', schema: CRITIQUE_SCHEMA }
)

phase('최종화')
const final = await agent(
  `${CTX}\n\n---\n\n# 당신의 역할: 콘텐츠 리드 — 최종화\n\n` +
    `비평을 반영해 이슈를 최종본으로 다듬어라. 권유/시점판단/전망/SoT위반은 모두 제거, 사실오류는 수정, 누락은 보강하라.\n` +
    `${SYNTH_GUIDE}\n\n` +
    `## 비평 결과\n\`\`\`json\n${JSON.stringify(critique, null, 2)}\n\`\`\`\n\n` +
    `## 기존 초안\n제목: ${draft.title}\n\n${draft.body_markdown}\n\n` +
    `## 검증된 가이드 (참조)\n\`\`\`json\n${JSON.stringify(verifiedAll, null, 2)}\n\`\`\``,
  { label: '최종화:이슈', phase: '최종화', schema: ISSUE_SCHEMA }
)

log('웹 해석 가이드 이슈 본문 완성')

return {
  final,
  critique,
  stats: { accepted_items: okItems, rejected, groups: GROUPS.length },
  verifiedAll,
}
