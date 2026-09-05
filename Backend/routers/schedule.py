import logging
from fastapi import APIRouter, Depends
from db.security import get_current_clerk_user
from crud.manualTask import get_manual_tasks_by_user_id
from crud.oauth import get_free_slots_for_user
from crud.schedule import build_schedule_suggestion
from schemas.schedule import ScheduleSuggestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/suggest", response_model=ScheduleSuggestion)
async def suggest_schedule(clerk_user: dict = Depends(get_current_clerk_user)):
    """
    規則式排程建議：抓使用者未完成的任務 + Google Calendar 未來 7 天空檔，
    依 priority／due_date 排序後依序塞進空檔。不寫回 Google Calendar，
    純粹回傳一份建議清單給前端顯示。
    """
    tasks = await get_manual_tasks_by_user_id(clerk_user["sub"]) or []
    free_slots = await get_free_slots_for_user(clerk_user["sub"])

    suggestion = build_schedule_suggestion(tasks, free_slots)
    logger.debug(
        "Schedule suggestion for user_id=%s: %d scheduled, %d unscheduled",
        clerk_user["sub"], len(suggestion["scheduled"]), len(suggestion["unscheduled"]),
    )
    return suggestion
