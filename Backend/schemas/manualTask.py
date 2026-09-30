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
    # 使用者在排程精靈的拖拉排序畫面決定的順序（0 開始，數字越小排越前面）。
    # 只有做過拖拉排序才有值。排程時（crud/schedule.py）priority 仍然是主要
    # 排序依據，sort_order 只在「同一個 priority 內」當作誰先誰後的依據，
    # 取代原本用 due_date 當 tiebreaker 的退路。由 PUT /schedule/reorder 寫入
    # （見 schemas/schedule.py 的 ScheduleReorderInput，跨手動任務／外部平台
    # 項目統一處理，不是這個檔案自己的端點）。
    sort_order: Optional[int] = None
    # 使用者「確認排程」後，這筆任務被寫進 Google Calendar 的事件 id
    # （見 POST /schedule/confirm）。有值代表這筆任務已經鎖定：
    # 排程建議、拖拉排序精靈都會把它排除，不會再被重新排程或誤改，
    # 要改時間只能直接去 Google Calendar 改。
    calendar_event_id: Optional[str] = None
