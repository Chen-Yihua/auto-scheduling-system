from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from schemas.manual_task import PriorityEnum

# 前端顯示用格式（GET /jira/issues 的 response_model）——platforms/jira.py 的
# transform_jira_item() 已經把 Jira 原始 API 那種多層巢狀結構（fields.status.name、
# fields.assignee.displayName 等）拉平成單層
class JiraIssue(BaseModel):
    id: str
    key: str
    title: str
    status: str
    # status.name 是專案自訂的字串（"Done"、"已完成"、"Closed" 都有可能），
    # 沒辦法直接拿來判斷「這張是不是完成了」；status_category 是 Jira 自己
    # 正規化過的三選一："new"／"indeterminate"／"done"，才是可靠的完成判斷依據
    status_category: str = ""
    updated_at: str
    assignee: str
    avatar: str
    type: str
    iconUrl: str
    # 排程相關欄位，見 schemas/github.py 同樣的說明
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    scheduling_due_date: Optional[datetime] = None
    sort_order: Optional[int] = None
    calendar_event_id: Optional[str] = None
    done: bool = False
