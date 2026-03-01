from pydantic import BaseModel
from typing import Optional, List, Dict

class JiraUser(BaseModel):
    displayName: Optional[str]
    avatarUrls: Optional[Dict[str, str]]  # avatarUrls["48x48"] 可取頭像

class JiraStatus(BaseModel):
    name: Optional[str]

class JiraIssueType(BaseModel):
    name: Optional[str]
    iconUrl: Optional[str]

class JiraIssueFields(BaseModel):
    summary: str
    status: Optional[JiraStatus]
    assignee: Optional[JiraUser]
    issuetype: Optional[JiraIssueType]
    updated: Optional[str]  # 你也可以用 datetime

class JiraIssue(BaseModel):
    id: str
    key: str
    fields: JiraIssueFields
