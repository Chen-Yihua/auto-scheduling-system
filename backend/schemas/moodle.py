from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from schemas.manual_task import PriorityEnum

class MoodleAssignment(BaseModel):
    id: str  # 作業網址
    course_name: str
    title: str
    url: str
    due_date: str  # 爬到的原始文字，只供顯示；排程用 scheduling_due_date

    # 以下是使用者設定的排程欄位，同步時不會被覆蓋；爬不到提交狀態，done 只能手動標記
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    scheduling_due_date: Optional[datetime] = None
    sort_order: Optional[int] = None
    calendar_event_id: Optional[str] = None
    done: bool = False
