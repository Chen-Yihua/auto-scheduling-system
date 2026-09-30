export interface ScheduledTask {
  task_id: string
  title: string
  priority: 'Low' | 'Medium' | 'High'
  start: string
  end: string
}

export interface UnscheduledTask {
  task_id: string
  title: string
  priority: 'Low' | 'Medium' | 'High'
  reason: string
}

export interface ScheduleSuggestion {
  scheduled: ScheduledTask[]
  unscheduled: UnscheduledTask[]
}

export interface ConfirmedTask {
  task_id: string
  title: string
  calendar_event_id: string
}

export interface FailedConfirmation {
  task_id: string
  title: string
  reason: string
}

export interface ScheduleConfirmResult {
  confirmed: ConfirmedTask[]
  failed: FailedConfirmation[]
}

// 每週固定不工作時段，例如「每天 22:00-08:00」「週六、週日全天」。
// days_of_week 跟後端 Python datetime.weekday() 對齊：0=一...6=日。
// all_day 為 true 時 start_time/end_time 不需要值。
export interface BlockedRecurringRule {
  days_of_week: number[]
  all_day: boolean
  start_time: string | null // "HH:MM"
  end_time: string | null
}

// 這次排程期間內額外加的一次性不工作時段，只影響這一輪排程建議
export interface BlockedException {
  start: string // ISO
  end: string
}

// 使用者在排程精靈裡當場填的排程偏好，不存資料庫、每次都要重新帶給後端
// （見 AskUserQuestion 紀錄：使用者選擇「每次精靈重新選」）
export interface SchedulePreferences {
  blocked_recurring: BlockedRecurringRule[]
  blocked_exceptions: BlockedException[]
  buffer_minutes: number
  daily_max_minutes: number | null
}

export function defaultSchedulePreferences(): SchedulePreferences {
  return {
    blocked_recurring: [],
    blocked_exceptions: [],
    buffer_minutes: 0,
    daily_max_minutes: null,
  }
}
