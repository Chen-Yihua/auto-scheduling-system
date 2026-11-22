import type { SchedulableTask } from './schedulableTask';

export interface ScheduledTask {
  task_id: string;
  title: string;
  priority: 'Low' | 'Medium' | 'High';
  start: string;
  end: string;
}

export interface UnscheduledTask {
  task_id: string;
  title: string;
  priority: 'Low' | 'Medium' | 'High';
  reason: string;
}

export interface ScheduleSuggestion {
  scheduled: ScheduledTask[];
  unscheduled: UnscheduledTask[];
}

export interface ConfirmedTask {
  task_id: string;
  title: string;
  calendar_event_id: string;
}

// 對應後端 FailedConfirmation
export interface FailedConfirmation {
  task_id: string;
  title: string;
  reason: string;
  // 寫入 Google 失敗的原因；寫入前檢查不通過、前一個階段寫入失敗是 null
  error_code: string | null;
}

export interface ScheduleConfirmResult {
  confirmed: ConfirmedTask[];
  failed: FailedConfirmation[];
}

// 對應後端 LaterStage：勾選重新排程時會一起從 Google 日曆移除的後面階段
export interface LaterStage {
  task_id: string;
  stage: number;
}

// 對應後端 RemovedCalendarEventOut：Google 日曆上的事件已被刪除的項目
export interface RemovedCalendarEvent extends SchedulableTask {
  later_stages: LaterStage[];
}

// 對應後端 ResolveRemovedEventsFailure
export interface ResolveRemovedEventsFailure {
  task_id: string;
  reason: string;
  // 處理時編號已被換掉是 null
  error_code: string | null;
}

export interface ResolveRemovedEventsResult {
  succeeded: string[];
  failed: ResolveRemovedEventsFailure[];
}

// days_of_week：0=週一 ... 6=週日，和後端 weekday() 一致
export interface BlockedRecurringRule {
  days_of_week: number[];
  all_day: boolean;
  start_time: string | null // "HH:MM"
  end_time: string | null;
}

export interface BlockedException {
  start: string // ISO
  end: string;
}

// 對應後端 SavedSchedulePreferences：存在使用者帳號上、下次打開排程頁帶入的部分
export interface SavedSchedulePreferences {
  blocked_recurring: BlockedRecurringRule[];
  blocked_exceptions: BlockedException[];
  buffer_minutes: number;
  daily_max_minutes: number | null;
}

// 每次產生排程建議都要帶
export interface SchedulePreferences extends SavedSchedulePreferences {
  // IANA 時區，後端用來把當地時間換算成 UTC；不存，每次用瀏覽器當時的
  timezone: string;
}

export function defaultSchedulePreferences(): SchedulePreferences {
  return {
    blocked_recurring: [],
    blocked_exceptions: [],
    buffer_minutes: 0,
    daily_max_minutes: null,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };
}

// 對應後端 RescheduleTasksResult
export interface RescheduleTasksResult {
  succeeded: string[];
  failed: ResolveRemovedEventsFailure[];
}
