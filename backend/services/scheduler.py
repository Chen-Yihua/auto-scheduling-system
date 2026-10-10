import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# 沒有 duration 欄位的舊資料用這個值
DEFAULT_TASK_DURATION_MINUTES = 60

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}

# 截止日在這段時間內（含已過期）的任務不管 priority 一律先排
URGENT_WINDOW = timedelta(hours=24)


def _parse_iso(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sortable_due_date(due) -> datetime:
    """排序用：去掉 tzinfo 避免 aware/naive 混合比較出錯，幾小時的誤差不影響先後。"""
    if due is None:
        return datetime.max.replace(tzinfo=None)
    if due.tzinfo is not None:
        return due.replace(tzinfo=None)
    return due


def _due_as_utc(due) -> datetime | None:
    """轉成 aware UTC。pymongo 讀回的 naive datetime 本來就是 UTC。"""
    if due is None:
        return None
    if isinstance(due, str):
        due = _parse_iso(due)
    if due.tzinfo is None:
        return due.replace(tzinfo=timezone.utc)
    return due.astimezone(timezone.utc)


def _to_local_wall_time(value: datetime, zone: ZoneInfo) -> datetime:
    """轉成使用者當地的牆上時間（naive），才能跟「22:00」這類設定比較。naive 視為 UTC。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(zone).replace(tzinfo=None)


def _local_wall_time_to_utc_iso(value: datetime, zone: ZoneInfo) -> str:
    """_to_local_wall_time 的反向：當地牆上時間 → UTC ISO 字串（帶 Z）。"""
    utc = value.replace(tzinfo=zone).astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z")


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _expand_recurring_blocks(
    rules: list[dict], window_start: datetime, window_end: datetime,
) -> list[tuple[datetime, datetime]]:
    """
    把每週固定的不工作時段展開成時間窗內每天的實際區間。
    跨午夜的規則（例如 22:00-08:00）拆成當天和隔天兩段。
    不是 all_day 又沒有起訖時間的規則視為還沒填完，略過。
    """
    blocks: list[tuple[datetime, datetime]] = []
    day = window_start.date()
    end_day = window_end.date()
    while day <= end_day:
        weekday = day.weekday()  # 0=一...6=日
        next_midnight = datetime.combine(day, time.min) + timedelta(days=1)
        for rule in rules:
            if weekday not in rule.get("days_of_week", []):
                continue
            if rule.get("all_day"):
                blocks.append((datetime.combine(day, time.min), next_midnight))
                continue
            if not rule.get("start_time") or not rule.get("end_time"):
                continue
            start_t = _parse_hhmm(rule["start_time"])
            end_t = _parse_hhmm(rule["end_time"])
            start_dt = datetime.combine(day, start_t)
            if end_t <= start_t:
                blocks.append((start_dt, next_midnight))
                blocks.append((next_midnight, next_midnight + (datetime.combine(day, end_t) - datetime.combine(day, time.min))))
            else:
                blocks.append((start_dt, datetime.combine(day, end_t)))
        day += timedelta(days=1)
    return blocks


def _subtract_intervals(
    slots: list[tuple[datetime, datetime]], blocked: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """從 slots 挖掉所有跟 blocked 重疊的部分，一段 slot 可能因此被切成兩段。"""
    remaining = list(slots)
    for b_start, b_end in blocked:
        next_remaining = []
        for s_start, s_end in remaining:
            if b_end <= s_start or b_start >= s_end:
                next_remaining.append((s_start, s_end))
                continue
            if b_start > s_start:
                next_remaining.append((s_start, b_start))
            if b_end < s_end:
                next_remaining.append((b_end, s_end))
        remaining = next_remaining
    return remaining


def apply_blocked_periods(
    free_slots: list[dict],
    blocked_recurring: list[dict] | None = None,
    blocked_exceptions: list[dict] | None = None,
    tz_name: str = "UTC",
) -> list[dict]:
    """
    從空檔挖掉使用者設定的不工作時段（每週規律和一次性例外）。

    不工作時段是使用者當地（tz_name）的時間，空檔是 UTC，所以先換成當地時間再挖，
    最後轉回 UTC。輸出必須帶 Z，否則前端 new Date() 會當成瀏覽器的本地時間。
    """
    if not blocked_recurring and not blocked_exceptions:
        return free_slots

    zone = ZoneInfo(tz_name)
    parsed = []
    for s in free_slots:
        if not s.get("start") or not s.get("end"):
            continue
        parsed.append((
            _to_local_wall_time(_parse_iso(s["start"]), zone),
            _to_local_wall_time(_parse_iso(s["end"]), zone),
        ))
    if not parsed:
        return []

    window_start = min(s for s, _ in parsed)
    window_end = max(e for _, e in parsed)

    blocks: list[tuple[datetime, datetime]] = []
    if blocked_recurring:
        blocks += _expand_recurring_blocks(blocked_recurring, window_start, window_end)
    if blocked_exceptions:
        for e in blocked_exceptions:
            if not e.get("start") or not e.get("end"):
                continue
            blocks.append((
                _to_local_wall_time(_parse_iso(e["start"]), zone),
                _to_local_wall_time(_parse_iso(e["end"]), zone),
            ))

    remaining = sorted(_subtract_intervals(parsed, blocks), key=lambda t: t[0])
    return [
        {"start": _local_wall_time_to_utc_iso(s, zone), "end": _local_wall_time_to_utc_iso(e, zone)}
        for s, e in remaining
    ]


def build_schedule_suggestion(
    tasks: list[dict],
    free_slots: list[dict],
    task_duration_minutes: int = DEFAULT_TASK_DURATION_MINUTES,
    buffer_minutes: int = 0,
    daily_max_minutes: int | None = None,
    now: datetime | None = None,
    tz_name: str = "UTC",
) -> dict:
    """
    規則式排程建議（貪婪 First-Fit），只回傳建議，不寫入 Google Calendar。

    排序：
    - 已完成或已寫入行事曆（有 calendar_event_id）的任務不排。
    - 截止日在 URGENT_WINDOW 內或已過期的任務最優先，依截止日早到晚。
    - 其餘依 priority，同 priority 內依 sort_order；沒有 sort_order 的排在後面，依 due_date。

    安排：每個任務從最早的空檔找第一個放得下的。前面任務放不下的空檔仍保留給
    後面較短的任務。未過期的任務必須在截止日前結束，否則列入 unscheduled。

    buffer_minutes：每個任務後保留的緩衝時間。
    daily_max_minutes：每天最多安排的分鐘數，以使用者當地（tz_name）的日期計算。
    now：判斷緊急和過期的基準時間，測試可傳固定值。
    """
    now = now or datetime.now(timezone.utc)
    zone = ZoneInfo(tz_name)
    pending = [t for t in tasks if t.get("status") != "Done" and not t.get("calendar_event_id")]

    def sort_key(t):
        due = _due_as_utc(t.get("due_date"))
        if due is not None and due <= now + URGENT_WINDOW:
            return (0, due)
        priority_rank = PRIORITY_ORDER.get(t.get("priority"), len(PRIORITY_ORDER))
        sort_order = t.get("sort_order")
        if sort_order is not None:
            return (1, priority_rank, 0, sort_order)
        due_sort = _sortable_due_date(t.get("due_date"))
        return (1, priority_rank, 1, due_sort)

    pending_sorted = sorted(pending, key=sort_key)

    # 缺必要欄位的壞資料跳過，不讓一筆資料拖垮整個請求
    valid_tasks = []
    for t in pending_sorted:
        if not t.get("id") or not t.get("title") or not t.get("priority"):
            logger.warning("排程建議跳過缺少必要欄位的任務: %s", t)
            continue
        valid_tasks.append(t)

    valid_slots = []
    for s in free_slots:
        if not s.get("start") or not s.get("end"):
            logger.warning("排程建議跳過缺少 start/end 的空檔: %s", s)
            continue
        valid_slots.append({"start": _parse_iso(s["start"]), "end": _parse_iso(s["end"])})

    slots = sorted(valid_slots, key=lambda s: s["start"])

    scheduled = []
    unscheduled = []
    daily_used_minutes: dict = {}

    for task in valid_tasks:
        task_minutes = task.get("duration") or task_duration_minutes
        duration = timedelta(minutes=task_minutes)
        due = _due_as_utc(task.get("due_date"))
        deadline = due if due is not None and due > now else None
        placed = False
        missed_deadline = False
        for slot in slots:
            if slot["end"] - slot["start"] < duration:
                continue
            if daily_max_minutes is not None:
                day = slot["start"].astimezone(zone).date()
                remaining_today = daily_max_minutes - daily_used_minutes.get(day, 0)
                if remaining_today < task_minutes:
                    continue
            if deadline is not None and slot["start"] + duration > deadline:
                # slots 依開始時間排序，後面的只會更晚
                missed_deadline = True
                break
            start = slot["start"]
            end = start + duration
            scheduled.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "start": start,
                "end": end,
            })
            if daily_max_minutes is not None:
                day = start.astimezone(zone).date()
                daily_used_minutes[day] = daily_used_minutes.get(day, 0) + task_minutes
            slot["start"] = end + timedelta(minutes=buffer_minutes)
            placed = True
            break
        if not placed:
            unscheduled.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "reason": "截止日前沒有足夠的空檔" if missed_deadline else "沒有足夠的空檔可以安排",
            })

    return {"scheduled": scheduled, "unscheduled": unscheduled}


def check_suggestion_still_valid(
    scheduled: list[dict],
    current_tasks: list[dict],
    free_slots: list[dict],
    now: datetime | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    確認排程前，檢查使用者看到的建議是否仍能照原樣寫入（期間任務或行事曆可能已改變）。

    回傳 (可寫入的項目, 不能寫入的項目與原因)。free_slots 是此刻的空檔，
    不套用不工作時段，只檢查有沒有撞期。
    """
    now = now or datetime.now(timezone.utc)
    tasks_by_id = {t["id"]: t for t in current_tasks}
    slots = [(_parse_iso(s["start"]), _parse_iso(s["end"])) for s in free_slots if s.get("start") and s.get("end")]

    to_write = []
    failed = []
    for item in scheduled:
        task = tasks_by_id.get(item["task_id"])
        if task is None:
            reason = "任務已不存在"
        elif task.get("status") == "Done":
            reason = "任務已經完成"
        elif task.get("calendar_event_id"):
            reason = "任務已經排入行事曆"
        elif item["start"] < now:
            reason = "這個時段已經過了，請重新產生排程"
        elif not any(s_start <= item["start"] and item["end"] <= s_end for s_start, s_end in slots):
            reason = "這個時段已被其他行程占用，請重新產生排程"
        else:
            to_write.append(item)
            continue
        failed.append({"task_id": item["task_id"], "title": item["title"], "reason": reason})

    return to_write, failed
