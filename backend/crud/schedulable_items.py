"""
把手動任務和外部平台項目統一成可排程項目。

id 加上來源前綴（例如 "github:42"）：不同平台的 id 可能重複，前綴也用來決定要寫回哪個 collection。
"""
from collections import Counter
from datetime import datetime, timezone
from core.errors import InvalidRequestError, NotFoundError
from crud.manual_task import (
    TASK_NOT_FOUND_DETAIL,
    completed_at_after_status_change,
    get_manual_task_by_id,
    get_manual_tasks_by_user_id,
    set_calendar_event_id,
    update_manual_task_by_id,
    validate_reordered_stages,
    validate_task_change,
    write_manual_task_order,
)
from platforms import PLATFORMS

SOURCE_MANUAL = "manual"
INVALID_TASK_ID_DETAIL = "任務 id 格式錯誤"


def make_composite_id(source: str, item_id) -> str:
    return f"{source}:{item_id}"


def parse_composite_id(composite_id: str) -> tuple[str, str]:
    source, _, item_id = composite_id.partition(":")
    return source, item_id


def _external_id(platform, raw_id: str):
    try:
        return platform.id_type(raw_id)
    except ValueError:
        raise InvalidRequestError(INVALID_TASK_ID_DETAIL)


def _external_platform(source: str):
    """不認得的來源前綴（包括沒有冒號）是組合 id 格式錯誤。"""
    platform = PLATFORMS.get(source)
    if platform is None:
        raise InvalidRequestError(INVALID_TASK_ID_DETAIL)
    return platform


async def _find_own_external(source: str, raw_id: str, user_id: str) -> dict:
    """外部項目不存在或不屬於自己時和手動任務一樣回 404，不透露資料是否存在。"""
    platform = _external_platform(source)
    doc = await platform.collection.find_one({"id": _external_id(platform, raw_id), "user_id": user_id})
    if doc is None:
        raise NotFoundError(TASK_NOT_FOUND_DETAIL)
    return doc


async def _update_external(source: str, raw_id: str, user_id: str, fields: dict) -> None:
    """
    更新外部平台項目的排程欄位；不認得的來源、項目不存在都忽略。
    要檢查存在的呼叫端自己先查：確認排程寫回事件 id 時不能丟錯，否則 Google 上會留下沒記錄的事件。
    """
    platform = PLATFORMS.get(source)
    if platform is None:
        return
    await platform.collection.update_one(
        {"id": _external_id(platform, raw_id), "user_id": user_id},
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

    所有會回 400 的檢查都在寫入任何項目之前完成，任何一項不合法時整批都不寫。
    """
    manual_items = []
    external_items = []
    for index, item in enumerate(items):
        source, raw_id = parse_composite_id(item["task_id"])
        if source == SOURCE_MANUAL:
            manual_items.append({"task_id": raw_id, "priority": item["priority"], "sort_order": index, "composite_id": item["task_id"]})
        else:
            platform = _external_platform(source)
            external_items.append({
                "platform": platform, "id": _external_id(platform, raw_id), "priority": item["priority"],
                "sort_order": index, "composite_id": item["task_id"],
            })

    own_manual_tasks = {task["id"]: task for task in await get_manual_tasks_by_user_id(user_id)} if manual_items else {}
    unknown = {item["composite_id"] for item in manual_items if item["task_id"] not in own_manual_tasks}
    for item in external_items:
        if await item["platform"].collection.find_one({"id": item["id"], "user_id": user_id}) is None:
            unknown.add(item["composite_id"])
    if unknown:
        # 列出使用者送出的組合 id，外部和手動同一個訊息，不透露資料是否存在
        unknown_ids = [item["task_id"] for item in items if item["task_id"] in unknown]
        raise InvalidRequestError(f"包含不屬於你的任務 id: {unknown_ids}")

    validate_reordered_stages(own_manual_tasks, manual_items)

    for item in external_items:
        await item["platform"].collection.update_one(
            {"id": item["id"], "user_id": user_id},
            {"$set": {"sort_order": item["sort_order"], "priority": item["priority"]}},
        )
    await write_manual_task_order(user_id, manual_items)


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

    await _find_own_external(source, raw_id, user_id)
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

    doc = await _find_own_external(source, raw_id, user_id)
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
