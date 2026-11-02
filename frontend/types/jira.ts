// 對應後端 JiraIssue；每個欄位都保證有值（抓不到是空字串）
export interface JiraIssue {
    id: string
    key: string
    title: string
    status: string
    updated_at: string
    // 只有這欄可能是 null：還沒解決的 issue 沒有解決時間
    resolved_at?: string | null
    assignee: string
    avatar: string
    type: string
    iconUrl: string
  }