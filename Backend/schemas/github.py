from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# 前端轉換後格式（GET /github/issues 的 response_model）
class GitHubAuthor(BaseModel):
    username: Optional[str]
    avatar: Optional[str]

class GitHubIssue(BaseModel):
    id: int
    title: str
    state: str
    created_at: datetime
    updated_at: Optional[datetime]
    url: str
    isPR: bool
    author: Optional[GitHubAuthor]
    labels: Optional[List[str]]
    comments: Optional[int]
