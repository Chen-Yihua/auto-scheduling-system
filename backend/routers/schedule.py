import logging
from fastapi import APIRouter, Depends
from core.errors import AppError, ConflictError, InvalidRequestError, NotFoundError
from core.security import get_current_clerk_user
from crud.manual_task import get_manual_task_by_id, get_subtasks
from platforms import PLATFORMS
from routers.manual_task import _calendar_events_to_delete, _delete_task_records
from services.google_calendar import (
    get_free_slots_for_user,
    create_calendar_events_for_scheduled_tasks,
    delete_calendar_events,
    find_removed_calendar_events,
    get_calendar_event_ends,
)
from services.scheduler import build_schedule_suggestion, apply_blocked_periods, check_suggestion_still_valid
from core.datetimes import to_utc_datetime
from core.cache import cache_get, cache_set, cache_delete
from crud.schedulable_items import (
    INVALID_TASK_ID_DETAIL,
    SOURCE_MANUAL,
    clear_calendar_event_id_for_composite,
    get_all_schedulable_items,
    get_external_calendar_event_id,
    make_composite_id,
    parse_composite_id,
    reorder_schedulable_items,
    update_scheduling_fields,
    set_done,
)
from schemas.schedule import (
    ScheduleSuggestion,
    ScheduleConfirmResult,
    SchedulableTaskOut,
    ScheduleReorderInput,
    ScheduleTaskFieldsUpdate,
    ScheduleTaskDoneUpdate,
    SchedulePreferences,
    RemovedCalendarEventOut,
    ResolveRemovedEventsInput,
    ResolveRemovedEventsResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule", tags=["schedule"])

# 使用者看到的排程建議快照，確認時照這份寫入；過期後請使用者重新產生
SUGGESTION_SNAPSHOT_TTL_SECONDS = 30 * 60


def _suggestion_snapshot_key(user_id: str) -> str:
    return f"schedule_suggestion:{user_id}"


@router.get("/tasks", response_model=list[SchedulableTaskOut])
async def list_schedulable_tasks(clerk_user: dict = Depends(get_current_clerk_user)):
    """手動任務和外部平台項目的統一清單。"""
    return await get_all_schedulable_items(clerk_user["sub"])


@router.put("/reorder", response_model=list[SchedulableTaskOut])
async def reorder_schedule_tasks(
    body: ScheduleReorderInput,
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """儲存拖拉排序的結果（priority 和同 priority 內的順序）。"""
    items = [item.model_dump() for item in body.items]
    await reorder_schedulable_items(clerk_user["sub"], items)
    return await get_all_schedulable_items(clerk_user["sub"])


@router.patch("/tasks/fields")
async def update_schedule_task_fields(
    body: ScheduleTaskFieldsUpdate,
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """調整單一項目的截止日期和所需時長。"""
    data = body.model_dump(exclude={"task_id"}, exclude_none=True)
    await update_scheduling_fields(clerk_user["sub"], body.task_id, data)
    return {"task_id": body.task_id, "updated": True}


@router.patch("/tasks/done")
async def update_schedule_task_done(
    body: ScheduleTaskDoneUpdate,
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """手動標記完成或取消完成。"""
    await set_done(clerk_user["sub"], body.task_id, body.done)
    return {"task_id": body.task_id, "done": body.done}


def _previous_stage_event_ids(tasks: list[dict]) -> list[str]:
    """還要排的子任務，它的前一個階段已寫入行事曆但沒完成時，那個事件的 id。"""
    by_stage = {(t["parent_id"], t["stage"]): t for t in tasks if t.get("parent_id") and t.get("stage")}
    event_ids = []
    for t in tasks:
        if not t.get("parent_id") or not t.get("stage") or t.get("status") == "Done" or t.get("calendar_event_id"):
            continue
        previous = by_stage.get((t["parent_id"], t["stage"] - 1))
        if previous and previous.get("status") != "Done" and previous.get("calendar_event_id"):
            event_ids.append(previous["calendar_event_id"])
    return event_ids


async def _compute_suggestion(user_id: str, preferences: SchedulePreferences, error_detail: str) -> dict:
    """取得可排程項目和 Google Calendar 空檔，扣掉不工作時段後計算排程建議。"""
    tasks = await get_all_schedulable_items(user_id)
    free_slots = await get_free_slots_for_user(user_id)
    event_ids = _previous_stage_event_ids(tasks)
    previous_event_ends = await get_calendar_event_ends(user_id, event_ids) if event_ids else {}

    # 資料格式不符預期時回明確的錯誤訊息，而不是沒有說明的 500
    try:
        free_slots = apply_blocked_periods(
            free_slots,
            [r.model_dump() for r in preferences.blocked_recurring],
            [e.model_dump() for e in preferences.blocked_exceptions],
            tz_name=preferences.timezone,
        )
        return build_schedule_suggestion(
            tasks, free_slots,
            buffer_minutes=preferences.buffer_minutes,
            daily_max_minutes=preferences.daily_max_minutes,
            tz_name=preferences.timezone,
            previous_event_ends=previous_event_ends,
        )
    except Exception:
        logger.exception("計算排程建議失敗 user_id=%s", user_id)
        raise AppError(error_detail)


@router.post("/suggest", response_model=ScheduleSuggestion)
async def suggest_schedule(
    preferences: SchedulePreferences = SchedulePreferences(),
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """產生排程建議，不寫入 Google Calendar。建議會存成快照供確認時使用。"""
    suggestion = await _compute_suggestion(clerk_user["sub"], preferences, "產生排程建議失敗，請稍後再試")

    snapshot = [
        {**item, "start": item["start"].isoformat(), "end": item["end"].isoformat()}
        for item in suggestion["scheduled"]
    ]
    await cache_set(_suggestion_snapshot_key(clerk_user["sub"]), snapshot, SUGGESTION_SNAPSHOT_TTL_SECONDS)

    logger.debug(
        "Schedule suggestion for user_id=%s: %d scheduled, %d unscheduled",
        clerk_user["sub"], len(suggestion["scheduled"]), len(suggestion["unscheduled"]),
    )
    return suggestion


@router.post("/confirm", response_model=ScheduleConfirmResult)
async def confirm_schedule(
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """
    把使用者看到的排程建議寫入 Google Calendar。

    寫入的是後端存的快照，不重新計算：否則之後新增的任務也會被寫入，時間也可能
    和畫面不同；快照存在後端也讓前端無法竄改內容。
    寫入前逐筆檢查，已失效的項目列入 failed 並說明原因，其餘照寫。
    """
    user_id = clerk_user["sub"]
    snapshot_key = _suggestion_snapshot_key(user_id)
    snapshot = await cache_get(snapshot_key)
    if snapshot is None:
        raise ConflictError("排程建議已過期，請重新產生", error_code="SUGGESTION_EXPIRED")

    scheduled = [{**item, "start": to_utc_datetime(item["start"]), "end": to_utc_datetime(item["end"])} for item in snapshot]
    current_tasks = await get_all_schedulable_items(user_id)
    free_slots = await get_free_slots_for_user(user_id, use_cache=False)
    to_write, invalid = check_suggestion_still_valid(scheduled, current_tasks, free_slots)

    # 寫入前就刪掉快照：同一份建議只能確認一次，不然重複送出會重複建立行事曆事件
    await cache_delete(snapshot_key)
    result = await create_calendar_events_for_scheduled_tasks(user_id, to_write)

    logger.debug(
        "Schedule confirm for user_id=%s: %d confirmed, %d failed",
        user_id, len(result["confirmed"]), len(invalid) + len(result["failed"]),
    )
    return {"confirmed": result["confirmed"], "failed": invalid + result["failed"]}


EXTERNAL_DELETE_REJECTED = "外部平台的項目不能刪除，只能重新排程"
EVENT_ID_CHANGED_DETAIL = "任務的 Google 日曆事件已經變更，請重新整理後再試"


def _later_scheduled_stages(stages: list[dict], after_stage: int, excluded_ids: set[str]) -> list[dict]:
    """
    勾選某個階段重新排程時，要一起從 Google 日曆移除、重新排程的後面階段，依階段順序。

    stages 是同一個主任務的子任務（id 是組合 id）；只取 after_stage 之後、已排入、還沒完成、id 不在 excluded_ids 的。
    """
    later = [
        s for s in stages
        if (s.get("stage") or 0) > after_stage and s.get("calendar_event_id")
        and s.get("status") != "Done" and s["id"] not in excluded_ids
    ]
    return sorted(later, key=lambda s: s["stage"])


@router.get("/removed-events", response_model=list[RemovedCalendarEventOut])
async def list_removed_events(clerk_user: dict = Depends(get_current_clerk_user)):
    """
    已排入、還沒完成、不是主任務的項目裡，Google 日曆上的事件已被刪除的。
    每個階段任務另外帶上勾選重新排程時會一起移除的後面階段（不含也列在這裡的階段）。
    查詢 Google 失敗時整個請求失敗，錯誤照 find_removed_calendar_events。
    """
    user_id = clerk_user["sub"]
    items = await get_all_schedulable_items(user_id)
    scheduled = [
        item for item in items
        if item.get("calendar_event_id") and item.get("status") != "Done" and not item.get("is_parent")
    ]
    removed_event_ids = await find_removed_calendar_events(user_id, [item["calendar_event_id"] for item in scheduled])
    removed = [item for item in scheduled if item["calendar_event_id"] in removed_event_ids]

    removed_ids = {item["id"] for item in removed}
    result = []
    for item in removed:
        later = []
        if item.get("parent_id") and item.get("stage"):
            stages = [t for t in items if t.get("parent_id") == item["parent_id"]]
            later = _later_scheduled_stages(stages, item["stage"], removed_ids)
        result.append({**item, "later_stages": [{"task_id": s["id"], "stage": s["stage"]} for s in later]})
    return result


def _failure(task_id: str, reason: str, error_code: str | None) -> dict:
    return {"task_id": task_id, "reason": reason, "error_code": error_code}


async def _event_still_removed(user_id: str, event_id: str | None) -> bool:
    """處理前再向 Google 確認一次：畫面停留期間事件可能被復原。沒有編號時不用處理。"""
    return bool(event_id) and event_id in await find_removed_calendar_events(user_id, [event_id])


async def _delete_removed_item(user_id: str, composite_id: str) -> dict | None:
    """
    沒勾的項目：事件確實已被刪除時，照刪除任務的規則刪掉它。回傳這一項的失敗；成功或不需要處理回 None。
    Google 的錯誤不在這裡接住，讓整個請求停止。
    """
    source, raw_id = parse_composite_id(composite_id)
    if source != SOURCE_MANUAL:
        reason = EXTERNAL_DELETE_REJECTED if source in PLATFORMS else INVALID_TASK_ID_DETAIL
        return _failure(composite_id, reason, "INVALID_REQUEST")
    try:
        task = await get_manual_task_by_id(raw_id, user_id)
    except NotFoundError as e:
        return _failure(composite_id, e.detail, e.error_code)

    if not await _event_still_removed(user_id, task.get("calendar_event_id")):
        return None
    await delete_calendar_events(user_id, await _calendar_events_to_delete(task, user_id))
    try:
        await _delete_task_records(task, user_id)
    except (NotFoundError, ConflictError) as e:
        return _failure(composite_id, e.detail, e.error_code)
    return None


async def _reschedule_removed_item(user_id: str, composite_id: str, requested_ids: set[str]) -> dict | None:
    """
    勾選的項目：事件確實已被刪除時清掉編號，讓它回到待排。回傳這一項的失敗；成功或不需要處理回 None。

    階段任務先刪掉後面已排入、還沒完成、不在這次請求裡的階段在 Google 上的事件，再逐一清掉它們的編號，
    最後才清這一項：中途失敗時只會留下「Google 上沒有事件、任務還有編號」的項目，下次查詢會再列出。
    清除時編號已被換掉，這一項失敗，自己的編號不清。Google 的錯誤不在這裡接住，讓整個請求停止。
    """
    source, raw_id = parse_composite_id(composite_id)
    task = None
    try:
        if source == SOURCE_MANUAL:
            task = await get_manual_task_by_id(raw_id, user_id)
            event_id = task.get("calendar_event_id")
        else:
            event_id = await get_external_calendar_event_id(user_id, composite_id)
    except (InvalidRequestError, NotFoundError) as e:
        return _failure(composite_id, e.detail, e.error_code)

    if not event_id or not await _event_still_removed(user_id, event_id):
        return None

    later = []
    if task and task.get("parent_id") and task.get("stage"):
        stages = [
            {**s, "id": make_composite_id(SOURCE_MANUAL, s["id"])}
            for s in await get_subtasks(task["parent_id"], user_id)
        ]
        later = _later_scheduled_stages(stages, task["stage"], requested_ids)
    await delete_calendar_events(user_id, [s["calendar_event_id"] for s in later])
    for stage in later:
        if not await clear_calendar_event_id_for_composite(user_id, stage["id"], stage["calendar_event_id"]):
            return _failure(composite_id, EVENT_ID_CHANGED_DETAIL, None)
    if not await clear_calendar_event_id_for_composite(user_id, composite_id, event_id):
        return _failure(composite_id, EVENT_ID_CHANGED_DETAIL, None)
    return None


@router.post("/removed-events/resolve", response_model=ResolveRemovedEventsResult)
async def resolve_removed_events(
    body: ResolveRemovedEventsInput,
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """
    處理使用者在「處理已刪除的事件」步驟的選擇：先刪除 delete 的項目，再把 reschedule 的項目放回待排。

    依序處理，每一項都用處理當下的資料，處理前再向 Google 確認事件仍然不存在。
    單一項目的問題（id 格式錯、不存在或不屬於自己、要刪除外部項目、編號已被換掉、階段正在被別的請求改動）
    列在 failed，繼續處理下一項。Google 的錯誤（包括授權失效）直接丟出，還沒處理的項目都不處理；
    已處理成功的不復原。不用資料庫交易（ADR 0004）。
    """
    user_id = clerk_user["sub"]
    requested_ids = set(body.reschedule) | set(body.delete)
    succeeded: list[str] = []
    failed: list[dict] = []

    for composite_id in body.delete:
        failure = await _delete_removed_item(user_id, composite_id)
        if failure:
            failed.append(failure)
        else:
            succeeded.append(composite_id)
    for composite_id in body.reschedule:
        failure = await _reschedule_removed_item(user_id, composite_id, requested_ids)
        if failure:
            failed.append(failure)
        else:
            succeeded.append(composite_id)

    logger.debug("Resolve removed events for user_id=%s: %d succeeded, %d failed", user_id, len(succeeded), len(failed))
    return {"succeeded": succeeded, "failed": failed}
