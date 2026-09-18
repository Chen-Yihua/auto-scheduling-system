import logging
from fastapi import APIRouter, Depends, HTTPException, Response
from db.mongodb import db
from db.security import get_current_clerk_user
from db.crypto import decrypt_secret
from typing import List
from pymongo.errors import PyMongoError
from schemas.github import GitHubIssue
from crud.errors import NonRetryableError
from crud.github import fetch_github_user_issues, transform_github_item, sync_github_issues

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["github"])

# 即時抓 GitHub API；失敗時退回 DB 裡最後一次成功同步的資料（見 crud/external_sync.py）
@router.get("/issues", response_model=List[GitHubIssue])
async def get_github_issues(response: Response = None, clerk_user=Depends(get_current_clerk_user)):
    user_id = clerk_user["sub"]

    # 查詢綁定的 GitHub 帳號 (clerk_id + platform 這個組合保證唯一)
    try:
        linked = await db.linkedAccounts.find_one({
            "clerk_id": user_id,
            "platform": "github"
        })
    except PyMongoError as e:
        logger.error("DB error while fetching GitHub linked account: %s", e)
        raise HTTPException(status_code=503, detail="資料庫暫時無法使用，請稍後再試")

    if not linked or not linked.get("apiKey"):
        raise HTTPException(status_code=400, detail="No GitHub token linked")

    # 解密 token
    try:
        token = decrypt_secret(linked["apiKey"])
    except Exception:
        logger.exception("Failed to decrypt GitHub token for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="無法取得 GitHub 資料，請稍後再試")

    # 抓資料
    async def fetch():
        raw_items = await fetch_github_user_issues(token=token)
        return [transform_github_item(item) for item in raw_items]

    try:
        # stale, synced_at 決定要不要顯示「資料可能過期」的提示
        # auth_error 決定要不要顯示「請重新連結帳號」的提示
        issues, stale, synced_at, auth_error = await sync_github_issues(
            user_id=user_id,
            fetch_fn=fetch,
        )
    except NonRetryableError:
        logger.warning("GitHub token invalid/expired for user_id=%s", user_id)
        raise HTTPException(status_code=401, detail="GitHub 授權已失效，請重新連結帳號")
    except Exception:
        logger.exception("Failed to sync GitHub issues for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="無法取得 GitHub 資料，請稍後再試")

    if response is not None:
        response.headers["X-Data-Stale"] = str(stale).lower()
        if auth_error:
            response.headers["X-Auth-Error"] = "true"
        if synced_at:
            response.headers["X-Synced-At"] = synced_at.isoformat()
    return issues
