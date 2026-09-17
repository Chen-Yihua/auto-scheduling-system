from pydantic import BaseModel

# 前端顯示用格式（GET /jira/issues 的 response_model）——crud/jira.py 的
# transform_jira_item() 已經把 Jira 原始 API 那種多層巢狀結構（fields.status.name、
# fields.assignee.displayName 等）拉平成單層
class JiraIssue(BaseModel):
    id: str
    key: str
    summary: str
    status: str
    updated: str
    assignee: str
    avatar: str
    type: str
    iconUrl: str
