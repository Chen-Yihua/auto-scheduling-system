// 優先級的顏色：任務列表的標籤和分析頁的長條共用，同一個優先級在各頁顏色一樣
// 粉、黃、綠三個色相差很遠，一眼分得出來；都是淺色，配黑字
export const priorityColors: Record<string, string> = {
  High: 'var(--color-palette-4)',
  Medium: 'var(--color-sand-300)',
  Low: 'var(--color-fern-300)',
}
