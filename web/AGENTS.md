<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# 이 웹은 텔레그램 봇의 종속 표현이다

원본(source of truth)은 상위 저장소의 텔레그램 메시지 데이터/포맷이다. 이 웹은
봇이 발행한 스냅샷(`itda-skills/rs-golden-queens-data`)을 **읽기 전용**으로
표시할 뿐이다.

- 표시할 값은 발행 스냅샷에 이미 있어야 한다. 웹에서 데이터를 새로 수집·계산하거나
  거래일/휴장/색 의미 같은 시장 로직을 재구현하지 않는다.
- 스냅샷 스키마(상위 `market_flow/publisher.py`, `schema_version`)가 바뀌면 이
  웹의 `src/lib/types.ts`·`data.ts`와 해당 페이지/컴포넌트도 같은 변경에서 갱신한다.
- 색 컨벤션(상승 빨강 / 하락 파랑)은 값의 부호에서 파생한다(`src/lib/format.ts`).
- 변경 후 `npm run build` + `npx eslint src --max-warnings 0` 를 통과시킨다.
- 투자 권유·종목 추천·시점 판단을 노출하지 않는다(상위 도메인 불변성 동일 적용).
