from pydantic import BaseModel

# crud/moodle.py fetch_assignments() 爬蟲爬出來的作業資料，對應 GET /moodle/assignments 的 response_model
class MoodleAssignment(BaseModel):
    id: str  # 用 assignment_url 當同步用的唯一 id，不是真正的資料庫 id
    course_name: str
    assignment_title: str
    assignment_url: str
    due_date: str  # 直接存爬到的文字，抓不到時是 "無截止日期"，不是實際日期物件
