// 對應後端 ProductivitySummary（schemas/analytics.py）
import type { SchedulableSource } from './schedulableTask'

export interface SourceStat {
  source: SchedulableSource
  total: number
  done: number
}

export interface PriorityStat {
  // null 是外部平台還沒設定優先度的項目
  priority: 'Low' | 'Medium' | 'High' | null
  total: number
  done: number
}

export interface WeeklyCompletion {
  week_start: string // YYYY-MM-DD，使用者時區的週一
  completed: number
  completed_minutes: number
}

export interface ProductivitySummary {
  total: number
  done: number
  // 0 到 1；沒有任何項目時是 null
  completion_rate: number | null
  overdue: number
  done_minutes: number
  remaining_minutes: number
  unestimated_remaining: number
  // 開始記錄完成時間前就完成的項目，不在週趨勢和準時率裡
  untracked_done: number
  by_source: SourceStat[]
  by_priority: PriorityStat[]
  weekly: WeeklyCompletion[]
  on_time: { completed_with_due: number; on_time: number; rate: number | null }
}
