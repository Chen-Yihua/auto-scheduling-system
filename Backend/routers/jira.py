import logging
from fastapi import APIRouter, Depends, HTTPException, Response
from db.mongodb import db  # 假設有 access linkedAccounts
from db.security import get_current_clerk_user
from db.crypto import decrypt_secret
from pymongo.errors import PyMongoError
from crud.errors import NonRetryableError
from crud.jira import fetch_jira_user_issues, transform_jira_item
from crud.external_sync import sync_platform_items
from schemas.jira import JiraIssue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["jira"])

# 即時抓 Jira API；失敗時退回 DB 裡最後一次成功同步的資料（見 crud/external_sync.py）
@router.get("/issues", response_model=list[JiraIssue])
async def get_jira_issues(response: Response = None, user=Depends(get_current_clerk_user)):
    # 查找 Jira 的 API Key & Domain (clerk_id + platform 這個組合保證唯一)
    try:
        linked = await db.linkedAccounts.find_one({
            "clerk_id": user["sub"],
            "platform": "jira"
        })
    except PyMongoError as e:
        logger.error("DB error while fetching Jira linked account: %s", e)
        raise HTTPException(status_code=503, detail="資料庫暫時無法使用，請稍後再試")

    if not linked:
        raise HTTPException(status_code=400, detail="No Jira linked account")

    # 解密
    try:
        api_key = decrypt_secret(linked["apiKey"])
    except Exception:
        logger.exception("Failed to decrypt Jira API key for user_id=%s", user["sub"])
        raise HTTPException(status_code=500, detail="無法取得 Jira 資料，請稍後再試")
    domain = linked["domain"]

    # 抓資料
    async def fetch():
        raw_issues = await fetch_jira_user_issues(api_key, domain)
        return [transform_jira_item(issue) for issue in raw_issues]

    try:
        issues, stale, synced_at, auth_error = await sync_platform_items(
            collection=db.jira_issues,
            user_id=user["sub"],
            id_field="id",
            fetch_fn=fetch,
        )
    except NonRetryableError:
        logger.warning("Jira token invalid/expired for user_id=%s", user["sub"])
        raise HTTPException(status_code=401, detail="Jira 授權已失效，請重新連結帳號")
    except Exception:
        logger.exception("Failed to sync Jira issues for user_id=%s", user["sub"])
        raise HTTPException(status_code=500, detail="無法取得 Jira 資料，請稍後再試")

    if response is not None:
        response.headers["X-Data-Stale"] = str(stale).lower()
        if auth_error:
            response.headers["X-Auth-Error"] = "true"
        if synced_at:
            response.headers["X-Synced-At"] = synced_at.isoformat()
    return issues
