import logging
from datetime import datetime, time, timedelta, timezone

logger = logging.getLogger(__name__)

# manual_tasks 現在允許每個任務自己填（或由 LLM 推斷）預估時長；
# 這裡的預設值只給「沒有 duration 欄位」的舊資料當退路。
DEFAULT_TASK_DURATION_MINUTES = 60

PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def _parse_iso(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sortable_due_date(due) -> datetime:
    """
    due_date 可能是 aware 或 naive datetime（取決於建立任務當下帶的格式），
    排序前一律去掉 tzinfo，避免 aware/naive 互相比較直接噴例外。
    這裡只用來決定「誰先誰後」，容許幾小時時區誤差不影響排程建議的實用性。
    """
    if due is None:
        return datetime.max.replace(tzinfo=None)
    if due.tzinfo is not None:
        return due.replace(tzinfo=None)
    return due


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _expand_recurring_blocks(
    rules: list[dict], window_start: datetime, window_end: datetime,
) -> list[tuple[datetime, datetime]]:
    """
    把「每週固定規律」（例如「每天 22:00-08:00」「週六、週日全天」）展開成
    這個時間窗內、每一天實際對應的 datetime 區間。

    起訖時間跨過午夜（end_time <= start_time，例如 22:00-08:00）拆成兩段：
    當天 start_time ~ 24:00，跟隔天 00:00 ~ end_time——這樣才不會漏掉隔天
    一大早那一段，也不用處理「區間橫跨兩天」這種更複雜的表示法。

    使用者在精靈畫面上可能先勾了星期、還沒填起訖時間就送出（例如規律還在
    編輯中）；這種不是 all_day、卻沒有 start_time/end_time 的規則視為還沒
    設定完整，直接跳過，不當成錯誤擋掉整個排程建議。
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
) -> list[dict]:
    """
    從 Google Calendar 算出的空檔（free_slots）裡，再挖掉使用者這一輪在
    排程精靈填的「不工作時段」——每週固定規律 + 這次額外加的一次性例外。

    這裡「比較」的時候刻意把時間當成不含時區的牆上時鐘時間處理（跟
    _sortable_due_date 同樣的取捨：容許時區誤差，換取不用另外儲存/推斷
    使用者所在時區的複雜度），所以 Google 回來的 UTC ISO 字串跟使用者在
    畫面上填的「22:00」不是嚴格對齊的同一個時刻，但差距通常只有幾小時，
    不影響排程建議的實用性。

    但「輸出」一定要補回 UTC 時區標記（Z）——free_slots 本來就是 UTC，
    少了這個標記，前端 new Date(...) 會把它當成瀏覽器所在時區的本地時間
    解讀，讓排程建議看起來排到過去的時間（例如已經是晚上，卻顯示排在
    「今天早上」）。
    """
    if not blocked_recurring and not blocked_exceptions:
        return free_slots

    parsed = []
    for s in free_slots:
        if not s.get("start") or not s.get("end"):
            continue
        parsed.append((_parse_iso(s["start"]).replace(tzinfo=None), _parse_iso(s["end"]).replace(tzinfo=None)))
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
            blocks.append((_parse_iso(e["start"]).replace(tzinfo=None), _parse_iso(e["end"]).replace(tzinfo=None)))

    remaining = sorted(_subtract_intervals(parsed, blocks), key=lambda t: t[0])
    return [
        {
            "start": s.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            "end": e.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        for s, e in remaining
    ]


def build_schedule_suggestion(
    tasks: list[dict],
    free_slots: list[dict],
    task_duration_minutes: int = DEFAULT_TASK_DURATION_MINUTES,
    buffer_minutes: int = 0,
    daily_max_minutes: int | None = None,
) -> dict:
    """
    規則式排程建議：不寫回 Google Calendar，只回傳一份建議清單。

    已經「確認排程」過、寫進 Google Calendar 的任務（有 calendar_event_id，
    見 POST /schedule/confirm）會被排除，不會再被拿來重新排程——那些時段
    已經是既成事實，要改只能直接去 Google Calendar 改。

    排序規則：priority（High > Medium > Low）永遠是主要依據——排程精靈的
    拖拉排序畫面現在是低/中/高三欄，拖去別欄當場就是在改 priority
    （見 PUT /schedule/reorder），不是另外一套獨立的排序機制。
    同一個 priority 內，才看 sort_order（使用者在畫面上同一欄內排的上下
    順序）決定誰先誰後；沒有 sort_order 的任務（例如排完序後才新建的）
    退回舊規則，依 due_date 早到晚排序、沒有 due_date 的排在最後面，
    整批排在同 priority 內有 sort_order 的任務後面。

    排定規則：依序把任務塞進可用空檔，每個任務用自己的 duration
    （沒有就退回 task_duration_minutes）；每次都從最早的空檔開始找，
    只要找到一個容量夠的空檔就塞進去、消耗掉那段時間。
    因為每個任務時長可能不同，這裡故意不做「空檔用完就跳過」的捷徑——
    前面任務太大塞不下的空檔，仍要留給後面時長較短的任務用。
    塞不進任何空檔的任務，放進 unscheduled 並附上原因。

    buffer_minutes：每排完一個任務，消耗掉的時間多加這一段當緩衝
    （不算進下一個任務可用），0 就是目前預設的「完全貼著排」。
    daily_max_minutes：同一天已經排的時長加起來到這個上限後，當天剩下的
    空檔就先跳過、留給後面的任務找別天的空檔（不會因此整段消耗掉）。
    """
    pending = [t for t in tasks if t.get("status") != "Done" and not t.get("calendar_event_id")]

    def sort_key(t):
        priority_rank = PRIORITY_ORDER.get(t.get("priority"), len(PRIORITY_ORDER))
        sort_order = t.get("sort_order")
        if sort_order is not None:
            return (priority_rank, 0, sort_order)
        due_sort = _sortable_due_date(t.get("due_date"))
        return (priority_rank, 1, due_sort)

    pending_sorted = sorted(pending, key=sort_key)

    # 理論上 tasks 一定有 id/title/priority（見 schemas/manualTask.py 的
    # ManualTaskOut，這三個是必填欄位），但這裡不假設一定成立——資料格式
    # 以後可能改變、也可能有繞過驗證的舊資料。少了這些欄位就湊不出一筆
    # 有意義的排程結果（回傳的 ScheduleSuggestion 這幾個欄位也都是必填），
    # 與其讓整個請求因為一筆壞資料就當掉，不如跳過它、記錄下來
    valid_tasks = []
    for t in pending_sorted:
        if not t.get("id") or not t.get("title") or not t.get("priority"):
            logger.warning("排程建議跳過缺少必要欄位的任務: %s", t)
            continue
        valid_tasks.append(t)

    # free_slots 同理，缺 start/end 就不是一個有意義的空檔，直接跳過
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
        placed = False
        for slot in slots:
            if slot["end"] - slot["start"] < duration:
                continue
            if daily_max_minutes is not None:
                day = slot["start"].date()
                remaining_today = daily_max_minutes - daily_used_minutes.get(day, 0)
                if remaining_today < task_minutes:
                    continue
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
                day = start.date()
                daily_used_minutes[day] = daily_used_minutes.get(day, 0) + task_minutes
            slot["start"] = end + timedelta(minutes=buffer_minutes)
            placed = True
            break
        if not placed:
            unscheduled.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "reason": "沒有足夠的空檔可以安排",
            })

    return {"scheduled": scheduled, "unscheduled": unscheduled}
