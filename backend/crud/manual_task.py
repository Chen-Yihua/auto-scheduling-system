import logging
from datetime import datetime, timezone
from core.database import db
from core.datetimes import to_utc_datetime
from schemas.manual_task import MAX_SUBTASKS, ManualTaskOut, StatusEnum
from core.errors import InvalidRequestError, NotFoundError
from pymongo.errors import BulkWriteError, DuplicateKeyError, PyMongoError

logger = logging.getLogger(__name__)

PRIORITY_RANK = {"Low": 0, "Medium": 1, "High": 2}
LAST_SUBTASK_DETAIL = "主任務只剩這一個子任務，不能刪除；要刪除請改刪主任務"
PRIORITY_LABEL = {"Low": "低", "Medium": "中", "High": "高"}
TASK_NOT_FOUND_DETAIL = "Task not found"


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


def _ordered_subtasks(parent: dict, candidates: dict[str, dict]) -> list[dict]:
    """
    依主任務 subtask_ids 的順序取出子任務，階段編號是在陣列裡的位置（ADR 0004）。
    不在陣列裡的子任務（寫入一半失敗留下的）不算。
    """
    ordered = []
    for subtask_id in parent.get("subtask_ids") or []:
        subtask = candidates.get(subtask_id)
        if subtask is None or subtask.get("parent_id") != parent["id"]:
            continue
        subtask["stage"] = len(ordered) + 1
        ordered.append(subtask)
    return ordered


def _with_parents_computed(tasks: list[dict]) -> list[dict]:
    """主任務算出狀態與進度、子任務算出階段編號；不在任何主任務順序裡的子任務不回傳。"""
    by_id = {task["id"]: task for task in tasks}
    listed_subtask_ids = set()
    for task in tasks:
        if task.get("is_parent"):
            subtasks = _ordered_subtasks(task, by_id)
            listed_subtask_ids.update(s["id"] for s in subtasks)
            _with_parent_fields(task, subtasks)
    return [t for t in tasks if not t.get("parent_id") or t["id"] in listed_subtask_ids]


def _rank(priority) -> int:
    return PRIORITY_RANK.get(priority, PRIORITY_RANK["Medium"])


def validate_stage_due_dates(parent_due_date: datetime | None, stages: list[dict]) -> None:
    """
    stages 依階段順序排列。有填截止日時：子任務不能晚於主任務，後面的階段不能早於前面的階段。
    沒填截止日的階段不參與比對。
    """
    parent_due = to_utc_datetime(parent_due_date)
    latest_due = None
    latest_due_stage = 0
    for number, stage in enumerate(stages, start=1):
        due = to_utc_datetime(stage.get("due_date"))
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
    AI 推斷的優先序要落在前後兩個階段之間：比前一個階段高就調成前一個，比後面使用者填的最高值低就調成那個值。
    使用者填的不動，彼此衝突時交給 validate_stage_priorities。依序處理，前一個被調整時後面的會比對調整後的值。
    回傳被調整的階段編號。
    """
    adjusted = []
    for index in sorted(inferred_indexes):
        priority = stages[index]["priority"]
        # 後面推斷的階段之後只會被調到不高於這個階段，所以下限只看使用者填的
        later_fixed = [s["priority"] for i, s in enumerate(stages) if i > index and i not in inferred_indexes]
        floor = max(later_fixed, key=_rank) if later_fixed else None
        ceiling = stages[index - 1]["priority"] if index > 0 else None
        if ceiling is not None and _rank(priority) > _rank(ceiling):
            priority = ceiling
        elif floor is not None and _rank(priority) < _rank(floor):
            priority = floor
        if priority != stages[index]["priority"]:
            stages[index]["priority"] = priority
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
    """依主任務 subtask_ids 排序的子任務，附上階段編號。"""
    parent = await db.manual_tasks.find_one({"_id": parent_id, "user_id": user_id})
    if not parent:
        return []
    docs = await db.manual_tasks.find(
        {"user_id": user_id, "_id": {"$in": parent.get("subtask_ids") or []}}
    ).to_list(length=None)
    return _ordered_subtasks(_to_task(parent), {doc["_id"]: _to_task(doc) for doc in docs})


async def create_manual_task_with_subtasks(parent: dict, subtasks: list[dict], idempotency_key: str | None = None) -> dict:
    """
    一次寫入主任務和子任務（文件用 _id）。回傳主任務，subtasks 欄位放依階段排序的子任務。

    測試用的 mongomock 不支援交易，所以寫入失敗時刪掉這次已寫入的文件，不留下只有一半的主任務。
    """
    parent = {**parent, "subtask_ids": [doc["_id"] for doc in subtasks]}
    if idempotency_key:
        parent["idempotency_key"] = idempotency_key
    # 主任務放最後：中途失敗時，已寫入的子任務不在任何主任務的順序裡，讀取時不會出現
    docs = [*subtasks, parent]
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

    created_subtasks = [{**_to_task(dict(doc)), "stage": stage} for stage, doc in enumerate(subtasks, start=1)]
    created_parent = _with_parent_fields(_to_task(dict(parent)), created_subtasks)
    created_parent.pop("idempotency_key", None)
    return {**created_parent, "subtasks": created_subtasks}


async def insert_subtask(
    parent_id: str, user_id: str, subtask: dict, position: int,
    idempotency_key: str | None = None, convert: bool = False,
) -> bool:
    """
    在 position（從 1 開始）插入子任務（文件用 _id）。convert=True 時同時把一般任務轉成主任務。

    先寫入子任務，再用一次主任務的更新放進 subtask_ids；數量上限、插入位置、可以轉換的條件都寫在
    那次更新的 filter 裡，同時送出的請求也不會超過上限或產生空號（ADR 0004）。條件不成立時刪掉剛寫入的
    子任務並丟 400。同一個 Idempotency-Key 已經用過時什麼都不改，回傳 False。
    """
    doc = {**subtask, "user_id": user_id, "parent_id": parent_id}
    doc.pop("stage", None)
    if idempotency_key:
        doc["idempotency_key"] = idempotency_key
    # 重複的 key 在第一步就被唯一索引擋下，不會動到主任務
    try:
        await db.manual_tasks.insert_one(doc)
    except DuplicateKeyError:
        if idempotency_key:
            return False
        raise

    now = datetime.now(timezone.utc)
    if convert:
        condition = {
            "is_parent": {"$ne": True},
            "parent_id": None,
            "status": {"$ne": StatusEnum.done.value},
            "calendar_event_id": None,
        }
        update = {
            "$set": {"is_parent": True, "subtask_ids": [doc["_id"]], "inferred_fields": [], "updated": now},
            # 主任務的優先序、時長、狀態與 AI 推斷結果都交給子任務
            "$unset": {
                "priority": "", "duration": "", "inference_reason": "", "inference_hint": "",
                "status": "", "completed_at": "",
            },
        }
        rejected = "這個任務的狀態已經改變（已完成、已排入行事曆或已拆成階段），請重新整理後再試"
    else:
        # 用 $and：position 是 MAX_SUBTASKS + 1 時兩個條件是同一個欄位，寫成 dict 的 key 會互相蓋掉
        array_conditions: list[dict] = [{f"subtask_ids.{MAX_SUBTASKS - 1}": {"$exists": False}}]
        if position > 1:
            array_conditions.append({f"subtask_ids.{position - 2}": {"$exists": True}})
        condition = {"is_parent": True, "$and": array_conditions}
        update = {
            "$push": {"subtask_ids": {"$each": [doc["_id"]], "$position": position - 1}},
            "$set": {"updated": now},
        }
        rejected = f"子任務已達 {MAX_SUBTASKS} 個上限，或插入位置已經不存在，請重新整理後再試"

    try:
        result = await db.manual_tasks.update_one({"_id": parent_id, "user_id": user_id, **condition}, update)
    except PyMongoError:
        await db.manual_tasks.delete_one({"_id": doc["_id"]})
        raise
    if result.matched_count == 0:
        await db.manual_tasks.delete_one({"_id": doc["_id"]})
        raise InvalidRequestError(rejected)
    return True


async def delete_subtask(subtask: dict) -> None:
    """
    從主任務的順序移除子任務再刪掉文件。「至少還有 2 個」寫在同一次更新的 filter 裡，
    同時送出的刪除也不會刪到一個都不剩。
    """
    result = await db.manual_tasks.update_one(
        {
            "_id": subtask["parent_id"], "user_id": subtask["user_id"],
            "subtask_ids": subtask["id"], "subtask_ids.1": {"$exists": True},
        },
        {"$pull": {"subtask_ids": subtask["id"]}, "$set": {"updated": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise InvalidRequestError(LAST_SUBTASK_DETAIL)
    # 這一步失敗時，子任務已不在順序裡，讀取時不會出現
    await db.manual_tasks.delete_one({"_id": subtask["id"], "user_id": subtask["user_id"]})


async def delete_parent_with_subtasks(parent_id: str, user_id: str) -> None:
    # 先刪主任務：之後刪子任務失敗時，留下的子任務沒有主任務，讀取時不會出現
    await db.manual_tasks.delete_one({"_id": parent_id, "user_id": user_id})
    await db.manual_tasks.delete_many({"user_id": user_id, "parent_id": parent_id})


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
        raise NotFoundError(TASK_NOT_FOUND_DETAIL)
    task = _to_task(task)
    return await _with_stage_fields(task)


async def _with_stage_fields(task: dict) -> dict:
    """主任務算出狀態與進度；子任務算出階段編號，不在主任務順序裡的子任務當作不存在。"""
    if task.get("is_parent"):
        _with_parent_fields(task, await get_subtasks(task["id"], task["user_id"]))
    elif task.get("parent_id"):
        stage = next((s["stage"] for s in await get_subtasks(task["parent_id"], task["user_id"]) if s["id"] == task["id"]), None)
        if stage is None:
            raise NotFoundError(TASK_NOT_FOUND_DETAIL)
        task["stage"] = stage
    return task

async def get_manual_tasks_by_user_id(user_id: str):
    tasks = await db.manual_tasks.find({"user_id": user_id}).to_list()
    return _with_parents_computed([_to_task(task) for task in tasks])

async def write_manual_task_order(user_id: str, items: list[dict]) -> None:
    """
    寫回拖拉排序後的 priority 和 sort_order。sort_order 由呼叫端依跨來源的完整清單指定。

    呼叫端要先確認每個 id 都屬於這個使用者，並用 validate_reordered_stages 檢查過。
    不用 update_manual_task_by_id：順序沒變（modified_count 為 0）在這裡是正常情況，不該丟 400。
    """
    now = datetime.now(timezone.utc)
    for item in items:
        await db.manual_tasks.update_one(
            {"_id": item["task_id"], "user_id": user_id},
            {"$set": {"sort_order": item["sort_order"], "priority": item["priority"], "updated": now}},
        )


def validate_reordered_stages(own_tasks: dict[str, dict], items: list[dict]) -> None:
    """套用拖拉後的優先序再檢查每個受影響的主任務；items 的 id 都要在 own_tasks 裡。"""
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

async def clear_calendar_event_id(task_id: str, user_id: str, calendar_event_id: str) -> None:
    """事件已從 Google 刪掉、任務卻留下時呼叫，讓任務能重新排程。只清還指向這個事件的任務。"""
    await db.manual_tasks.update_one(
        {"_id": task_id, "user_id": user_id, "calendar_event_id": calendar_event_id},
        {"$set": {"calendar_event_id": None, "updated": datetime.now(timezone.utc)}},
    )

async def update_manual_task_by_id(task_id: str, data: dict):
    logger.debug("Updating manual task %s with data=%s", task_id, data)
    # id 對應 _id，不能更新；狀態（主任務）、進度、階段編號是讀取時算的；
    # 階段關係只由插入、刪除子任務的流程改，這裡寫回讀到的舊值會蓋掉同時進行的插入或刪除
    computed = {"id", "progress", "stage", "subtask_ids", "parent_id", "is_parent"}
    if data.get("is_parent"):
        computed.add("status")
    fields = {key: value for key, value in data.items() if key not in computed}
    result = await db.manual_tasks.update_one({"_id": task_id}, {"$set": fields})
    if result.modified_count == 0:
        raise InvalidRequestError("No valid fields to update")
    doc = await db.manual_tasks.find_one({"_id": task_id})
    if doc is None:
        raise NotFoundError(TASK_NOT_FOUND_DETAIL)
    task = _to_task(doc)
    if task.get("is_parent") or task.get("parent_id"):
        return await _with_stage_fields(task)
    return task

async def delete_manual_task_by_id(task_id: str):
    result = await db.manual_tasks.delete_one({"_id": task_id})
    if result.deleted_count == 0:
        raise NotFoundError(TASK_NOT_FOUND_DETAIL)
