import logging
from fastapi import APIRouter, Depends, HTTPException, Response
from db.mongodb import db
from db.security import get_current_clerk_user
from db.crypto import decrypt_secret
from typing import List
from schemas.github import GitHubIssue
from crud.github import fetch_github_user_issues, transform_github_item
from crud.external_sync import sync_platform_items

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["github"])

# 即時抓 GitHub API；失敗時退回 DB 裡最後一次成功同步的資料（見 crud/external_sync.py）
@router.get("/issues", response_model=List[GitHubIssue])
async def get_github_issues(response: Response = None, clerk_user=Depends(get_current_clerk_user)):
    user_id = clerk_user["sub"]

    linked = await db.linkedAccounts.find_one({
        "clerk_id": user_id,
        "platform": "github"
    })

    if not linked or not linked.get("apiKey"):
        raise HTTPException(status_code=400, detail="No GitHub token linked")

    token = decrypt_secret(linked["apiKey"])

    async def fetch():
        raw_items = await fetch_github_user_issues(token=token)
        return [transform_github_item(item) for item in raw_items]

    try:
        issues, stale, synced_at = await sync_platform_items(
            collection=db.github_issues,
            user_id=user_id,
            id_field="id",
            fetch_fn=fetch,
        )
    except Exception:
        logger.exception("Failed to sync GitHub issues for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="無法取得 GitHub 資料，請稍後再試")

    if response is not None:
        response.headers["X-Data-Stale"] = str(stale).lower()
        if synced_at:
            response.headers["X-Synced-At"] = synced_at.isoformat()
    return issues
