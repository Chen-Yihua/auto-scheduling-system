// 把 ISO 時間字串轉成「X 分鐘前」這種相對時間文字，給資料新鮮度提示用
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '未知時間'

  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60000)

  if (minutes < 1) return '剛剛'
  if (minutes < 60) return `${minutes} 分鐘前`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小時前`

  const days = Math.floor(hours / 24)
  return `${days} 天前`
}
