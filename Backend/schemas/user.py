# schemas/user.py

from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    clerk_id: str
    email: EmailStr
    name: str
    
#回傳給前端看的模型（把 _id 換成 id）
class UserOut(BaseModel):
    id:        str
    email:     EmailStr
    name:      str

# 更新使用者用的模型：欄位都可選（部分更新），且刻意不包含 clerk_id，
# 避免 client 竄改自己的 clerk_id（mass assignment）
class UserUpdate(BaseModel):
    name:  Optional[str] = None
    email: Optional[EmailStr] = None
class UserInDB(UserCreate):
    id: str  # MongoDB 的 ObjectId 被轉成字串後傳回

class UserPublic(BaseModel):
    id: str
    name: str
