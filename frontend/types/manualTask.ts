// 對應後端 ManualTaskOut
export interface Task {
    id: string
    user_id: string
    title: string
    description: string
    // 主任務沒有優先序和時長
    priority: 'Low' | 'Medium' | 'High' | null
    status: string
    due_date: string | null
    duration?: number | null
    inferred_fields?: string[]
    inference_reason?: string | null
    inference_hint?: string | null
    // 同 priority 內的排序（越小越前）
    sort_order?: number | null
    // 有值代表已寫入行事曆，不再參與排程
    calendar_event_id?: string | null
    // 變成 Done 的時間，由後端寫入
    completed_at?: string | null
    // 階段任務：子任務有 parent_id、stage（從 1 開始），主任務有 is_parent 和 progress
    parent_id?: string | null
    stage?: number | null
    is_parent?: boolean
    progress?: { done: number; total: number } | null
}

// 對應後端 ManualTaskWithSubtasksOut：建立任務、新增子任務的回應
export interface TaskWithSubtasks extends Task {
    subtasks?: Task[]
    // AI 推斷的優先序被調成和前一個階段一樣的階段編號
    priority_adjusted_stages?: number[]
}
