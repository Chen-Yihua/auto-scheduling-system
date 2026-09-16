from datetime import datetime, timedelta

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


def build_schedule_suggestion(
    tasks: list[dict],
    free_slots: list[dict],
    task_duration_minutes: int = DEFAULT_TASK_DURATION_MINUTES,
) -> dict:
    """
    規則式排程建議：不寫回 Google Calendar，只回傳一份建議清單。

    排序規則：priority（High > Medium > Low）優先，同優先權內依 due_date
    早到晚排序，沒有 due_date 的排在同優先權最後面。

    排定規則：依序把任務塞進可用空檔，每個任務用自己的 duration
    （沒有就退回 task_duration_minutes）；每次都從最早的空檔開始找，
    只要找到一個容量夠的空檔就塞進去、消耗掉那段時間。
    因為每個任務時長可能不同，這裡故意不做「空檔用完就跳過」的捷徑——
    前面任務太大塞不下的空檔，仍要留給後面時長較短的任務用。
    塞不進任何空檔的任務，放進 unscheduled 並附上原因。
    """
    pending = [t for t in tasks if t.get("status") != "Done"]

    def sort_key(t):
        priority_rank = PRIORITY_ORDER.get(t.get("priority"), len(PRIORITY_ORDER))
        due_sort = _sortable_due_date(t.get("due_date"))
        return (priority_rank, due_sort)

    pending_sorted = sorted(pending, key=sort_key)

    slots = sorted(
        (
            {"start": _parse_iso(s["start"]), "end": _parse_iso(s["end"])}
            for s in free_slots
        ),
        key=lambda s: s["start"],
    )

    scheduled = []
    unscheduled = []

    for task in pending_sorted:
        duration = timedelta(minutes=task.get("duration") or task_duration_minutes)
        placed = False
        for slot in slots:
            if slot["end"] - slot["start"] >= duration:
                start = slot["start"]
                end = start + duration
                scheduled.append({
                    "task_id": task["id"],
                    "title": task["title"],
                    "priority": task["priority"],
                    "start": start,
                    "end": end,
                })
                slot["start"] = end
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
