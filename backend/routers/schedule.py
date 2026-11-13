import logging
from fastapi import APIRouter, Depends
from core.errors import AppError, ConflictError
from core.security import get_current_clerk_user
from services.google_calendar import (
    get_free_slots_for_user,
    create_calendar_events_for_scheduled_tasks,
    get_calendar_event_ends,
)
from services.scheduler import build_schedule_suggestion, apply_blocked_periods, check_suggestion_still_valid
from core.datetimes import to_utc_datetime
from core.cache import cache_get, cache_set, cache_delete
from crud.schedulable_items import (
    get_all_schedulable_items,
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
