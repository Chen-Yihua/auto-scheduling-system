from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime

class StatusEnum(str, Enum):
    todo = "To Do"
    in_progress = "In Progress"
    done = "Done"

class PriorityEnum(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"

class ManualTaskInput(BaseModel):
    # 沒有 user_id：一律用登入者的 clerk_id，避免冒充別人建立任務
    title: str
    description: str
    due_date: Optional[datetime] = None
    status: StatusEnum
    priority: Optional[PriorityEnum] = None  # 留空由 LLM 推斷
    duration: Optional[int] = None  # 分鐘，留空由 LLM 推斷
    inference_hint: Optional[str] = None  # 給 LLM 推斷時參考

class ManualTaskUpdate(BaseModel):
    """部分更新。刻意不含 user_id、id、created，避免 client 把任務轉到別的帳號。"""
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[StatusEnum] = None
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    inference_hint: Optional[str] = None

class ManualTaskOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    due_date: Optional[datetime] = None
    created: datetime
    updated: datetime
    status: StatusEnum
    priority: PriorityEnum
    duration: int = 60  # 分鐘
    inferred_fields: list[str] = []  # 由 LLM 推斷的欄位
    inference_reason: Optional[str] = None
    inference_hint: Optional[str] = None
    # 同 priority 內的排序（越小越前），由 PUT /schedule/reorder 寫入
    sort_order: Optional[int] = None
    # 確認排程後寫入的 Google Calendar 事件 id；有值的任務不再參與排程
    calendar_event_id: Optional[str] = None
