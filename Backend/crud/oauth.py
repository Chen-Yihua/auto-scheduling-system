import logging
from db.mongodb import db
from fastapi import HTTPException
from datetime import datetime
import os, httpx
from services.google_calendar import (
    fetch_google_calendar_list,
    fetch_freebusy,
    compute_free_times,
)

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
        "created_at": datetime.utcnow(),
        "status": "connected",
    }
    await db.googleCalendarTokens.update_one({"_id": clerk_id}, {"$set": doc}, upsert=True)
    return {"message": "Google Token 儲存成功"}

# 取得 token
async def get_google_calendar_token(clerk_id: str) -> str:
    doc = await db.googleCalendarTokens.find_one({"_id": clerk_id})
    if not doc or not doc.get("access_token"):
        raise HTTPException(status_code=401, detail="尚未連接 Google Calendar")
    return doc["access_token"]

async def refresh_google_calendar_token(clerk_id: str) -> str:
    """
    用存在 DB 的 refresh_token 去 Google 換新 access_token，
    並把新的 token 寫回 DB。最後回傳新的 access_token。
    """
    # 1. 先從 DB 拿 refresh_token
    doc = await db.googleCalendarTokens.find_one({"_id": clerk_id})
    if not doc or not doc.get("refresh_token"):
        raise HTTPException(status_code=401, detail="沒有可用的 Refresh Token，請重新授權")
    refresh_token = doc["refresh_token"]

    # 2. Call Google Token Endpoint
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(token_url, data=payload)
        logger.debug("Google token refresh response status=%s", res.status_code)
        if res.status_code != 200:
            # 失敗回應是 Google 的錯誤代碼/描述，不含 token，可以安全記錄方便除錯
            logger.warning("Google token refresh failed: %s", res.text)
        res.raise_for_status()
        token_data = res.json()

    # 3. 擷取新的 access_token（與可能新的 refresh_token）
    access_token  = token_data.get("access_token")
    new_rt        = token_data.get("refresh_token", refresh_token)

    if not access_token:
        raise HTTPException(status_code=400, detail="Google 刷新 Token 失敗")

    # 4. 把新的 Token 寫回 DB
    await db.googleCalendarTokens.update_one(
        {"_id": clerk_id},
        {
            "$set": {
                "access_token":  access_token,
                "refresh_token": new_rt,
                "updated_at":    datetime.utcnow()
            }
        }
    )
    logger.info("Refreshed Google Calendar token for clerk_id=%s", clerk_id)
    return access_token


async def get_free_slots_for_user(clerk_id: str) -> list[dict]:
    """
    取得使用者 primary calendar 未來 7 天的空閒時段（UTC ISO 字串）。
    被 /oauth/available 跟排程建議（crud/schedule.py）共用，
    401 就自動 refresh token 重打一次，不用兩邊各寫一份。
    """
    access_token = await get_google_calendar_token(clerk_id)

    try:
        calendars = await fetch_google_calendar_list(access_token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            access_token = await refresh_google_calendar_token(clerk_id)
            calendars = await fetch_google_calendar_list(access_token)
        else:
            raise HTTPException(status_code=400, detail="取得行事曆列表失敗")

    primary = next((c for c in calendars if c.get("primary")), None)
    if not primary:
        raise HTTPException(status_code=404, detail="找不到 primary calendar")

    fb_response = await fetch_freebusy(access_token, primary["id"])

    window_start = fb_response["timeMin"]
    window_end = fb_response["timeMax"]
    busy_list = fb_response["calendars"][primary["id"]]["busy"]
    return compute_free_times(busy_list, window_start, window_end)
