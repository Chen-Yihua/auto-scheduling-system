// 對應後端 JiraIssue；每個欄位都保證有值（抓不到是空字串）
export interface JiraIssue {
    id: string
    key: string
    title: string
    status: string
    updated_at: string
    assignee: string
    avatar: string
    type: string
    iconUrl: string
  }