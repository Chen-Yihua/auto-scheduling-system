from pydantic import BaseModel
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
