import logging
from datetime import datetime, timezone
from core.database import db
from schemas.manual_task import ManualTaskOut, StatusEnum
from core.errors import InvalidRequestError, NotFoundError
from pymongo.errors import BulkWriteError, DuplicateKeyError, PyMongoError

logger = logging.getLogger(__name__)

PRIORITY_RANK = {"Low": 0, "Medium": 1, "High": 2}
PRIORITY_LABEL = {"Low": "低", "Medium": "中", "High": "高"}


# 資料庫用 _id 存任務 id，對外（API、其他模組）一律叫 id
def _to_task(doc: dict) -> dict:
    doc["id"] = doc.pop("_id")
    return doc


def parent_status_and_progress(subtasks: list[dict]) -> tuple[str, dict]:
    done = sum(1 for s in subtasks if s.get("status") == StatusEnum.done)
    if subtasks and done == len(subtasks):
        status = StatusEnum.done
    elif done or any(s.get("status") == StatusEnum.in_progress for s in subtasks):
        status = StatusEnum.in_progress
    else:
        status = StatusEnum.todo
    return status.value, {"done": done, "total": len(subtasks)}


def _with_parent_fields(parent: dict, subtasks: list[dict]) -> dict:
    """主任務的狀態與進度不存資料庫，讀取時才算，避免和子任務不一致。"""
    parent["status"], parent["progress"] = parent_status_and_progress(subtasks)
    # 明確給 None：ManualTaskOut 的 duration 預設 60，主任務不能套用
    parent["priority"] = None
    parent["duration"] = None
    return parent


def _with_parents_computed(tasks: list[dict]) -> list[dict]:
    subtasks_by_parent: dict[str, list[dict]] = {}
    for task in tasks:
        if task.get("parent_id"):
            subtasks_by_parent.setdefault(task["parent_id"], []).append(task)
    for task in tasks:
        if task.get("is_parent"):
            _with_parent_fields(task, subtasks_by_parent.get(task["id"], []))
    return tasks


def _as_utc(value: datetime | None) -> datetime | None:
    # Mongo 讀回的 datetime 不帶時區但存的是 UTC，要補上才能和請求帶來的時間比較
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _rank(priority) -> int:
    return PRIORITY_RANK.get(priority, PRIORITY_RANK["Medium"])


def validate_stage_due_dates(parent_due_date: datetime | None, stages: list[dict]) -> None:
    """
    stages 依階段順序排列。有填截止日時：子任務不能晚於主任務，後面的階段不能早於前面的階段。
    沒填截止日的階段不參與比對。
    """
    parent_due = _as_utc(parent_due_date)
    latest_due = None
    latest_due_stage = 0
    for number, stage in enumerate(stages, start=1):
        due = _as_utc(stage.get("due_date"))
        if due is None:
            continue
        if parent_due is not None and due > parent_due:
            raise InvalidRequestError(f"階段 {number} 的截止日不能晚於主任務的截止日")
        if latest_due is not None and due < latest_due:
            raise InvalidRequestError(f"階段 {number} 的截止日不能早於階段 {latest_due_stage} 的截止日")
        latest_due, latest_due_stage = due, number


def validate_stage_priorities(stages: list[dict]) -> None:
    for number in range(2, len(stages) + 1):
        current, previous = stages[number - 1]["priority"], stages[number - 2]["priority"]
        if _rank(current) > _rank(previous):
            raise InvalidRequestError(
                f"階段 {number} 的優先序（{PRIORITY_LABEL.get(current, current)}）"
                f"不能高於階段 {number - 1}（{PRIORITY_LABEL.get(previous, previous)}），優先序為高 > 中 > 低"
            )


def validate_stage_chain(parent_due_date: datetime | None, stages: list[dict]) -> None:
    """新增、修改子任務和主任務截止日、排程頁拖拉、排程精靈都用這個檢查階段之間的限制。"""
    validate_stage_priorities(stages)
    validate_stage_due_dates(parent_due_date, stages)


def adjust_inferred_priorities(stages: list[dict], inferred_indexes: set[int]) -> list[int]:
    """
    AI 推斷的優先序比前一個階段高時，調成和前一個階段一樣；使用者填的不動，交給 validate_stage_priorities。
    依序處理，前一個被調低時後面的會跟著比對調低後的值。回傳被調整的階段編號。
    """
    adjusted = []
    for index in sorted(inferred_indexes):
        if index == 0:
            continue
        previous = stages[index - 1]["priority"]
        if _rank(stages[index]["priority"]) > _rank(previous):
            stages[index]["priority"] = previous
            adjusted.append(index + 1)
    return adjusted


def completed_at_after_status_change(previous_status, previous_completed_at, new_status, now: datetime):
    """本來就是 Done 要保留原值，否則每次編輯已完成的任務都會把它算成這週完成。"""
    if new_status != StatusEnum.done:
        return None
    if previous_status == StatusEnum.done:
        return previous_completed_at
    return now


async def get_manual_task_by_idempotency_key(user_id: str, idempotency_key: str) -> dict | None:
    doc = await db.manual_tasks.find_one({"user_id": user_id, "idempotency_key": idempotency_key})
    if not doc:
        return None
    task = _to_task(doc)
    if task.get("is_parent"):
        _with_parent_fields(task, await get_subtasks(task["id"], user_id))
    return task


def _is_duplicate_key_error(error: PyMongoError) -> bool:
    # insert_many 遇到重複的 key 丟的是 BulkWriteError，不是 DuplicateKeyError
    if isinstance(error, DuplicateKeyError):
        return True
    if isinstance(error, BulkWriteError):
        return any(e.get("code") == 11000 for e in error.details.get("writeErrors", []))
    return False


async def get_subtasks(parent_id: str, user_id: str) -> list[dict]:
    """依階段排序的子任務。"""
    docs = await db.manual_tasks.find({"user_id": user_id, "parent_id": parent_id}).to_list(length=None)
    return sorted((_to_task(doc) for doc in docs), key=lambda t: t.get("stage") or 0)


async def create_manual_task_with_subtasks(parent: dict, subtasks: list[dict], idempotency_key: str | None = None) -> dict:
    """
    一次寫入主任務和子任務（文件用 _id）。回傳主任務，subtasks 欄位放依階段排序的子任務。

    測試用的 mongomock 不支援交易，所以寫入失敗時刪掉這次已寫入的文件，不留下只有一半的主任務。
    """
    parent = dict(parent)
    if idempotency_key:
        parent["idempotency_key"] = idempotency_key
    docs = [parent, *subtasks]
    try:
        await db.manual_tasks.insert_many(docs)
    except PyMongoError as e:
        await db.manual_tasks.delete_many({"_id": {"$in": [doc["_id"] for doc in docs]}})
        # 同一個 key 的請求同時送達，另一個已經建立成功，回傳那一筆
        existing = (
            await get_manual_task_by_idempotency_key(parent["user_id"], idempotency_key)
            if idempotency_key and _is_duplicate_key_error(e) else None
        )
        if existing is None:
            raise
        return {**existing, "subtasks": await get_subtasks(existing["id"], existing["user_id"])}

    created_subtasks = [_to_task(dict(doc)) for doc in subtasks]
    created_parent = _with_parent_fields(_to_task(dict(parent)), created_subtasks)
    created_parent.pop("idempotency_key", None)
    return {**created_parent, "subtasks": created_subtasks}


async def insert_subtask(parent_id: str, user_id: str, subtask: dict, position: int) -> None:
    """在 position 插入子任務（文件用 _id），原本 position 以後的階段編號加 1。"""
    await db.manual_tasks.update_many(
        {"user_id": user_id, "parent_id": parent_id, "stage": {"$gte": position}},
        {"$inc": {"stage": 1}},
    )
    await db.manual_tasks.insert_one({**subtask, "user_id": user_id, "parent_id": parent_id, "stage": position})


async def convert_to_parent(task_id: str, user_id: str) -> None:
    """一般任務新增第 1 個子任務後變成主任務：本身的優先序、時長、狀態與 AI 推斷結果都交給子任務。"""
    await db.manual_tasks.update_one(
        {"_id": task_id, "user_id": user_id},
        {
            "$set": {"is_parent": True, "inferred_fields": [], "updated": datetime.now(timezone.utc)},
            "$unset": {"priority": "", "duration": "", "inference_reason": "", "status": "", "completed_at": ""},
        },
    )


async def delete_subtask(subtask: dict) -> None:
    """刪除子任務，後面的階段編號往前遞補。"""
    await db.manual_tasks.delete_one({"_id": subtask["id"], "user_id": subtask["user_id"]})
    await db.manual_tasks.update_many(
        {"user_id": subtask["user_id"], "parent_id": subtask["parent_id"], "stage": {"$gt": subtask["stage"]}},
        {"$inc": {"stage": -1}},
    )


async def delete_parent_with_subtasks(parent_id: str, user_id: str) -> None:
    await db.manual_tasks.delete_many({"user_id": user_id, "parent_id": parent_id})
    await db.manual_tasks.delete_one({"_id": parent_id, "user_id": user_id})


async def create_manual_task(task: ManualTaskOut, idempotency_key: str | None = None) -> dict:
    doc = task.model_dump()
    doc["_id"] = doc.pop("id")
    if idempotency_key:
        doc["idempotency_key"] = idempotency_key
    try:
        await db.manual_tasks.insert_one(doc)
    except DuplicateKeyError:
        # 同一個 key 的請求同時送達，另一個已經建立成功，回傳那一筆
        existing = await get_manual_task_by_idempotency_key(task.user_id, idempotency_key) if idempotency_key else None
        if existing is None:
            raise
        return existing
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
        "completed_at": doc.get("completed_at"),
    }

async def get_manual_task_by_id(task_id: str, user_id: str):
    task = await db.manual_tasks.find_one({"_id": task_id, "user_id": user_id})
    if not task:
        raise NotFoundError("Task not found")
    task = _to_task(task)
    if task.get("is_parent"):
        _with_parent_fields(task, await get_subtasks(task_id, user_id))
    return task

async def get_manual_tasks_by_user_id(user_id: str):
    tasks = await db.manual_tasks.find({"user_id": user_id}).to_list()
    return _with_parents_computed([_to_task(task) for task in tasks])

async def reorder_manual_tasks(user_id: str, items: list[dict]):
    """
    寫回拖拉排序後的 priority 和 sort_order。sort_order 由呼叫端依跨來源的完整清單指定。

    先確認每個 id 都屬於這個使用者，避免竄改別人的任務。
    不用 update_manual_task_by_id：順序沒變（modified_count 為 0）在這裡是正常情況，不該丟 400。
    """
    if not items:
        return []

    own_tasks = {task["id"]: task for task in await get_manual_tasks_by_user_id(user_id)}

    unknown_ids = [item["task_id"] for item in items if item["task_id"] not in own_tasks]
    if unknown_ids:
        raise InvalidRequestError(f"包含不屬於你的任務 id: {unknown_ids}")

    _validate_reordered_stages(own_tasks, items)

    now = datetime.now(timezone.utc)
    for item in items:
        await db.manual_tasks.update_one(
            {"_id": item["task_id"], "user_id": user_id},
            {"$set": {"sort_order": item["sort_order"], "priority": item["priority"], "updated": now}},
        )

    return await get_manual_tasks_by_user_id(user_id)


def _validate_reordered_stages(own_tasks: dict[str, dict], items: list[dict]) -> None:
    """套用拖拉後的優先序再檢查每個受影響的主任務；先檢查完才寫入，違反時資料保持不變。"""
    new_priority = {item["task_id"]: item["priority"] for item in items}
    if any(own_tasks[task_id].get("is_parent") for task_id in new_priority):
        raise InvalidRequestError("主任務沒有優先序，不能排序")

    affected_parents = {own_tasks[task_id]["parent_id"] for task_id in new_priority if own_tasks[task_id].get("parent_id")}
    for parent_id in affected_parents:
        stages = sorted(
            (t for t in own_tasks.values() if t.get("parent_id") == parent_id),
            key=lambda t: t.get("stage") or 0,
        )
        validate_stage_priorities([{**t, "priority": new_priority.get(t["id"], t.get("priority"))} for t in stages])


async def validate_task_change(task: dict, changes: dict) -> None:
    """
    修改主任務或子任務前檢查階段之間的限制；一般任務不檢查。
    task 是目前的內容，changes 是要寫入的欄位。
    """
    if task.get("is_parent"):
        if "due_date" in changes:
            validate_stage_due_dates(changes["due_date"], await get_subtasks(task["id"], task["user_id"]))
        return
    if not task.get("parent_id"):
        return
    parent = await get_manual_task_by_id(task["parent_id"], task["user_id"])
    stages = [{**s, **changes} if s["id"] == task["id"] else s for s in await get_subtasks(task["parent_id"], task["user_id"])]
    validate_stage_chain(parent.get("due_date"), stages)


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
    # id 對應 _id，不能更新；主任務的狀態與進度是讀取時算的，不存
    computed = {"id", "progress", "status"} if data.get("is_parent") else {"id", "progress"}
    fields = {key: value for key, value in data.items() if key not in computed}
    result = await db.manual_tasks.update_one({"_id": task_id}, {"$set": fields})
    if result.modified_count == 0:
        raise InvalidRequestError("No valid fields to update")
    doc = await db.manual_tasks.find_one({"_id": task_id})
    if doc is None:
        raise NotFoundError("Task not found")
    task = _to_task(doc)
    if task.get("is_parent"):
        _with_parent_fields(task, await get_subtasks(task_id, task["user_id"]))
    return task

async def delete_manual_task_by_id(task_id: str):
    result = await db.manual_tasks.delete_one({"_id": task_id})
    if result.deleted_count == 0:
        raise NotFoundError("Task not found")
