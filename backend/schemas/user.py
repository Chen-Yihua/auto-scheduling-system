from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    clerk_id: str
    email: EmailStr
    name: str

class UserOut(BaseModel):
    id:        str
    email:     EmailStr
    name:      str

# 刻意不含 clerk_id，避免 client 竄改
class UserUpdate(BaseModel):
    name:  Optional[str] = None
    email: Optional[EmailStr] = None
