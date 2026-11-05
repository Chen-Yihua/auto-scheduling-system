from pydantic import BaseModel, Field, field_validator, model_validator
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

MAX_SUBTASKS = 10


class SubtaskInput(BaseModel):
    """子任務的欄位，和一般任務相同；優先序、時長留空由 LLM 推斷。"""
    title: str
    description: str = ""
    due_date: Optional[datetime] = None
    status: StatusEnum = StatusEnum.todo
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    inference_hint: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("子任務要有標題")
        return value


class SubtaskCreate(SubtaskInput):
    # 1～N+1，留空放在最後
    position: Optional[int] = Field(default=None, ge=1)


class ManualTaskInput(BaseModel):
    # 沒有 user_id：一律用登入者的 clerk_id，避免冒充別人建立任務
    title: str
    description: str
    due_date: Optional[datetime] = None
    # 一般任務必填；帶 subtasks 時是主任務，狀態依子任務計算，不能帶
    status: Optional[StatusEnum] = None
    priority: Optional[PriorityEnum] = None  # 留空由 LLM 推斷
    duration: Optional[int] = None  # 分鐘，留空由 LLM 推斷
    inference_hint: Optional[str] = None  # 給 LLM 推斷時參考
    # 依順序成為階段 1～N
    subtasks: Optional[list[SubtaskInput]] = Field(default=None, min_length=1, max_length=MAX_SUBTASKS)

    @model_validator(mode="after")
    def _status_required_without_subtasks(self):
        if self.subtasks is None and self.status is None:
            raise ValueError("status 為必填")
        return self

class ManualTaskUpdate(BaseModel):
    """部分更新。刻意不含 user_id、id、created，避免 client 把任務轉到別的帳號。"""
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[StatusEnum] = None
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    inference_hint: Optional[str] = None

class SubtaskProgress(BaseModel):
    done: int
    total: int


class ManualTaskOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    due_date: Optional[datetime] = None
    created: datetime
    updated: datetime
    # 主任務的狀態在讀取時依子任務計算
    status: StatusEnum
    # 主任務沒有優先序和時長
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = 60  # 分鐘
    inferred_fields: list[str] = []  # 由 LLM 推斷的欄位
    inference_reason: Optional[str] = None
    inference_hint: Optional[str] = None
    # 同 priority 內的排序（越小越前），由 PUT /schedule/reorder 寫入
    sort_order: Optional[int] = None
    # 確認排程後寫入的 Google Calendar 事件 id；有值的任務不再參與排程
    calendar_event_id: Optional[str] = None
    # 變成 Done 的時間，由後端在狀態改變時寫入；ManualTaskUpdate 不含這欄，避免 client 竄改統計
    completed_at: Optional[datetime] = None
    # 階段任務：子任務有 parent_id、stage（從 1 開始），主任務有 is_parent；只由後端寫入
    parent_id: Optional[str] = None
    stage: Optional[int] = None
    is_parent: bool = False
    # 只有主任務有，讀取時計算
    progress: Optional[SubtaskProgress] = None


class ManualTaskWithSubtasksOut(ManualTaskOut):
    """建立任務、新增子任務的回應：主任務附上依階段排序的子任務。"""
    subtasks: list[ManualTaskOut] = []
    # AI 推斷的優先序比前一個階段高、被調成和前一個階段一樣的階段編號；只在這次回應裡，不存資料庫
    priority_adjusted_stages: list[int] = []
