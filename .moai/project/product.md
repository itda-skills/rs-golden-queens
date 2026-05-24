# product.md — rs-golden-queens

## 프로젝트명

**rs-golden-queens**

## 요약

네이버 금융 공개 페이지에서 한국 주식시장 투자자 매매동향(개인·외국인·기관)과 외국인·기관 종목별 매매 랭킹을 매일 자동 수집하여 텔레그램으로 즉시 발송하는 단독 자동화 서비스.

## 목적과 대상 사용자

| 항목 | 내용 |
|---|---|
| 목적 | 개인 투자자 본인이 직접 사용하는 데이터 보조 도구. 매일 장 마감 후 시장 흐름을 스마트폰 텔레그램 알림 한 건으로 확인. |
| 대상 | 개인 투자자 1인 (자기 계정, 자기 봇, 자기 chat ID 사용). 다수 사용자 배포·SaaS·API 서비스 목적이 아님. |

> 본 서비스는 사실 데이터만 제공합니다. 투자 권유·종목 추천·시점 판단이 아니며, 데이터 정확성·완전성·시의성을 보장하지 않습니다. 투자 결정 전 공식 출처를 반드시 확인하십시오.

## 핵심 기능

- 매일 KST 18:10 GitHub Actions cron 자동 실행 (시간외 거래 18:00 종료 직후)
- 네이버 금융 공개 페이지 9회 호출: flow_day 1회 + deal_rank 8조합 (KOSPI/KOSDAQ × 외국인/기관 × 매수/매도)
- 응답 EUC-KR 자동 디코딩 + HTML 파싱 → 정형 데이터 추출
- 마크다운 보고서 생성 후 텔레그램 sendMessage 전송 (최대 4096자, 초과 시 자동 잘림 표시)
- Telegram 환경변수 부재 시 stdout만 출력하고 정상 종료 — 로컬·CI 코드 경로 동일
- CLI 단발 조회: `python3 -m naver_investor_flow flow_day` / `deal_rank` (json/table/csv 포맷 선택)
- Makefile 11개 타겟으로 자주 쓰는 운영 명령 래핑

## 핵심 사용 시나리오

### 시나리오 1: cron 자동 수집 (주 사용)

1. GitHub Actions `daily.yml` cron `10 9 * * *` (UTC) 실행
2. `python -m naver_investor_flow.collect` → 9회 HTTP 호출
3. 보고서 빌드 → stdout 출력 (Actions 로그)
4. `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` 환경변수가 있으면 텔레그램 발송
5. 사용자는 스마트폰에서 보고서를 받음

### 시나리오 2: CLI 단발 조회

```bash
# flow_day — 오늘 날짜 자동 주입
make flow

# deal_rank — 필수 인자 지정
make rank MARKET=kospi INVESTOR=foreign SIDE=buy
```

### 시나리오 3: 텔레그램 연결 검증

```bash
TELEGRAM_BOT_TOKEN=<token> TELEGRAM_CHAT_ID=<id> make notify-test
```

## 정체성

rs-golden-queens는 **스킬 카탈로그의 한 항목이 아닌 독립 자동화 서비스**다. 원래 `itda-skills` 모노리포의 `itda-stocks/skills/naver-investor-flow/` 스킬로 구현되었으나, "매일 정해진 시간에 자동 수집 + 텔레그램 알림"은 스킬 형태보다 단독 서비스 형태가 적합하다는 결정으로 2026-05-23에 분리·이전되었다. 원 모노리포에서 관련 3개 commit이 `git reset --hard`로 폐기되어 **이 저장소가 유일한 보유처**다. `itda-skills` 측에는 코드 흔적 0건이다.

## 명시적 비목표

다음은 의도적으로 구현하지 않은 기능이다. 향후에도 추가하지 않는다.

| 비목표 항목 | 이유 |
|---|---|
| **데이터 저장** (commit/Release/Pages) | 본 저장소는 코드 저장 목적만. 수집 결과 이력이 필요하면 별도 데이터 저장소를 분리. |
| **시간별 매매동향** | 사용자가 명시적으로 "필요없음"으로 거부. |
| **시계열 누적** | 스냅샷만. `shared/itda_path.py` 같은 외부 디렉토리 의존 없음. |
| **매매 신호·종목 추천·자문** | 사실 데이터만 제공. SPEC-GOV-STOCK-001 P-1 동형 디스클레이머 적용. |
| **단위 통일** (flow_day ↔ deal_rank) | [HARD] 의도적 차별화. flow_day=억원, deal_rank=백만원. 통일 금지. |
| **`deal_rank --bizdate` 옵션 신설** | [HARD] 네이버 서버가 파라미터를 무시하므로 신설 금지. SPEC REQ-020.4 명시 거부. |
| **WebFetch 사용** | [HARD] Anthropic 인프라 IP 차단 위험·헤더 정규화 문제. `urllib` 자체 호출만 허용. |

## 출처

- `HANDOFF.md` §1 (출생 배경), §5.3 (절대 하지 말 것)
- `.moai/project/interview.md` Round 1 (Ownership and Purpose), Round 2 (Constraints and Non-Goals)
- `README.md` 요약·면책 섹션
