// 顯示用的中文對照。資料本身維持英文（後端只接受英文值），對照表沒有的值原樣顯示。

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

// GitHub API 回傳小寫
export const githubStateLabels: Record<string, string> = {
  open: '開啟中',
  closed: '已關閉',
  merged: '已合併',
}

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
