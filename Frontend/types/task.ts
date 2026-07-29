export interface Task {
    id: string
    user_id: string
    title: string
    description: string
    priority: 'Low' | 'Medium' | 'High'
    status: string
    due_date: string
}
