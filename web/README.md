# Golden Queens Web

한국·미국 시장 매매동향 **읽기 전용** 아카이브 (Next.js App Router).

발행 데이터 저장소 [`itda-skills/rs-golden-queens-data`](https://github.com/itda-skills/rs-golden-queens-data)의
스냅샷 JSON을 GitHub raw content로 읽어 ISR(10분)로 정적 렌더한다.
사실 데이터만 표시하며 투자 권유를 포함하지 않는다.

## 개발

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # 정적 생성 검증
```

## 환경변수 (.env.example 참조)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEXT_PUBLIC_DATA_BASE_URL` | unset | 로컬/프리뷰용 스냅샷 base URL. 설정 시 repo/branch보다 우선 |
| `NEXT_PUBLIC_DATA_REPO` | `itda-skills/rs-golden-queens-data` | 발행 데이터 저장소 |
| `NEXT_PUBLIC_DATA_BRANCH` | `main` | 읽을 브랜치 (test 가능) |

## Vercel 배포

- **Root Directory**: `web`
- Framework: Next.js (자동 감지)
- 환경변수는 기본값으로 동작 (별도 설정 불필요)
- ISR revalidate 10분 — 발행 직후 즉시 갱신은 후속(M3 on-demand revalidate)

## 라우트

| 경로 | 내용 |
|------|------|
| `/` | 최신 KR/US/주간 요약 |
| `/kr/[date]` | 한국장 일별 (코스피·코스닥·프로그램매매·추이) |
| `/us/[date]` | 미국장 (지수·변동성·매크로·섹터·워치ETF) |
| `/weekly/[week]` | 주간 (코스피·코스닥 추이 + 워치 5일 등락) |
| `/archive` | 전체 발행 날짜 인덱스 |

색 컨벤션: 한국 증시 관례 — 상승 🔴 / 하락 🔵 / 보합 –.
