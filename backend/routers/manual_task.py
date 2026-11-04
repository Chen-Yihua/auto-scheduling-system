import logging
from fastapi import APIRouter, Depends, Header, Request
from crud import manual_task as manual_task_crud
from core.errors import InvalidRequestError
from services.google_calendar import delete_upcoming_calendar_events
from services.task_inference import infer_missing_subtask_fields, infer_missing_task_fields
from schemas.manual_task import (
    MAX_SUBTASKS,
    ManualTaskInput,
    ManualTaskOut,
    ManualTaskUpdate,
    ManualTaskWithSubtasksOut,
    StatusEnum,
    SubtaskCreate,
    SubtaskInput,
)
from core.security import get_current_clerk_user
from datetime import datetime, timezone
from uuid import uuid4
from core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manual-tasks", tags=["manual-tasks"])

# 主任務只當容器，這些欄位由子任務決定
PARENT_ONLY_FROM_SUBTASKS = ("priority", "duration", "inference_hint", "status")
PARENT_FIELDS_REJECTED = "主任務不能設定優先序、時長、給 AI 的提醒或狀態，這些由子任務決定"


def _subtask_doc(subtask: dict, user_id: str, now: datetime) -> dict:
    return {
        **subtask,
        "_id": str(uuid4()),
        "user_id": user_id,
        "created": now,
        "updated": now,
        "completed_at": now if subtask.get("status") == StatusEnum.done else None,
    }


async def _fill_inferred_fields(parent_title: str, parent_description: str, subtasks: list[dict]) -> set[int]:
    """
    缺 priority 或 duration 的子任務一起問一次 LLM，直接填回 subtasks。
    回傳 priority 是推斷出來的子任務索引，交給 adjust_inferred_priorities。
    """
    indexes = [i for i, s in enumerate(subtasks) if s.get("priority") is None or s.get("duration") is None]
    if not indexes:
        return set()
    inferences = await infer_missing_subtask_fields(parent_title, parent_description, [subtasks[i] for i in indexes])
    inferred_priority = set()
    for index, inference in zip(indexes, inferences):
        subtask = subtasks[index]
        inferred_fields = []
        if subtask.get("priority") is None:
            subtask["priority"] = inference["priority"]
            inferred_fields.append("priority")
            inferred_priority.add(index)
        if subtask.get("duration") is None:
            subtask["duration"] = inference["duration"]
            inferred_fields.append("duration")
        subtask["inferred_fields"] = inferred_fields
        subtask["inference_reason"] = inference["reason"]
    return inferred_priority


async def _create_with_subtasks(task_input: ManualTaskInput, user_id: str, idempotency_key: str | None) -> dict:
    """先完成所有驗證與 AI 推斷，再一次寫入；任何一步失敗都不留下資料。"""
    if any(getattr(task_input, field) is not None for field in PARENT_ONLY_FROM_SUBTASKS):
        raise InvalidRequestError(PARENT_FIELDS_REJECTED)

    subtasks = [s.model_dump() for s in task_input.subtasks or []]
    # 截止日不需要 AI 結果就能檢查，先擋下，不浪費一次 LLM 呼叫
    manual_task_crud.validate_stage_due_dates(task_input.due_date, subtasks)
    inferred_priority = await _fill_inferred_fields(task_input.title, task_input.description, subtasks)
    adjusted = manual_task_crud.adjust_inferred_priorities(subtasks, inferred_priority)
    manual_task_crud.validate_stage_priorities(subtasks)

    now = datetime.now(timezone.utc)
    parent_id = str(uuid4())
    parent = {
        "_id": parent_id,
        "user_id": user_id,
        "title": task_input.title,
        "description": task_input.description,
        "due_date": task_input.due_date,
        "created": now,
        "updated": now,
        "is_parent": True,
        "inferred_fields": [],
    }
    subtask_docs = [
        {**_subtask_doc(s, user_id, now), "parent_id": parent_id, "stage": stage}
        for stage, s in enumerate(subtasks, start=1)
    ]
    created = await manual_task_crud.create_manual_task_with_subtasks(parent, subtask_docs, idempotency_key)
    return {**created, "priority_adjusted_stages": adjusted}


async def _with_subtasks(task: dict) -> dict:
    if not task.get("is_parent"):
        return task
    return {**task, "subtasks": await manual_task_crud.get_subtasks(task["id"], task["user_id"])}


# 沒填 priority/duration 時會呼叫 Gemini，限流避免 LLM 額度被燒光；帶子任務時一樣只算一次
@router.post("/", response_model=ManualTaskWithSubtasksOut, status_code=201)
@limiter.limit("20/minute")
async def create_manual_task(
    request: Request,
    taskInput: ManualTaskInput,
    clerk_user: dict = Depends(get_current_clerk_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
):
    """
    建立任務。沒填 priority/duration 時用 LLM 從 title/description 推斷。
    帶 subtasks 時建立主任務和依序編號的子任務，回應附上子任務。
    帶相同 Idempotency-Key 的重送請求會回傳第一次建立的任務，不會重複建立。
    """
    if idempotency_key:
        existing = await manual_task_crud.get_manual_task_by_idempotency_key(clerk_user["sub"], idempotency_key)
        if existing:
            return await _with_subtasks(existing)

    if taskInput.subtasks is not None:
        return await _create_with_subtasks(taskInput, clerk_user["sub"], idempotency_key)

    task_data = taskInput.model_dump(exclude={"subtasks"})
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
        completed_at=now if taskInput.status == StatusEnum.done else None,
    )

    logger.debug("Creating manual task: %s (inferred_fields=%s)", task.title, inferred_fields)
    new_task = await manual_task_crud.create_manual_task(task, idempotency_key)
    return new_task


@router.post("/{task_id}/subtasks", response_model=ManualTaskWithSubtasksOut, status_code=201)
@limiter.limit("20/minute")
async def add_subtask(
    request: Request,
    task_id: str,
    subtaskInput: SubtaskCreate,
    clerk_user: dict = Depends(get_current_clerk_user),
):
    """
    在主任務的 position 插入子任務（預設放最後），後面的階段編號加 1。
    對一般任務新增第 1 個子任務時，它會變成主任務。回應是主任務並附上所有子任務。
    """
    user_id = clerk_user["sub"]
    task = await manual_task_crud.get_manual_task_by_id(task_id, user_id)
    if task.get("parent_id"):
        raise InvalidRequestError("子任務不能再拆成子任務")
    if task.get("is_parent"):
        stages = await manual_task_crud.get_subtasks(task_id, user_id)
        if len(stages) >= MAX_SUBTASKS:
            raise InvalidRequestError(f"一個主任務最多只能有 {MAX_SUBTASKS} 個子任務")
    else:
        if task.get("status") == StatusEnum.done:
            raise InvalidRequestError("已完成的任務不能拆成階段")
        if task.get("calendar_event_id"):
            raise InvalidRequestError("已寫入行事曆的任務不能拆成階段")
        stages = []

    position = subtaskInput.position or len(stages) + 1
    if position > len(stages) + 1:
        raise InvalidRequestError(f"插入位置要在 1～{len(stages) + 1} 之間")

    new_subtask = SubtaskInput(**subtaskInput.model_dump(exclude={"position"})).model_dump()
    chain = [*stages[: position - 1], new_subtask, *stages[position - 1:]]
    manual_task_crud.validate_stage_due_dates(task.get("due_date"), chain)
    inferred_priority = await _fill_inferred_fields(task["title"], task.get("description") or "", [new_subtask])
    adjusted = manual_task_crud.adjust_inferred_priorities(chain, {position - 1} if inferred_priority else set())
    manual_task_crud.validate_stage_priorities(chain)

    if not task.get("is_parent"):
        await manual_task_crud.convert_to_parent(task_id, user_id)
    now = datetime.now(timezone.utc)
    await manual_task_crud.insert_subtask(task_id, user_id, _subtask_doc(new_subtask, user_id, now), position)

    parent = await manual_task_crud.get_manual_task_by_id(task_id, user_id)
    return {**await _with_subtasks(parent), "priority_adjusted_stages": adjusted}


@router.get("/me", response_model=list[ManualTaskOut])
async def get_user_tasks(
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """取得目前登入者的所有任務（主任務和子任務各一筆）。沒有任務時回空陣列，不是 404。"""
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
    """
    更新指定的任務，只能改自己的。主任務只能改標題、描述、截止日；
    主任務和子任務的修改都要符合階段之間的優先序與截止日限制。
    """
    task = await manual_task_crud.get_manual_task_by_id(task_id, clerk_user["sub"])
    # exclude_none：沒帶的欄位保留原值，不被 None 覆蓋
    changes = taskInput.model_dump(exclude_none=True)
    if task.get("is_parent") and any(field in changes for field in PARENT_ONLY_FROM_SUBTASKS):
        raise InvalidRequestError(PARENT_FIELDS_REJECTED)
    await manual_task_crud.validate_task_change(task, changes)

    now = datetime.now(timezone.utc)
    task.update({"updated": now})
    if taskInput.status is not None:
        task["completed_at"] = manual_task_crud.completed_at_after_status_change(
            task.get("status"), task.get("completed_at"), taskInput.status, now
        )
    task.update(changes)

    updated_task = await manual_task_crud.update_manual_task_by_id(task_id, task)
    return updated_task

@router.delete("/{task_id}")
async def delete_manual_task(
    task_id: str,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    刪除指定的任務，只能刪自己的。刪除主任務會一併刪除所有子任務；
    主任務和子任務會先刪掉子任務在 Google Calendar 上還沒開始的事件，成功後才刪任務，
    所以刪事件失敗時任務都還在，可以重試。一般任務不動行事曆。
    """
    user_id = clerk_user["sub"]
    task = await manual_task_crud.get_manual_task_by_id(task_id, user_id)  # 確認是自己的任務，不存在會 404

    if task.get("is_parent"):
        subtasks = await manual_task_crud.get_subtasks(task_id, user_id)
        await delete_upcoming_calendar_events(user_id, [s["calendar_event_id"] for s in subtasks if s.get("calendar_event_id")])
        await manual_task_crud.delete_parent_with_subtasks(task_id, user_id)
    elif task.get("parent_id"):
        if len(await manual_task_crud.get_subtasks(task["parent_id"], user_id)) <= 1:
            raise InvalidRequestError("主任務只剩這一個子任務，不能刪除；要刪除請改刪主任務")
        await delete_upcoming_calendar_events(user_id, [task["calendar_event_id"]] if task.get("calendar_event_id") else [])
        await manual_task_crud.delete_subtask(task)
    else:
        await manual_task_crud.delete_manual_task_by_id(task_id)
    return {"task ID": task_id,"deleted": True}
