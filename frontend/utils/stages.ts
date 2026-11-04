// 階段任務在排程頁拖拉時的檢查，規則和後端的階段鏈驗證一致：後面的階段優先序不能高於前面的階段
import type { SchedulableTask } from '~/types/schedulableTask'

type Priority = 'Low' | 'Medium' | 'High'

const PRIORITY_RANK: Record<Priority, number> = { Low: 0, Medium: 1, High: 2 }

// 模擬 useScheduleWizard 的 moveTask，回傳會讓階段限制被違反的原因；沒問題回 null
export function stageMoveBlockReason(
  columns: Record<Priority, SchedulableTask[]>,
  allTasks: SchedulableTask[],
  fromColumn: Priority,
  fromIndex: number,
  toColumn: Priority,
  toIndex: number,
): string | null {
  const moved = columns[fromColumn][fromIndex]
  if (!moved?.parent_id || !moved.stage) return null

  const source = [...columns[fromColumn]]
  source.splice(fromIndex, 1)
  const target = fromColumn === toColumn ? source : [...columns[toColumn]]
  target.splice(Math.max(0, Math.min(toIndex, target.length)), 0, moved)

  // 不在欄位裡的階段（已完成、已排入行事曆）用原本的優先序
  const priorityById = new Map<string, Priority | null | undefined>(allTasks.map((t) => [t.id, t.priority]))
  for (const column of Object.keys(columns) as Priority[]) {
    for (const task of columns[column]) priorityById.set(task.id, column)
  }
  priorityById.set(moved.id, toColumn)

  const siblings = allTasks.filter((t) => t.parent_id === moved.parent_id && t.id !== moved.id && t.stage)
  for (const sibling of siblings) {
    const siblingRank = PRIORITY_RANK[priorityById.get(sibling.id) ?? 'Medium']
    const movedRank = PRIORITY_RANK[toColumn]
    if (sibling.stage! < moved.stage && movedRank > siblingRank) {
      return `階段 ${moved.stage} 的優先序不能高於階段 ${sibling.stage}`
    }
    if (sibling.stage! > moved.stage && siblingRank > movedRank) {
      return `階段 ${sibling.stage} 的優先序不能高於階段 ${moved.stage}`
    }
  }

  const sameParentInTarget = target.filter((t) => t.parent_id === moved.parent_id)
  for (let i = 1; i < sameParentInTarget.length; i++) {
    const above = sameParentInTarget[i - 1]!
    const below = sameParentInTarget[i]!
    if ((above.stage ?? 0) > (below.stage ?? 0)) {
      return `同一欄內，階段 ${above.stage} 不能排在階段 ${below.stage} 前面`
    }
  }
  return null
}
