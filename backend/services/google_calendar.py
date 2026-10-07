"""
以使用者為單位操作 Google Calendar：自動處理 token（過期就換新再重打一次），
再呼叫 services/google_calendar_client.py 的 Google API。
"""
import logging

import httpx
from fastapi import HTTPException

from core.cache import cache_get, cache_set
from crud.google_tokens import get_google_calendar_token, refresh_google_calendar_token
from crud.schedulable_items import set_calendar_event_id_for_composite
from services.google_calendar_client import (
    fetch_google_calendar_list,
    fetch_freebusy,
    compute_free_times,
    create_calendar_event,
)

logger = logging.getLogger(__name__)

# 空檔查詢的快取時間——短到使用者改了行事曆一分鐘內就能反映，
# 長到「打開排程頁又順手看一次可用時間」這種常見情境不用重複打兩次 Google API。
FREE_SLOTS_CACHE_TTL_SECONDS = 60


async def _get_access_token_and_calendars(clerk_id: str) -> tuple[str, list[dict]]:
    """
    取得可用的 access_token 跟使用者的行事曆列表，401 就自動 refresh token 重打一次。
    回傳的 access_token 是換新後的那個，呼叫端接著打其他 Google API 時要用它。
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

    return access_token, calendars


async def list_calendars_for_user(clerk_id: str) -> list[dict]:
    """使用者的 Google 行事曆列表（給 /oauth/calendars）。"""
    _, calendars = await _get_access_token_and_calendars(clerk_id)
    return calendars


async def _get_access_token_and_primary_calendar_id(clerk_id: str) -> tuple[str, str]:
    """被 get_free_slots_for_user 跟 create_calendar_events_for_scheduled_tasks 共用。"""
    access_token, calendars = await _get_access_token_and_calendars(clerk_id)

    primary = next((c for c in calendars if c.get("primary")), None)
    if not primary:
        raise HTTPException(status_code=404, detail="找不到 primary calendar")

    return access_token, primary["id"]


async def get_free_slots_for_user(clerk_id: str, use_cache: bool = True) -> list[dict]:
    """
    取得使用者 primary calendar 未來 7 天的空閒時段（UTC ISO 字串）。
    被排程建議（services/scheduler.py）共用，
    401 就自動 refresh token 重打一次，不用兩邊各寫一份。

    這裡是單純的效能快取（見 core/cache.py），不是失敗時的退路——跟
    platforms/sync.py 那套「live-first + 失敗才退回 DB」是不同用途：
    這裡只要快取沒過期就直接用，減少重複打 Google API 的次數。

    use_cache=False：確認排程寫入前，要用「此刻」真正的行事曆檢查時段是否
    還空著，不能用最多 60 秒前的快取——那 60 秒內新增的行程會檢查不到。
    """
    cache_key = f"free_slots:{clerk_id}"
    if use_cache:
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
