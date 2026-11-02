// null 是「沒有資料可算」，要和 0% 區分
export function formatPercent(rate: number | null): string {
  if (rate === null) return '—'
  return `${Math.round(rate * 100)}%`
}

export function formatMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest} 分`
  if (rest === 0) return `${hours} 小時`
  return `${hours} 小時 ${rest} 分`
}
