# Telegram 일일 보고서 컨텍스트 스키마 (SPEC-REPORT-001)

`daily_report.md` 슬롯 채우기에 사용되는 컨텍스트 dict 명세. `context-schema.json` (draft-07) 이 기계 검증용 정본이며, 본 문서는 사람이 읽는 보충 설명이다.

## 필수 슬롯 (default 템플릿이 사용)

| 이름 | 타입 | 단위 | 기본값 | 설명 |
|---|---|---|---|---|
| `title_emoji` | str | — | `📊` | 보고서 제목 이모지 |
| `bizdate` | str | — | (런타임 주입) | 기준일 YYYYMMDD (KST) |
| `fetched_at` | str | — | (런타임 주입) | 수집 시각 ISO 8601 (KST) |
| `flow_day_table` | str | 억원 | (런타임 빌드) | 일별 시장 매매 블록 — 헤더 1줄 + 본문 N줄 (N = `flow_day_rows`) |
| `rank_sections_block` | str | 백만원 | (런타임 빌드) | 8조합 랭킹 섹션을 빈 줄 구분 + 끝에 \n 1개 |
| `divider` | str | — | `─────────` | 본문 ↔ 디스클레이머 구분선 |
| `disclaimer` | str | — | `출처: finance.naver.com (사실 데이터, 투자 권유 아님)` | [HARD] 정확 문구 보존 |

## 선택 슬롯 (커스텀 템플릿용, Option B)

사용자가 `NIF_TEMPLATE_PATH` 로 자체 템플릿을 지정할 때 섹션 순서 재배치나 일부만 표시를 위해 사용 가능하다. 기본 템플릿은 사용하지 않는다.

| 이름 | 타입 | 단위 | 설명 |
|---|---|---|---|
| `rank_kospi_foreign_buy_top` | str | 백만원 | KOSPI 외국인 매수 TOP-N |
| `rank_kospi_foreign_sell_top` | str | 백만원 | KOSPI 외국인 매도 TOP-N |
| `rank_kospi_institution_buy_top` | str | 백만원 | KOSPI 기관 매수 TOP-N |
| `rank_kospi_institution_sell_top` | str | 백만원 | KOSPI 기관 매도 TOP-N |
| `rank_kosdaq_foreign_buy_top` | str | 백만원 | KOSDAQ 외국인 매수 TOP-N |
| `rank_kosdaq_foreign_sell_top` | str | 백만원 | KOSDAQ 외국인 매도 TOP-N |
| `rank_kosdaq_institution_buy_top` | str | 백만원 | KOSDAQ 기관 매수 TOP-N |
| `rank_kosdaq_institution_sell_top` | str | 백만원 | KOSDAQ 기관 매도 TOP-N |
| `flow_day_rows_limit` | int | — | `context-config.json` 의 `flow_day_rows` 사본 |
| `rank_top_n` | int | — | `context-config.json` 의 `rank_top_n` 사본 |

## 설정 (`context-config.json`)

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `flow_day_rows` | int | 5 | flow_day 표시 행 수 |
| `rank_top_n` | int | 3 | 각 랭킹 섹션 TOP-N |

## 동기화 규칙

- `daily_report.md` 의 모든 `{slot}` 은 `context-schema.json` `properties` 에 존재해야 한다.
- 반대도 성립: schema 의 `properties` 키는 모두 template 슬롯으로 사용되어야 한다.
- `tests/test_report_engine.py::TestSchemaTemplateSync` 가 양방향 검증.
