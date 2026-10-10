// 對應後端 SchedulableTaskOut。id 是帶來源前綴的組合 id，例如 "github:42"
export type SchedulableSource = 'manual' | 'github' | 'jira' | 'moodle'

export interface SchedulableTask {
  id: string
  source: SchedulableSource
  title: string
  // 只有手動任務有值
  description?: string | null
  status: string
  priority?: 'Low' | 'Medium' | 'High' | null
  duration?: number | null
  due_date?: string | null
  sort_order?: number | null
  calendar_event_id?: string | null
  url?: string | null
}
