from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from schemas.manualTask import PriorityEnum


class ScheduledTask(BaseModel):
    task_id: str
    title: str
    priority: PriorityEnum
    start: datetime
    end: datetime


class UnscheduledTask(BaseModel):
    task_id: str
    title: str
    priority: PriorityEnum
    reason: str


class ScheduleSuggestion(BaseModel):
    scheduled: list[ScheduledTask]
    unscheduled: list[UnscheduledTask]


class ConfirmedTask(BaseModel):
    task_id: str
    title: str
    calendar_event_id: str


class FailedConfirmation(BaseModel):
    task_id: str
    title: str
    reason: str


class ScheduleConfirmResult(BaseModel):
    confirmed: list[ConfirmedTask]
    failed: list[FailedConfirmation]


class SchedulableTaskOut(BaseModel):
    """手動任務／GitHub issue／Jira issue／Moodle 作業統一後的格式，給前端的
    任務列表、排程精靈用。id 是加了來源前綴的組合 id
    （見 crud/schedulable_items.py），status 是 "To Do"／"In Progress"／"Done"
    （外部平台項目只會是前後兩者其中之一，手動任務三種都可能）。"""
    id: str
    source: str
    title: str
    # 只有手動任務有值——外部平台項目沒有對應欄位，前端顯示時這裡會是 None
    description: Optional[str] = None
    status: str
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    due_date: Optional[datetime] = None
    sort_order: Optional[int] = None
    calendar_event_id: Optional[str] = None
    url: Optional[str] = None


class ScheduleReorderItem(BaseModel):
    task_id: str  # 組合 id，例如 "manual:abc123"／"github:42"
    priority: PriorityEnum


class ScheduleReorderInput(BaseModel):
    # 使用者拖拉排序（三欄：低/中/高，可跨欄拖動，可能混著手動任務跟外部平台
    # 項目）後的最終結果，依序列出。每筆的索引就是它的 sort_order（0 開始）；
    # 不同來源、不同 priority 的項目混在同一個 list 裡沒關係，sort_order 只在
    # 同一個 priority 內比較，見 crud/schedule.py
    items: list[ScheduleReorderItem]


class ScheduleTaskFieldsUpdate(BaseModel):
    """排程精靈 step 2：使用者可以調整的欄位，留空就交給 LLM／保留原值。
    task_id 故意放在 body 而不是路徑參數——Moodle 的組合 id 是完整網址，
    本身就帶斜線和問號，直接放進 URL 路徑會被誤判成路徑分隔或查詢字串，
    放 body 完全不用處理任何 URL escape 問題。"""
    task_id: str
    due_date: Optional[datetime] = None
    duration: Optional[int] = None


class ScheduleTaskDoneUpdate(BaseModel):
    """理由同 ScheduleTaskFieldsUpdate，task_id 放 body。"""
    task_id: str
    done: bool


class BlockedRecurringRule(BaseModel):
    """每週固定不工作時段，例如「每天 22:00-08:00」「週六、週日全天」。
    days_of_week 用 Python datetime.weekday() 的編號：0=一...6=日。
    all_day 為 True 時忽略 start_time/end_time；start_time/end_time 是
    "HH:MM" 字串，end_time <= start_time 視為跨過午夜（例如 22:00-08:00）。"""
    days_of_week: list[int]
    all_day: bool = False
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class BlockedException(BaseModel):
    """這一輪排程額外加的一次性不工作時段，只影響這次的排程建議。"""
    start: datetime
    end: datetime


class SchedulePreferences(BaseModel):
    """使用者在排程精靈裡當場填的排程偏好，不會存進資料庫、只影響這一次
    /schedule/suggest、/schedule/confirm 的計算結果（見 AskUserQuestion
    紀錄：使用者選擇「每次精靈重新選」，不做成長期個人設定）。"""
    blocked_recurring: list[BlockedRecurringRule] = []
    blocked_exceptions: list[BlockedException] = []
    buffer_minutes: int = 0
    daily_max_minutes: Optional[int] = None
