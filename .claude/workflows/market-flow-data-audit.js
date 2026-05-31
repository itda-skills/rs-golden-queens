// ── 재사용 워크플로우: 매매동향 데이터 수집 감사 ──────────────────────────
// 6개 전문 렌즈 진단 → 렌즈별 적대적 검증 → 데이터소스 실현성 리서치(WebSearch)
// → 종합 → 완결성 비평 → 최종화. (약 19개 에이전트)
//
// 실행:  Workflow({ name: 'market-flow-data-audit' })
//        다른 경로/CI:  Workflow({ name: 'market-flow-data-audit', args: { root: '/abs/path' } })
// 산출:  { final: { title, summary, top_priorities, body_markdown, labels },
//          verifiedAll, feasAll, critique, stats }
//        → final.body_markdown 을 GitHub 이슈 본문으로 사용 (gh issue create --body-file).
// ───────────────────────────────────────────────────────────────────────────
export const meta = {
  name: 'market-flow-data-audit',
  description: 'rs-golden-queens 매매동향 데이터 수집을 6개 전문 렌즈로 진단·적대검증하고 GitHub 이슈 초안 생성',
  phases: [
    { title: '진단', detail: '6개 전문 렌즈 병렬 진단' },
    { title: '검증', detail: '렌즈별 발견을 코드 근거로 적대적 검증' },
    { title: '실현성', detail: '데이터 소스가 실제 제공하는지 리서치' },
    { title: '종합', detail: '검증된 발견을 GitHub 이슈로 종합' },
    { title: '완결성', detail: '누락된 관점·발견 비평' },
    { title: '최종화', detail: '비평 반영 최종 이슈 본문' },
  ],
}

// 기본은 이 저장소의 로컬 경로. 다른 위치/CI에서는 args.root 로 주입한다.
const ROOT = (args && typeof args === 'object' && args.root) || '/Users/allieus/Apps/itda-skills/rs-golden-queens'

// ── 모든 에이전트가 공유하는 도메인·코드 맵 컨텍스트 ──
const CTX = `
# 대상 프로젝트: rs-golden-queens (매매동향 텔레그램 봇)

한국장·미국장 마감 후 "시장 매매동향(자금흐름) 요약"을 텔레그램으로 발송하는 개인 투자 데이터 봇이다.
핵심 도메인 불변성(반드시 준수): **사실 데이터만 출력**한다. 투자 권유·종목 추천·매수/매도 시점 판단을 추가하지 않는다.
따라서 모든 개선 제안도 "더 정확하고 완전한 사실 데이터/지표"를 향해야 하며, 매매 시그널·추천을 만들어내는 방향은 안 된다.

## 현재 수집되는 데이터 (이미 구현됨 — 중복 제안 금지)

### 한국 일간 (market_flow/daily_kr.py → fetchers/naver_kr.py, fetchers/kr_etfs.py, fetchers/kr_money_flow.py)
- 네이버 모바일 API (m.stock.naver.com/api/index/{KOSPI|KOSDAQ}/integration):
  - 코스피·코스닥 당일 투자자별 순매수 합산: 외인/기관/개인 (억원)
  - 프로그램매매: 차익(arb)/비차익(nonarb)/합계 (코스피·코스닥)
- 네이버 데스크탑 HTML 정규식 파싱:
  - 코스피 시간별 누적(intraday) — 수집은 하지만 발송/발행에는 미사용
  - 코스피 일별 10거래일 추이 + 기관 세부 7종(금융투자/보험/투신/은행/기타금융/연기금/기타법인)
  - 코스피 5거래일 누적 (일별에서 합산 계산)
- KIS API (한국투자증권, **오늘 날짜 발송에서만**; 과거일 재발송 시 통째로 스킵):
  - 섹터 ETF 18종: 마감가/등락률/거래량강도(vol_ratio=당일/5일평균)/거래대금
  - 동적 수급 워치: volume_rank 상위 40개 후보 풀 → 외인+기관 합산(종가환산) 내림차순 Top ETF5 + 개별주5

### 미국 일간 (market_flow/daily_us.py → fetchers/us_market.py, yfinance)
- 지수 4 (S&P500/나스닥/다우/러셀2000), 변동성 3 (VIX/VVIX/SKEW)
- 위험선호 (HYG vs IEF 갭으로 위험선호/안전자산/중립 판정)
- 매크로 6 (10Y/30Y금리/DXY/원달러/WTI/금), 섹터 11 (S&P SPDR)
- 워치 ETF 8 (QQQ/SMH/NLR/XLE/GLD/SLV/ITA/XOVR)
- 각 항목: 종가/등락률/거래량강도(vol_ratio). **투자자 수급·자금흐름 데이터는 없음(가격/거래량만)**

### 주간 (market_flow/weekly.py)
- 코스피 5거래일 누적 (네이버 일별) + 워치 ETF 5거래일 누적 등락 (yfinance)

## KIS 클라이언트가 제공하지만 현재 미사용인 메서드 (kis/client.py)
inquire_investor(종목별 투자자 일별 매매동향), volume_rank, fluctuation_rank(등락률순위),
etf_components(ETF 구성종목), etf_nav_daily(NAV추이), inquire_asking_price(호가),
check_holiday, market_time. (주문/잔고 API도 있으나 봇과 무관)

## 직접 확인해야 할 핵심 파일 (절대경로, Read 도구로 반드시 원본 확인 — 추측 금지)
- ${ROOT}/market_flow/fetchers/naver_kr.py
- ${ROOT}/market_flow/fetchers/us_market.py
- ${ROOT}/market_flow/fetchers/kr_etfs.py
- ${ROOT}/market_flow/fetchers/kr_money_flow.py
- ${ROOT}/market_flow/screeners/money_flow.py
- ${ROOT}/market_flow/daily_kr.py
- ${ROOT}/market_flow/daily_us.py
- ${ROOT}/market_flow/weekly.py
- ${ROOT}/market_flow/formatter.py
- ${ROOT}/market_flow/publisher.py
- ${ROOT}/market_flow/calendar_utils.py
- ${ROOT}/kis/client.py
- ${ROOT}/kis/auth.py

## 알려진 설계 제약 (이미 인지된 사실 — "발견"으로 다시 보고하되 trade-off를 감안)
- 운영 수집 데이터는 디스크에 영구 저장하지 않는다(텔레그램 발송 + 웹 발행 스냅샷만).
- 외부 호출은 fetcher/publisher 레이어에 둔다. 발송 실패 시 침묵 종료 금지.
- 무료/저비용 소스(네이버/KIS 무료 시세/yfinance) 중심. 유료 데이터는 도입 장벽 높음.
`.trim()

// ── Phase A: 6개 전문 진단 렌즈 ──
const LENSES = [
  {
    key: 'quant-flow',
    title: '퀀트·수급 애널리스트',
    focus: `"시장 매매동향=자금흐름" 분석의 본질 관점. 현재 수집 항목으로 외국인/기관/개인의 진짜 방향성을 읽을 수 있는가?
빠진 핵심 수급 축을 찾아라: 예) 외국인·기관 선물 순매수와 미결제약정(현물만 보면 반쪽), 공매도 잔고/비중,
신용융자잔고·고객예탁금(수급 선행지표), 업종/섹터별 투자자 순매수(어디로 돈이 가는지), 시장 폭(상승/하락 종목수, 신고가/신저가, 거래대금 추세).
각 축이 "왜 매매동향 해석에 필수인지", "현재 무엇으로도 대체 안 되는지"를 논증하라.`,
  },
  {
    key: 'data-reliability',
    title: '데이터 엔지니어·신뢰성',
    focus: `수집 파이프라인의 견고성·정합성 관점. 비공식 네이버 모바일 API와 정규식 HTML 파싱의 취약성(필드명/페이지 구조 변경 시 silent 실패),
수집 데이터의 bizdate가 요청 날짜와 일치하는지 검증 부재, yfinance가 직전 거래일 데이터를 조용히 반환하는 신선도 문제,
타임아웃/재시도/백오프 부재, 부분 실패가 사용자에게 안 보이는 문제(일부 티커 None이어도 성공 발송), 스키마 검증 부재를 코드 근거로 짚어라.
"조용한 오작동(silently wrong)"이 가장 위험하다 — 어디서 발생 가능한지 구체적으로.`,
  },
  {
    key: 'kr-domain',
    title: '한국시장 도메인 전문가',
    focus: `한국 증시(코스피/코스닥) 특유의 수급 구조 관점. 코스닥은 당일 합산만 있고 일별 추이·기관세부가 없는 비대칭(코스닥은 개인·외인 비중과 변동성이 코스피와 다름),
프로그램매매 차익/비차익 해석의 맥락 부재, 기관 세부 7종을 보여주지만 연기금/투신/금융투자의 의미 차이, 코스피 5일 누적은 있지만 코스닥 5일 누적은 없는 점,
KIS 섹터 ETF가 과거일 재발송 시 통째 누락되는 점이 한국 사용자에게 주는 실질 영향을 평가하라. 무료로 얻을 수 있는 KRX/네이버 추가 데이터도 제안.`,
  },
  {
    key: 'us-macro',
    title: '미국·글로벌 매크로 전문가',
    focus: `미국장 데이터의 "매매동향" 적정성 관점. 현재 미국장은 가격/등락률/거래량강도뿐 — 투자자 자금흐름(fund flow) 데이터가 전무하다.
빠진 것: ETF 자금 유입/유출(fund flow), 풋콜레이쇼·옵션 흐름, 시장 폭(advance/decline, % above MA), 채권/달러/원자재의 매크로 레짐 해석,
위험선호 판정이 HYG vs IEF 단일 축으로 거친 점, 섹터 로테이션을 등락률 정렬로만 보는 한계. 무료/저비용으로 보강 가능한 소스(예: yfinance로 가능한 추가 티커, ETF flow 공개 데이터)를 제안하라.`,
  },
  {
    key: 'screener-algo',
    title: '스크리너 알고리즘 검증가',
    focus: `money_flow 스크리너(screeners/money_flow.py, fetchers/kr_money_flow.py)의 로직 정확성·편향 관점. 핵심 의심점을 코드로 검증하라:
(1) 정렬이 combined(외인+기관 합산) 내림차순 → "자금 유입 Top"만 보이고 "대량 순매도 Top"은 구조적으로 누락(주석에도 명시). 매매동향은 유입·유출 양방향이 중요.
(2) 후보 풀이 volume_rank 상위 40개로 한정 → 거래량은 적지만 조용히 매집되는 종목, 거래대금 큰 우량주 누락 가능.
(3) 외인/기관 순매수 수량→금액 환산을 '종가'로 함 → 일중 평균가가 아니라 부정확.
(4) ETF 판별이 이름 prefix 화이트리스트(KODEX/TIGER 등) → 신규 운용사 누락.
(5) grade/mf_score 가중치의 임의성. 각 항목의 실제 영향과 개선안을 논증하라.`,
  },
  {
    key: 'qa-bugs',
    title: 'QA·버그·엣지케이스 탐지가',
    focus: `실제 코드 결함·엣지케이스 관점. 추측 말고 코드에서 실증하라:
naver_kr._parse_trend_rows의 11컬럼 가정이 깨질 때 동작,
숫자 파싱('-' 처리, to_int의 '+'만 제거)에서 음수/콤마/공백 엣지, vol_ratio가 지수(^GSPC 등 거래량 0/NaN)에서 의미 없는 값, 휴장 직후 직전일 데이터 혼입,
타임존/날짜 경계(KST vs ET vs naive), KIS rate limit(time.sleep 0.12 고정)와 18종+스크리너 직렬 호출의 총 소요시간/타임아웃 위험, 테스트가 못 잡는 통합 결함을 짚어라.`,
  },
]

// ── Phase C: 데이터 소스 실현성 리서치 주제 ──
const SOURCES = [
  {
    key: 'kis-api',
    q: `한국투자증권 KIS Open API가 제공하는 "투자자별 매매동향·수급" 관련 추가 데이터를 조사하라.
특히: 시장 전체(코스피/코스닥) 투자자별 매매동향, 업종별 투자자 순매수, 프로그램매매 종목별, 공매도, 선물/옵션 투자자 동향 관련 공식 API(엔드포인트/tr_id)가 존재하는지.
현재 봇은 inquire_investor(종목별)만 쓴다. WebSearch로 KIS 개발자센터/공식 문서 기반 사실만 보고하라. 추측이면 그렇게 표기.`,
  },
  {
    key: 'naver-krx',
    q: `네이버 금융과 KRX 정보데이터시스템(data.krx.co.kr)에서 무료로 얻을 수 있는 한국 매매동향 보강 데이터를 조사하라.
특히: 업종별 투자자 순매수, 공매도 잔고/거래, 신용융자잔고, 고객예탁금, 투자자별 선물 동향, 시장 폭(등락종목수/신고가신저가).
어떤 URL/API 형태로 접근 가능한지, 봇의 기존 네이버 비공식 API 방식과 비교해 안정성은 어떤지 WebSearch 기반 사실로 보고하라.`,
  },
  {
    key: 'us-flow',
    q: `미국장 "매매동향/자금흐름"을 무료 또는 저비용으로 얻는 방법을 조사하라.
특히: ETF fund flow(자금 유입/유출), 풋콜레이쇼(CBOE), 시장 폭(advance/decline, % above 200MA), AAII 심리지수, yfinance로 추가 수집 가능한 티커/지표.
현재 봇은 yfinance 가격/거래량만 쓴다. 각 소스의 접근성(무료 여부/API/스크래핑)과 신뢰성을 WebSearch 기반으로 보고하라.`,
  },
  {
    key: 'market-internals',
    q: `한국·미국 공통의 "시장 내부(market internals)·투자심리" 지표를 무료로 얻는 소스를 조사하라.
특히: 등락주선(advance/decline line), 신고가-신저가, 거래대금 추세, VIX 외 공포탐욕지수(CNN Fear&Greed), 풋콜레이쇼.
이런 지표가 "매매동향 해석"을 어떻게 보강하는지와 데이터 접근 방법을 WebSearch 기반 사실로 보고하라.`,
  },
]

// ── 스키마 ──
const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lens', 'current_assessment', 'findings'],
  properties: {
    lens: { type: 'string' },
    current_assessment: { type: 'string', description: '이 렌즈에서 본 현재 데이터 수집의 종합 평가 (2-4문장)' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'type', 'title', 'detail', 'evidence', 'impact', 'proposal'],
        properties: {
          id: { type: 'string', description: 'kebab-case 식별자' },
          type: { type: 'string', enum: ['error', 'omission', 'improvement'], description: 'error=버그/오류, omission=누락, improvement=개선' },
          title: { type: 'string' },
          detail: { type: 'string', description: '무엇이 문제인지 구체적으로' },
          evidence: { type: 'string', description: '코드 근거 (파일:라인 또는 함수명). 없으면 "도메인 논증"' },
          impact: { type: 'string', enum: ['high', 'medium', 'low'] },
          proposal: { type: 'string', description: '구체적 개선안 (도메인 불변성 준수)' },
          data_source_needed: { type: 'string', description: '필요한 데이터 소스/API. 없으면 빈 문자열' },
        },
      },
    },
  },
}

const VERIFIED_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lens', 'verified'],
  properties: {
    lens: { type: 'string' },
    verified: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'type', 'title', 'verdict', 'verdict_reason', 'corrected_impact', 'feasibility', 'detail', 'proposal', 'evidence'],
        properties: {
          id: { type: 'string' },
          type: { type: 'string', enum: ['error', 'omission', 'improvement'] },
          title: { type: 'string' },
          detail: { type: 'string', description: '검증 후 다듬은 문제 설명' },
          evidence: { type: 'string', description: '검증으로 확인한 코드 근거' },
          proposal: { type: 'string', description: '검증 후 다듬은 제안' },
          verdict: { type: 'string', enum: ['confirmed', 'partial', 'rejected'], description: 'confirmed=코드/도메인 근거로 사실, partial=일부만/조건부, rejected=거짓양성·오해' },
          verdict_reason: { type: 'string', description: '판정 근거 (코드 재확인 결과). 왜 confirmed/partial/rejected인지' },
          corrected_impact: { type: 'string', enum: ['high', 'medium', 'low'] },
          feasibility: { type: 'string', enum: ['easy', 'moderate', 'hard', 'unknown'], description: '개선 구현/데이터수집 난이도' },
        },
      },
    },
  },
}

const FEASIBILITY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['source', 'available_data', 'notes'],
  properties: {
    source: { type: 'string' },
    available_data: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'description', 'access_method', 'relevance', 'difficulty', 'confidence'],
        properties: {
          name: { type: 'string', description: '데이터/지표 이름' },
          description: { type: 'string' },
          access_method: { type: 'string', description: 'API 엔드포인트/URL/라이브러리 등 접근 방법' },
          relevance: { type: 'string', description: '매매동향 해석에 어떻게 기여하는지' },
          difficulty: { type: 'string', enum: ['easy', 'moderate', 'hard'] },
          confidence: { type: 'string', enum: ['verified', 'likely', 'uncertain'], description: 'WebSearch로 확인된 정도' },
        },
      },
    },
    notes: { type: 'string', description: '종합 코멘트·주의점' },
  },
}

const ISSUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['title', 'summary', 'top_priorities', 'body_markdown', 'labels'],
  properties: {
    title: { type: 'string', description: 'GitHub 이슈 제목 (한국어, 간결)' },
    summary: { type: 'string', description: '사용자에게 보여줄 3-5문장 요약' },
    top_priorities: { type: 'array', items: { type: 'string' }, description: '최우선 개선 항목 3-6개 (한 줄씩)' },
    body_markdown: { type: 'string', description: 'GitHub 이슈 본문 전체 (한국어 마크다운). 아래 종합 지침의 구조를 따를 것' },
    labels: { type: 'array', items: { type: 'string' } },
  },
}

const CRITIQUE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['missing_perspectives', 'weak_or_unsupported', 'false_positives_to_drop', 'verdict'],
  properties: {
    missing_perspectives: { type: 'array', items: { type: 'string' }, description: '이슈 초안이 놓친 매매동향 관점·발견' },
    weak_or_unsupported: { type: 'array', items: { type: 'string' }, description: '근거가 약하거나 과장된 주장' },
    false_positives_to_drop: { type: 'array', items: { type: 'string' }, description: '거짓양성으로 빼야 할 항목' },
    verdict: { type: 'string', enum: ['solid', 'needs_revision'], description: '초안이 견고한지' },
  },
}

// ───────────────────────────────────────────────
//  실행
// ───────────────────────────────────────────────

log(`매매동향 데이터 감사 시작 — ${LENSES.length}개 렌즈 진단 + ${SOURCES.length}개 소스 실현성 리서치`)

// Phase A+B: 렌즈별 진단 → 적대적 검증 (pipeline — 한 렌즈가 검증 중일 때 다른 렌즈는 아직 진단 가능)
const findVerify = pipeline(
  LENSES,
  (lens) =>
    agent(
      `${CTX}\n\n---\n\n# 당신의 역할: ${lens.title}\n\n${lens.focus}\n\n` +
        `위에 나열된 핵심 파일을 Read 도구로 **직접 열어 확인**하라. 이미 구현된 항목을 "누락"으로 잘못 보고하지 마라.\n` +
        `필요하면 WebSearch로 도메인 사실(어떤 지표가 매매동향에 중요한지)을 보강하되, 코드 사실은 반드시 원본으로 확인하라.\n` +
        `현재 상태를 냉정히 평가하고, error(오류)·omission(누락)·improvement(개선)으로 분류된 발견 목록을 반환하라. 5~10개 발견을 목표로 하되 질이 양보다 우선이다.`,
      { label: `진단:${lens.key}`, phase: '진단', schema: FINDINGS_SCHEMA }
    ),
  (found, lens) => {
    if (!found || !found.findings || !found.findings.length) return { lens: lens.title, verified: [] }
    return agent(
      `${CTX}\n\n---\n\n# 당신의 역할: 적대적 검증가 (대상 렌즈: ${lens.title})\n\n` +
        `아래는 "${lens.title}" 렌즈가 보고한 발견 목록(JSON)이다. 당신의 임무는 **각 발견을 의심하고 코드로 재검증**하는 것이다.\n` +
        `기본 입장은 회의적으로: 핵심 파일을 Read로 다시 열어 주장의 코드 근거를 확인하라.\n` +
        `- 이미 구현되어 있는데 "누락"이라 한 것 → rejected\n` +
        `- 코드를 오해한 것, 영향이 과장된 것 → rejected 또는 impact 하향\n` +
        `- 실제 코드/도메인 근거가 확실 → confirmed\n` +
        `- 일부만 맞거나 조건부 → partial\n` +
        `각 발견에 verdict, verdict_reason(코드 재확인 결과), corrected_impact, feasibility(구현/데이터수집 난이도)를 부여하라.\n` +
        `도메인 불변성(사실 데이터만, 투자권유 금지)을 위반하는 제안은 rejected 처리하라.\n\n` +
        `## 검증 대상 발견 목록\n\`\`\`json\n${JSON.stringify(found, null, 2)}\n\`\`\``,
      { label: `검증:${lens.key}`, phase: '검증', schema: VERIFIED_SCHEMA }
    )
  }
)

// Phase C: 데이터 소스 실현성 리서치 (A+B와 동시 진행)
const feasResearch = parallel(
  SOURCES.map((s) => () =>
    agent(
      `${CTX}\n\n---\n\n# 당신의 역할: 데이터 소스 실현성 리서처\n\n${s.q}\n\n` +
        `WebSearch를 적극 활용하라. 목표는 "개선 제안이 실제 무료/저비용으로 수집 가능한지"의 사실 근거 확보다.\n` +
        `확인된 것은 confidence=verified, 정황상 가능은 likely, 불확실은 uncertain으로 정직하게 표기하라. 존재하지 않는 API를 지어내지 마라.`,
      { label: `실현성:${s.key}`, phase: '실현성', schema: FEASIBILITY_SCHEMA }
    )
  )
)

const [reviewed, feasibility] = await Promise.all([findVerify, feasResearch])

const verifiedAll = (reviewed || []).filter(Boolean)
const feasAll = (feasibility || []).filter(Boolean)

const confirmedCount = verifiedAll.reduce(
  (acc, r) => acc + (r.verified || []).filter((v) => v.verdict === 'confirmed' || v.verdict === 'partial').length,
  0
)
const rejectedCount = verifiedAll.reduce(
  (acc, r) => acc + (r.verified || []).filter((v) => v.verdict === 'rejected').length,
  0
)
log(`검증 완료 — 확정/부분 ${confirmedCount}건, 기각(거짓양성) ${rejectedCount}건. 실현성 리서치 ${feasAll.length}건. 종합 시작.`)

// Phase D: 종합 → 이슈 초안
const SYNTH_GUIDE = `
# 종합 지침 — GitHub 이슈 본문(body_markdown) 구조

검증 결과 verdict=rejected 인 항목은 본문에서 제외하라(단, 특히 중요한 거짓양성은 "검토했으나 제외한 항목"에 짧게 남겨도 됨).
confirmed/partial 만 채택한다. corrected_impact 와 feasibility로 우선순위를 매겨라(영향 high & feasibility easy/moderate가 최우선).
실현성 리서치(feasibility) 결과로 각 제안에 "수집 가능 여부/방법"의 근거를 붙여라. 존재 확인 안 된 소스는 그렇게 표기.

본문은 한국어 마크다운으로 다음 구조를 따른다:

## 배경 / 목적
한 문단: 현재 봇이 무엇을 수집하는지, 이 이슈가 무엇을 점검했는지(매매동향 파악의 최선 여부).

## 현황 진단 요약
6개 렌즈의 current_assessment를 2~3문장으로 압축한 종합 평가. 잘 되어 있는 점도 공정하게 인정.

## 🐞 발견된 오류 (type=error, confirmed/partial)
표 또는 목록: 제목 · 코드 근거(파일) · 영향 · 제안. 재현/근거가 분명한 것만.

## 🕳️ 데이터 누락 (type=omission)
"매매동향 해석에 필요한데 현재 전혀 없는" 데이터 축. 각 항목: 왜 필요한지 · 현재 대체 불가 이유 · 수집 가능 소스(실현성 근거) · 난이도.
선물/공매도/신용·예탁금/업종별 수급/시장 폭/미국 fund flow 등 핵심 누락을 우선 배치.

## 🔧 개선 제안 (type=improvement)
정확성·견고성 개선. 스크리너 정렬 편향, 종가환산, 검증/재시도, 신선도 체크 등.

## 우선순위 로드맵
P0(즉시·저비용·고영향) / P1(중기) / P2(장기·고난이도)로 그룹핑. 각 항목 한 줄 + 근거(영향/난이도).

## 검토했으나 제외한 항목 (선택)
거짓양성으로 판정한 주요 주장과 그 이유 — 후속 혼동 방지용.

## 부록: 데이터 소스 실현성 메모
리서치로 확인된 소스별 접근 방법 요약.

전체적으로: 구체적이고, 코드 근거가 있고, 도메인 불변성을 지키며, 실현 가능한 제안 중심으로. 막연한 일반론 금지.
`.trim()

phase('종합')
const draft = await agent(
  `${CTX}\n\n---\n\n# 당신의 역할: 수석 애널리스트 — 종합 및 이슈 작성\n\n` +
    `6개 렌즈의 적대적 검증 결과와 데이터 소스 실현성 리서치를 종합해 하나의 GitHub 이슈 초안을 작성하라.\n\n` +
    `${SYNTH_GUIDE}\n\n` +
    `## 입력 1: 검증된 발견 (렌즈별)\n\`\`\`json\n${JSON.stringify(verifiedAll, null, 2)}\n\`\`\`\n\n` +
    `## 입력 2: 데이터 소스 실현성 리서치\n\`\`\`json\n${JSON.stringify(feasAll, null, 2)}\n\`\`\``,
  { label: '종합:이슈초안', phase: '종합', schema: ISSUE_SCHEMA }
)

// Phase E: 완결성 비평
phase('완결성')
const critique = await agent(
  `${CTX}\n\n---\n\n# 당신의 역할: 완결성 비평가\n\n` +
    `아래 이슈 초안을 비판적으로 검토하라. "매매동향을 파악하기 위한 최선인가"라는 본질 질문에 비추어:\n` +
    `1. 놓친 중요한 매매동향 관점·데이터 축이 있는가? (missing_perspectives)\n` +
    `2. 근거가 약하거나 과장된 주장은? (weak_or_unsupported)\n` +
    `3. 거짓양성으로 빼야 할 항목은? (false_positives_to_drop)\n` +
    `필요하면 핵심 코드 파일을 Read로 다시 확인하라. 냉정하고 구체적으로.\n\n` +
    `## 이슈 초안\n제목: ${draft.title}\n\n${draft.body_markdown}`,
  { label: '완결성:비평', phase: '완결성', schema: CRITIQUE_SCHEMA }
)

// Phase F: 비평 반영 최종화
phase('최종화')
const final = await agent(
  `${CTX}\n\n---\n\n# 당신의 역할: 수석 애널리스트 — 최종화\n\n` +
    `완결성 비평을 반영해 이슈를 최종본으로 다듬어라. 누락 관점은 보강하고, 과장/거짓양성은 제거하며, 구조와 우선순위를 정제하라.\n` +
    `${SYNTH_GUIDE}\n\n` +
    `## 비평 결과\n\`\`\`json\n${JSON.stringify(critique, null, 2)}\n\`\`\`\n\n` +
    `## 기존 초안\n제목: ${draft.title}\n\n${draft.body_markdown}\n\n` +
    `## 원본 검증 발견 (필요시 참조)\n\`\`\`json\n${JSON.stringify(verifiedAll, null, 2)}\n\`\`\`\n\n` +
    `## 실현성 리서치 (필요시 참조)\n\`\`\`json\n${JSON.stringify(feasAll, null, 2)}\n\`\`\``,
  { label: '최종화:이슈', phase: '최종화', schema: ISSUE_SCHEMA }
)

log('최종 이슈 본문 완성')

return {
  final,
  critique,
  stats: { confirmed_or_partial: confirmedCount, rejected: rejectedCount, lenses: LENSES.length, sources: SOURCES.length },
  verifiedAll,
  feasAll,
}
