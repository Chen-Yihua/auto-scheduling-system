"""
把手動任務和外部平台項目統一成可排程項目。

id 加上來源前綴（例如 "github:42"）：不同平台的 id 可能重複，前綴也用來決定要寫回哪個 collection。
"""
from collections import Counter
from datetime import datetime, timezone
from core.errors import InvalidRequestError
from crud.manual_task import (
    completed_at_after_status_change,
    get_manual_task_by_id,
    get_manual_tasks_by_user_id,
    reorder_manual_tasks,
    set_calendar_event_id,
    update_manual_task_by_id,
    validate_task_change,
)
from platforms import PLATFORMS

SOURCE_MANUAL = "manual"


def make_composite_id(source: str, item_id) -> str:
    return f"{source}:{item_id}"


def parse_composite_id(composite_id: str) -> tuple[str, str]:
    source, _, item_id = composite_id.partition(":")
    return source, item_id


async def _update_external(source: str, raw_id: str, user_id: str, fields: dict) -> None:
    """更新外部平台項目的排程欄位，不認得的來源忽略。"""
    platform = PLATFORMS.get(source)
    if platform is None:
        return
    await platform.collection.update_one(
        {"id": platform.id_type(raw_id), "user_id": user_id},
        {"$set": fields},
    )


def _normalize_external(source: str, doc: dict) -> dict:
    platform = PLATFORMS[source]
    platform_done = platform.is_done(doc)
    # 平台回報完成或使用者手動標記完成，任一成立即視為完成
    done = bool(doc.get("done")) or platform_done
    completed_at = None
    if done:
        # 平台的關閉時間比使用者事後補標記的時間準
        completed_at = (platform.completed_at(doc) if platform_done else None) or doc.get("completed_at")
    return {
        "id": make_composite_id(source, doc["id"]),
        "source": source,
        "title": doc.get("title") or "",
        "status": "Done" if done else "To Do",
        "priority": doc.get("priority"),
        "duration": doc.get("duration"),
        "due_date": doc.get("scheduling_due_date"),
        "sort_order": doc.get("sort_order"),
        "calendar_event_id": doc.get("calendar_event_id"),
        "url": doc.get("url"),
        "completed_at": completed_at,
    }


async def get_all_schedulable_items(user_id: str) -> list[dict]:
    """取得使用者所有可排程項目（手動任務和外部平台項目）。"""
    manual_tasks = await get_manual_tasks_by_user_id(user_id)
    titles = {t["id"]: t.get("title") for t in manual_tasks}
    stage_counts = Counter(t["parent_id"] for t in manual_tasks if t.get("parent_id"))
    items = []
    for t in manual_tasks:
        item = {**t, "source": SOURCE_MANUAL, "id": make_composite_id(SOURCE_MANUAL, t["id"]), "url": None}
        if t.get("parent_id"):
            item["parent_id"] = make_composite_id(SOURCE_MANUAL, t["parent_id"])
            item["parent_title"] = titles.get(t["parent_id"])
            item["stage_count"] = stage_counts[t["parent_id"]]
        items.append(item)

    for source, platform in PLATFORMS.items():
        docs = await platform.collection.find({"user_id": user_id}).to_list(length=None)
        items.extend(_normalize_external(source, doc) for doc in docs)

    return items


async def reorder_schedulable_items(user_id: str, items: list[dict]):
    """
    處理使用者拖拉任務後的排序結果，將排序資訊寫入對應的項目。
    items 是拖拉排序後的完整順序，可混合不同來源。
    sort_order 用整份清單的索引，不分來源各自編號，否則同一欄內交錯的順序會被打散。
    """
    manual_items = []
    for index, item in enumerate(items):
        source, raw_id = parse_composite_id(item["task_id"])
        if source == SOURCE_MANUAL:
            manual_items.append({"task_id": raw_id, "priority": item["priority"], "sort_order": index})
        else:
            await _update_external(source, raw_id, user_id, {"sort_order": index, "priority": item["priority"]})

    if manual_items:
        await reorder_manual_tasks(user_id, manual_items)


async def update_scheduling_fields(user_id: str, composite_id: str, data: dict):
    """設定單一項目的排程欄位（due_date、duration）。"""
    source, raw_id = parse_composite_id(composite_id)
    if source == SOURCE_MANUAL:
        task = await get_manual_task_by_id(raw_id, user_id)
        if task.get("is_parent") and "duration" in data:
            raise InvalidRequestError("主任務沒有時長，請修改子任務")
        await validate_task_change(task, data)
        task.update({"updated": datetime.now(timezone.utc)})
        task.update(data)
        await update_manual_task_by_id(raw_id, task)
        return

    await _update_external(source, raw_id, user_id, data)


async def set_done(user_id: str, composite_id: str, done: bool):
    """
    手動標記完成或取消完成。外部平台項目存在獨立的 done 欄位，
    不影響平台本身的狀態，也不會被下次同步覆蓋。
    """
    source, raw_id = parse_composite_id(composite_id)
    if source == SOURCE_MANUAL:
        task = await get_manual_task_by_id(raw_id, user_id)
        if task.get("is_parent"):
            raise InvalidRequestError("主任務的狀態依子任務自動計算，不能手動標記完成")
        now = datetime.now(timezone.utc)
        status = "Done" if done else "To Do"
        task["completed_at"] = completed_at_after_status_change(task.get("status"), task.get("completed_at"), status, now)
        task.update({"status": status, "updated": now})
        await update_manual_task_by_id(raw_id, task)
        return

    platform = PLATFORMS.get(source)
    if platform is None:
        return
    doc = await platform.collection.find_one({"id": platform.id_type(raw_id), "user_id": user_id})
    if doc is None:
        return
    completed_at = None
    if done:
        completed_at = doc.get("completed_at") if doc.get("done") else datetime.now(timezone.utc)
    await _update_external(source, raw_id, user_id, {"done": done, "completed_at": completed_at})


async def set_calendar_event_id_for_composite(user_id: str, composite_id: str, calendar_event_id: str):
    """把確認排程後的 Google Calendar 事件 id 寫回對應的項目。"""
    source, raw_id = parse_composite_id(composite_id)
    if source == SOURCE_MANUAL:
        await set_calendar_event_id(raw_id, user_id, calendar_event_id)
        return

    await _update_external(source, raw_id, user_id, {"calendar_event_id": calendar_event_id})
