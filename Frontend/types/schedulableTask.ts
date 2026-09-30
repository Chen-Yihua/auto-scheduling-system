// 手動任務／GitHub issue／Jira issue／Moodle 作業統一後的格式，對應後端
// schemas/schedule.py 的 SchedulableTaskOut。id 是加了來源前綴的組合 id
// （例如 "manual:abc123"、"github:42"），source 用來決定顯示的圖示/連結行為。
export type SchedulableSource = 'manual' | 'github' | 'jira' | 'moodle'

export interface SchedulableTask {
  id: string
  source: SchedulableSource
  title: string
  // 只有手動任務有值，外部平台項目一律是 null
  description?: string | null
  status: string
  priority?: 'Low' | 'Medium' | 'High' | null
  duration?: number | null
  due_date?: string | null
  sort_order?: number | null
  calendar_event_id?: string | null
  url?: string | null
}
