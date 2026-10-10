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

// days_of_week：0=週一 ... 6=週日，和後端 weekday() 一致
export interface BlockedRecurringRule {
  days_of_week: number[]
  all_day: boolean
  start_time: string | null // "HH:MM"
  end_time: string | null
}

export interface BlockedException {
  start: string // ISO
  end: string
}

// 不存資料庫，每次請求都要帶
export interface SchedulePreferences {
  blocked_recurring: BlockedRecurringRule[]
  blocked_exceptions: BlockedException[]
  buffer_minutes: number
  daily_max_minutes: number | null
  // IANA 時區，後端用來把當地時間換算成 UTC
  timezone: string
}

export function defaultSchedulePreferences(): SchedulePreferences {
  return {
    blocked_recurring: [],
    blocked_exceptions: [],
    buffer_minutes: 0,
    daily_max_minutes: null,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  }
}
