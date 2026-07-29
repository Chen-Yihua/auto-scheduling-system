from fastapi import APIRouter, HTTPException, Depends, Request
from crud import manualTask as manualTask_crud
from schemas.manualTask import ManualTaskInput, ManualTaskOut
from db.security import get_current_clerk_user
from datetime import datetime, timezone
from uuid import uuid4

router = APIRouter(prefix="/manual_tasks", tags=["manual_tasks"])

# 建立任務
@router.post("/", response_model=ManualTaskOut)
async def create_manual_task(
    taskInput: ManualTaskInput,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    建立新的任務（需驗證 JWT）
    """
    now = datetime.now(timezone.utc)
    task = ManualTaskOut(
        **taskInput.model_dump(),
        id=str(uuid4()), # 隨機產生id
        created=now,
        updated=now
    )
    task.user_id = clerk_user["sub"]

    print(task)
    new_task = await manualTask_crud.create_manual_task(task)
    return new_task

# 查詢user所有任務
@router.get("/me", response_model=list[ManualTaskOut])
async def get_user_tasks(
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    取得目前登入者的所有任務（需驗證 JWT）
    """
    tasks = await manualTask_crud.get_manual_tasks_by_user_id(clerk_user["sub"])
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found")
    return tasks

# 查詢任務
@router.get("/{task_id}", response_model=ManualTaskOut)
async def get_manual_task(
    task_id: str,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    取得指定的任務（需驗證 JWT）
    """
    task = await manualTask_crud.get_manual_task_by_id(task_id, clerk_user["sub"]) # 只能查自己的task
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

# 更新任務
@router.put("/{task_id}", response_model=ManualTaskOut)
async def update_manual_task(
    task_id: str,
    taskInput: ManualTaskInput,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    更新指定的任務（需驗證 JWT）
    """
    task = await manualTask_crud.get_manual_task_by_id(task_id, clerk_user["sub"]) # 只能查自己的task
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    now = datetime.now(timezone.utc)
    task.update({"updated": now})
    task.update(taskInput.model_dump())    

    updated_task = await manualTask_crud.update_manual_task_by_id(task_id, task)
    return updated_task

# 刪除任務
@router.delete("/{task_id}")
async def delete_manual_task(
    task_id: str,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    刪除指定的任務（需驗證 JWT）
    """
    task = await manualTask_crud.get_manual_task_by_id(task_id, clerk_user["sub"])
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    success = await manualTask_crud.delete_manual_task_by_id(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Delete failed")
    return {"task ID": task_id,"deleted": True}