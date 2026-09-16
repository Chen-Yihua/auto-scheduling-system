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
}
