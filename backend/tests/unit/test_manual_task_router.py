# 直接呼叫 router 函式，測試 LLM 推斷、任務擁有者、保留原值、只能操作自己的任務等規則
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID
from core.errors import NotFoundError

import routers.manual_task as manual_task_router
from core.database import db
from schemas.manual_task import ManualTaskInput, ManualTaskUpdate

mock_user = {"sub": "test_user_123"}


def _task_input(**overrides):
    fields = dict(
        title="期末報告", description="整理資料並簡報", status="To Do",
        priority="Low", duration=30, inference_hint="提醒",
    )
    fields.update(overrides)
    return ManualTaskInput(**fields)


async def _create(task_input, idempotency_key=None):
    return await manual_task_router.create_manual_task(
        request=MagicMock(), taskInput=task_input, clerk_user=mock_user, idempotency_key=idempotency_key
    )


@pytest.fixture
def created_tasks(monkeypatch):
    """收集 router 交給 crud 要存起來的任務（不真的寫資料庫）。"""
    saved = []

    async def fake_create(task, idempotency_key=None):
        saved.append(task)
        return task

    monkeypatch.setattr(manual_task_router.manual_task_crud, "create_manual_task", fake_create)
    return saved


@pytest.fixture
def infer_calls(monkeypatch):
    """把 LLM 換成固定回覆（priority=High、duration=120），並記錄它被問了幾次、問了什麼。"""
    calls = []

    async def fake_infer(title, description, hint):
        calls.append((title, description, hint))
        return {"priority": "High", "duration": 120, "reason": "看起來很重要"}

    monkeypatch.setattr(manual_task_router, "infer_missing_task_fields", fake_infer)
    return calls


# ---------- 建立任務：priority / duration 有沒有填，一共 4 種組合 ----------

@pytest.mark.asyncio
async def test_create_manual_task_does_not_ask_llm_when_priority_and_duration_are_given(created_tasks, infer_calls):
    """priority 和 duration 都填了 → 不問 LLM，照使用者填的存，也沒有任何「AI 推斷」的標記。"""
    await _create(_task_input(priority="Low", duration=30))

    task = created_tasks[0]
    assert infer_calls == []
    assert (task.priority, task.duration) == ("Low", 30)
    assert task.inferred_fields == []
    assert task.inference_reason is None


@pytest.mark.asyncio
async def test_create_manual_task_infers_both_when_priority_and_duration_are_missing(created_tasks, infer_calls):
    """priority 和 duration 都沒填 → 兩個都用 LLM 推斷，並記錄哪些欄位是推斷的和理由。"""
    await _create(_task_input(priority=None, duration=None))

    task = created_tasks[0]
    assert infer_calls == [("期末報告", "整理資料並簡報", "提醒")]
    assert (task.priority, task.duration) == ("High", 120)
    assert task.inferred_fields == ["priority", "duration"]
    assert task.inference_reason == "看起來很重要"


@pytest.mark.asyncio
async def test_create_manual_task_infers_only_duration_and_keeps_users_priority(created_tasks, infer_calls):
    """只有 duration 沒填 → 只推斷 duration；使用者自己選的 priority 不能被 LLM 的推斷值覆蓋。"""
    await _create(_task_input(priority="Low", duration=None))

    task = created_tasks[0]
    assert (task.priority, task.duration) == ("Low", 120)  # LLM 說 High，但使用者選的 Low 要保留
    assert task.inferred_fields == ["duration"]


@pytest.mark.asyncio
async def test_create_manual_task_infers_only_priority_and_keeps_users_duration(created_tasks, infer_calls):
    """只有 priority 沒填 → 只推斷 priority；使用者自己填的 duration 不能被 LLM 的推斷值覆蓋。"""
    await _create(_task_input(priority=None, duration=30))

    task = created_tasks[0]
    assert (task.priority, task.duration) == ("High", 30)  # LLM 說 120 分鐘，但使用者填的 30 要保留
    assert task.inferred_fields == ["priority"]


# ---------- 建立任務：擁有者與識別碼 ----------

@pytest.mark.asyncio
async def test_create_manual_task_owner_is_the_logged_in_user(created_tasks, infer_calls):
    """建立任務時，擁有者一律是登入者本人；每個任務有自己獨一無二的 id，建立與更新時間相同。"""
    await _create(_task_input())
    await _create(_task_input())

    first, second = created_tasks
    assert first.user_id == second.user_id == "test_user_123"
    assert first.id != second.id
    UUID(first.id)  # 是合法的 UUID，不是隨便一個字串
    assert first.created == first.updated


@pytest.mark.asyncio
async def test_create_manual_task_with_used_idempotency_key_returns_existing_task(monkeypatch, created_tasks, infer_calls):
    """同一個 Idempotency-Key 重送 → 回傳第一次建立的任務，不再建立、也不再呼叫 LLM。"""
    existing = {"id": "t-first", "user_id": "test_user_123", "title": "期末報告"}

    async def fake_get_by_key(user_id, key):
        return existing if (user_id, key) == ("test_user_123", "key-1") else None

    monkeypatch.setattr(manual_task_router.manual_task_crud, "get_manual_task_by_idempotency_key", fake_get_by_key)

    result = await _create(_task_input(priority=None, duration=None), idempotency_key="key-1")

    assert result is existing
    assert created_tasks == []
    assert infer_calls == []


# ---------- 更新任務 ----------

@pytest.mark.asyncio
async def test_update_manual_task_keeps_original_values_for_fields_not_provided(monkeypatch):
    """更新時沒帶的欄位（priority、duration）保留原本的值，不會被空值蓋掉；有帶的欄位（title）換成新值。"""
    existing = {
        "id": "t1", "user_id": "test_user_123", "title": "舊標題", "description": "描述",
        "status": "To Do", "priority": "High", "duration": 90,
        "updated": datetime(2023, 1, 1, tzinfo=timezone.utc),
    }
    saved = {}

    async def fake_get(task_id, user_id):
        return dict(existing)

    async def fake_update(task_id, data):
        saved.update(data)
        return data

    monkeypatch.setattr(manual_task_router.manual_task_crud, "get_manual_task_by_id", fake_get)
    monkeypatch.setattr(manual_task_router.manual_task_crud, "update_manual_task_by_id", fake_update)

    await manual_task_router.update_manual_task("t1", ManualTaskUpdate(title="新標題"), clerk_user=mock_user)

    assert saved["title"] == "新標題"
    assert saved["priority"] == "High"
    assert saved["duration"] == 90
    assert saved["updated"] > existing["updated"]  # 更新時間有刷新


@pytest.fixture
def saved_update(monkeypatch):
    """讓 router 讀到 existing_task 指定的任務，並收集 router 交給 crud 要寫入的內容。"""
    state = {"existing": {}, "saved": {}}

    async def fake_get(task_id, user_id):
        return dict(state["existing"])

    async def fake_update(task_id, data):
        state["saved"].update(data)
        return data

    monkeypatch.setattr(manual_task_router.manual_task_crud, "get_manual_task_by_id", fake_get)
    monkeypatch.setattr(manual_task_router.manual_task_crud, "update_manual_task_by_id", fake_update)
    return state


def _existing_task(**overrides):
    task = {
        "id": "t1", "user_id": "test_user_123", "title": "標題", "description": "描述",
        "status": "To Do", "priority": "High", "duration": 90, "completed_at": None,
        "updated": datetime(2023, 1, 1, tzinfo=timezone.utc),
    }
    task.update(overrides)
    return task


@pytest.mark.asyncio
async def test_update_manual_task_to_done_records_completed_at(saved_update):
    saved_update["existing"] = _existing_task(status="In Progress")

    await manual_task_router.update_manual_task("t1", ManualTaskUpdate(status="Done"), clerk_user=mock_user)

    assert saved_update["saved"]["completed_at"] == saved_update["saved"]["updated"]


@pytest.mark.asyncio
async def test_update_manual_task_keeps_completed_at_when_still_done_or_status_not_given(saved_update):
    """已完成的任務改標題、或再送一次 Done，完成時間都不能被刷新。"""
    done_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    saved_update["existing"] = _existing_task(status="Done", completed_at=done_at)

    await manual_task_router.update_manual_task("t1", ManualTaskUpdate(title="新標題"), clerk_user=mock_user)
    assert saved_update["saved"]["completed_at"] == done_at

    await manual_task_router.update_manual_task("t1", ManualTaskUpdate(status="Done"), clerk_user=mock_user)
    assert saved_update["saved"]["completed_at"] == done_at


@pytest.mark.asyncio
async def test_update_manual_task_back_from_done_clears_completed_at(saved_update):
    saved_update["existing"] = _existing_task(status="Done", completed_at=datetime(2026, 10, 1, tzinfo=timezone.utc))

    await manual_task_router.update_manual_task("t1", ManualTaskUpdate(status="To Do"), clerk_user=mock_user)

    assert saved_update["saved"]["completed_at"] is None


@pytest.mark.asyncio
async def test_create_manual_task_already_done_is_completed_at_creation(created_tasks, infer_calls):
    await _create(_task_input(status="Done"))
    await _create(_task_input(status="To Do"))

    done_task, todo_task = created_tasks
    assert done_task.completed_at == done_task.created
    assert todo_task.completed_at is None


# ---------- 只能動自己的任務（用真的 crud 加記憶體資料庫，才測得到 router 與 crud 的串接）----------

async def _insert_alice_task(task_id):
    await db.manual_tasks.insert_one({"_id": task_id, "user_id": "alice", "title": "Alice 的任務"})


async def _remove_task(task_id):
    await db.manual_tasks.delete_many({"_id": task_id})


@pytest.mark.asyncio
async def test_get_manual_task_hides_other_users_task():
    """使用者 bob 查 alice 的任務 → 404，看不到內容。"""
    await _insert_alice_task("router-t1")
    try:
        with pytest.raises(NotFoundError):
            await manual_task_router.get_manual_task("router-t1", clerk_user={"sub": "bob"})
    finally:
        await _remove_task("router-t1")


@pytest.mark.asyncio
async def test_update_manual_task_refuses_other_users_task_and_leaves_it_unchanged():
    """使用者 bob 更新 alice 的任務 → 404，alice 的任務內容不會被改動。"""
    await _insert_alice_task("router-t2")
    try:
        with pytest.raises(NotFoundError):
            await manual_task_router.update_manual_task(
                "router-t2", ManualTaskUpdate(title="被 bob 改掉了"), clerk_user={"sub": "bob"}
            )
        assert (await db.manual_tasks.find_one({"_id": "router-t2"}))["title"] == "Alice 的任務"
    finally:
        await _remove_task("router-t2")


@pytest.mark.asyncio
async def test_delete_manual_task_refuses_other_users_task_and_keeps_it():
    """使用者 bob 刪除 alice 的任務 → 404，任務仍在資料庫裡。"""
    await _insert_alice_task("router-t3")
    try:
        with pytest.raises(NotFoundError):
            await manual_task_router.delete_manual_task("router-t3", clerk_user={"sub": "bob"})
        assert await db.manual_tasks.find_one({"_id": "router-t3"}) is not None
    finally:
        await _remove_task("router-t3")


# ---------- 階段任務（用記憶體資料庫，測 router 的規則與 crud 的串接）----------

import pytest_asyncio
from core.errors import InvalidRequestError
from schemas.manual_task import SubtaskCreate

STAGE_USER = {"sub": "router_stage_user"}


@pytest_asyncio.fixture
async def stage_db():
    yield db.manual_tasks
    await db.manual_tasks.delete_many({"user_id": STAGE_USER["sub"]})


@pytest.fixture
def subtask_infer_calls(monkeypatch):
    """把批次推斷換成依序回覆 replies 的值，並記錄每次的參數。"""
    state = {"calls": [], "replies": []}

    async def fake_infer(parent_title, parent_description, subtasks):
        state["calls"].append((parent_title, parent_description, [s["title"] for s in subtasks]))
        return state["replies"][: len(subtasks)]

    monkeypatch.setattr(manual_task_router, "infer_missing_subtask_fields", fake_infer)
    return state


@pytest.fixture
def deleted_events(monkeypatch):
    """記錄 router 要求刪除哪些行事曆事件。"""
    calls = []

    async def fake_delete(user_id, event_ids):
        calls.append(list(event_ids))

    monkeypatch.setattr(manual_task_router, "delete_upcoming_calendar_events", fake_delete)
    return calls


async def _create_staged(subtasks, **parent_fields):
    fields = dict(title="期末報告", description="資料結構", subtasks=subtasks)
    fields.update(parent_fields)
    return await manual_task_router.create_manual_task(
        request=MagicMock(), taskInput=ManualTaskInput(**fields), clerk_user=STAGE_USER, idempotency_key=None,
    )


def _sub(title, **fields):
    return {"title": title, **fields}


async def _add(task_id, **fields):
    return await manual_task_router.add_subtask(
        request=MagicMock(), task_id=task_id, subtaskInput=SubtaskCreate(**fields), clerk_user=STAGE_USER,
        idempotency_key=None,
    )


async def _stage_docs(parent_id):
    docs = await db.manual_tasks.find({"parent_id": parent_id}).sort("stage", 1).to_list(length=None)
    return docs


@pytest.mark.asyncio
async def test_ac1_creates_parent_and_subtasks_in_given_order(stage_db, subtask_infer_calls):
    """AC1：一次建立 → 1 個主任務加 N 個子任務，依填寫順序成為階段 1～N；回應包含主任務與子任務。"""
    result = await _create_staged([
        _sub("蒐集資料", priority="High", duration=30),
        _sub("寫初稿", priority="Medium", duration=90),
    ])

    assert result["is_parent"] is True
    assert result["progress"] == {"done": 0, "total": 2}
    assert [(s["title"], s["stage"], s["parent_id"]) for s in result["subtasks"]] == [
        ("蒐集資料", 1, result["id"]), ("寫初稿", 2, result["id"]),
    ]
    assert [d["title"] for d in await _stage_docs(result["id"])] == ["蒐集資料", "寫初稿"]
    assert subtask_infer_calls["calls"] == []


@pytest.mark.asyncio
async def test_ac5_only_subtasks_missing_fields_are_inferred_in_one_call_with_parent_context(stage_db, subtask_infer_calls):
    """AC5：需要 AI 推斷的子任務一起送一次，參考主任務的標題和描述；都填了的子任務不送。"""
    subtask_infer_calls["replies"] = [
        {"priority": "Low", "duration": 45, "reason": "理由一"},
        {"priority": "Low", "duration": 50, "reason": "理由二"},
    ]

    result = await _create_staged([
        _sub("一", priority="High", duration=30),
        _sub("二"),
        _sub("三", priority="Low"),
    ])

    assert subtask_infer_calls["calls"] == [("期末報告", "資料結構", ["二", "三"])]
    second, third = result["subtasks"][1], result["subtasks"][2]
    assert (second["priority"], second["duration"], second["inferred_fields"]) == ("Low", 45, ["priority", "duration"])
    assert (third["priority"], third["duration"], third["inferred_fields"]) == ("Low", 50, ["duration"])


@pytest.mark.asyncio
async def test_ac6_inferred_priority_higher_than_previous_stage_is_lowered_and_reported(stage_db, subtask_infer_calls):
    """AC6：AI 推斷的優先序比前一個階段高 → 調成和前一個階段一樣，回應列出被調整的階段。"""
    subtask_infer_calls["replies"] = [{"priority": "High", "duration": 30, "reason": "AI 覺得很急"}]

    result = await _create_staged([_sub("一", priority="Medium", duration=30), _sub("二", duration=30)])

    assert result["subtasks"][1]["priority"] == "Medium"
    assert result["priority_adjusted_stages"] == [2]


@pytest.mark.asyncio
async def test_ac7_user_priority_higher_than_previous_stage_is_rejected_and_nothing_created(stage_db, subtask_infer_calls):
    """AC7 / AC4：使用者自己填的優先序比前一個階段高 → 400 指出階段，主任務和子任務都不建立。"""
    with pytest.raises(InvalidRequestError) as exc_info:
        await _create_staged([_sub("一", priority="Low", duration=30), _sub("二", priority="High", duration=30)])

    assert "階段 2" in exc_info.value.detail
    assert await stage_db.count_documents({"user_id": STAGE_USER["sub"]}) == 0


@pytest.mark.asyncio
async def test_ac8_subtask_due_after_parent_is_rejected_before_asking_ai(stage_db, subtask_infer_calls):
    """AC8 / AC4：子任務截止日晚於主任務 → 400 指出階段，不建立任何資料，也不浪費一次 AI 呼叫。"""
    with pytest.raises(InvalidRequestError) as exc_info:
        await _create_staged(
            [_sub("一"), _sub("二", due_date=datetime(2030, 2, 1, tzinfo=timezone.utc))],
            due_date=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )

    assert "階段 2" in exc_info.value.detail
    assert subtask_infer_calls["calls"] == []
    assert await stage_db.count_documents({"user_id": STAGE_USER["sub"]}) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("field, value", [
    ("priority", "High"), ("duration", 30), ("inference_hint", "提醒"), ("status", "To Do"),
])
async def test_parent_with_own_priority_duration_hint_or_status_is_rejected(stage_db, field, value):
    """假設 6：建立主任務時帶了 priority、duration、inference_hint 或 status → 400，不靜默忽略。"""
    with pytest.raises(InvalidRequestError):
        await _create_staged([_sub("一", priority="Low", duration=30)], **{field: value})


@pytest.mark.asyncio
async def test_retry_with_same_idempotency_key_returns_first_parent_with_subtasks(stage_db, subtask_infer_calls):
    """假設 13：一次建立帶 Idempotency-Key 重送 → 回傳第一次建立的主任務與子任務，不重複建立。"""
    task_input = ManualTaskInput(title="報告", description="", subtasks=[_sub("一", priority="Low", duration=30)])

    first = await manual_task_router.create_manual_task(
        request=MagicMock(), taskInput=task_input, clerk_user=STAGE_USER, idempotency_key="stage-key",
    )
    second = await manual_task_router.create_manual_task(
        request=MagicMock(), taskInput=task_input, clerk_user=STAGE_USER, idempotency_key="stage-key",
    )

    assert second["id"] == first["id"]
    assert [s["id"] for s in second["subtasks"]] == [s["id"] for s in first["subtasks"]]
    assert await stage_db.count_documents({"user_id": STAGE_USER["sub"]}) == 2


# ---------- 新增子任務 ----------

async def _three_stage_parent(subtask_infer_calls, priorities=("High", "Medium", "Low"), dues=(None, None, None), parent_due=None):
    return await _create_staged(
        [_sub(f"階段{i}", priority=p, duration=30, due_date=d) for i, (p, d) in enumerate(zip(priorities, dues), start=1)],
        due_date=parent_due,
    )


@pytest.mark.asyncio
async def test_ac10_insert_at_position_renumbers_and_defaults_to_last(stage_db, subtask_infer_calls):
    """AC10：指定位置插入，後面的階段編號加 1；沒指定位置時放在最後。"""
    parent = await _three_stage_parent(subtask_infer_calls)

    await _add(parent["id"], title="插在 2", priority="Medium", duration=30, position=2)
    await _add(parent["id"], title="放最後", priority="Low", duration=30)

    assert [d["title"] for d in await _stage_docs(parent["id"])] == ["階段1", "插在 2", "階段2", "階段3", "放最後"]


@pytest.mark.asyncio
async def test_ac10_inserted_priority_must_fit_between_neighbours(stage_db, subtask_infer_calls):
    """AC10 / AC7：插入的子任務優先序比前一個高或比後一個低 → 400，其他階段不變。"""
    parent = await _three_stage_parent(subtask_infer_calls)

    with pytest.raises(InvalidRequestError):
        await _add(parent["id"], title="比前一個高", priority="High", duration=30, position=3)
    with pytest.raises(InvalidRequestError):
        await _add(parent["id"], title="比後一個低", priority="Low", duration=30, position=2)

    assert [d["stage"] for d in await _stage_docs(parent["id"])] == [1, 2, 3]


@pytest.mark.asyncio
async def test_ac10_inserted_due_date_must_fit_between_neighbours(stage_db, subtask_infer_calls):
    """AC10 / AC8：插入的子任務截止日早於前一個階段 → 400。"""
    parent = await _three_stage_parent(
        subtask_infer_calls, dues=(datetime(2030, 1, 5, tzinfo=timezone.utc), None, datetime(2030, 1, 20, tzinfo=timezone.utc)),
    )

    with pytest.raises(InvalidRequestError):
        await _add(parent["id"], title="太早", priority="Medium", duration=30, position=2,
                   due_date=datetime(2030, 1, 1, tzinfo=timezone.utc))


@pytest.mark.asyncio
async def test_ac10_inferred_priority_of_inserted_subtask_is_lowered_to_previous_stage(stage_db, subtask_infer_calls):
    """AC10 / AC6：插入時 AI 推斷的優先序比前一個階段高 → 調成和前一個階段一樣；推斷參考主任務的標題和描述。"""
    parent = await _three_stage_parent(subtask_infer_calls, priorities=("Medium", "Medium", "Low"))
    subtask_infer_calls["replies"] = [{"priority": "High", "duration": 40, "reason": "AI"}]

    result = await _add(parent["id"], title="AI 來填", position=2)

    assert subtask_infer_calls["calls"] == [("期末報告", "資料結構", ["AI 來填"])]
    assert (await _stage_docs(parent["id"]))[1]["priority"] == "Medium"
    assert result["priority_adjusted_stages"] == [2]


@pytest.mark.asyncio
async def test_ac11_parent_with_ten_subtasks_cannot_get_more(stage_db, subtask_infer_calls):
    """AC11：已經有 10 個子任務 → 400，不新增。"""
    parent = await _create_staged([_sub(f"{i}", priority="Low", duration=30) for i in range(10)])

    with pytest.raises(InvalidRequestError):
        await _add(parent["id"], title="第 11 個", priority="Low", duration=30)

    assert len(await _stage_docs(parent["id"])) == 10


async def _insert_plain_task(task_id, **fields):
    doc = {
        "_id": task_id, "user_id": STAGE_USER["sub"], "title": "一般任務", "description": "說明",
        "status": "In Progress", "priority": "High", "duration": 90, "inferred_fields": ["priority"],
        "inference_reason": "AI 理由", "inference_hint": "給 AI 的提醒", "calendar_event_id": None,
    }
    doc.update(fields)
    await db.manual_tasks.insert_one(doc)


@pytest.mark.asyncio
async def test_ac12_first_subtask_turns_plain_task_into_parent_and_clears_own_fields(stage_db, subtask_infer_calls):
    """AC12：一般任務新增第 1 個子任務 → 變成主任務，本身的優先序、時長、AI 推斷理由清空。"""
    await _insert_plain_task("plain-1")

    result = await _add("plain-1", title="第一階段", priority="High", duration=90)

    assert result["is_parent"] is True
    assert (result["priority"], result["duration"], result.get("inference_reason")) == (None, None, None)
    assert [(s["title"], s["stage"]) for s in result["subtasks"]] == [("第一階段", 1)]
    stored = await db.manual_tasks.find_one({"_id": "plain-1"})
    assert stored["is_parent"] is True
    for field in ("priority", "duration", "inference_reason", "inference_hint", "status", "completed_at"):
        assert stored.get(field) is None, field
    assert stored["inferred_fields"] == []
    # 原本是 In Progress，轉換後依子任務（To Do）計算
    assert result["status"] == "To Do"


@pytest.mark.asyncio
@pytest.mark.parametrize("fields, reason", [
    ({"status": "Done"}, "已完成"),
    ({"calendar_event_id": "ev-1"}, "行事曆"),
])
async def test_ac13_done_or_scheduled_plain_task_cannot_get_subtasks(stage_db, subtask_infer_calls, fields, reason):
    """AC13：已完成或已寫入行事曆的一般任務不能新增子任務，訊息說明原因，任務不變。"""
    await _insert_plain_task("plain-2", **fields)

    with pytest.raises(InvalidRequestError) as exc_info:
        await _add("plain-2", title="階段", priority="Low", duration=30)

    assert reason in exc_info.value.detail
    assert (await db.manual_tasks.find_one({"_id": "plain-2"})).get("is_parent") is None


@pytest.mark.asyncio
async def test_ac14_subtask_cannot_have_subtasks(stage_db, subtask_infer_calls):
    """AC14：不能對子任務再新增子任務（只有兩層）。"""
    parent = await _three_stage_parent(subtask_infer_calls)

    with pytest.raises(InvalidRequestError):
        await _add(parent["subtasks"][0]["id"], title="第三層", priority="Low", duration=30)


@pytest.mark.asyncio
async def test_ac15_other_users_task_returns_404(stage_db):
    """AC15：對別人的任務新增子任務 → 404，和查詢一樣。"""
    await db.manual_tasks.insert_one({"_id": "alice-stage-task", "user_id": "alice", "title": "Alice 的任務", "status": "To Do"})
    try:
        with pytest.raises(NotFoundError):
            await _add("alice-stage-task", title="偷塞", priority="Low", duration=30)
        assert await db.manual_tasks.count_documents({"parent_id": "alice-stage-task"}) == 0
    finally:
        await db.manual_tasks.delete_many({"_id": "alice-stage-task"})


# ---------- 修改 ----------

async def _put(task_id, **fields):
    return await manual_task_router.update_manual_task(task_id, ManualTaskUpdate(**fields), clerk_user=STAGE_USER)


@pytest.mark.asyncio
@pytest.mark.parametrize("field, value", [
    ("status", "Done"), ("priority", "High"), ("duration", 30), ("inference_hint", "提醒"),
])
async def test_ac17_ac19_parent_status_priority_duration_cannot_be_set(stage_db, subtask_infer_calls, field, value):
    """AC17 / AC19 / 假設 6：PUT 主任務帶了 status、priority、duration 或 inference_hint → 400。"""
    parent = await _three_stage_parent(subtask_infer_calls)

    with pytest.raises(InvalidRequestError):
        await _put(parent["id"], **{field: value})


@pytest.mark.asyncio
async def test_ac19_parent_title_description_and_due_date_can_be_edited(stage_db, subtask_infer_calls):
    """AC19：主任務可以修改標題、描述、截止日；狀態仍依子任務計算，不會被存進資料庫。"""
    parent = await _three_stage_parent(subtask_infer_calls)

    result = await _put(parent["id"], title="新標題", description="新描述", due_date=datetime(2030, 3, 1, tzinfo=timezone.utc))

    assert (result["title"], result["description"], result["status"]) == ("新標題", "新描述", "To Do")
    assert "status" not in await db.manual_tasks.find_one({"_id": parent["id"]})


@pytest.mark.asyncio
async def test_ac19_parent_due_date_earlier_than_a_subtask_is_rejected(stage_db, subtask_infer_calls):
    """AC19：主任務的截止日改到早於任何一個子任務的截止日 → 400，截止日不變。"""
    parent = await _three_stage_parent(subtask_infer_calls, dues=(None, datetime(2030, 1, 20, tzinfo=timezone.utc), None))

    with pytest.raises(InvalidRequestError):
        await _put(parent["id"], due_date=datetime(2030, 1, 10, tzinfo=timezone.utc))

    assert (await db.manual_tasks.find_one({"_id": parent["id"]})).get("due_date") is None


@pytest.mark.asyncio
async def test_ac20_put_subtask_that_breaks_stage_chain_is_rejected_and_unchanged(stage_db, subtask_infer_calls):
    """AC20：PUT 子任務讓它的優先序高於前一個階段 → 400，資料保持不變；符合限制的修改照常更新。"""
    parent = await _three_stage_parent(subtask_infer_calls)  # 高、中、低
    stage3 = parent["subtasks"][2]

    with pytest.raises(InvalidRequestError):
        await _put(stage3["id"], priority="High", title="不該存進去")
    assert (await db.manual_tasks.find_one({"_id": stage3["id"]}))["title"] == "階段3"

    updated = await _put(stage3["id"], priority="Medium", status="In Progress")
    assert (updated["priority"], updated["status"]) == ("Medium", "In Progress")


@pytest.mark.asyncio
async def test_ac38_update_cannot_change_parent_id_stage_or_is_parent(stage_db, subtask_infer_calls):
    """AC38：ManualTaskUpdate 不接受 parent_id、stage、is_parent，client 不能把子任務掛到別的主任務或改階段編號。"""
    assert not {"parent_id", "stage", "is_parent"} & set(ManualTaskUpdate.model_fields)


# ---------- 刪除 ----------

@pytest.mark.asyncio
async def test_ac28_deleting_parent_deletes_subtasks_and_their_calendar_events(stage_db, subtask_infer_calls, deleted_events):
    """AC28：刪除主任務 → 主任務和所有子任務都刪掉，並要求刪除子任務的行事曆事件。"""
    parent = await _three_stage_parent(subtask_infer_calls)
    await db.manual_tasks.update_one({"_id": parent["subtasks"][0]["id"]}, {"$set": {"calendar_event_id": "ev-1"}})
    await db.manual_tasks.update_one({"_id": parent["subtasks"][2]["id"]}, {"$set": {"calendar_event_id": "ev-3"}})

    await manual_task_router.delete_manual_task(parent["id"], clerk_user=STAGE_USER)

    assert deleted_events == [["ev-1", "ev-3"]]
    assert await stage_db.count_documents({"user_id": STAGE_USER["sub"]}) == 0


@pytest.mark.asyncio
async def test_ac29_deleting_subtask_deletes_its_event_and_renumbers(stage_db, subtask_infer_calls, deleted_events):
    """AC29：刪除子任務 → 刪它的行事曆事件，後面的階段往前遞補。"""
    parent = await _three_stage_parent(subtask_infer_calls)
    stage2_id = parent["subtasks"][1]["id"]
    await db.manual_tasks.update_one({"_id": stage2_id}, {"$set": {"calendar_event_id": "ev-2"}})

    await manual_task_router.delete_manual_task(stage2_id, clerk_user=STAGE_USER)

    assert deleted_events == [["ev-2"]]
    assert [(d["title"], d["stage"]) for d in await _stage_docs(parent["id"])] == [("階段1", 1), ("階段3", 2)]


@pytest.mark.asyncio
async def test_ac30_last_remaining_subtask_cannot_be_deleted(stage_db, subtask_infer_calls, deleted_events):
    """AC30：主任務只剩一個子任務 → 這個子任務不能刪，400 並提示改刪主任務。"""
    parent = await _create_staged([_sub("唯一", priority="Low", duration=30)])

    with pytest.raises(InvalidRequestError) as exc_info:
        await manual_task_router.delete_manual_task(parent["subtasks"][0]["id"], clerk_user=STAGE_USER)

    assert "主任務" in exc_info.value.detail
    assert deleted_events == []
    assert len(await _stage_docs(parent["id"])) == 1


@pytest.mark.asyncio
async def test_ac32_ac33_tasks_are_kept_when_deleting_events_fails(stage_db, subtask_infer_calls, monkeypatch):
    """AC32 / AC33：刪事件失敗（要求重新連接或 Google 暫時失敗）→ 例外往外丟，主任務和子任務全部保留。"""
    from core.errors import ExternalServiceError

    parent = await _three_stage_parent(subtask_infer_calls)
    await db.manual_tasks.update_one({"_id": parent["subtasks"][0]["id"]}, {"$set": {"calendar_event_id": "ev-1"}})

    async def failing_delete(user_id, event_ids):
        raise ExternalServiceError("刪除 Google Calendar 事件失敗，請重試")

    monkeypatch.setattr(manual_task_router, "delete_upcoming_calendar_events", failing_delete)

    with pytest.raises(ExternalServiceError):
        await manual_task_router.delete_manual_task(parent["id"], clerk_user=STAGE_USER)

    assert await stage_db.count_documents({"user_id": STAGE_USER["sub"]}) == 4


@pytest.mark.asyncio
async def test_ac34_deleting_plain_task_does_not_touch_calendar(stage_db, deleted_events):
    """AC34：一般任務的刪除行為不變，就算有行事曆事件也不刪。"""
    await _insert_plain_task("plain-3", calendar_event_id="ev-plain")

    await manual_task_router.delete_manual_task("plain-3", clerk_user=STAGE_USER)

    assert deleted_events == []
    assert await db.manual_tasks.find_one({"_id": "plain-3"}) is None


@pytest.mark.asyncio
async def test_ac6_inferred_priority_lower_than_user_filled_next_stage_is_raised(stage_db, subtask_infer_calls):
    """AC6：一次建立時階段 1 交給 AI（推斷成中）、階段 2 使用者填高 → 階段 1 調成高，建立成功並回報被調整的階段。"""
    subtask_infer_calls["replies"] = [{"priority": "Medium", "duration": 30, "reason": "AI"}]

    result = await _create_staged([_sub("一", duration=30), _sub("二", priority="High", duration=30)])

    assert [s["priority"] for s in result["subtasks"]] == ["High", "High"]
    assert result["priority_adjusted_stages"] == [1]


@pytest.mark.asyncio
async def test_ac10_inferred_priority_of_inserted_subtask_is_raised_to_next_stage(stage_db, subtask_infer_calls):
    """AC10 / AC6：插在中間、AI 推斷的優先序比後一個階段低 → 調成和後一個階段一樣，不回 400。"""
    parent = await _three_stage_parent(subtask_infer_calls)  # 高、中、低
    subtask_infer_calls["replies"] = [{"priority": "Low", "duration": 40, "reason": "AI"}]

    result = await _add(parent["id"], title="AI 來填", position=2)

    assert [d["priority"] for d in await _stage_docs(parent["id"])] == ["High", "Medium", "Medium", "Low"]
    assert result["priority_adjusted_stages"] == [2]
