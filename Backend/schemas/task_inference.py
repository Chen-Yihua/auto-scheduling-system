from typing import Literal
from pydantic import BaseModel


# 給 Gemini 的 response_schema 用：讓模型從源頭就照這個格式回傳，
# crud/task_inference.py 收到後仍會再驗證一次（schema 只是降低出錯機率，不是保證）
class TaskFieldInference(BaseModel):
    priority: Literal["High", "Medium", "Low"]
    duration_minutes: int
    reason: str
