# Project Interview

> 본 인터뷰는 사용자 선택에 따라 라이브 Q&A 대신 **HANDOFF.md(2026-05-23 작성)**의 압축으로 대체되었다.
> 출처: 저장소 루트 `HANDOFF.md` (untracked, working tree 보존)

## Round 1: Ownership and Purpose

**Question**: 누가 유지하는가, 향후 방향은?

**Answer**: 활발히 운영 중인 **단일 자동화 서비스**.
- 2026-05-23 분리·이전된 저장소. 원조는 `itda-skills/skills/naver-investor-flow/` 스킬이었으나, 원 모노리포에서 관련 3개 commit이 `git reset --hard`로 폐기되어 **이 저장소가 유일한 보유처**.
- 원 SPEC: `SPEC-NAVER-INVESTOR-FLOW-001` v0.3.0 (Completed, Migrated to rs-golden-queens). 현 commit에 SPEC 본문은 미포함 — README + HANDOFF + commit message로 의도가 보존됨.
- 정체성은 "스킬 카탈로그의 한 항목"이 아닌 **독립 자동화 서비스**.

## Round 2: Constraints and Non-Goals

**Question**: 알려진 제약·기술 부채·의도적으로 안 하는 것은?

**Answer**: 다수의 [HARD] 제약이 의도되어 있다.

### 의도된 기술 제약
- **stdlib only**: `urllib` + `html.parser` + `csv` + `datetime` + `re`만 사용. `requests`/`httpx`/`aiohttp`/`bs4`/`lxml` 도입 금지. `pytest`만 옵션 테스트 의존.
- **`WebFetch` 금지**: Anthropic 인프라 IP 차단·헤더 정규화 위험.
- **데이터 저장 금지**: commit/Release/Pages에 수집 결과 저장 안 함. 본 저장소는 코드 저장 목적만.

### 라이브 검증으로 박힌 함정 3건
1. **`flow_day`의 `bizdate`는 필수** — 미지정 시 1.6KB 빈 페이지 반환. `collect.fetch_flow_day`와 `cli._build_flow_url`이 미지정 시 오늘 KST 자동 주입.
2. **`deal_rank`의 `bizdate`는 무시됨** — 네이버 서버단이 이 파라미터를 안 본다. CLI에 `--bizdate` 옵션 신설 금지 (SPEC `REQ-020.4`로 명시적 거부).
3. **단위 의도적 차별화** — `flow_day=억원`, `deal_rank=백만원`. 통일 금지 (100배 차이로 사용자 의사결정 오류 방지). `test_formatter.py`가 negative assertion으로 강제.

### 절대 거부 사항 (사용자 명시)
- 데이터 저장 (commit/Release/Pages)
- 시간별 매매동향 / 시계열 누적
- `WebFetch` 사용
- 단위 통일 (flow_day vs deal_rank)
- `deal_rank --bizdate` 신설
- 매매 신호·종목 추천·자문 (사실 데이터 + 디스클레이머만)

### 운영 제약
- cron `10 9 * * *` UTC = KST 18:10 (시간외 18:00 종료 + 안정 마진 10분).
- 평일·주말 분기 없음 (주말도 직전 영업일 데이터 반환됨).
- Telegram secrets 부재 시 `collect.py`가 stdout만 출력하고 정상 종료 — 로컬·CI 코드 동일 경로.
- `tests/test_live_smoke.py`는 라이브 호출 → `make test`에서 `--ignore`로 제외. CI도 동일.

## Round 3: Documentation Priority

**Question**: 문서에서 가장 정확히 담아야 할 것은?

**Answer**: **숨은 결정·함정**. 코드에서 자동 추론되지 않는 다음 정보들이 product.md / tech.md에 반드시 명시적으로 박혀야 한다:

1. **stdlib-only 정책의 근거** (의존성 0 → GitHub Actions 캐시 불필요, 보안 표면 0)
2. **bizdate 비대칭** (`flow_day`=필수, `deal_rank`=무시) — API 설계자의 함정 회피 패턴
3. **단위 의도적 차별화** — 통일하지 말라는 negative requirement
4. **Referer 효과 0이지만 유지하는 이유** — 미래 차단 회피 보험
5. **cron 시각 산정 로직** — KST 18:10 = 시간외 종료 + 마진
6. **데이터 저장 명시 거부** — 외부 디렉토리·이력 보관 별도 데이터 저장소로 분리

아키텍처(structure.md)와 기술 스택(tech.md)은 코드 자동 분석으로 충분하나, **제약·거부 사항은 사람이 명시적으로 문서화하지 않으면 다음 세션이 즉시 깬다**.
