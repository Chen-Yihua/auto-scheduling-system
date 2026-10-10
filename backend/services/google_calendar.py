"""以使用者為單位操作 Google Calendar，access_token 過期時自動換新重試。"""
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

# 夠短讓行事曆的變更很快反映，又能避免短時間內重複呼叫 Google API
FREE_SLOTS_CACHE_TTL_SECONDS = 60


async def _get_access_token_and_calendars(clerk_id: str) -> tuple[str, list[dict]]:
    """
    取得行事曆列表，401 時換新 token 重試。
    回傳的 access_token 可能已換新，呼叫端之後的請求要用它。
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
    """使用者的 Google 行事曆列表。"""
    _, calendars = await _get_access_token_and_calendars(clerk_id)
    return calendars


async def _get_access_token_and_primary_calendar_id(clerk_id: str) -> tuple[str, str]:
    access_token, calendars = await _get_access_token_and_calendars(clerk_id)

    primary = next((c for c in calendars if c.get("primary")), None)
    if not primary:
        raise HTTPException(status_code=404, detail="找不到 primary calendar")

    return access_token, primary["id"]


async def get_free_slots_for_user(clerk_id: str, use_cache: bool = True) -> list[dict]:
    """
    取得 primary calendar 未來 7 天的空檔（UTC ISO 字串）。

    use_cache=False：確認排程時要檢查此刻的行事曆，不能用快取，否則會漏掉剛新增的行程。
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
    把排程建議逐筆寫入 primary calendar，成功的任務記下 calendar_event_id。
    每筆獨立成功或失敗，回傳成功和失敗兩份清單，不因單筆失敗讓整批失敗。
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
