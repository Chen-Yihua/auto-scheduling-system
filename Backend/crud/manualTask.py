import logging
from datetime import datetime, timezone
from db.mongodb import db
from schemas.manualTask import ManualTaskOut
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# 建立任務
async def create_manual_task(task: ManualTaskOut) -> str:
    doc = task.model_dump()
    await db.manual_tasks.insert_one(doc)
    return {
        "id": doc["id"],
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

# 查詢指定任務
async def get_manual_task_by_id(task_id: str, user_id: str):
    task = await db.manual_tasks.find_one({"id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.pop("_id", None)  # Mongo 自動加的 ObjectId，不是我們自己用的 id 欄位，不該再被塞回更新內容裡
    return task

# 查詢 user 所有任務
async def get_manual_tasks_by_user_id(user_id: str):
    tasks = await db.manual_tasks.find({"user_id": user_id}).to_list()
    for task in tasks:
        task.pop("_id", None)
    return tasks

# 依拖拉排序（三欄：低/中/高，可跨欄拖動，可能跟其他來源的項目混在同一次
# 排程精靈提交裡）後的結果，寫回 priority 和 sort_order
async def reorder_manual_tasks(user_id: str, items: list[dict]):
    """
    items 每筆帶著 task_id、被拖到哪一欄的 priority、還有 sort_order
    （由呼叫端——crud/schedulable_items.py 的 reorder_schedulable_items——
    依「使用者提交的完整清單裡的位置」指定，不是這裡自己 enumerate 算出來的：
    排程精靈可能同時混著手動任務跟外部平台項目，sort_order 只在同一個
    priority 內比較，必須是跨來源一致的同一套數字，不能各自從 0 重算）。

    先確認每個 id 都是這個使用者自己的任務，再一次寫回——不能讓人把別人
    帳號下的任務 id 混進來，藉此竄改不屬於自己的任務。

    用 update_one 逐筆寫入而不是 update_manual_task_by_id：後者「這次沒有
    任何欄位真的被改到就丟 400」的假設在這裡不成立——拖拉排序後名次剛好
    跟原本一樣（modified_count == 0）是完全正常的情況，不該被當成錯誤。
    """
    if not items:
        return []

    own_tasks = await db.manual_tasks.find({"user_id": user_id}).to_list()
    own_task_ids = {task["id"] for task in own_tasks}

    unknown_ids = [item["task_id"] for item in items if item["task_id"] not in own_task_ids]
    if unknown_ids:
        raise HTTPException(status_code=400, detail=f"包含不屬於你的任務 id: {unknown_ids}")

    now = datetime.now(timezone.utc)
    for item in items:
        await db.manual_tasks.update_one(
            {"id": item["task_id"], "user_id": user_id},
            {"$set": {"sort_order": item["sort_order"], "priority": item["priority"], "updated": now}},
        )

    return await get_manual_tasks_by_user_id(user_id)


# 確認排程後，把 Google Calendar 事件 id 寫回任務，標記為已鎖定
async def set_calendar_event_id(task_id: str, user_id: str, calendar_event_id: str):
    """
    只有 crud/oauth.py 的 create_calendar_events_for_scheduled_tasks（使用者
    「確認排程」時）會呼叫，不透過一般的 PUT /manual-tasks/{id} 更新流程——
    calendar_event_id 不該讓 client 透過一般更新請求自己填，那樣等於能無中生有
    「假裝」一筆任務已經鎖定，跳過真正建立 Google Calendar 事件那一步。
    """
    await db.manual_tasks.update_one(
        {"id": task_id, "user_id": user_id},
        {"$set": {"calendar_event_id": calendar_event_id, "updated": datetime.now(timezone.utc)}},
    )

# 更新任務
async def update_manual_task_by_id(task_id: str, data: dict):
    logger.debug("Updating manual task %s with data=%s", task_id, data)
    result = await db.manual_tasks.update_one({"id": task_id}, {"$set": data})
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    return await db.manual_tasks.find_one({"id": task_id})

# 刪除任務
async def delete_manual_task_by_id(task_id: str):
    result = await db.manual_tasks.delete_one({"id": task_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
