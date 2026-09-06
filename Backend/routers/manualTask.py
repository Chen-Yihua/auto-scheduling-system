import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from crud import manualTask as manualTask_crud
from crud.task_inference import infer_missing_task_fields
from schemas.manualTask import ManualTaskInput, ManualTaskOut
from db.security import get_current_clerk_user
from datetime import datetime, timezone
from uuid import uuid4
from rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manual_tasks", tags=["manual_tasks"])

# 建立任務
# 沒填 priority/duration 時會呼叫 Gemini（見 crud/task_inference.py），
# 限流避免有人（或壞掉的前端迴圈）連續狂建任務，把 LLM 額度燒光
@router.post("/", response_model=ManualTaskOut)
@limiter.limit("20/minute")
async def create_manual_task(
    request: Request,
    taskInput: ManualTaskInput,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    建立新的任務（需驗證 JWT）。
    使用者沒填 priority／duration（不確定）時，用 LLM 從 title/description 推斷。
    """
    task_data = taskInput.model_dump()
    inferred_fields = []
    inference_reason = None

    if taskInput.priority is None or taskInput.duration is None:
        inference = await infer_missing_task_fields(
            taskInput.title, taskInput.description, taskInput.inference_hint
        )
        if taskInput.priority is None:
            task_data["priority"] = inference["priority"]
            inferred_fields.append("priority")
        if taskInput.duration is None:
            task_data["duration"] = inference["duration"]
            inferred_fields.append("duration")
        inference_reason = inference["reason"]

    now = datetime.now(timezone.utc)
    task = ManualTaskOut(
        **task_data,
        id=str(uuid4()), # 隨機產生id
        created=now,
        updated=now,
        inferred_fields=inferred_fields,
        inference_reason=inference_reason,
    )
    task.user_id = clerk_user["sub"]

    logger.debug("Creating manual task: %s (inferred_fields=%s)", task.title, inferred_fields)
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
    # exclude_none：priority/duration 現在允許留空，若這次更新沒帶，
    # 保留原本的值，不要被 None 覆蓋掉
    task.update(taskInput.model_dump(exclude_none=True))

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