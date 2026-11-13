"""以使用者為單位操作 Google Calendar，access_token 過期時自動換新重試。"""
import logging
from datetime import datetime, timezone

import httpx
from core.errors import AppError, ExternalServiceError, InvalidRequestError, NotFoundError, ReauthRequiredError

from core.cache import cache_get, cache_set
from core.crypto import SecretDecryptError
from core.datetimes import to_utc_datetime
from crud.google_tokens import get_google_calendar_token, is_google_calendar_connected
from services.google_errors import DETAIL_BY_ERROR_CODE, google_error_code, rate_limit_headers, request_error_code
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
    if status >= 500 or status == 429:
        return ExternalServiceError(DETAIL_BY_ERROR_CODE[error_code], error_code=error_code, headers=headers)
    message = detail if error_code == "UPSTREAM_ERROR" else DETAIL_BY_ERROR_CODE[error_code]
    return InvalidRequestError(message, error_code=error_code, headers=headers)


def _unreachable(e: httpx.RequestError, log_message: str, detail: str | None = None) -> ExternalServiceError:
    logger.error("%s: %s", log_message, e)
    error_code, default_detail = request_error_code(e)
    return ExternalServiceError(detail or default_detail, error_code=error_code)


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
        raise NotFoundError("找不到 Google 的主要行事曆（primary calendar）", error_code="NO_PRIMARY_CALENDAR")

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
        return request_error_code(e)
    if e.response.status_code == 401:
        return "REAUTH_REQUIRED", GOOGLE_REAUTH_DETAIL
    error_code = google_error_code(e.response)
    return error_code, DETAIL_BY_ERROR_CODE[error_code]


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

        await set_calendar_event_id_for_composite(clerk_id, task["task_id"], event["id"])
        confirmed.append({
            "task_id": task["task_id"],
            "title": task["title"],
            "calendar_event_id": event["id"],
        })

    return {"confirmed": confirmed, "failed": failed}


def _parse_event_time(value: dict | None) -> datetime | None:
    return to_utc_datetime((value or {}).get("dateTime"))


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
            event = await get_calendar_event(access_token, calendar_id, event_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _EVENT_GONE_STATUSES:
                ends[event_id] = None
                continue
            raise _google_error(e, "取得行事曆事件失敗")
        except httpx.RequestError as e:
            raise _unreachable(e, "連線 Google Calendar API 失敗")
        ends[event_id] = None if event.get("status") == "cancelled" else _parse_event_time(event.get("end"))
    return ends


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


async def delete_upcoming_calendar_events(clerk_id: str, event_ids: list[str], now: datetime | None = None) -> list[str]:
    """
    刪除開始時間晚於現在的事件，已經開始或過去的保留；事件已不存在（404 / 410）當作刪除成功。
    回傳這次真的刪掉的事件 id。

    沒有連接或授權失效丟 ReauthRequiredError；Google 5xx、429 或連不上丟 ExternalServiceError。
    中途失敗時已刪掉的事件不復原，呼叫端要等這裡成功才刪任務，重試時已刪的事件會走 404 / 410。
    """
    if not event_ids:
        return []
    now = now or datetime.now(timezone.utc)
    if not await is_google_calendar_connected(clerk_id):
        raise ReauthRequiredError(GOOGLE_REAUTH_DETAIL)
    access_token, calendar_id = await _get_access_token_and_primary_calendar_id(clerk_id)

    deleted = []
    for event_id in event_ids:
        try:
            event = await get_calendar_event(access_token, calendar_id, event_id)
            if event.get("status") == "cancelled":
                continue
            start = _parse_event_time(event.get("start"))
            if start is None or start <= now:
                continue
            await delete_calendar_event(access_token, calendar_id, event_id)
            deleted.append(event_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _EVENT_GONE_STATUSES:
                continue
            raise _delete_error(e)
        except httpx.RequestError as e:
            raise _unreachable(e, "連線 Google Calendar API 失敗", DELETE_RETRY_DETAIL)
    return deleted
