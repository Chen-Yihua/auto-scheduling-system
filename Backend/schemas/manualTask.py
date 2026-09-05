# schemas/manualTask.py

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
    user_id: str
    title: str
    description: str
    due_date: Optional[datetime] = None
    status: StatusEnum
    priority: Optional[PriorityEnum] = None  # 不確定就留空，由 LLM 幫忙推斷
    duration: Optional[int] = None  # 分鐘，不確定就留空，由 LLM 幫忙推斷

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
    inferred_fields: list[str] = []  # 哪些欄位是 LLM 幫忙推斷的，前端可以標示「AI 推斷」
    inference_reason: Optional[str] = None  # LLM 推斷的理由（只有真的推斷過才有值）
