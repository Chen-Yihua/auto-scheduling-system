// 對應後端 JiraIssue；時間以外的欄位都保證有值（抓不到是空字串）
export interface JiraIssue {
    id: string
    key: string
    title: string
    status: string
    // ISO 8601（UTC）；Jira 沒給時是 null
    updated_at: string | null
    // 還沒解決的 issue 沒有解決時間
    resolved_at?: string | null
    assignee: string
    avatar: string
    type: string
    iconUrl: string
  }