from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, Query
from core.errors import InvalidRequestError
from core.security import get_current_clerk_user
from crud.schedulable_items import get_all_schedulable_items
from schemas.analytics import ProductivitySummary
from services.productivity import build_productivity_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/productivity", response_model=ProductivitySummary)
async def get_productivity_summary(
    tz_name: str = Query("UTC", alias="timezone"),
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """工作效率統計。timezone 是瀏覽器的 IANA 時區，週趨勢依當地時間的週一切分。"""
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise InvalidRequestError(f"不認得的時區：{tz_name}")

    items = await get_all_schedulable_items(clerk_user["sub"])
    return build_productivity_summary(items, datetime.now(timezone.utc), tz_name)
