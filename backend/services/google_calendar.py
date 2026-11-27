"""以使用者為單位操作 Google Calendar，access_token 過期時自動換新重試。"""
import logging
from datetime import datetime

import httpx
from core.errors import AppError, ExternalServiceError, InvalidRequestError, ReauthRequiredError, request_error_code

from core.cache import cache_get, cache_set
from core.crypto import SecretDecryptError
from core.datetimes import to_utc_datetime
from crud.google_tokens import get_google_calendar_token, is_google_calendar_connected
from services.google_errors import google_detail, google_error_code, rate_limit_headers
from services.google_oauth import GOOGLE_REAUTH_DETAIL, refresh_google_calendar_token
from crud.schedulable_items import set_calendar_event_id_for_composite
from services.google_calendar_client import (
    fetch_google_calendar_list,
    fetch_freebusy,
    compute_free_times,
    create_calendar_event,
    delete_calendar_event,
    get_calendar_event,
)

logger = logging.getLogger(__name__)

# 夠短讓行事曆的變更很快反映，又能避免短時間內重複呼叫 Google API
FREE_SLOTS_CACHE_TTL_SECONDS = 60

PREVIOUS_STAGE_WRITE_FAILED = "前一個階段寫入失敗"
DELETE_RETRY_DETAIL = "刪除 Google Calendar 事件失敗，請稍後重試"

# 事件已經不存在
_EVENT_GONE_STATUSES = {404, 410}


def _google_error(e: httpx.HTTPStatusError, detail: str) -> AppError:
    """依 Google 的原因給 error_code。detail 是無法判斷原因的 4xx 用的說明。"""
    status = e.response.status_code
    logger.warning("Google Calendar API 回應錯誤: %s %s", status, e.response.text)
    error_code = google_error_code(e.response)
    headers = rate_limit_headers(e.response)
    message = detail if error_code == "UPSTREAM_ERROR" and 400 <= status < 500 else google_detail(error_code)
    return AppError(message, error_code=error_code, headers=headers)


def _unreachable(e: httpx.RequestError, log_message: str, detail: str | None = None) -> ExternalServiceError:
    logger.error("%s: %s", log_message, e)
    error_code = request_error_code(e)
    return ExternalServiceError(detail or google_detail(error_code), error_code=error_code)


async def _fetch_calendar_list_after_refresh(access_token: str) -> list[dict]:
    """換新 token 後仍回 401，代表授權本身不能用，再換也沒用，要請使用者重新連接。"""
    try:
        return await fetch_google_calendar_list(access_token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.warning("換新 token 後 Google Calendar 仍回 401: %s", e.response.text)
            raise ReauthRequiredError(GOOGLE_REAUTH_DETAIL)
        raise _google_error(e, "取得行事曆列表失敗")
    except httpx.RequestError as e:
        raise _unreachable(e, "換新 token 後連線 Google Calendar API 失敗")


async def _get_access_token_and_calendars(clerk_id: str) -> tuple[str, list[dict]]:
    """
    取得行事曆列表，401 時換新 token 重試。
    回傳的 access_token 可能已換新，呼叫端之後的請求要用它。
    """
    try:
        access_token = await get_google_calendar_token(clerk_id)
    except SecretDecryptError:
        # 不刪 token：正式和開發環境共用 DB，可能是另一個環境用它自己的金鑰加密的
        logger.warning("Google access token 解密失敗 clerk_id=%s", clerk_id)
        raise ReauthRequiredError(GOOGLE_REAUTH_DETAIL)
    if not access_token:
        raise InvalidRequestError("尚未連接 Google Calendar", error_code="NOT_LINKED")

    try:
        calendars = await fetch_google_calendar_list(access_token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            access_token = await refresh_google_calendar_token(clerk_id)
            calendars = await _fetch_calendar_list_after_refresh(access_token)
        else:
            raise _google_error(e, "取得行事曆列表失敗")
    except httpx.RequestError as e:
        raise _unreachable(e, "連線 Google Calendar API 失敗")

    return access_token, calendars


async def list_calendars_for_user(clerk_id: str) -> list[dict]:
    """使用者的 Google 行事曆列表。"""
    _, calendars = await _get_access_token_and_calendars(clerk_id)
    return calendars


async def _get_access_token_and_primary_calendar_id(clerk_id: str) -> tuple[str, str]:
    access_token, calendars = await _get_access_token_and_calendars(clerk_id)

    primary = next((c for c in calendars if c.get("primary")), None)
    if not primary:
        logger.warning("Google 行事曆列表沒有 primary calendar clerk_id=%s", clerk_id)
        raise ExternalServiceError("找不到 Google 的主要行事曆（primary calendar）")

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
    except httpx.HTTPStatusError as e:
        raise _google_error(e, "取得行事曆空檔失敗")
    except httpx.RequestError as e:
        raise _unreachable(e, "連線 Google FreeBusy API 失敗")

    window_start = fb_response["timeMin"]
    window_end = fb_response["timeMax"]
    busy_list = fb_response["calendars"][primary_calendar_id]["busy"]
    free_slots = compute_free_times(busy_list, window_start, window_end)

    await cache_set(cache_key, free_slots, FREE_SLOTS_CACHE_TTL_SECONDS)
    return free_slots


def _write_failure(e: httpx.HTTPStatusError | httpx.RequestError) -> tuple[str, str]:
    """
    寫入事件失敗的 (error_code, reason)，分類同其他 Google 請求。
    401 直接要求重新連接：寫入迴圈開始前剛驗證或換過 token，再換也沒用。
    """
    if isinstance(e, httpx.RequestError):
        error_code = request_error_code(e)
        return error_code, google_detail(error_code)
    if e.response.status_code == 401:
        return "REAUTH_REQUIRED", GOOGLE_REAUTH_DETAIL
    error_code = google_error_code(e.response)
    return error_code, google_detail(error_code)


async def create_calendar_events_for_scheduled_tasks(clerk_id: str, scheduled: list[dict]) -> dict:
    """
    把排程建議逐筆寫入 primary calendar，成功的任務記下 calendar_event_id 與時段。
    每筆獨立成功或失敗，回傳成功和失敗兩份清單，不因單筆失敗讓整批失敗。
    """
    if not scheduled:
        return {"confirmed": [], "failed": []}

    access_token, primary_calendar_id = await _get_access_token_and_primary_calendar_id(clerk_id)

    confirmed = []
    failed = []
    failed_ids = set()
    for task in scheduled:
        if task.get("previous_task_id") in failed_ids:
            failed_ids.add(task["task_id"])
            failed.append({
                "task_id": task["task_id"], "title": task["title"], "reason": PREVIOUS_STAGE_WRITE_FAILED, "error_code": None,
            })
            continue
        start_iso = task["start"].isoformat().replace("+00:00", "Z")
        end_iso = task["end"].isoformat().replace("+00:00", "Z")
        try:
            event = await create_calendar_event(
                access_token, primary_calendar_id, task["title"], start_iso, end_iso
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.exception("寫入 Google Calendar 失敗 task_id=%s", task["task_id"])
            error_code, reason = _write_failure(e)
            failed_ids.add(task["task_id"])
            failed.append({"task_id": task["task_id"], "title": task["title"], "reason": reason, "error_code": error_code})
            continue

        await set_calendar_event_id_for_composite(clerk_id, task["task_id"], event["id"], task["start"], task["end"])
        confirmed.append({
            "task_id": task["task_id"],
            "title": task["title"],
            "calendar_event_id": event["id"],
        })

    return {"confirmed": confirmed, "failed": failed}


def _parse_event_time(value: dict | None) -> datetime | None:
    return to_utc_datetime((value or {}).get("dateTime"))


async def _get_event_unless_removed(access_token: str, calendar_id: str, event_id: str) -> dict | None:
    """事件已被刪除（Google 回 404 / 410，或狀態是 cancelled）時回 None；其他錯誤原樣丟出 httpx 的例外。"""
    try:
        event = await get_calendar_event(access_token, calendar_id, event_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in _EVENT_GONE_STATUSES:
            return None
        raise
    return None if event.get("status") == "cancelled" else event


async def get_calendar_event_ends(clerk_id: str, event_ids: list[str]) -> dict[str, datetime | None]:
    """
    事件在 Google 上最新的結束時間（使用者可能在 Google 上拖動過）。
    事件已不存在（404 / 410 或已取消）時是 None。
    """
    if not event_ids:
        return {}
    access_token, calendar_id = await _get_access_token_and_primary_calendar_id(clerk_id)

    ends: dict[str, datetime | None] = {}
    for event_id in event_ids:
        try:
            event = await _get_event_unless_removed(access_token, calendar_id, event_id)
        except httpx.HTTPStatusError as e:
            raise _google_error(e, "取得行事曆事件失敗")
        except httpx.RequestError as e:
            raise _unreachable(e, "連線 Google Calendar API 失敗")
        ends[event_id] = _parse_event_time(event.get("end")) if event else None
    return ends


def _event_lookup_error(e: httpx.HTTPStatusError) -> AppError:
    """
    401 直接要求重新連接：前面取行事曆列表時剛驗證或換過 token，再換也沒用。
    權限不足同樣要重新連接；其他照 _google_error 分類。
    """
    if e.response.status_code == 401 or google_error_code(e.response) == "REAUTH_REQUIRED":
        logger.warning("查詢 Google Calendar 事件需要重新連接: %s %s", e.response.status_code, e.response.text)
        return ReauthRequiredError(GOOGLE_REAUTH_DETAIL)
    return _google_error(e, "取得行事曆事件失敗")


async def find_removed_calendar_events(clerk_id: str, event_ids: list[str]) -> set[str]:
    """
    回傳 event_ids 裡在 Google 上已被刪除的事件（判斷規則同 get_calendar_event_ends）。

    依序查詢，任何一個失敗就丟出錯誤：沒有連接、Google 回 401 或權限不足丟 ReauthRequiredError；
    其他錯誤照 _google_error、_unreachable 分類。event_ids 是空的時不呼叫 Google。
    """
    if not event_ids:
        return set()
    try:
        access_token, calendar_id = await _get_access_token_and_primary_calendar_id(clerk_id)
    except InvalidRequestError as e:
        # 任務還存著事件編號卻沒有連接，代表授權被移除了，要請使用者重新連接
        if e.error_code == "NOT_LINKED":
            raise ReauthRequiredError(GOOGLE_REAUTH_DETAIL)
        raise

    removed = set()
    for event_id in event_ids:
        try:
            if await _get_event_unless_removed(access_token, calendar_id, event_id) is None:
                removed.add(event_id)
        except httpx.HTTPStatusError as e:
            raise _event_lookup_error(e)
        except httpx.RequestError as e:
            raise _unreachable(e, "連線 Google Calendar API 失敗")
    return removed


def _delete_error(e: httpx.HTTPStatusError) -> AppError:
    status = e.response.status_code
    if status == 401:
        return ReauthRequiredError(GOOGLE_REAUTH_DETAIL)
    if status >= 500 or status == 429:
        logger.warning("刪除 Google Calendar 事件失敗: %s %s", status, e.response.text)
        return ExternalServiceError(
            DELETE_RETRY_DETAIL, error_code=google_error_code(e.response), headers=rate_limit_headers(e.response)
        )
    return _google_error(e, "刪除 Google Calendar 事件失敗")


async def delete_calendar_events(clerk_id: str, event_ids: list[str]) -> None:
    """
    刪除使用者主要行事曆上的事件，不管事件已經開始、已經過去都刪；事件已不存在（404 / 410）當作刪除成功。

    參數：
    - clerk_id：要操作哪個使用者的 Google Calendar。
    - event_ids：要刪的事件 id（任務的 calendar_event_id）。空的時直接回傳，不檢查連接、不呼叫 Google。

    沒有連接、或 Google 回 401（授權失效）丟 ReauthRequiredError；Google 5xx、429 或連不上丟 ExternalServiceError；
    其他錯誤依 Google 的原因分類（_google_error）。
    中途失敗時已刪掉的事件不復原，任務仍保留這些事件 id；所以呼叫端要等這裡成功才刪任務，重試時已刪的事件會走 404 / 410。
    """
    if not event_ids:
        return
    if not await is_google_calendar_connected(clerk_id):
        raise ReauthRequiredError(GOOGLE_REAUTH_DETAIL)
    access_token, calendar_id = await _get_access_token_and_primary_calendar_id(clerk_id)

    for event_id in event_ids:
        try:
            await delete_calendar_event(access_token, calendar_id, event_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _EVENT_GONE_STATUSES:
                continue
            raise _delete_error(e)
        except httpx.RequestError as e:
            raise _unreachable(e, "連線 Google Calendar API 失敗", DELETE_RETRY_DETAIL)
