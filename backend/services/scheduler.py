import logging
from datetime import MAXYEAR, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from core.datetimes import to_utc_datetime

logger = logging.getLogger(__name__)

# 沒設定 duration 的項目用這個值，例如還沒在排程精靈填過時長的外部平台項目
DEFAULT_TASK_DURATION_MINUTES = 60

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}

# 截止日在這段時間內（含已過期）的任務不管 priority 一律先排
URGENT_WINDOW = timedelta(hours=24)

PREVIOUS_STAGE_NOT_SCHEDULED = "前一個階段還沒排入"
PREVIOUS_STAGE_WRITE_FAILED = "前一個階段寫入失敗"


def _stage_key(task: dict, offset: int) -> tuple | None:
    if not task.get("parent_id") or not task.get("stage"):
        return None
    return (task["parent_id"], task["stage"] + offset)


def _derived_deadlines(tasks: list[dict], by_stage: dict[tuple, dict], default_minutes: int) -> dict[str, datetime]:
    """
    沒有截止日的階段，期限是「下一個階段的期限 − 下一個階段的時長」，從最後一個有截止日的階段往前遞推。
    下一個階段已完成時不受它限制。只用在排程，不寫回資料庫。
    """
    memo: dict[str, datetime | None] = {}

    def deadline_of(task: dict) -> datetime | None:
        if task["id"] in memo:
            return memo[task["id"]]
        result = to_utc_datetime(task.get("due_date"))
        if result is None:
            key = _stage_key(task, 1)
            following = by_stage.get(key) if key else None
            if following is not None and following.get("status") != "Done":
                following_deadline = deadline_of(following)
                if following_deadline is not None:
                    result = following_deadline - timedelta(minutes=following.get("duration") or default_minutes)
        memo[task["id"]] = result
        return result

    derived = {}
    for task in tasks:
        if task.get("parent_id") and task.get("due_date") is None:
            deadline = deadline_of(task)
            if deadline is not None:
                derived[task["id"]] = deadline
    return derived


_NO_DUE_DATE = datetime(MAXYEAR, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)


def _sortable_due_date(due) -> datetime:
    """排序用：沒有截止日的排在最後。"""
    return to_utc_datetime(due) or _NO_DUE_DATE


def _to_local_wall_time(value: datetime, zone: ZoneInfo) -> datetime:
    """轉成使用者當地的牆上時間（naive），才能跟「22:00」這類設定比較。naive 視為 UTC。"""
    return to_utc_datetime(value).astimezone(zone).replace(tzinfo=None)


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
            _to_local_wall_time(to_utc_datetime(s["start"]), zone),
            _to_local_wall_time(to_utc_datetime(s["end"]), zone),
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
                _to_local_wall_time(to_utc_datetime(e["start"]), zone),
                _to_local_wall_time(to_utc_datetime(e["end"]), zone),
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
    previous_event_ends: dict[str, datetime | None] | None = None,
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

    階段任務：主任務不排。子任務一定在前一個階段之後處理，開始時間不早於前一個階段的結束時間加緩衝；
    前一個階段已完成則不受限制，已寫入行事曆則用 previous_event_ends（calendar_event_id → Google 上
    最新的結束時間，事件已不存在是 None，不受限制）。前一個階段沒排進去，後面的階段也不排。
    """
    now = now or datetime.now(timezone.utc)
    zone = ZoneInfo(tz_name)
    previous_event_ends = previous_event_ends or {}
    by_stage = {key: t for t in tasks if (key := _stage_key(t, 0))}
    derived_deadlines = _derived_deadlines(tasks, by_stage, task_duration_minutes)
    pending = [
        t for t in tasks
        if not t.get("is_parent") and t.get("status") != "Done" and not t.get("calendar_event_id")
    ]

    def sort_key(t):
        # 推算的期限也算緊急：否則後面的階段快到期時，前面的階段反而排在其他任務之後
        due = to_utc_datetime(t.get("due_date")) or derived_deadlines.get(t["id"])
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
        valid_slots.append({"start": to_utc_datetime(s["start"]), "end": to_utc_datetime(s["end"])})

    slots = sorted(valid_slots, key=lambda s: s["start"])

    scheduled = []
    unscheduled = []
    daily_used_minutes: dict = {}
    buffer = timedelta(minutes=buffer_minutes)
    scheduled_end: dict[str, datetime] = {}

    def unschedule(task, reason):
        unscheduled.append({"task_id": task["id"], "title": task["title"], "priority": task["priority"], "reason": reason})

    def earliest_start(task) -> tuple[bool, datetime | None]:
        """(能不能排, 最早的開始時間)。"""
        key = _stage_key(task, -1)
        previous = by_stage.get(key) if key else None
        if previous is None or previous.get("status") == "Done":
            return True, None
        if previous.get("calendar_event_id"):
            event_end = previous_event_ends.get(previous["calendar_event_id"])
            return True, (event_end + buffer if event_end is not None else None)
        if previous["id"] in scheduled_end:
            return True, scheduled_end[previous["id"]] + buffer
        return False, None

    def place(task):
        can_schedule, earliest = earliest_start(task)
        if not can_schedule:
            unschedule(task, PREVIOUS_STAGE_NOT_SCHEDULED)
            return
        task_minutes = task.get("duration") or task_duration_minutes
        duration = timedelta(minutes=task_minutes)
        due = to_utc_datetime(task.get("due_date")) or derived_deadlines.get(task["id"])
        deadline = due if due is not None and due > now else None
        missed_deadline = False
        for index, slot in enumerate(slots):
            start = max(slot["start"], earliest) if earliest is not None else slot["start"]
            if slot["end"] - start < duration:
                continue
            if daily_max_minutes is not None:
                day = start.astimezone(zone).date()
                remaining_today = daily_max_minutes - daily_used_minutes.get(day, 0)
                if remaining_today < task_minutes:
                    continue
            if deadline is not None and start + duration > deadline:
                # slots 依開始時間排序，後面的只會更晚
                missed_deadline = True
                break
            end = start + duration
            scheduled.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "start": start,
                "end": end,
                # 回應不帶出，存進確認用的快照：前一個階段被刪掉後，確認時才知道後面的階段屬於哪個主任務
                "parent_id": task.get("parent_id"),
            })
            scheduled_end[task["id"]] = end
            if daily_max_minutes is not None:
                day = start.astimezone(zone).date()
                daily_used_minutes[day] = daily_used_minutes.get(day, 0) + task_minutes
            # 被前一個階段往後推時，前面空出來的時間留給其他任務，同樣在結束前保留緩衝
            if start - buffer > slot["start"]:
                slots.insert(index, {"start": slot["start"], "end": start - buffer})
            slot["start"] = end + buffer
            slots.sort(key=lambda s: s["start"])
            return
        unschedule(task, "截止日前沒有足夠的空檔" if missed_deadline else "沒有足夠的空檔可以安排")

    valid_ids = {t["id"] for t in valid_tasks}
    processed: set[str] = set()
    waiting_for: dict[str, list[dict]] = {}

    def process(task):
        place(task)
        processed.add(task["id"])
        for following in waiting_for.pop(task["id"], []):
            process(following)

    for task in valid_tasks:
        key = _stage_key(task, -1)
        previous = by_stage.get(key) if key else None
        if previous is not None and previous["id"] in valid_ids and previous["id"] not in processed:
            # 前一個階段排序較後面，等它處理完再排
            waiting_for.setdefault(previous["id"], []).append(task)
            continue
        process(task)

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
    slots = [(to_utc_datetime(s["start"]), to_utc_datetime(s["end"])) for s in free_slots if s.get("start") and s.get("end")]

    to_write = []
    failed = []
    blocked_parents = set()
    last_written_by_parent: dict[str, str] = {}
    for item in scheduled:
        task = tasks_by_id.get(item["task_id"])
        parent_id = item.get("parent_id") or (task.get("parent_id") if task else None)
        # 「已經完成」「已經排入行事曆」不用寫入，但不代表後面的階段排錯了，不擋
        blocks_later_stages = True
        if task is None:
            reason = "任務已不存在"
        elif task.get("status") == "Done":
            reason = "任務已經完成"
            blocks_later_stages = False
        elif task.get("calendar_event_id"):
            reason = "任務已經排入行事曆"
            blocks_later_stages = False
        elif item["start"] < now:
            reason = "這個時段已經過了，請重新產生排程"
        elif not any(s_start <= item["start"] and item["end"] <= s_end for s_start, s_end in slots):
            reason = "這個時段已被其他行程占用，請重新產生排程"
        elif parent_id in blocked_parents:
            reason = PREVIOUS_STAGE_WRITE_FAILED
        else:
            # 同一個主任務前面的階段也在這次寫入時標上它，寫入 Google 時前一個失敗就跳過
            previous_id = last_written_by_parent.get(parent_id) if parent_id else None
            to_write.append({**item, "previous_task_id": previous_id} if previous_id else item)
            if parent_id:
                last_written_by_parent[parent_id] = item["task_id"]
            continue
        if parent_id and blocks_later_stages:
            blocked_parents.add(parent_id)
        failed.append({"task_id": item["task_id"], "title": item["title"], "reason": reason})

    return to_write, failed
