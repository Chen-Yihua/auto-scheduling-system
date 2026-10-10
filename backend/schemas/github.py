from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from schemas.manual_task import PriorityEnum

class GitHubAuthor(BaseModel):
    username: Optional[str]
    avatar: Optional[str]

class GitHubIssue(BaseModel):
    id: int  # 全域唯一
    number: int  # repo 內的編號，顯示用
    title: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    url: str
    isPR: bool
    author: Optional[GitHubAuthor]
    labels: Optional[List[str]]
    comments: Optional[int]
    # 以下是使用者設定的排程欄位，同步時不會被覆蓋
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    scheduling_due_date: Optional[datetime] = None
    sort_order: Optional[int] = None
    calendar_event_id: Optional[str] = None
    # 使用者手動標記完成，和 GitHub 的 open/closed 分開存
    done: bool = False
