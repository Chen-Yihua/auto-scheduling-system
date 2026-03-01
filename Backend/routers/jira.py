from fastapi import APIRouter, Depends, HTTPException
from db.mongodb import db  # 假設有 access linkedAccounts
from db.security import get_current_clerk_user
from crud.jira import fetch_jira_user_issues
from schemas.jira import JiraIssue

router = APIRouter(prefix="/jira", tags=["jira"])

@router.get("/issues", response_model=list[JiraIssue])
async def get_jira_issues(user=Depends(get_current_clerk_user)):
    # 從 MongoDB 查找 linkedAccount 中 Jira 的 API Key & Domain
    linked = await db.linkedAccounts.find_one({
        "clerk_id": user["sub"],
        "platform": "jira"
    })

    if not linked:
        raise HTTPException(status_code=400, detail="No Jira linked account")

    api_key = linked["apiKey"]
    domain = linked["domain"]

    try:
        issues = await fetch_jira_user_issues(api_key, domain)
        return issues 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
