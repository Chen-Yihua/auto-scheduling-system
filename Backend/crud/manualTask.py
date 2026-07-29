from db.mongodb import db
from schemas.manualTask import ManualTaskOut
from fastapi import HTTPException

# 建立任務
async def create_manual_task(task: ManualTaskOut) -> str:
    doc = task.dict()
    try:
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
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 查詢任務
async def get_manual_task_by_id(task_id: str, user_id: str):
    task = await db.manual_tasks.find_one({"id": task_id, "user_id": user_id})
    if not task:
        return None
    return task

# 查詢user所有任務
async def get_manual_tasks_by_user_id(user_id: str):
    tasks = await db.manual_tasks.find({"user_id": user_id}).to_list()
    if not tasks:
        return None
    return tasks

# 更新任務
async def update_manual_task_by_id(task_id: str, data: dict):
    print(data)
    result = await db.manual_tasks.update_one({"id": task_id}, {"$set": data})
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    output = await db.manual_tasks.find_one({"id": task_id})
    return output

# 刪除任務
async def delete_manual_task_by_id(task_id: str):
    result = await db.manual_tasks.delete_one({"id": task_id})
    return result.deleted_count > 0
