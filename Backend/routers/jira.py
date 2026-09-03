from fastapi import APIRouter, Depends, HTTPException, Response
from db.mongodb import db  # 假設有 access linkedAccounts
from db.security import get_current_clerk_user
from db.crypto import decrypt_secret
from crud.jira import fetch_jira_user_issues
from crud.external_sync import sync_platform_items
from schemas.jira import JiraIssue

router = APIRouter(prefix="/jira", tags=["jira"])

# 即時抓 Jira API；失敗時退回 DB 裡最後一次成功同步的資料（見 crud/external_sync.py）
@router.get("/issues", response_model=list[JiraIssue])
async def get_jira_issues(response: Response = None, user=Depends(get_current_clerk_user)):
    # 從 MongoDB 查找 linkedAccount 中 Jira 的 API Key & Domain
    linked = await db.linkedAccounts.find_one({
        "clerk_id": user["sub"],
        "platform": "jira"
    })

    if not linked:
        raise HTTPException(status_code=400, detail="No Jira linked account")

    api_key = decrypt_secret(linked["apiKey"])
    domain = linked["domain"]

    try:
        issues, stale, synced_at = await sync_platform_items(
            collection=db.jira_issues,
            user_id=user["sub"],
            id_field="id",
            fetch_fn=lambda: fetch_jira_user_issues(api_key, domain),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if response is not None:
        response.headers["X-Data-Stale"] = str(stale).lower()
        if synced_at:
            response.headers["X-Synced-At"] = synced_at.isoformat()
    return issues
