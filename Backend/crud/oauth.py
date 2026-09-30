import logging
from db.mongodb import db
from fastapi import HTTPException
from datetime import datetime, timezone
import os, httpx
from pymongo.errors import PyMongoError
from services.google_calendar import (
    GOOGLE_HTTP_TIMEOUT,
    fetch_google_calendar_list,
    fetch_freebusy,
    compute_free_times,
    create_calendar_event,
)
from cache import cache_get, cache_set
from crud.schedulable_items import set_calendar_event_id_for_composite

logger = logging.getLogger(__name__)

# 空檔查詢的快取時間——短到使用者改了行事曆一分鐘內就能反映，
# 長到「打開排程頁又順手看一次可用時間」這種常見情境不用重複打兩次 Google API。
FREE_SLOTS_CACHE_TTL_SECONDS = 60

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


async def _get_access_token_and_primary_calendar_id(clerk_id: str) -> tuple[str, str]:
    """
    取得可用的 access_token 跟 primary calendar id，401 就自動 refresh token 重打一次。
    被 get_free_slots_for_user 跟 create_calendar_events_for_scheduled_tasks 共用。
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
    except httpx.RequestError as e:
        logger.error("連線 Google Calendar API 失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 Google，請稍後再試")

    primary = next((c for c in calendars if c.get("primary")), None)
    if not primary:
        raise HTTPException(status_code=404, detail="找不到 primary calendar")

    return access_token, primary["id"]


async def get_free_slots_for_user(clerk_id: str) -> list[dict]:
    """
    取得使用者 primary calendar 未來 7 天的空閒時段（UTC ISO 字串）。
    被 /oauth/available 跟排程建議（crud/schedule.py）共用，
    401 就自動 refresh token 重打一次，不用兩邊各寫一份。

    這裡是單純的效能快取（見 cache.py），不是失敗時的退路——跟
    crud/external_sync.py 那套「live-first + 失敗才退回 DB」是不同用途：
    這裡只要快取沒過期就直接用，減少重複打 Google API 的次數。
    """
    cache_key = f"free_slots:{clerk_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    access_token, primary_calendar_id = await _get_access_token_and_primary_calendar_id(clerk_id)

    try:
        fb_response = await fetch_freebusy(access_token, primary_calendar_id)
    except httpx.RequestError as e:
        logger.error("連線 Google FreeBusy API 失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 Google，請稍後再試")

    window_start = fb_response["timeMin"]
    window_end = fb_response["timeMax"]
    busy_list = fb_response["calendars"][primary_calendar_id]["busy"]
    free_slots = compute_free_times(busy_list, window_start, window_end)

    await cache_set(cache_key, free_slots, FREE_SLOTS_CACHE_TTL_SECONDS)
    return free_slots


async def create_calendar_events_for_scheduled_tasks(clerk_id: str, scheduled: list[dict]) -> dict:
    """
    使用者「確認排程」時呼叫：把排程建議裡「已排入時段」的任務，逐一寫進
    使用者 Google Calendar 的 primary calendar，當作一個事件。寫入成功的
    任務會把 calendar_event_id 存回去（見 crud/schedulable_items.py 的
    set_calendar_event_id_for_composite，依 task_id 的來源前綴寫回手動任務
    或對應的外部平台 collection）標記為已鎖定，之後不會再被排程建議或拖拉
    排序精靈動到，要改時間只能直接去 Google Calendar 改。

    scheduled 裡每一筆的 task_id/title 一定有值（build_schedule_suggestion
    已經驗證過），start/end 是 datetime 物件，這裡轉成 Google API 要的
    ISO 字串。

    Google API 這種第三方呼叫，一筆一筆各自獨立成功/失敗，不能因為某一筆
    炸了就讓整批都失敗，也不能靜靜吞掉失敗不讓使用者知道——回傳成功／
    失敗兩份清單，讓前端清楚呈現「這幾筆確認了、這幾筆要重試」。
    """
    if not scheduled:
        return {"confirmed": [], "failed": []}

    access_token, primary_calendar_id = await _get_access_token_and_primary_calendar_id(clerk_id)

    confirmed = []
    failed = []
    for task in scheduled:
        start_iso = task["start"].isoformat().replace("+00:00", "Z")
        end_iso = task["end"].isoformat().replace("+00:00", "Z")
        try:
            event = await create_calendar_event(
                access_token, primary_calendar_id, task["title"], start_iso, end_iso
            )
        except (httpx.HTTPStatusError, httpx.RequestError):
            logger.exception("寫入 Google Calendar 失敗 task_id=%s", task["task_id"])
            failed.append({
                "task_id": task["task_id"],
                "title": task["title"],
                "reason": "寫入 Google Calendar 失敗，請稍後再試",
            })
            continue

        await set_calendar_event_id_for_composite(clerk_id, task["task_id"], event["id"])
        confirmed.append({
            "task_id": task["task_id"],
            "title": task["title"],
            "calendar_event_id": event["id"],
        })

    return {"confirmed": confirmed, "failed": failed}
