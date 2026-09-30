from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from schemas.manualTask import PriorityEnum

# 前端轉換後格式（GET /github/issues 的 response_model）
class GitHubAuthor(BaseModel):
    username: Optional[str]
    avatar: Optional[str]

class GitHubIssue(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    url: str
    isPR: bool
    author: Optional[GitHubAuthor]
    labels: Optional[List[str]]
    comments: Optional[int]
    # 排程相關欄位：跟同步回來的 GitHub 原始資料無關，是使用者在排程精靈裡
    # 額外指定的。sync_platform_items 用 $set 更新，不會動到這些欄位，
    # 重新同步不會把它們洗掉。見 crud/schedulable_items.py
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    scheduling_due_date: Optional[datetime] = None
    sort_order: Optional[int] = None
    calendar_event_id: Optional[str] = None
    # 使用者在 App 內手動標記完成——跟 GitHub 自己的 open/closed 狀態分開，
    # 兩者只要有一個成立就視為已完成，不再出現在排程建議裡
    done: bool = False
