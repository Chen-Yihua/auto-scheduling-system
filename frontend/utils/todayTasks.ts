// 首頁今日卡片的分區、排序與狀態標籤；「現在」由參數傳入，測試才能固定時間
import type { SchedulableTask } from '~/types/schedulableTask'

export type TodayLabel = '已逾期' | '已完成' | '進行中' | '未開始'

export interface TodayRow {
  task: SchedulableTask
  label: TodayLabel
  overdue: boolean
}

export interface TodayView {
  overdue: TodayRow[]
  today: TodayRow[]
  // 批次重新排程要送出的任務 id：已逾期而且有 calendar_event_id
  batchIds: string[]
  // 批次重新排程會一起移除的後面階段數量（去掉重複，不含批次裡的任務）
  laterStageCount: number
}

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()

const isSameDay = (a: Date, b: Date) => startOfDay(a) === startOfDay(b)

function isOverdue(task: SchedulableTask, now: Date): boolean {
  if (task.status === 'Done') return false
  // 截止日那一天已經結束才算：今天 00:00 截止的任務今天還不算已逾期
  if (task.due_date && startOfDay(new Date(task.due_date)) < startOfDay(now)) return true
  return !!task.scheduled_end && new Date(task.scheduled_end) < now
}

function labelOf(task: SchedulableTask, overdue: boolean): TodayLabel {
  if (overdue) return '已逾期'
  if (task.status === 'Done') return '已完成'
  if (task.status === 'In Progress') return '進行中'
  return '未開始'
}

// 已逾期排序用截止日期與時段結束時間中較早的那個；只有一個時用那一個
function overdueSortTime(task: SchedulableTask): number {
  const times = [task.due_date, task.scheduled_end].filter(Boolean).map((v) => new Date(v!).getTime())
  return Math.min(...times)
}

export function buildTodayView(tasks: SchedulableTask[], now: Date): TodayView {
  const candidates = tasks.filter((t) => !t.is_parent)

  const overdue = candidates
    .filter((t) => isOverdue(t, now))
    .sort((a, b) => overdueSortTime(a) - overdueSortTime(b))
    .map((task) => ({ task, label: labelOf(task, true), overdue: true }))

  const overdueIds = new Set(overdue.map((r) => r.task.id))
  const today = candidates
    .filter((t) => !overdueIds.has(t.id) && !!t.scheduled_start && isSameDay(new Date(t.scheduled_start), now))
    .sort((a, b) => {
      const doneOrder = Number(a.status === 'Done') - Number(b.status === 'Done')
      return doneOrder || new Date(a.scheduled_start!).getTime() - new Date(b.scheduled_start!).getTime()
    })
    .map((task) => ({ task, label: labelOf(task, false), overdue: false }))

  const batch = overdue.map((r) => r.task).filter((t) => !!t.calendar_event_id)
  const batchIds = batch.map((t) => t.id)
  const later = new Set<string>()
  for (const t of batch) {
    if (!t.parent_id || !t.stage) continue
    for (const s of tasks) {
      if (s.parent_id === t.parent_id && (s.stage ?? 0) > t.stage && s.calendar_event_id
        && s.status !== 'Done' && !batchIds.includes(s.id)) later.add(s.id)
    }
  }

  return { overdue, today, batchIds, laterStageCount: later.size }
}
