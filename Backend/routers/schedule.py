import logging
from fastapi import APIRouter, Depends, HTTPException
from db.security import get_current_clerk_user
from crud.oauth import get_free_slots_for_user, create_calendar_events_for_scheduled_tasks
from crud.schedule import build_schedule_suggestion, apply_blocked_periods
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
    這裡的順序只在同一個 priority 內決定誰先誰後（見 crud/schedule.py 的
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
        )
        return build_schedule_suggestion(
            tasks, free_slots,
            buffer_minutes=preferences.buffer_minutes,
            daily_max_minutes=preferences.daily_max_minutes,
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

    logger.debug(
        "Schedule suggestion for user_id=%s: %d scheduled, %d unscheduled",
        clerk_user["sub"], len(suggestion["scheduled"]), len(suggestion["unscheduled"]),
    )
    return suggestion


@router.post("/confirm", response_model=ScheduleConfirmResult)
async def confirm_schedule(
    preferences: SchedulePreferences = SchedulePreferences(),
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """
    使用者確認排程建議、要正式寫進 Google Calendar 時呼叫。這裡重新計算一次
    排程建議（不吃前端傳來的結果），避免依賴前端手上可能已經過期或被竄改的
    資料去建立 Calendar 事件；preferences 要跟產生建議時同一份，前端從
    useSchedule 記住的 lastPreferences 帶過來（見前端 composables/useSchedule.ts）。

    「已排入時段」的項目逐一寫進 Google Calendar，成功的會標記為已鎖定
    （見 crud/schedule.py 的 build_schedule_suggestion），之後排程建議
    跟拖拉排序精靈都不會再動到它們；要改時間只能直接去 Google Calendar 改。
    """
    suggestion = await _compute_suggestion(clerk_user["sub"], preferences, "確認排程失敗，請稍後再試")

    result = await create_calendar_events_for_scheduled_tasks(clerk_user["sub"], suggestion["scheduled"])

    logger.debug(
        "Schedule confirm for user_id=%s: %d confirmed, %d failed",
        clerk_user["sub"], len(result["confirmed"]), len(result["failed"]),
    )
    return result
