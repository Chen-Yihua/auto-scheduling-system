from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from schemas.manual_task import PriorityEnum

# platforms/moodle.py fetch_assignments() 爬蟲爬出來的作業資料，對應 GET /moodle/assignments 的 response_model
class MoodleAssignment(BaseModel):
    id: str  # 用 url 當同步用的唯一 id，不是真正的資料庫 id
    course_name: str
    title: str
    url: str
    due_date: str  # 直接存爬到的文字，抓不到時是 "無截止日期"，不是實際日期物件；
    # 純顯示用，格式不固定、不保證能解析，排程要用 scheduling_due_date

    # 排程相關欄位，見 schemas/github.py 同樣的說明。Moodle 爬蟲抓不到「這份作業
    # 交了沒」，done 完全只能靠使用者自己在 App 裡標記，沒有平台狀態可以參考
    priority: Optional[PriorityEnum] = None
    duration: Optional[int] = None
    scheduling_due_date: Optional[datetime] = None
    sort_order: Optional[int] = None
    calendar_event_id: Optional[str] = None
    done: bool = False
