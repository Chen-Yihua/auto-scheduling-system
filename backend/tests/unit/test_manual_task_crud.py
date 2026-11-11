"""crud/manual_task.py 的邊界情境：查無資料、沒有變更、刪不到等。"""
import pytest
from core.errors import InvalidRequestError, NotFoundError

import crud.manual_task as manual_task_crud
from pymongo.errors import DuplicateKeyError


# ---------- 只能查自己的任務，回傳的任務用 id 表示（用記憶體資料庫，不 mock 查詢）----------

@pytest.mark.asyncio
async def test_get_manual_task_by_id_returns_own_task_with_id():
    """查自己的任務 → 回傳任務內容，任務 id 放在 id 欄位（跟 API 回傳的格式一致），不是 _id。"""
    await manual_task_crud.db.manual_tasks.insert_one({"_id": "crud-t1", "user_id": "alice", "title": "Alice 的任務"})
    try:
        task = await manual_task_crud.get_manual_task_by_id("crud-t1", "alice")
        assert task["title"] == "Alice 的任務"
        assert task["id"] == "crud-t1"
        assert "_id" not in task
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"_id": "crud-t1"})


@pytest.mark.asyncio
async def test_get_manual_task_by_id_hides_other_users_task():
    """使用者 bob 查 alice 的任務 → 404，不能讓他看到。"""
    await manual_task_crud.db.manual_tasks.insert_one({"_id": "crud-t2", "user_id": "alice", "title": "Alice 的任務"})
    try:
        with pytest.raises(NotFoundError) as exc_info:
            await manual_task_crud.get_manual_task_by_id("crud-t2", "bob")
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"_id": "crud-t2"})


@pytest.mark.asyncio
async def test_get_manual_tasks_by_user_id_returns_only_own_tasks():
    """列出任務只會回傳自己的（不含別人的），每筆的任務 id 都放在 id 欄位。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"_id": "crud-t3", "user_id": "alice", "title": "Alice 的任務一"},
        {"_id": "crud-t4", "user_id": "alice", "title": "Alice 的任務二"},
        {"_id": "crud-t5", "user_id": "bob", "title": "Bob 的任務"},
    ])
    try:
        tasks = await manual_task_crud.get_manual_tasks_by_user_id("alice")
        assert sorted(t["id"] for t in tasks) == ["crud-t3", "crud-t4"]
        assert all("_id" not in t for t in tasks)
    finally:
        await collection.delete_many({"_id": {"$in": ["crud-t3", "crud-t4", "crud-t5"]}})


# ---------- get_manual_task_by_id ----------

@pytest.mark.asyncio
async def test_get_manual_task_by_id_raises_404_when_not_found(monkeypatch):
    """查無此任務 → 404。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find_one", mock_find_one)

    with pytest.raises(NotFoundError) as exc_info:
        await manual_task_crud.get_manual_task_by_id("task1", "uid123")



# ---------- get_manual_tasks_by_user_id ----------

@pytest.mark.asyncio
async def test_get_manual_tasks_by_user_id_returns_empty_list_when_no_tasks(monkeypatch):
    """使用者沒有任何任務 → 回傳空清單，不是 None，呼叫端不用再特別處理。"""
    class FakeCursor:
        async def to_list(self):
            return []

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find", lambda query: FakeCursor())

    result = await manual_task_crud.get_manual_tasks_by_user_id("uid123")

    assert result == []


# ---------- set_calendar_event_id ----------

@pytest.mark.asyncio
async def test_set_calendar_event_id_writes_id_and_does_not_touch_other_tasks():
    """確認排程成功後把 calendar_event_id 寫回去，且只會動到指定的那筆任務。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"_id": "confirm-t1", "user_id": "alice", "title": "任務一"},
        {"_id": "confirm-t2", "user_id": "alice", "title": "任務二"},
    ])
    try:
        await manual_task_crud.set_calendar_event_id("confirm-t1", "alice", "event-abc")

        task1 = await collection.find_one({"_id": "confirm-t1"})
        task2 = await collection.find_one({"_id": "confirm-t2"})
        assert task1["calendar_event_id"] == "event-abc"
        assert task2.get("calendar_event_id") is None
    finally:
        await collection.delete_many({"_id": {"$in": ["confirm-t1", "confirm-t2"]}})


# ---------- write_manual_task_order ----------

def _reorder_item(task_id, priority, sort_order):
    return {"task_id": task_id, "priority": priority, "sort_order": sort_order}


async def _sort_orders(user_id):
    return {t["id"]: (t["sort_order"], t["priority"]) for t in await manual_task_crud.get_manual_tasks_by_user_id(user_id)}


@pytest.mark.asyncio
async def test_write_manual_task_order_writes_sort_order_from_each_item():
    """依每筆傳入的 sort_order 寫回（呼叫端依跨來源的完整清單指定，不是這裡自己算的）。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"_id": "reorder-t1", "user_id": "alice", "title": "任務一", "priority": "Medium"},
        {"_id": "reorder-t2", "user_id": "alice", "title": "任務二", "priority": "Medium"},
        {"_id": "reorder-t3", "user_id": "alice", "title": "任務三", "priority": "Medium"},
    ])
    try:
        await manual_task_crud.write_manual_task_order("alice", [
            _reorder_item("reorder-t3", "Medium", 0),
            _reorder_item("reorder-t1", "Medium", 1),
            _reorder_item("reorder-t2", "Medium", 2),
        ])

        by_id = {task_id: order for task_id, (order, _) in (await _sort_orders("alice")).items()}
        assert by_id == {"reorder-t3": 0, "reorder-t1": 1, "reorder-t2": 2}
    finally:
        await collection.delete_many({"_id": {"$in": ["reorder-t1", "reorder-t2", "reorder-t3"]}})


@pytest.mark.asyncio
async def test_write_manual_task_order_writes_priority_from_which_column_task_was_dropped_in():
    """拖到不同欄（priority）要跟著寫回去——這是三欄式拖拉排序畫面「拖去別欄＝改優先權」的核心行為。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"_id": "reorder-t8", "user_id": "alice", "title": "任務", "priority": "Low"},
    ])
    try:
        await manual_task_crud.write_manual_task_order("alice", [
            _reorder_item("reorder-t8", "High", 0),  # 使用者把它從 Low 欄拖到 High 欄
        ])

        assert (await _sort_orders("alice"))["reorder-t8"] == (0, "High")
    finally:
        await collection.delete_many({"_id": "reorder-t8"})


@pytest.mark.asyncio
async def test_write_manual_task_order_does_not_touch_another_users_task():
    """寫入時也帶 user_id 條件：就算呼叫端漏檢查，別人的任務也不會被改。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"_id": "reorder-t5", "user_id": "bob", "title": "Bob 的任務", "priority": "Medium", "sort_order": 9},
    ])
    try:
        await manual_task_crud.write_manual_task_order("alice", [_reorder_item("reorder-t5", "High", 0)])

        assert (await _sort_orders("bob"))["reorder-t5"] == (9, "Medium")
    finally:
        await collection.delete_many({"_id": "reorder-t5"})


@pytest.mark.asyncio
async def test_write_manual_task_order_same_order_again_does_not_raise():
    """重新提交跟現在一模一樣的順序（sort_order 沒有真的變動）→ 不能因此噴錯。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"_id": "reorder-t6", "user_id": "alice", "title": "任務一", "priority": "Medium", "sort_order": 0},
        {"_id": "reorder-t7", "user_id": "alice", "title": "任務二", "priority": "Medium", "sort_order": 1},
    ])
    try:
        await manual_task_crud.write_manual_task_order("alice", [
            _reorder_item("reorder-t6", "Medium", 0),
            _reorder_item("reorder-t7", "Medium", 1),
        ])
        by_id = {task_id: order for task_id, (order, _) in (await _sort_orders("alice")).items()}
        assert by_id == {"reorder-t6": 0, "reorder-t7": 1}
    finally:
        await collection.delete_many({"_id": {"$in": ["reorder-t6", "reorder-t7"]}})


# ---------- update_manual_task_by_id ----------

@pytest.mark.asyncio
async def test_update_manual_task_by_id_raises_400_when_nothing_modified(monkeypatch):
    """更新後沒有任何欄位真的變動 → 400。"""
    async def mock_update_one(query, update):
        return type("Result", (), {"modified_count": 0})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "update_one", mock_update_one)

    with pytest.raises(InvalidRequestError) as exc_info:
        await manual_task_crud.update_manual_task_by_id("task1", {"title": "沒變"})



@pytest.mark.asyncio
async def test_update_manual_task_by_id_returns_updated_doc(monkeypatch):
    """更新成功 → 重新查一次，回傳更新後的完整任務；傳進來的 id 不會被當成要更新的欄位。"""
    updates = []

    async def mock_update_one(query, update):
        updates.append((query, update))
        return type("Result", (), {"modified_count": 1})()

    async def mock_find_one(query):
        return {"_id": "task1", "title": "新標題"}

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "update_one", mock_update_one)
    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find_one", mock_find_one)

    result = await manual_task_crud.update_manual_task_by_id("task1", {"id": "task1", "title": "新標題"})

    assert updates == [({"_id": "task1"}, {"$set": {"title": "新標題"}})]
    assert result == {"id": "task1", "title": "新標題"}


# ---------- delete_manual_task_by_id ----------

@pytest.mark.asyncio
async def test_delete_manual_task_by_id_raises_404_when_nothing_deleted(monkeypatch):
    """要刪除的任務不存在 → 404。"""
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 0})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "delete_one", mock_delete_one)

    with pytest.raises(NotFoundError) as exc_info:
        await manual_task_crud.delete_manual_task_by_id("task1")



@pytest.mark.asyncio
async def test_delete_manual_task_by_id_succeeds(monkeypatch):
    """刪除任務成功 → 不出錯。"""
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 1})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "delete_one", mock_delete_one)

    # 不丟例外就代表成功
    await manual_task_crud.delete_manual_task_by_id("task1")


# ---------- 建立任務：Idempotency-Key ----------

def _task(user_id="idem_user"):
    from datetime import datetime, timezone
    from schemas.manual_task import ManualTaskOut
    now = datetime.now(timezone.utc)
    return ManualTaskOut(
        id="new-task", user_id=user_id, title="期末報告", description="", status="To Do",
        priority="Low", duration=30, created=now, updated=now,
    )


@pytest.mark.asyncio
async def test_create_manual_task_stores_idempotency_key(monkeypatch):
    """帶 key 建立 → key 一起存進資料庫，之後才查得到。"""
    saved = {}

    async def fake_insert_one(doc):
        saved.update(doc)

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "insert_one", fake_insert_one)

    await manual_task_crud.create_manual_task(_task(), "key-1")

    assert saved["idempotency_key"] == "key-1"


@pytest.mark.asyncio
async def test_create_manual_task_returns_existing_when_same_key_inserted_concurrently(monkeypatch):
    """同一個 key 的兩個請求同時送達，另一個先寫入 → 回傳已建立的那筆，不丟錯誤。"""
    async def fake_insert_one(doc):
        raise DuplicateKeyError("duplicate")

    async def fake_find_one(query):
        assert query == {"user_id": "idem_user", "idempotency_key": "key-1"}
        return {"_id": "first-task", "user_id": "idem_user", "title": "期末報告"}

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "insert_one", fake_insert_one)
    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find_one", fake_find_one)

    result = await manual_task_crud.create_manual_task(_task(), "key-1")

    assert result["id"] == "first-task"


# ---------- 狀態改變後的完成時間 ----------

def test_completed_at_after_status_change_rules():
    """變成 Done 記下當下；本來就是 Done 保留原值（包括沒記錄的舊任務）；離開 Done 清空。"""
    from datetime import datetime, timezone

    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    earlier = datetime(2026, 11, 1, tzinfo=timezone.utc)
    rule = manual_task_crud.completed_at_after_status_change

    assert rule("To Do", None, "Done", now) == now
    assert rule("In Progress", None, "Done", now) == now
    assert rule("Done", earlier, "Done", now) == earlier
    assert rule("Done", None, "Done", now) is None
    assert rule("Done", earlier, "To Do", now) is None
    assert rule("To Do", None, "In Progress", now) is None


# ---------- 階段任務：主任務的狀態與進度（AC16）----------

@pytest.mark.parametrize("statuses, expected", [
    (["Done", "Done"], "Done"),
    (["Done", "To Do"], "In Progress"),
    (["To Do", "In Progress"], "In Progress"),
    (["To Do", "To Do"], "To Do"),
])
def test_ac16_parent_status_is_computed_from_subtasks(statuses, expected):
    """AC16：全部完成 → Done；有任何一個已完成或進行中 → In Progress；其他 → To Do；進度是已完成數 / 總數。"""
    status, progress = manual_task_crud.parent_status_and_progress([{"status": s} for s in statuses])

    assert status == expected
    assert progress == {"done": statuses.count("Done"), "total": len(statuses)}


@pytest.mark.asyncio
async def test_ac16_reading_parent_returns_computed_status_and_progress_not_stored_values():
    """AC16 / 假設 1：讀取主任務時才依子任務計算狀態與進度；主任務沒有優先序和時長。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"_id": "ac16-p", "user_id": "alice", "title": "報告", "is_parent": True, "subtask_ids": ["ac16-s1", "ac16-s2"]},
        {"_id": "ac16-s1", "user_id": "alice", "title": "一", "parent_id": "ac16-p", "status": "Done", "priority": "High", "duration": 30},
        {"_id": "ac16-s2", "user_id": "alice", "title": "二", "parent_id": "ac16-p", "status": "To Do", "priority": "High", "duration": 30},
    ])
    try:
        one = await manual_task_crud.get_manual_task_by_id("ac16-p", "alice")
        listed = {t["id"]: t for t in await manual_task_crud.get_manual_tasks_by_user_id("alice")}

        for parent in (one, listed["ac16-p"]):
            assert parent["status"] == "In Progress"
            assert parent["progress"] == {"done": 1, "total": 2}
            assert parent["priority"] is None
            assert parent["duration"] is None
        assert "status" not in await collection.find_one({"_id": "ac16-p"})
    finally:
        await collection.delete_many({"_id": {"$regex": "^ac16-"}})


# ---------- 階段任務：階段鏈的驗證（AC7、AC8）----------

def _stage(priority="Medium", due_date=None):
    return {"priority": priority, "due_date": due_date}


def _d(day):
    from datetime import datetime, timezone
    return datetime(2030, 1, day, tzinfo=timezone.utc)


def test_ac7_later_stage_with_higher_priority_is_rejected_naming_the_stage():
    """AC7：後面的階段優先序比前一個高（高 > 中 > 低）→ 擋下，訊息指出是哪一個階段。"""
    with pytest.raises(InvalidRequestError) as exc_info:
        manual_task_crud.validate_stage_chain(None, [_stage("High"), _stage("Low"), _stage("Medium")])

    assert "階段 3" in exc_info.value.detail


def test_ac7_equal_or_lower_priorities_are_allowed():
    """AC7：同樣或較低的優先序可以。"""
    manual_task_crud.validate_stage_chain(None, [_stage("High"), _stage("High"), _stage("Medium"), _stage("Low")])


def test_ac8_stage_due_after_parent_due_is_rejected_naming_the_stage():
    """AC8：子任務的截止日晚於主任務 → 擋下並指出是哪一個階段。"""
    with pytest.raises(InvalidRequestError) as exc_info:
        manual_task_crud.validate_stage_chain(_d(10), [_stage(due_date=_d(5)), _stage(due_date=_d(11))])

    assert "階段 2" in exc_info.value.detail


def test_ac8_later_stage_due_before_earlier_stage_is_rejected_even_with_gaps_without_due_date():
    """AC8：後面的階段截止日早於前面的階段 → 擋下；中間沒填截止日的階段不影響比對。"""
    with pytest.raises(InvalidRequestError) as exc_info:
        manual_task_crud.validate_stage_chain(None, [_stage(due_date=_d(5)), _stage(), _stage(due_date=_d(3))])

    assert "階段 3" in exc_info.value.detail


def test_ac8_naive_parent_due_date_compares_with_aware_stage_due_dates():
    """不帶時區的主任務截止日（舊資料，或請求沒帶時區）視為 UTC，要能和帶時區的階段截止日比較，不能丟 TypeError。"""
    from datetime import datetime
    manual_task_crud.validate_stage_chain(datetime(2030, 1, 10), [_stage(due_date=_d(5)), _stage(due_date=_d(10))])


def test_ac6_inferred_priority_higher_than_previous_stage_is_lowered_to_previous():
    """AC6：AI 推斷的優先序比前一個階段高 → 調成和前一個階段一樣，回傳被調整的階段編號；使用者填的不調整。"""
    stages = [_stage("Low"), _stage("High"), _stage("High")]

    adjusted = manual_task_crud.adjust_inferred_priorities(stages, inferred_indexes={1})

    assert [s["priority"] for s in stages] == ["Low", "Low", "High"]
    assert adjusted == [2]


# ---------- 階段任務：一次建立（AC4）----------

@pytest.mark.asyncio
async def test_ac4_write_failure_removes_documents_already_written():
    """AC4 / 假設 4：insert_many 寫到一半失敗 → 刪掉這次已寫入的文件，主任務和子任務都不留下，例外照樣往外丟。"""
    from pymongo.errors import PyMongoError

    collection = manual_task_crud.db.manual_tasks
    real_insert_one = collection.insert_one

    async def insert_first_then_fail(docs, **kwargs):
        await real_insert_one(docs[0])
        raise PyMongoError("寫入中斷")

    parent = {"_id": "ac4-p", "user_id": "alice", "title": "報告", "is_parent": True, "subtask_ids": ["ac4-s1"]}
    subtasks = [{"_id": "ac4-s1", "user_id": "alice", "title": "一", "parent_id": "ac4-p", "status": "To Do"}]
    original = collection.insert_many
    collection.insert_many = insert_first_then_fail
    try:
        with pytest.raises(PyMongoError):
            await manual_task_crud.create_manual_task_with_subtasks(parent, subtasks)
        assert await collection.count_documents({"_id": {"$in": ["ac4-p", "ac4-s1"]}}) == 0
    finally:
        collection.insert_many = original
        await collection.delete_many({"_id": {"$regex": "^ac4-"}})


# ---------- 階段任務：插入與刪除時調整階段編號（AC10、AC29）----------

async def _insert_chain(prefix, count):
    subtask_ids = [f"{prefix}-s{i}" for i in range(1, count + 1)]
    await manual_task_crud.db.manual_tasks.insert_many(
        [{"_id": f"{prefix}-p", "user_id": "alice", "title": "主任務", "is_parent": True, "subtask_ids": subtask_ids}]
        + [
            {"_id": f"{prefix}-s{i}", "user_id": "alice", "title": f"階段{i}", "parent_id": f"{prefix}-p",
             "status": "To Do", "priority": "Medium", "duration": 30}
            for i in range(1, count + 1)
        ]
    )


async def _stage_titles(parent_id):
    return [s["title"] for s in await manual_task_crud.get_subtasks(parent_id, "alice")]


@pytest.mark.asyncio
async def test_ac10_inserting_shifts_later_stages_by_one():
    """AC10：在位置 2 插入 → 新的子任務成為階段 2，原本的階段 2、3 變成 3、4。"""
    await _insert_chain("ac10", 3)
    try:
        new = {"_id": "ac10-new", "user_id": "alice", "title": "插入的", "status": "To Do", "priority": "Medium", "duration": 30}
        await manual_task_crud.insert_subtask("ac10-p", "alice", new, position=2)

        stages = await manual_task_crud.get_subtasks("ac10-p", "alice")
        assert [(s["title"], s["stage"]) for s in stages] == [("階段1", 1), ("插入的", 2), ("階段2", 3), ("階段3", 4)]
        assert stages[1]["parent_id"] == "ac10-p"
        # ADR 0004：階段編號是在主任務 subtask_ids 裡的位置，不存在子任務上
        assert (await manual_task_crud.db.manual_tasks.find_one({"_id": "ac10-p"}))["subtask_ids"][1] == "ac10-new"
        assert await manual_task_crud.db.manual_tasks.count_documents({"_id": {"$regex": "^ac10-"}, "stage": {"$exists": True}}) == 0
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"_id": {"$regex": "^ac10-"}})


@pytest.mark.asyncio
async def test_ac29_deleting_a_stage_moves_later_stages_forward():
    """AC29：刪除階段 2 → 原本的階段 3 變成階段 2。"""
    await _insert_chain("ac29", 3)
    try:
        stage2 = await manual_task_crud.get_manual_task_by_id("ac29-s2", "alice")
        await manual_task_crud.delete_subtask(stage2)

        stages = await manual_task_crud.get_subtasks("ac29-p", "alice")
        assert [(s["title"], s["stage"]) for s in stages] == [("階段1", 1), ("階段3", 2)]
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"_id": {"$regex": "^ac29-"}})


@pytest.mark.asyncio
async def test_ac28_deleting_parent_removes_all_its_subtasks_only():
    """AC28：刪除主任務 → 主任務和它的子任務都刪掉，別的任務不受影響。"""
    await _insert_chain("ac28", 2)
    await manual_task_crud.db.manual_tasks.insert_one({"_id": "ac28-other", "user_id": "alice", "title": "別的"})
    try:
        await manual_task_crud.delete_parent_with_subtasks("ac28-p", "alice")

        remaining = await manual_task_crud.db.manual_tasks.find({"_id": {"$regex": "^ac28-"}}).to_list(length=None)
        assert [d["_id"] for d in remaining] == ["ac28-other"]
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"_id": {"$regex": "^ac28-"}})


def test_ac6_inferred_priority_lower_than_next_stage_is_raised_to_next():
    """AC6：AI 推斷的優先序比後一個階段（使用者填的）低 → 調成和後一個階段一樣，不讓建立失敗。"""
    stages = [_stage("Low"), _stage("High")]

    adjusted = manual_task_crud.adjust_inferred_priorities(stages, inferred_indexes={0})

    assert [s["priority"] for s in stages] == ["High", "High"]
    assert adjusted == [1]


def test_ac6_inferred_priority_is_kept_between_previous_and_next_stage():
    """AC6 / AC10：插在中間的階段，推斷值要落在前後兩個階段之間（前 ≥ 自己 ≥ 後）。"""
    too_low = [_stage("High"), _stage("Low"), _stage("Medium")]
    too_high = [_stage("Medium"), _stage("High"), _stage("Low")]

    assert manual_task_crud.adjust_inferred_priorities(too_low, inferred_indexes={1}) == [2]
    assert manual_task_crud.adjust_inferred_priorities(too_high, inferred_indexes={1}) == [2]
    assert [s["priority"] for s in too_low] == ["High", "Medium", "Medium"]
    assert [s["priority"] for s in too_high] == ["Medium", "Medium", "Low"]


# ---------- 階段任務：插入、刪除、轉換的原子性（AC39，ADR 0004）----------

async def _visible_titles(parent_id):
    return [s["title"] for s in await manual_task_crud.get_subtasks(parent_id, "alice")]


def _new_subtask(task_id):
    return {"_id": task_id, "user_id": "alice", "title": "新的", "status": "To Do", "priority": "Medium", "duration": 30}


@pytest.mark.asyncio
async def test_ac39_insert_into_full_parent_is_rejected_and_leaves_no_trace():
    """AC39：主任務在寫入當下已經有 10 個子任務（例如另一個請求先放進去）→ 400，數量不超過 10，也不留下新的子任務。"""
    await _insert_chain("ac39a", 10)
    try:
        with pytest.raises(InvalidRequestError):
            await manual_task_crud.insert_subtask("ac39a-p", "alice", _new_subtask("ac39a-new"), position=11)

        assert len(await _visible_titles("ac39a-p")) == 10
        assert await manual_task_crud.db.manual_tasks.find_one({"_id": "ac39a-new"}) is None
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"_id": {"$regex": "^ac39a-"}})


@pytest.mark.asyncio
async def test_ac39_insert_position_beyond_current_count_is_rejected():
    """AC39：插入位置在寫入當下已經不存在（例如另一個請求刪掉了階段）→ 400，不產生空號。"""
    await _insert_chain("ac39b", 2)
    try:
        with pytest.raises(InvalidRequestError):
            await manual_task_crud.insert_subtask("ac39b-p", "alice", _new_subtask("ac39b-new"), position=4)

        assert await _visible_titles("ac39b-p") == ["階段1", "階段2"]
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"_id": {"$regex": "^ac39b-"}})


@pytest.mark.asyncio
async def test_ac39_failure_updating_parent_keeps_stages_unchanged():
    """AC39：子任務寫入後、更新主任務順序時失敗 → 使用者看到的子任務數量和階段編號不變，例外照樣往外丟。"""
    from pymongo.errors import PyMongoError

    await _insert_chain("ac39c", 2)
    collection = manual_task_crud.db.manual_tasks
    original = collection.update_one

    async def fail_on_parent(filter, update, **kwargs):
        if filter.get("_id") == "ac39c-p":
            raise PyMongoError("寫入中斷")
        return await original(filter, update, **kwargs)

    collection.update_one = fail_on_parent
    try:
        with pytest.raises(PyMongoError):
            await manual_task_crud.insert_subtask("ac39c-p", "alice", _new_subtask("ac39c-new"), position=1)
    finally:
        collection.update_one = original
    try:
        assert await _visible_titles("ac39c-p") == ["階段1", "階段2"]
        listed = [t["id"] for t in await manual_task_crud.get_manual_tasks_by_user_id("alice")]
        assert "ac39c-new" not in listed
    finally:
        await collection.delete_many({"_id": {"$regex": "^ac39c-"}})


@pytest.mark.asyncio
async def test_ac39_converting_task_that_changed_meanwhile_is_rejected_and_unchanged():
    """AC39：一般任務在轉換當下已經完成（另一個請求改的）→ 400，任務維持一般任務，不留下子任務。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_one({"_id": "ac39d-t", "user_id": "alice", "title": "一般", "status": "Done", "priority": "Low"})
    try:
        with pytest.raises(InvalidRequestError):
            await manual_task_crud.insert_subtask("ac39d-t", "alice", _new_subtask("ac39d-new"), position=1, convert=True)

        stored = await collection.find_one({"_id": "ac39d-t"})
        assert stored.get("is_parent") is None and stored["priority"] == "Low"
        assert await collection.find_one({"_id": "ac39d-new"}) is None
    finally:
        await collection.delete_many({"_id": {"$regex": "^ac39d-"}})


@pytest.mark.asyncio
async def test_ac39_conversion_sets_parent_fields_and_first_subtask_in_one_update():
    """AC39 / AC12：轉換成主任務時，is_parent、清空的欄位和第一個子任務在同一次更新完成。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_one({
        "_id": "ac39e-t", "user_id": "alice", "title": "一般", "status": "In Progress", "priority": "Low",
        "duration": 30, "inference_hint": "提醒",
    })
    try:
        await manual_task_crud.insert_subtask("ac39e-t", "alice", _new_subtask("ac39e-new"), position=1, convert=True)

        stored = await collection.find_one({"_id": "ac39e-t"})
        assert stored["is_parent"] is True and stored["subtask_ids"] == ["ac39e-new"]
        assert all(field not in stored for field in ("priority", "duration", "inference_hint", "status"))
    finally:
        await collection.delete_many({"_id": {"$regex": "^ac39e-"}})


@pytest.mark.asyncio
async def test_ac39_ac30_deleting_when_only_one_stage_remains_is_rejected():
    """AC39 / AC30：刪除當下主任務只剩一個子任務（另一個請求先刪了）→ 400，至少保留 1 個。"""
    await _insert_chain("ac39f", 1)
    try:
        only = await manual_task_crud.get_manual_task_by_id("ac39f-s1", "alice")
        with pytest.raises(InvalidRequestError):
            await manual_task_crud.delete_subtask(only)

        assert await _visible_titles("ac39f-p") == ["階段1"]
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"_id": {"$regex": "^ac39f-"}})


@pytest.mark.asyncio
async def test_ac39_subtask_not_in_parent_order_is_hidden_everywhere():
    """AC39：不在主任務 subtask_ids 裡的子任務（寫入失敗留下的、主任務已不存在的）不出現在列表、排程清單和查詢。"""
    import crud.schedulable_items as schedulable_items

    await _insert_chain("ac39g", 1)
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {**_new_subtask("ac39g-stray"), "parent_id": "ac39g-p"},
        {**_new_subtask("ac39g-orphan"), "parent_id": "ac39g-gone"},
    ])
    try:
        listed = {t["id"] for t in await manual_task_crud.get_manual_tasks_by_user_id("alice")}
        schedulable = {t["id"] for t in await schedulable_items.get_all_schedulable_items("alice")}

        assert "ac39g-s1" in listed
        assert not {"ac39g-stray", "ac39g-orphan"} & listed
        assert not {"manual:ac39g-stray", "manual:ac39g-orphan"} & schedulable
        assert (await manual_task_crud.get_manual_task_by_id("ac39g-p", "alice"))["progress"] == {"done": 0, "total": 1}
        with pytest.raises(NotFoundError):
            await manual_task_crud.get_manual_task_by_id("ac39g-stray", "alice")
    finally:
        await collection.delete_many({"_id": {"$regex": "^ac39g-"}})
