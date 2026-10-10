export interface Task {
    id: string
    user_id: string
    title: string
    description: string
    priority: 'Low' | 'Medium' | 'High'
    status: string
    due_date: string | null
    duration?: number
    inferred_fields?: string[]
    inference_reason?: string | null
    inference_hint?: string | null
    // 同 priority 內的排序（越小越前）
    sort_order?: number | null
    // 有值代表已寫入行事曆，不再參與排程
    calendar_event_id?: string | null
}
