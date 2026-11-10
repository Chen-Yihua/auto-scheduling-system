from pydantic import BaseModel
from typing import Optional

class LinkedAccountCreate(BaseModel):
    platform: str
    status: str
    username: str
    password: Optional[str] = None
    apiKey: Optional[str] = None
    domain: Optional[str] = None

class LinkedAccountUpdate(BaseModel):
    status: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    apiKey: Optional[str] = None
    domain: Optional[str] = None

class LinkedAccountOut(BaseModel):
    id: str
    platform: str
    status: str
    username: str
    apiKey: Optional[str] = None
    avatar_url: Optional[str] = None
    domain: Optional[str] = None  # Jira 用
    password: Optional[str] = None  # Moodle 用，已遮罩
    # 回應時算出來的，不存進資料庫：已存的憑證解不開，要重新連結
    needs_reauth: bool = False
