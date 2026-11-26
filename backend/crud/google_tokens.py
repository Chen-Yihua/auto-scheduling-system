"""使用者 Google Calendar 授權 token 的存取，token 一律加密後存入。"""
from datetime import datetime, timezone

from core.crypto import encrypt_secret, decrypt_secret
from core import database


async def save_google_calendar_token(clerk_id: str, access_token: str, refresh_token: str | None):
    doc = {
        "_id": clerk_id,
        "clerk_id": clerk_id,
        "access_token": encrypt_secret(access_token),
        "refresh_token": encrypt_secret(refresh_token) if refresh_token else None,
        "created_at": datetime.now(timezone.utc),
        "status": "connected",
    }
    await database.get_db().googleCalendarTokens.update_one({"_id": clerk_id}, {"$set": doc}, upsert=True)


async def update_google_calendar_token(clerk_id: str, access_token: str, refresh_token: str | None):
    await database.get_db().googleCalendarTokens.update_one(
        {"_id": clerk_id},
        {
            "$set": {
                "access_token": encrypt_secret(access_token),
                "refresh_token": encrypt_secret(refresh_token) if refresh_token else None,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


async def delete_google_calendar_token(clerk_id: str):
    await database.get_db().googleCalendarTokens.delete_one({"_id": clerk_id})


async def is_google_calendar_connected(clerk_id: str) -> bool:
    doc = await database.get_db().googleCalendarTokens.find_one({"_id": clerk_id})
    return bool(doc and doc.get("access_token"))


async def get_google_calendar_token(clerk_id: str) -> str | None:
    """解密後的 access_token；還沒連接時回傳 None。"""
    doc = await database.get_db().googleCalendarTokens.find_one({"_id": clerk_id})
    if not doc or not doc.get("access_token"):
        return None
    return decrypt_secret(doc["access_token"])


async def get_google_refresh_token(clerk_id: str) -> str | None:
    """解密後的 refresh_token；沒有時回傳 None。"""
    doc = await database.get_db().googleCalendarTokens.find_one({"_id": clerk_id})
    if not doc or not doc.get("refresh_token"):
        return None
    return decrypt_secret(doc["refresh_token"])
