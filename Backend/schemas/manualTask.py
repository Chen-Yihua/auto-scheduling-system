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
    priority: PriorityEnum

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
