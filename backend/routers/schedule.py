import logging
from fastapi import APIRouter, Depends, HTTPException
from core.security import get_current_clerk_user
from services.google_calendar import get_free_slots_for_user, create_calendar_events_for_scheduled_tasks
from services.scheduler import build_schedule_suggestion, apply_blocked_periods, check_suggestion_still_valid, _parse_iso
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

# 產生排程建議時，把使用者看到的那一份存起來，確認時照這份寫入（見 confirm_schedule）。
# 30 分鐘後過期——放太久，行事曆、任務都可能已經變了很多，不如請使用者重新產生
SUGGESTION_SNAPSHOT_TTL_SECONDS = 30 * 60


def _suggestion_snapshot_key(user_id: str) -> str:
    return f"schedule_suggestion:{user_id}"


@router.get("/tasks", response_model=list[SchedulableTaskOut])
async def list_schedulable_tasks(clerk_user: dict = Depends(get_current_clerk_user)):
    """
    給前端「任務列表」用的統一清單：手動任務 + GitHub/Jira/Moodle 項目，
    見 crud/schedulable_items.py 的 get_all_schedulable_items。
    """
    return await get_all_schedulable_items(clerk_user["sub"])


@router.put("/reorder", response_model=list[SchedulableTaskOut])
async def reorder_schedule_tasks(
    body: ScheduleReorderInput,
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """
    使用者在排程精靈的拖拉排序畫面（低/中/高三欄，可跨欄拖動，可能混著手動
    任務跟外部平台項目）完成排序後呼叫。priority 仍是排程時的主要依據，
    這裡的順序只在同一個 priority 內決定誰先誰後（見 services/scheduler.py 的
    build_schedule_suggestion）。
    """
    items = [item.model_dump() for item in body.items]
    await reorder_schedulable_items(clerk_user["sub"], items)
    return await get_all_schedulable_items(clerk_user["sub"])


@router.patch("/tasks/fields")
async def update_schedule_task_fields(
    body: ScheduleTaskFieldsUpdate,
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """排程精靈 step 2：調整單一項目的截止日期／所需時長。"""
    data = body.model_dump(exclude={"task_id"}, exclude_none=True)
    if data:
        await update_scheduling_fields(clerk_user["sub"], body.task_id, data)
    return {"task_id": body.task_id, "updated": True}


@router.patch("/tasks/done")
async def update_schedule_task_done(
    body: ScheduleTaskDoneUpdate,
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """使用者在 App 內手動標記完成／取消完成（見 crud/schedulable_items.py 的 set_done）。"""
    await set_done(clerk_user["sub"], body.task_id, body.done)
    return {"task_id": body.task_id, "done": body.done}


async def _compute_suggestion(user_id: str, preferences: SchedulePreferences, error_detail: str) -> dict:
    """
    /schedule/suggest 跟 /schedule/confirm 共用的排程建議計算：抓可排程項目 +
    Google Calendar 空檔，先套用使用者這一輪填的「不工作時段」把空檔挖掉，
    再依 buffer_minutes／daily_max_minutes 把任務塞進剩下的空檔裡。
    preferences 不會存資料庫，每次呼叫都要靠前端重新帶——見 SchedulePreferences。
    """
    tasks = await get_all_schedulable_items(user_id)
    free_slots = await get_free_slots_for_user(user_id)

    # apply_blocked_periods／build_schedule_suggestion 本身是純計算、不會自己丟
    # HTTPException，這裡包起來只是為了防萬一（例如未來資料格式跟這裡假設的
    # 不一樣），讓使用者看到清楚的中文錯誤，而不是沒有說明的原始 500
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
        )
    except Exception:
        logger.exception("計算排程建議失敗 user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/suggest", response_model=ScheduleSuggestion)
async def suggest_schedule(
    preferences: SchedulePreferences = SchedulePreferences(),
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """
    規則式排程建議：抓使用者所有可排程項目（手動任務 + GitHub/Jira/Moodle）+
    Google Calendar 未來 7 天空檔（先扣掉 preferences 裡的不工作時段），
    依 priority／sort_order 排序後依序塞進空檔。不寫回 Google Calendar，
    純粹回傳一份建議清單給前端顯示。
    """
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
    使用者確認排程建議、要正式寫進 Google Calendar 時呼叫。

    寫入的是使用者在畫面上看到、按下確認的那一份——產生建議時存在快取裡的快照
    （見 suggest_schedule），不重新計算：重新計算的話，看到建議之後才新增的任務
    會被直接寫進行事曆，時間也可能跟畫面上不一樣。快照存在後端，前端只送「確認」
    這個動作，沒辦法竄改要寫入的任務或時間。

    寫入前用此刻的任務跟行事曆逐筆檢查（check_suggestion_still_valid）：任務已經
    完成／刪除、時段已經過了或被新行程占用的，不寫入、列進 failed 說明原因，其餘照寫。
    寫入成功的任務會標記為已鎖定，之後排程建議跟拖拉排序精靈都不會再動到它們。
    """
    user_id = clerk_user["sub"]
    snapshot_key = _suggestion_snapshot_key(user_id)
    snapshot = await cache_get(snapshot_key)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="排程建議已過期，請重新產生")

    scheduled = [{**item, "start": _parse_iso(item["start"]), "end": _parse_iso(item["end"])} for item in snapshot]
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
