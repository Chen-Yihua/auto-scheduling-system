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
    # user_id 不開放給 client 填——一律用登入者本人的 clerk_id（見 routers/manualTask.py
    # 的 create_manual_task），避免有人建立任務時冒充別人的 user_id
    title: str
    description: str
    due_date: Optional[datetime] = None
    status: StatusEnum
    priority: Optional[PriorityEnum] = None  # 不確定就留空，由 LLM 幫忙推斷
    duration: Optional[int] = None  # 分鐘，不確定就留空，由 LLM 幫忙推斷
    inference_hint: Optional[str] = None  # 給 LLM 推斷 priority/duration 時參考的提醒

class ManualTaskUpdate(BaseModel):
    """
    更新任務用的模型，欄位都可選（部分更新）。
    刻意不包含 user_id / id / created 等欄位——這些是任務的歸屬與身分，
    不該讓 client 透過更新請求竄改（否則能把任務轉移到別的帳號下）。
    """
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
    inferred_fields: list[str] = []  # 哪些欄位是 LLM 幫忙推斷的，前端可以標示「AI 推斷」
    inference_reason: Optional[str] = None  # LLM 推斷的理由（只有真的推斷過才有值）
    inference_hint: Optional[str] = None  # 使用者當初給 LLM 的提醒，留著讓之後編輯時看得到
