from pydantic import BaseModel
from typing import Optional

class LinkedAccountCreate(BaseModel):
    platform: str
    status: str
    username: str
    password: Optional[str] = None
    apiKey: Optional[str] = None
    domain: Optional[str] = None

class LinkedAccountOut(BaseModel):
    id: str  # _id 轉成 id
    platform: str
    status: str
    username: str
    apiKey: Optional[str] = None
    avatar_url: Optional[str] = None
    domain: Optional[str] = None  # Jira 用
    password: Optional[str] = None  # Moodle 用，回傳前已遮罩
