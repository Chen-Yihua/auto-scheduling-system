// 對應後端 schemas/jira.py 的 JiraIssue——後端已經把 Jira 原始 API 的巢狀結構
// 拉平成單層，這裡每個欄位後端都保證會給字串（抓不到就是空字串），不是 optional
export interface JiraIssue {
    id: string
    key: string
    summary: string
    status: string
    updated: string
    assignee: string
    avatar: string
    type: string
    iconUrl: string
  }