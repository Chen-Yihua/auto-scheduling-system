from datetime import datetime
from typing import Optional

from pydantic import BaseModel

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
    # 最近一次成功同步的時間；同步用的其他內部欄位（鎖、開始時間、link_id 等）不回給前端
    last_synced_at: Optional[datetime] = None
