from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

# 前端轉換後格式
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

# API 原始格式(原始格式可以拿來驗證)
class GitHubUserRaw(BaseModel):
    login: Optional[str]
    avatar_url: Optional[str]

class GitHubLabelRaw(BaseModel):
    name: str

class GitHubAPIRawItem(BaseModel):
    number: int
    title: str
    state: str
    created_at: datetime
    updated_at: Optional[datetime]
    html_url: str
    pull_request: Optional[dict]
    user: Optional[GitHubUserRaw]
    labels: Optional[List[GitHubLabelRaw]]
    comments: Optional[int]
