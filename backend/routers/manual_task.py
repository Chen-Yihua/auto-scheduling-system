import logging
from fastapi import APIRouter, Depends, Request
from crud import manual_task as manual_task_crud
from services.task_inference import infer_missing_task_fields
from schemas.manual_task import ManualTaskInput, ManualTaskOut, ManualTaskUpdate
from core.security import get_current_clerk_user
from datetime import datetime, timezone
from uuid import uuid4
from core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manual-tasks", tags=["manual-tasks"])

# 沒填 priority/duration 時會呼叫 Gemini，限流避免 LLM 額度被燒光
@router.post("/", response_model=ManualTaskOut, status_code=201)
@limiter.limit("20/minute")
async def create_manual_task(
    request: Request,
    taskInput: ManualTaskInput,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """建立任務。沒填 priority/duration 時用 LLM 從 title/description 推斷。"""
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
        id=str(uuid4()),
        user_id=clerk_user["sub"],  # 不接受 client 指定
        created=now,
        updated=now,
        inferred_fields=inferred_fields,
        inference_reason=inference_reason,
    )

    logger.debug("Creating manual task: %s (inferred_fields=%s)", task.title, inferred_fields)
    new_task = await manual_task_crud.create_manual_task(task)
    return new_task

@router.get("/me", response_model=list[ManualTaskOut])
async def get_user_tasks(
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """取得目前登入者的所有任務。沒有任務時回空陣列，不是 404。"""
    tasks = await manual_task_crud.get_manual_tasks_by_user_id(clerk_user["sub"])
    return tasks

@router.get("/{task_id}", response_model=ManualTaskOut)
async def get_manual_task(
    task_id: str,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """取得指定的任務，只能查自己的。"""
    return await manual_task_crud.get_manual_task_by_id(task_id, clerk_user["sub"])

@router.put("/{task_id}", response_model=ManualTaskOut)
async def update_manual_task(
    task_id: str,
    taskInput: ManualTaskUpdate,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """更新指定的任務，只能改自己的。"""
    task = await manual_task_crud.get_manual_task_by_id(task_id, clerk_user["sub"])
    now = datetime.now(timezone.utc)
    task.update({"updated": now})
    # exclude_none：沒帶的欄位保留原值，不被 None 覆蓋
    task.update(taskInput.model_dump(exclude_none=True))

    updated_task = await manual_task_crud.update_manual_task_by_id(task_id, task)
    return updated_task

@router.delete("/{task_id}")
async def delete_manual_task(
    task_id: str,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """刪除指定的任務，只能刪自己的。"""
    await manual_task_crud.get_manual_task_by_id(task_id, clerk_user["sub"])  # 確認是自己的任務，不存在會 404
    await manual_task_crud.delete_manual_task_by_id(task_id)
    return {"task ID": task_id,"deleted": True}