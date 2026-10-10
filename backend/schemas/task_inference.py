from typing import Literal
from pydantic import BaseModel


# Gemini 的 response_schema；模型不保證遵守，收到後仍要驗證
class TaskFieldInference(BaseModel):
    priority: Literal["High", "Medium", "Low"]
    duration_minutes: int
    reason: str
