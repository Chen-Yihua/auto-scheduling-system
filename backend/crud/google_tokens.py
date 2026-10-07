"""使用者 Google Calendar 授權 token 的存取與換新。"""
import logging
from core.database import db
from fastapi import HTTPException
from datetime import datetime, timezone
import os, httpx
from pymongo.errors import PyMongoError
from services.google_calendar_client import GOOGLE_HTTP_TIMEOUT

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# 儲存使用者 Google Token
async def save_google_calendar_token(clerk_id: str, access_token: str, refresh_token: str | None):
    doc = {
        "_id": clerk_id,
        "clerk_id": clerk_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "created_at": datetime.now(timezone.utc),
        "status": "connected",
    }
    await db.googleCalendarTokens.update_one({"_id": clerk_id}, {"$set": doc}, upsert=True)
    return {"message": "Google Token 儲存成功"}

# 只查 DB、不打 Google API 的輕量檢查，給前端在真的呼叫 /oauth/calendars
# 之前先確認「有沒有連接過」，跟 github/jira/moodle 各自的 linked-accounts
# 檢查一樣，避免還沒授權就白打一次注定失敗的 Google API 請求
async def is_google_calendar_connected(clerk_id: str) -> bool:
    doc = await db.googleCalendarTokens.find_one({"_id": clerk_id})
    return bool(doc and doc.get("access_token"))

# 取得 token
async def get_google_calendar_token(clerk_id: str) -> str:
    doc = await db.googleCalendarTokens.find_one({"_id": clerk_id})
    if not doc or not doc.get("access_token"):
        # 400（尚未設定）跟 401（憑證失效，需要重新授權）分開，
        # 跟 github.py/jira.py「尚未連結帳號」統一用 400 的慣例對齊，
        # 前端才能區分「本來就沒接」跟「接過但失效了」兩種情況
        raise HTTPException(status_code=400, detail="尚未連接 Google Calendar")
    return doc["access_token"]

async def refresh_google_calendar_token(clerk_id: str) -> str:
    """
    用存在 DB 的 refresh_token 去 Google 換新 access_token，
    並把新的 token 寫回 DB。最後回傳新的 access_token。
    """
    # 從 DB 拿 refresh_token
    doc = await db.googleCalendarTokens.find_one({"_id": clerk_id})
    if not doc or not doc.get("refresh_token"):
        raise HTTPException(status_code=401, detail="沒有可用的 Refresh Token，請重新授權")
    refresh_token = doc["refresh_token"]

    # Call Google Token Endpoint
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        async with httpx.AsyncClient(timeout=GOOGLE_HTTP_TIMEOUT) as client:
            res = await client.post(token_url, data=payload)
            logger.debug("Google token refresh response status=%s", res.status_code)
            if res.status_code != 200:
                # 失敗回應是 Google 的錯誤代碼/描述，不含 token，可以安全記錄方便除錯
                logger.warning("Google token refresh failed: %s", res.text)
            res.raise_for_status()
            token_data = res.json()
    except httpx.RequestError as e:
        logger.error("連線 Google Token Endpoint 失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 Google，請稍後再試")
    except httpx.HTTPStatusError as e:
        # Google 拒絕這個 refresh_token 本身（例如使用者在 Google 那邊撤銷了授權，
        # 或者 OAuth 同意畫面還在 Testing 狀態時，refresh token 7 天後會自動失效）。
        # 這種情況換不到新 token 也沒有意義再留著舊的，清掉讓 /oauth/status
        # 正確回報「尚未連接」，使用者才會看到清楚的「請重新連接」而不是卡住
        logger.warning("Google refresh token 已失效: %s", e.response.text)
        try:
            await db.googleCalendarTokens.delete_one({"_id": clerk_id})
        except PyMongoError:
            logger.exception("清除失效的 Google Calendar token 失敗")
        raise HTTPException(status_code=401, detail="Google 授權已失效，請重新連接 Google Calendar")

    # 擷取新的 access_token（與可能新的 refresh_token）
    access_token  = token_data.get("access_token")
    new_rt        = token_data.get("refresh_token", refresh_token)

    if not access_token:
        raise HTTPException(status_code=400, detail="Google 刷新 Token 失敗")

    # 把新的 Token 寫回 DB
    await db.googleCalendarTokens.update_one(
        {"_id": clerk_id},
        {
            "$set": {
                "access_token":  access_token,
                "refresh_token": new_rt,
                "updated_at":    datetime.now(timezone.utc)
            }
        }
    )
    logger.info("Refreshed Google Calendar token for clerk_id=%s", clerk_id)
    return access_token
