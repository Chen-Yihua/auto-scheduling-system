from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from schemas.manual_task import PriorityEnum


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
    """手動任務和外部平台項目統一後的格式。id 是帶來源前綴的組合 id，例如 "github:42"。"""
    id: str
    source: str
    title: str
    # 只有手動任務有值
    description: Optional[str] = None
    status: str
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    due_date: Optional[datetime] = None
    sort_order: Optional[int] = None
    calendar_event_id: Optional[str] = None
    url: Optional[str] = None


class ScheduleReorderItem(BaseModel):
    task_id: str  # 組合 id
    priority: PriorityEnum


class ScheduleReorderInput(BaseModel):
    # 拖拉排序後的結果，索引即 sort_order；sort_order 只在同 priority 內比較
    items: list[ScheduleReorderItem]


class ScheduleTaskFieldsUpdate(BaseModel):
    """
    排程精靈中可調整的欄位，留空則保留原值。
    task_id 放 body 而不是路徑：Moodle 的 id 是含斜線和問號的網址。
    """
    task_id: str
    due_date: Optional[datetime] = None
    duration: Optional[int] = None


class ScheduleTaskDoneUpdate(BaseModel):
    """task_id 放 body 的原因同 ScheduleTaskFieldsUpdate。"""
    task_id: str
    done: bool


class BlockedRecurringRule(BaseModel):
    """
    每週固定的不工作時段。days_of_week 是 weekday() 編號（0=週一）。
    all_day 時忽略起訖時間；end_time <= start_time 視為跨午夜。
    """
    days_of_week: list[int]
    all_day: bool = False
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class BlockedException(BaseModel):
    """一次性的不工作時段。"""
    start: datetime
    end: datetime


class SchedulePreferences(BaseModel):
    """排程精靈中填的偏好，不存進資料庫，只影響這一次的計算。"""
    blocked_recurring: list[BlockedRecurringRule] = []
    blocked_exceptions: list[BlockedException] = []
    buffer_minutes: int = 0
    daily_max_minutes: Optional[int] = None
    # 瀏覽器提供的 IANA 時區；不工作時段和每日上限都以當地時間計算
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def _must_be_valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"不認得的時區：{value}")
        return value
