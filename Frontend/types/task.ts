export interface Task {
    id: string
    user_id: string
    title: string
    description: string
    priority: 'Low' | 'Medium' | 'High'
    status: string
    due_date: string
    duration?: number
    inferred_fields?: string[]
    inference_reason?: string | null
    inference_hint?: string | null
    // 使用者在排程精靈的拖拉排序畫面決定的順序（0 開始，數字越小排越前面）。
    // 只有做過拖拉排序才有值，見 PUT /manual_tasks/reorder
    sort_order?: number | null
    // 使用者「確認排程」後，這筆任務被寫進 Google Calendar 的事件 id。
    // 有值代表已經鎖定，不會再被排程建議或拖拉排序精靈動到，見 POST /schedule/confirm
    calendar_event_id?: string | null
}
