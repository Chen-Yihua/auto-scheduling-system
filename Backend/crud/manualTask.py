import logging
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
