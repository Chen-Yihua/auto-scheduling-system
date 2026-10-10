from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from schemas.manual_task import PriorityEnum

class JiraIssue(BaseModel):
    id: str
    key: str
    title: str
    status: str
    # 判斷完成要用 status_category（new/indeterminate/done），status 是各專案自訂的字串
    status_category: str = ""
    updated_at: str
    assignee: str
    avatar: str
    type: str
    iconUrl: str
    # 以下是使用者設定的排程欄位，同步時不會被覆蓋
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    scheduling_due_date: Optional[datetime] = None
    sort_order: Optional[int] = None
    calendar_event_id: Optional[str] = None
    done: bool = False
