"""從可排程項目算出工作效率統計：現況（完成率、工時、逾期）和近幾週的完成趨勢。"""
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from core.datetimes import to_utc_datetime
from crud.schedulable_items import SOURCE_MANUAL
from platforms import PLATFORMS

TREND_WEEKS = 8

SOURCE_ORDER = [SOURCE_MANUAL, *PLATFORMS]
PRIORITY_ORDER = ["High", "Medium", "Low", None]


def _week_start(moment: datetime, tz: ZoneInfo) -> date:
    local_date = moment.astimezone(tz).date()
    return local_date - timedelta(days=local_date.weekday())


def _rate(part: int, whole: int) -> Optional[float]:
    return part / whole if whole else None


def _group_counts(items: list[dict], key: str, order: list) -> list[dict]:
    counts = {value: {"total": 0, "done": 0} for value in order}
    for item in items:
        group = counts.setdefault(item.get(key), {"total": 0, "done": 0})
        group["total"] += 1
        group["done"] += item["status"] == "Done"
    return [{key: value, **c} for value, c in counts.items() if c["total"]]


def build_productivity_summary(items: list[dict], now: datetime, tz_name: str) -> dict:
    # 主任務只是容器，狀態由子任務算出，計入會重複計算
    items = [item for item in items if not item.get("is_parent")]
    tz = ZoneInfo(tz_name)
    current_week = _week_start(now, tz)
    week_starts = [current_week - timedelta(weeks=n) for n in range(TREND_WEEKS - 1, -1, -1)]
    weekly = {start: {"week_start": start, "completed": 0, "completed_minutes": 0} for start in week_starts}

    done = done_minutes = remaining_minutes = unestimated_remaining = overdue = untracked_done = 0
    completed_with_due = on_time = 0

    for item in items:
        duration = item.get("duration")
        due_date = to_utc_datetime(item.get("due_date"))

        if item["status"] != "Done":
            remaining_minutes += duration or 0
            unestimated_remaining += duration is None
            overdue += due_date is not None and due_date < now
            continue

        done += 1
        done_minutes += duration or 0
        completed_at = to_utc_datetime(item.get("completed_at"))
        if completed_at is None:
            untracked_done += 1
            continue

        week = weekly.get(_week_start(completed_at, tz))
        if week is None:
            continue
        week["completed"] += 1
        week["completed_minutes"] += duration or 0
        if due_date is not None:
            completed_with_due += 1
            on_time += completed_at <= due_date

    return {
        "generated_at": now,
        "total": len(items),
        "done": done,
        "completion_rate": _rate(done, len(items)),
        "overdue": overdue,
        "done_minutes": done_minutes,
        "remaining_minutes": remaining_minutes,
        "unestimated_remaining": unestimated_remaining,
        "untracked_done": untracked_done,
        "by_source": _group_counts(items, "source", SOURCE_ORDER),
        "by_priority": _group_counts(items, "priority", PRIORITY_ORDER),
        "weekly": list(weekly.values()),
        "on_time": {
            "completed_with_due": completed_with_due,
            "on_time": on_time,
            "rate": _rate(on_time, completed_with_due),
        },
    }
