from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel
from schemas.manual_task import PriorityEnum


class SourceStat(BaseModel):
    source: str
    total: int
    done: int


class PriorityStat(BaseModel):
    # None 是外部平台還沒設定優先度的項目
    priority: Optional[PriorityEnum]
    total: int
    done: int


class WeeklyCompletion(BaseModel):
    week_start: date  # 使用者時區的週一
    completed: int
    completed_minutes: int


class OnTimeStat(BaseModel):
    """統計週數內完成、而且有截止日的項目。"""
    completed_with_due: int
    on_time: int
    rate: Optional[float]


class ProductivitySummary(BaseModel):
    generated_at: datetime  # UTC
    total: int
    done: int
    # 0 到 1；沒有任何項目時是 None，和完成率 0% 區分
    completion_rate: Optional[float]
    overdue: int
    # 預估工時（分鐘），沒有 duration 的項目不計入
    done_minutes: int
    remaining_minutes: int
    unestimated_remaining: int
    # 開始記錄完成時間前就完成的項目，不在週趨勢和準時率裡
    untracked_done: int
    by_source: list[SourceStat]
    by_priority: list[PriorityStat]
    weekly: list[WeeklyCompletion]
    on_time: OnTimeStat
