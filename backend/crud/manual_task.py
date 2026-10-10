import logging
from datetime import datetime, timezone
from core.database import db
from schemas.manual_task import ManualTaskOut
from fastapi import HTTPException

logger = logging.getLogger(__name__)


# 資料庫用 _id 存任務 id，對外（API、其他模組）一律叫 id
def _to_task(doc: dict) -> dict:
    doc["id"] = doc.pop("_id")
    return doc


async def create_manual_task(task: ManualTaskOut) -> dict:
    doc = task.model_dump()
    doc["_id"] = doc.pop("id")
    await db.manual_tasks.insert_one(doc)
    return {
        "id": doc["_id"],
        "user_id": doc.get("user_id"),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "due_date": doc.get("due_date"),
        "created": doc.get("created"),
        "updated": doc.get("updated"),
        "status": doc.get("status"),
        "priority": doc.get("priority"),
        "duration": doc.get("duration"),
        "inferred_fields": doc.get("inferred_fields", []),
        "inference_reason": doc.get("inference_reason"),
        "inference_hint": doc.get("inference_hint"),
        "sort_order": doc.get("sort_order"),
        "calendar_event_id": doc.get("calendar_event_id"),
    }

async def get_manual_task_by_id(task_id: str, user_id: str):
    task = await db.manual_tasks.find_one({"_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_task(task)

async def get_manual_tasks_by_user_id(user_id: str):
    tasks = await db.manual_tasks.find({"user_id": user_id}).to_list()
    return [_to_task(task) for task in tasks]

async def reorder_manual_tasks(user_id: str, items: list[dict]):
    """
    寫回拖拉排序後的 priority 和 sort_order。sort_order 由呼叫端依跨來源的完整清單指定。

    先確認每個 id 都屬於這個使用者，避免竄改別人的任務。
    不用 update_manual_task_by_id：順序沒變（modified_count 為 0）在這裡是正常情況，不該丟 400。
    """
    if not items:
        return []

    own_tasks = await db.manual_tasks.find({"user_id": user_id}, {"_id": 1}).to_list()
    own_task_ids = {task["_id"] for task in own_tasks}

    unknown_ids = [item["task_id"] for item in items if item["task_id"] not in own_task_ids]
    if unknown_ids:
        raise HTTPException(status_code=400, detail=f"包含不屬於你的任務 id: {unknown_ids}")

    now = datetime.now(timezone.utc)
    for item in items:
        await db.manual_tasks.update_one(
            {"_id": item["task_id"], "user_id": user_id},
            {"$set": {"sort_order": item["sort_order"], "priority": item["priority"], "updated": now}},
        )

    return await get_manual_tasks_by_user_id(user_id)


async def set_calendar_event_id(task_id: str, user_id: str, calendar_event_id: str):
    """
    確認排程建立行事曆事件後呼叫。calendar_event_id 不開放透過一般更新 API 寫入，
    否則 client 可以假裝任務已排入行事曆。
    """
    await db.manual_tasks.update_one(
        {"_id": task_id, "user_id": user_id},
        {"$set": {"calendar_event_id": calendar_event_id, "updated": datetime.now(timezone.utc)}},
    )

async def update_manual_task_by_id(task_id: str, data: dict):
    logger.debug("Updating manual task %s with data=%s", task_id, data)
    # id 對應 _id，不能更新
    fields = {key: value for key, value in data.items() if key != "id"}
    result = await db.manual_tasks.update_one({"_id": task_id}, {"$set": fields})
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    doc = await db.manual_tasks.find_one({"_id": task_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_task(doc)

async def delete_manual_task_by_id(task_id: str):
    result = await db.manual_tasks.delete_one({"_id": task_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
