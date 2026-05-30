// 발행 목록(최신순 내림차순)에서 현재 항목의 이전(과거)/다음(미래)을 구한다.
// 서버 컴포넌트에서 호출되므로 클라이언트 코드와 분리한다.

export function adjacent(
  ids: string[],
  current: string,
): { prev: string | null; next: string | null } {
  const i = ids.indexOf(current);
  if (i === -1) return { prev: null, next: null };
  // ids 내림차순: i+1 = 더 과거(prev), i-1 = 더 미래(next)
  return {
    prev: i + 1 < ids.length ? ids[i + 1] : null,
    next: i - 1 >= 0 ? ids[i - 1] : null,
  };
}
