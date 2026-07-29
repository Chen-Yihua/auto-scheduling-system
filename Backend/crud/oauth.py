from db.mongodb import db
from fastapi import HTTPException
from datetime import datetime
import os, httpx

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
        print("Google 回傳狀態碼", res.status_code)
        print("Google 回傳內容", res.text)  # << 加這行！
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
    print("成功refresh Google Token")
    return access_token