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
async def test_delete_manual_task_refuses_other_users_task_and_keeps_it(monkeypatch):
    """issue-30 AC18：使用者 bob 刪除 alice 已排入行事曆的任務 → 404，不呼叫 Google 刪事件，任務仍在資料庫裡。"""
    await _insert_alice_task("router-t3")
    await db.manual_tasks.update_one({"_id": "router-t3"}, {"$set": {"calendar_event_id": "ev-alice"}})
    event_calls = []

    async def record_delete(user_id, event_ids):
        event_calls.append((user_id, list(event_ids)))

    monkeypatch.setattr(manual_task_router, "delete_calendar_events", record_delete)
    try:
        with pytest.raises(NotFoundError):
            await manual_task_router.delete_manual_task("router-t3", clerk_user={"sub": "bob"})
        assert event_calls == []
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

    monkeypatch.setattr(manual_task_router, "delete_calendar_events", fake_delete)
    return calls


async def _create_staged(subtasks, idempotency_key=None, **parent_fields):
    fields = dict(title="期末報告", description="資料結構", subtasks=subtasks)
    fields.update(parent_fields)
    return await manual_task_router.create_manual_task(
        request=MagicMock(), taskInput=ManualTaskInput(**fields), clerk_user=STAGE_USER, idempotency_key=idempotency_key,
    )


def _sub(title, **fields):
    return {"title": title, **fields}


async def _add(task_id, idempotency_key=None, **fields):
    return await manual_task_router.add_subtask(
        request=MagicMock(), task_id=task_id, subtaskInput=SubtaskCreate(**fields), clerk_user=STAGE_USER,
        idempotency_key=idempotency_key,
    )


async def _stage_docs(parent_id):
    # 階段順序以主任務的 subtask_ids 為準（ADR 0004）
    return await manual_task_router.manual_task_crud.get_subtasks(parent_id, STAGE_USER["sub"])


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
    """AC6 / issue-32 AC1、AC2：AI 推斷的優先序比前一個階段高 → 調成和前一個階段一樣；回應寫出被調整的子任務 id、原本與調整後的值，比較的是前一個階段。"""
    subtask_infer_calls["replies"] = [{"priority": "High", "duration": 30, "reason": "AI 覺得很急"}]

    result = await _create_staged([_sub("一", priority="Medium", duration=30), _sub("二", duration=30)])

    first, second = result["subtasks"]
    assert second["priority"] == "Medium"
    assert result["priority_adjustments"] == [
        {"subtask_id": second["id"], "from_priority": "High", "to_priority": "Medium", "compared_subtask_id": first["id"]},
    ]
    assert "priority_adjusted_stages" not in result


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
    stages = await _stage_docs(parent["id"])
    assert stages[1]["priority"] == "Medium"
    # issue-32 AC5：回應寫出這個階段的調整內容，比較的是前一個階段
    assert result["priority_adjustments"] == [
        {"subtask_id": stages[1]["id"], "from_priority": "High", "to_priority": "Medium", "compared_subtask_id": stages[0]["id"]},
    ]


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
    assert not {"parent_id", "stage", "is_parent", "subtask_ids"} & set(ManualTaskUpdate.model_fields)


# ---------- 刪除（issue-30：任務和它在 Google Calendar 上的事件一起刪）----------

import asyncio
from core.error_codes import status_for_error_code
from core.errors import ConflictError, ExternalServiceError, ReauthRequiredError
from pymongo.errors import PyMongoError
import services.google_calendar as calendar_service


async def _delete(task_id):
    return await manual_task_router.delete_manual_task(task_id, clerk_user=STAGE_USER)


async def _schedule(task_id, event_id):
    await db.manual_tasks.update_one({"_id": task_id}, {"$set": {"calendar_event_id": event_id}})


async def _doc(task_id):
    return await db.manual_tasks.find_one({"_id": task_id})


async def _user_doc_count():
    return await db.manual_tasks.count_documents({"user_id": STAGE_USER["sub"]})


async def _two_stage_parent(event_ids=(None, None)):
    parent = await _create_staged([_sub("階段1", priority="High", duration=30), _sub("階段2", priority="Low", duration=30)])
    ids = [s["id"] for s in parent["subtasks"]]
    for subtask_id, event_id in zip(ids, event_ids):
        if event_id:
            await _schedule(subtask_id, event_id)
    return parent, ids


async def _one_stage_parent(event_id=None):
    parent = await _create_staged([_sub("唯一", priority="Low", duration=30)])
    only_id = parent["subtasks"][0]["id"]
    if event_id:
        await _schedule(only_id, event_id)
    return parent, only_id


def _not_connected(monkeypatch):
    async def not_connected(clerk_id):
        return False

    monkeypatch.setattr(calendar_service, "is_google_calendar_connected", not_connected)


async def _delete_together(monkeypatch, task_ids):
    """
    同時送出多個刪除：每個請求都通過擁有者檢查、刪完事件後，才一起進入資料庫步驟。
    回傳 (每個請求的結果或例外, 每個請求要求刪除的事件)。
    """
    deleted = []
    all_arrived = asyncio.Event()

    async def delete_after_all_arrive(user_id, event_ids):
        deleted.append(list(event_ids))
        if len(deleted) == len(task_ids):
            all_arrived.set()
        await asyncio.wait_for(all_arrived.wait(), timeout=1)

    monkeypatch.setattr(manual_task_router, "delete_calendar_events", delete_after_all_arrive)
    results = await asyncio.gather(*(_delete(i) for i in task_ids), return_exceptions=True)
    return results, deleted


def _succeeded_or_not_found(results):
    return all(isinstance(r, dict) or isinstance(r, NotFoundError) for r in results)


@pytest.mark.asyncio
async def test_issue30_ac1_deleting_scheduled_plain_task_deletes_its_event(stage_db, deleted_events):
    """issue-30 AC1：已排入行事曆的一般任務 → 刪掉它的事件，任務也刪掉（取代 staged-tasks AC34：一般任務不動行事曆）。"""
    await _insert_plain_task("plain-3", calendar_event_id="ev-plain")

    await _delete("plain-3")

    assert deleted_events == [["ev-plain"]]
    assert await _doc("plain-3") is None


@pytest.mark.asyncio
async def test_issue30_ac2_ac3_deleting_parent_deletes_all_subtasks_and_their_events(stage_db, subtask_infer_calls, deleted_events):
    """issue-30 AC2、AC3：刪除主任務 → 主任務和所有子任務都刪掉，每個子任務的行事曆事件都要求刪除。"""
    parent = await _three_stage_parent(subtask_infer_calls)
    await _schedule(parent["subtasks"][0]["id"], "ev-1")
    await _schedule(parent["subtasks"][2]["id"], "ev-3")

    await _delete(parent["id"])

    assert deleted_events == [["ev-1", "ev-3"]]
    assert await _user_doc_count() == 0


@pytest.mark.asyncio
async def test_issue30_ac4_ac5_deleting_one_of_three_subtasks_only_touches_it_and_renumbers(stage_db, subtask_infer_calls, deleted_events):
    """issue-30 AC4、AC5：三個子任務刪階段 2 → 只刪它和它的事件，其他子任務的欄位與事件不變，階段 3 往前遞補成 2。"""
    parent = await _three_stage_parent(subtask_infer_calls)
    ids = [s["id"] for s in parent["subtasks"]]
    for subtask_id, event_id in zip(ids, ("ev-1", "ev-2", "ev-3")):
        await _schedule(subtask_id, event_id)
    others_before = [await _doc(ids[0]), await _doc(ids[2])]

    await _delete(ids[1])

    assert deleted_events == [["ev-2"]]
    assert [await _doc(ids[0]), await _doc(ids[2])] == others_before
    assert [(d["title"], d["stage"]) for d in await _stage_docs(parent["id"])] == [("階段1", 1), ("階段3", 2)]


@pytest.mark.asyncio
async def test_issue30_ac5_deleting_one_of_two_subtasks_keeps_parent_with_one_subtask(stage_db, subtask_infer_calls, deleted_events):
    """issue-30 AC5：兩個子任務刪階段 1 → 剩一個子任務的主任務照常存在，階段 2 遞補成 1。"""
    parent, ids = await _two_stage_parent(("ev-1", "ev-2"))

    await _delete(ids[0])

    assert deleted_events == [["ev-1"]]
    assert (await _doc(parent["id"]))["is_parent"] is True
    assert [(d["title"], d["stage"], d["calendar_event_id"]) for d in await _stage_docs(parent["id"])] == [("階段2", 1, "ev-2")]


@pytest.mark.asyncio
async def test_issue30_ac6_deleting_only_subtask_deletes_whole_parent(stage_db, subtask_infer_calls, deleted_events):
    """issue-30 AC6：刪主任務唯一的子任務 → 主任務、子任務、事件都刪掉，回應成功（取代 staged-tasks AC30：不能刪）。"""
    parent, only_id = await _one_stage_parent("ev-only")

    result = await _delete(only_id)

    assert result == {"task ID": only_id, "deleted": True}
    assert deleted_events == [["ev-only"]]
    assert await _user_doc_count() == 0


@pytest.mark.asyncio
async def test_issue30_ac7_event_of_completed_subtask_is_deleted_too(stage_db, subtask_infer_calls, deleted_events):
    """issue-30 AC7：子任務已經完成，它的行事曆事件也要刪。"""
    _, ids = await _two_stage_parent(("ev-1", "ev-2"))
    await db.manual_tasks.update_one({"_id": ids[0]}, {"$set": {"status": "Done"}})

    await _delete(ids[0])

    assert deleted_events == [["ev-1"]]
    assert await _doc(ids[0]) is None


@pytest.mark.asyncio
async def test_issue30_ac8_tasks_without_events_are_deleted_without_google_connection(stage_db, subtask_infer_calls, monkeypatch):
    """issue-30 AC8：沒排入行事曆的一般任務、子任務都沒排入的主任務 → 沒有連接 Google 也刪得掉。"""
    _not_connected(monkeypatch)
    await _insert_plain_task("plain-unscheduled")
    parent, _ = await _two_stage_parent()

    await _delete("plain-unscheduled")
    await _delete(parent["id"])

    assert await _user_doc_count() == 0


@pytest.mark.asyncio
async def test_issue30_ac10_scheduled_plain_task_without_connection_is_kept_and_reauth_required(stage_db, monkeypatch):
    """issue-30 AC10：已排入的一般任務，但沒有連接 Google → 409 REAUTH_REQUIRED，任務還在。"""
    _not_connected(monkeypatch)
    await _insert_plain_task("plain-scheduled", calendar_event_id="ev-plain")

    with pytest.raises(ReauthRequiredError) as exc_info:
        await _delete("plain-scheduled")

    assert status_for_error_code(exc_info.value.error_code) == 409
    assert exc_info.value.error_code == "REAUTH_REQUIRED"
    assert await _doc("plain-scheduled") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [
    ReauthRequiredError("Google 授權已失效，請重新連接 Google Calendar"),
    ExternalServiceError("刪除 Google Calendar 事件失敗，請稍後重試"),
], ids=["reauth", "google-failure"])
@pytest.mark.parametrize("target", ["plain", "parent", "one-of-two", "only-subtask"])
async def test_issue30_ac10_ac13_ac16_failed_event_deletion_keeps_every_task(stage_db, subtask_infer_calls, monkeypatch, error, target):
    """issue-30 AC10、AC13、AC16：刪事件失敗（要求重新連接或 Google 暫時失敗）→ 例外往外丟，所有任務都保留，可以重試。"""
    await _insert_plain_task("plain-kept", calendar_event_id="ev-plain")
    two_parent, two_ids = await _two_stage_parent(("ev-1", "ev-2"))
    one_parent, only_id = await _one_stage_parent("ev-only")
    count_before = await _user_doc_count()
    stages_before = [await _stage_docs(two_parent["id"]), await _stage_docs(one_parent["id"])]

    async def failing_delete(user_id, event_ids):
        raise error

    monkeypatch.setattr(manual_task_router, "delete_calendar_events", failing_delete)
    task_id = {"plain": "plain-kept", "parent": two_parent["id"], "one-of-two": two_ids[0], "only-subtask": only_id}[target]

    with pytest.raises(type(error)):
        await _delete(task_id)

    assert await _user_doc_count() == count_before
    assert [await _stage_docs(two_parent["id"]), await _stage_docs(one_parent["id"])] == stages_before


@pytest.mark.asyncio
async def test_issue30_ac17_concurrent_deletes_of_last_two_subtasks_delete_whole_parent(stage_db, subtask_infer_calls, monkeypatch):
    """
    issue-30 AC17：同時刪最後兩個子任務 → 和依序刪除一樣，主任務、兩個子任務與兩個事件都刪掉，兩個請求都成功
    （取代 issue-37 AC1、AC2：後到的回 400、被擋下的清事件 id）。
    """
    _, ids = await _two_stage_parent(("ev-1", "ev-2"))

    results, deleted = await _delete_together(monkeypatch, ids)

    assert all(isinstance(r, dict) for r in results), results
    assert sorted(deleted) == [["ev-1"], ["ev-2"]]
    assert await _user_doc_count() == 0


@pytest.mark.asyncio
async def test_issue30_ac24_same_subtask_deleted_twice_among_three_only_deletes_it(stage_db, subtask_infer_calls, monkeypatch):
    """issue-30 AC24：三個子任務時同一個子任務同時刪兩次 → 只刪它和它的事件，其他子任務不變，兩個請求回成功或 404。"""
    parent = await _three_stage_parent(subtask_infer_calls)
    ids = [s["id"] for s in parent["subtasks"]]
    for subtask_id, event_id in zip(ids, ("ev-1", "ev-2", "ev-3")):
        await _schedule(subtask_id, event_id)
    others_before = [await _doc(ids[0]), await _doc(ids[2])]

    results, deleted = await _delete_together(monkeypatch, [ids[1], ids[1]])

    assert _succeeded_or_not_found(results), results
    assert deleted == [["ev-2"], ["ev-2"]]
    assert [await _doc(ids[0]), await _doc(ids[2])] == others_before
    assert [d["title"] for d in await _stage_docs(parent["id"])] == ["階段1", "階段3"]


@pytest.mark.asyncio
async def test_issue30_ac24_same_subtask_deleted_twice_among_two_keeps_the_other(stage_db, subtask_infer_calls, monkeypatch):
    """issue-30 AC24：兩個子任務時同一個子任務同時刪兩次 → 另一個子任務和它的事件還在，主任務照常存在。"""
    parent, ids = await _two_stage_parent(("ev-1", "ev-2"))
    other_before = await _doc(ids[1])

    results, deleted = await _delete_together(monkeypatch, [ids[0], ids[0]])

    assert _succeeded_or_not_found(results), results
    assert deleted == [["ev-1"], ["ev-1"]]
    assert await _doc(ids[1]) == other_before
    assert [d["id"] for d in await _stage_docs(parent["id"])] == [ids[1]]


@pytest.mark.asyncio
async def test_issue30_ac24_second_request_arriving_after_subtask_was_removed_keeps_the_other(stage_db, subtask_infer_calls, monkeypatch):
    """
    issue-30 AC24：兩個子任務 A、B，同時刪 A 兩次，第二個請求通過擁有者檢查後、進入資料庫步驟前，第一個請求已經刪掉 A
    → 第二個請求回成功，不會把 B 當成唯一的子任務刪掉整個主任務；B 和它的事件還在。
    """
    parent, ids = await _two_stage_parent(("ev-1", "ev-2"))
    other_before = await _doc(ids[1])
    deleted = []

    async def let_first_request_finish(user_id, event_ids):
        deleted.append(list(event_ids))
        if len(deleted) == 1:
            # 這裡是第二個請求：讓第一個請求整個跑完，才回到第二個請求的資料庫步驟
            assert await _delete(ids[0]) == {"task ID": ids[0], "deleted": True}

    monkeypatch.setattr(manual_task_router, "delete_calendar_events", let_first_request_finish)

    assert await _delete(ids[0]) == {"task ID": ids[0], "deleted": True}

    assert deleted == [["ev-1"], ["ev-1"]]
    assert await _doc(ids[1]) == other_before
    assert [d["id"] for d in await _stage_docs(parent["id"])] == [ids[1]]


@pytest.mark.asyncio
async def test_issue30_ac24_retry_after_document_deletion_failed_returns_404(stage_db, subtask_infer_calls, deleted_events, monkeypatch):
    """issue-30 AC24：子任務已移出清單、刪文件時資料庫失敗 → 重試回 404，其他子任務和主任務不變。"""
    parent, ids = await _two_stage_parent(("ev-1", "ev-2"))
    other_before = await _doc(ids[1])
    collection = manual_task_router.manual_task_crud.db.manual_tasks
    real_delete_one = collection.delete_one
    failures = []

    async def fail_once(*args, **kwargs):
        if not failures:
            failures.append(True)
            raise PyMongoError("資料庫暫時失敗")
        return await real_delete_one(*args, **kwargs)

    monkeypatch.setattr(collection, "delete_one", fail_once)

    with pytest.raises(PyMongoError):
        await _delete(ids[0])
    with pytest.raises(NotFoundError):
        await _delete(ids[0])

    assert await _doc(ids[1]) == other_before
    assert [d["id"] for d in await _stage_docs(parent["id"])] == [ids[1]]


@pytest.mark.asyncio
async def test_issue30_ac25_subtask_already_removed_from_list_has_its_document_deleted(stage_db, subtask_infer_calls):
    """issue-30 AC25：子任務已經不在主任務的清單裡、文件還在（前一次刪文件失敗）→ 刪掉這份文件，其他子任務和主任務不變。"""
    parent, ids = await _two_stage_parent()
    other_before = await _doc(ids[1])
    leftover = await manual_task_router.manual_task_crud.get_manual_task_by_id(ids[0], STAGE_USER["sub"])
    await db.manual_tasks.update_one({"_id": parent["id"]}, {"$pull": {"subtask_ids": ids[0]}})

    await manual_task_router._delete_subtask_records(leftover)

    assert await _doc(ids[0]) is None
    assert await _doc(ids[1]) == other_before
    assert [d["id"] for d in await _stage_docs(parent["id"])] == [ids[1]]


@pytest.mark.asyncio
async def test_issue30_ac24_stage_added_meanwhile_retries_and_deletes_only_this_subtask(stage_db, subtask_infer_calls, deleted_events, monkeypatch):
    """
    issue-30 AC24：刪唯一的子任務 A 時，另一個請求剛好新增了階段 B（「至少 2 個」和「只剩它」都不成立）
    → 重新讀取後再試，只刪 A；主任務和 B 都還在。
    """
    parent, only_id = await _one_stage_parent("ev-only")
    crud = manual_task_router.manual_task_crud
    real_delete_parent = crud.delete_parent_if_only_subtask
    added = []

    async def stage_added_just_before(subtask):
        if not added:
            new_stage = {"_id": "issue30-added", "user_id": STAGE_USER["sub"], "title": "新增的", "status": "To Do", "priority": "Low", "duration": 30}
            await crud.insert_subtask(parent["id"], STAGE_USER["sub"], new_stage, position=2)
            added.append(True)
        return await real_delete_parent(subtask)

    monkeypatch.setattr(crud, "delete_parent_if_only_subtask", stage_added_just_before)

    assert await _delete(only_id) == {"task ID": only_id, "deleted": True}

    assert await _doc(only_id) is None
    assert [d["id"] for d in await _stage_docs(parent["id"])] == ["issue30-added"]


@pytest.mark.asyncio
async def test_issue30_ac24_stages_keep_changing_for_three_rounds_returns_request_in_progress(stage_db, subtask_infer_calls, deleted_events, monkeypatch):
    """issue-30 AC24：三輪都碰上別的請求在改階段（兩個條件都不成立、它還在清單裡）→ 409 REQUEST_IN_PROGRESS，所有子任務都還在。"""
    parent, ids = await _two_stage_parent(("ev-1", "ev-2"))
    crud = manual_task_router.manual_task_crud
    attempts = []

    async def never_matches(subtask):
        attempts.append(subtask["id"])
        return False

    monkeypatch.setattr(crud, "delete_subtask", never_matches)
    monkeypatch.setattr(crud, "delete_parent_if_only_subtask", never_matches)

    with pytest.raises(ConflictError) as exc_info:
        await _delete(ids[0])

    assert exc_info.value.error_code == "REQUEST_IN_PROGRESS"
    assert len(attempts) == 6
    assert [d["id"] for d in await _stage_docs(parent["id"])] == ids


@pytest.mark.asyncio
async def test_issue30_ac24_only_subtask_deleted_twice_deletes_whole_parent(stage_db, subtask_infer_calls, monkeypatch):
    """issue-30 AC24、AC6：只有一個子任務時同時刪它兩次 → 主任務、子任務、事件都不在，兩個請求回成功或 404。"""
    _, only_id = await _one_stage_parent("ev-only")

    results, deleted = await _delete_together(monkeypatch, [only_id, only_id])

    assert _succeeded_or_not_found(results), results
    assert deleted == [["ev-only"], ["ev-only"]]
    assert await _user_doc_count() == 0


@pytest.mark.asyncio
async def test_ac6_inferred_priority_lower_than_user_filled_next_stage_is_raised(stage_db, subtask_infer_calls):
    """AC6：一次建立時階段 1 交給 AI（推斷成中）、階段 2 使用者填高 → 階段 1 調成高，建立成功並回報被調整的階段。"""
    subtask_infer_calls["replies"] = [{"priority": "Medium", "duration": 30, "reason": "AI"}]

    result = await _create_staged([_sub("一", duration=30), _sub("二", priority="High", duration=30)])

    first, second = result["subtasks"]
    assert [s["priority"] for s in result["subtasks"]] == ["High", "High"]
    # issue-32 AC1、AC2：被調高時比較的是後面使用者填的階段
    assert result["priority_adjustments"] == [
        {"subtask_id": first["id"], "from_priority": "Medium", "to_priority": "High", "compared_subtask_id": second["id"]},
    ]


@pytest.mark.asyncio
async def test_ac10_inferred_priority_of_inserted_subtask_is_raised_to_next_stage(stage_db, subtask_infer_calls):
    """AC10 / AC6：插在中間、AI 推斷的優先序比後一個階段低 → 調成和後一個階段一樣，不回 400。"""
    parent = await _three_stage_parent(subtask_infer_calls)  # 高、中、低
    subtask_infer_calls["replies"] = [{"priority": "Low", "duration": 40, "reason": "AI"}]

    result = await _add(parent["id"], title="AI 來填", position=2)

    stages = await _stage_docs(parent["id"])
    assert [d["priority"] for d in stages] == ["High", "Medium", "Medium", "Low"]
    # issue-32 AC5：被調高時比較的是後面的既有階段
    assert result["priority_adjustments"] == [
        {"subtask_id": stages[1]["id"], "from_priority": "Low", "to_priority": "Medium", "compared_subtask_id": stages[2]["id"]},
    ]


# ---------- 需求 4：Idempotency-Key 衝突的 error_code ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("existing_parent, subtask_ids, error_code", [
    ("another-task", [], "IDEMPOTENCY_KEY_REUSED"),
    ("task-1", ["other-subtask"], "REQUEST_IN_PROGRESS"),
], ids=["key-used-elsewhere", "still-in-progress"])
async def test_subtask_idempotency_conflicts_have_their_own_error_codes(monkeypatch, existing_parent, subtask_ids, error_code):
    """需求 4：新增子任務時 key 用在別的請求是 IDEMPOTENCY_KEY_REUSED、同一個請求還在處理是 REQUEST_IN_PROGRESS（都是 409）。"""
    from core.errors import AppError
    crud = manual_task_router.manual_task_crud

    async def fake_by_key(user_id, key):
        return {"id": "new-subtask", "parent_id": existing_parent}

    async def fake_get(task_id, user_id):
        return {"id": task_id}

    async def fake_with_subtasks(task):
        return {"id": task["id"], "subtasks": [{"id": s} for s in subtask_ids]}

    monkeypatch.setattr(crud, "get_manual_task_by_idempotency_key", fake_by_key)
    monkeypatch.setattr(crud, "get_manual_task_by_id", fake_get)
    monkeypatch.setattr(manual_task_router, "_with_subtasks", fake_with_subtasks)

    with pytest.raises(AppError) as exc_info:
        await manual_task_router._subtask_result_for_key("task-1", "test_user_123", "key")

    assert exc_info.value.error_code == error_code


# ---------- issue-32：優先序自動調整的清單存進資料庫，重送時回傳同一份 ----------

def _first_key_lookup_misses(monkeypatch):
    """讓第一次用 key 查詢查不到，模擬同一個 key 的另一個請求在這次查詢之後才寫入（同時送達）。"""
    crud = manual_task_router.manual_task_crud
    real_lookup = crud.get_manual_task_by_idempotency_key
    state = {"missed": False}

    async def lookup(user_id, key):
        if not state["missed"]:
            state["missed"] = True
            return None
        return await real_lookup(user_id, key)

    monkeypatch.setattr(crud, "get_manual_task_by_idempotency_key", lookup)


@pytest.mark.asyncio
async def test_issue32_ac4_concurrent_create_hitting_duplicate_returns_adjustments_of_first_write(stage_db, subtask_infer_calls, monkeypatch):
    """issue-32 AC4：同一個 key 的一次建立同時送達、這次撞上重複 → 回應的清單是先寫入那筆存的，不是這次重新算的。"""
    from pymongo.errors import BulkWriteError

    subtask_infer_calls["replies"] = [{"priority": "High", "duration": 30, "reason": "AI"}]
    first = await _create_staged([_sub("一", priority="Medium", duration=30), _sub("二", duration=30)], idempotency_key="ac4-key")
    assert first["priority_adjustments"]

    # 這次的輸入會算出不同的清單（階段 1 被調高）
    subtask_infer_calls["replies"] = [{"priority": "Low", "duration": 30, "reason": "AI"}]
    _first_key_lookup_misses(monkeypatch)

    async def duplicate_insert_many(docs):
        raise BulkWriteError({"writeErrors": [{"code": 11000}]})

    monkeypatch.setattr(stage_db, "insert_many", duplicate_insert_many)

    second = await _create_staged([_sub("一", duration=30), _sub("二", priority="High", duration=30)], idempotency_key="ac4-key")

    assert second["id"] == first["id"]
    assert second["priority_adjustments"] == first["priority_adjustments"]


@pytest.mark.asyncio
async def test_issue32_ac6_concurrent_add_subtask_returns_adjustments_of_first_write(stage_db, subtask_infer_calls, monkeypatch):
    """issue-32 AC6：新增階段同時送達、另一個先寫入（insert_subtask 回 False）→ 回應的清單是先寫入那個階段存的。"""
    parent = await _three_stage_parent(subtask_infer_calls, priorities=("Medium", "Medium", "Low"))
    subtask_infer_calls["replies"] = [{"priority": "High", "duration": 40, "reason": "AI"}]
    first = await _add(parent["id"], idempotency_key="ac6-key", title="AI 來填", position=2)
    assert first["priority_adjustments"]

    _first_key_lookup_misses(monkeypatch)

    async def already_inserted(*args, **kwargs):
        return False

    monkeypatch.setattr(manual_task_router.manual_task_crud, "insert_subtask", already_inserted)

    # 這次自己填了優先序，算出的是空清單
    second = await _add(parent["id"], idempotency_key="ac6-key", title="AI 來填", priority="Medium", duration=40, position=2)

    assert second["priority_adjustments"] == first["priority_adjustments"]


@pytest.mark.asyncio
async def test_issue32_ac7_retry_of_data_stored_before_this_change_returns_empty_adjustments(stage_db):
    """issue-32 AC7：資料庫裡的主任務、子任務沒有這份清單（舊資料）時，重送建立、重送新增都回空清單，不報錯。"""
    user_id = STAGE_USER["sub"]
    now = datetime.now(timezone.utc)
    common = {"user_id": user_id, "description": "", "created": now, "updated": now, "inferred_fields": []}
    await stage_db.insert_many([
        {**common, "_id": "ac7-s1", "title": "一", "parent_id": "ac7-p", "status": "To Do", "priority": "Low", "duration": 30},
        {**common, "_id": "ac7-s2", "title": "二", "parent_id": "ac7-p", "status": "To Do", "priority": "Low", "duration": 30,
         "idempotency_key": "ac7-add-key"},
        {**common, "_id": "ac7-p", "title": "舊主任務", "is_parent": True, "subtask_ids": ["ac7-s1", "ac7-s2"],
         "idempotency_key": "ac7-create-key"},
    ])

    created = await _create_staged([_sub("一", priority="Low", duration=30)], idempotency_key="ac7-create-key")
    added = await _add("ac7-p", idempotency_key="ac7-add-key", title="二", priority="Low", duration=30)

    assert created["id"] == "ac7-p"
    assert created.get("priority_adjustments", []) == []
    assert added.get("priority_adjustments", []) == []


@pytest.mark.asyncio
async def test_issue32_ac14_add_without_adjustment_never_returns_parents_stored_adjustments(stage_db, subtask_infer_calls):
    """issue-32 AC14：主任務建立時存了清單，新增一個沒被調整的階段 → 第一次與重送的回應清單都是空的。"""
    subtask_infer_calls["replies"] = [{"priority": "High", "duration": 30, "reason": "AI"}]
    parent = await _create_staged([_sub("一", priority="Medium", duration=30), _sub("二", duration=30)])
    assert parent["priority_adjustments"]

    first = await _add(parent["id"], idempotency_key="ac14-key", title="三", priority="Low", duration=30)
    retry = await _add(parent["id"], idempotency_key="ac14-key", title="三", priority="Low", duration=30)

    assert first["priority_adjustments"] == []
    assert retry["priority_adjustments"] == []
