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

// 對應後端 PriorityAdjustment：一個 AI 推斷的優先序被自動調整的階段
export interface PriorityAdjustment {
    subtask_id: string
    // AI 原本推斷的值
    from_priority: 'Low' | 'Medium' | 'High'
    // 調整後的值，等於比較的階段當時的值
    to_priority: 'Low' | 'Medium' | 'High'
    // 被調低時是前一個階段；被調高時是後面不是 AI 推斷的階段裡最高的那個（同樣高取最前面）
    compared_subtask_id: string
}

// 對應後端 ManualTaskWithSubtasksOut：建立任務、新增子任務的回應
export interface TaskWithSubtasks extends Task {
    subtasks?: Task[]
    // AI 推斷的優先序比前一個階段高會被調低、比後面的階段低會被調高，每個被調整的階段一筆；
    // 一次建立是這次建立的、新增單一階段是這次新增的，同一個 Idempotency-Key 重送時也相同
    priority_adjustments?: PriorityAdjustment[]
}
