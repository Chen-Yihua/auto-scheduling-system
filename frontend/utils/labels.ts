// 畫面上顯示用的中文對照表。
//
// 這些欄位的「值」是後端與資料庫存的內容（例如 priority 一定是 High / Medium / Low），
// 不能改成中文，否則送去後端會被拒絕；所以只在「顯示」的時候轉成中文，資料本身維持英文。
// 對照表裡沒有的值（例如未來新增的狀態）會原樣顯示，不會變成空白。

export const priorityLabels: Record<string, string> = {
  High: '高',
  Medium: '中',
  Low: '低',
}

export const taskStatusLabels: Record<string, string> = {
  'To Do': '待辦',
  'In Progress': '進行中',
  Done: '已完成',
}

// GitHub 的 issue / PR 狀態（API 回傳小寫）
export const githubStateLabels: Record<string, string> = {
  open: '開啟中',
  closed: '已關閉',
  merged: '已合併',
}

// LeetCode 題目難度
export const leetcodeDifficultyLabels: Record<string, string> = {
  Easy: '簡單',
  Medium: '中等',
  Hard: '困難',
}

function labelOf(labels: Record<string, string>, value: string | undefined | null): string {
  if (!value) return ''
  return labels[value] ?? value
}

export const priorityLabel = (value: string | undefined | null) => labelOf(priorityLabels, value)
export const taskStatusLabel = (value: string | undefined | null) => labelOf(taskStatusLabels, value)
export const githubStateLabel = (value: string | undefined | null) => labelOf(githubStateLabels, value)
export const leetcodeDifficultyLabel = (value: string | undefined | null) => labelOf(leetcodeDifficultyLabels, value)
