"""
crud/manual_task.py 的邊界情境：查無資料、沒有變更、刪不到東西等。
資料庫連不上這類錯誤不在這裡處理，crud 直接讓例外往外丟，由全域 handler 統一轉成回應，
見 test_db_error_handling.py。
"""
import pytest
from fastapi import HTTPException

import crud.manual_task as manual_task_crud


# ---------- 只能查自己的任務、回傳不含 Mongo 內部的 _id（用記憶體資料庫，不 mock 查詢）----------

@pytest.mark.asyncio
async def test_get_manual_task_by_id_returns_own_task_without_mongo_id():
    """查自己的任務 → 回傳任務內容，且不含 Mongo 自動加的 _id（否則之後更新時會被塞回去）。"""
    await manual_task_crud.db.manual_tasks.insert_one({"id": "crud-t1", "user_id": "alice", "title": "Alice 的任務"})
    try:
        task = await manual_task_crud.get_manual_task_by_id("crud-t1", "alice")
        assert task["title"] == "Alice 的任務"
        assert "_id" not in task
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"id": "crud-t1"})


@pytest.mark.asyncio
async def test_get_manual_task_by_id_hides_other_users_task():
    """使用者 bob 查 alice 的任務 → 404，不能讓他看到。"""
    await manual_task_crud.db.manual_tasks.insert_one({"id": "crud-t2", "user_id": "alice", "title": "Alice 的任務"})
    try:
        with pytest.raises(HTTPException) as exc_info:
            await manual_task_crud.get_manual_task_by_id("crud-t2", "bob")
        assert exc_info.value.status_code == 404
    finally:
        await manual_task_crud.db.manual_tasks.delete_many({"id": "crud-t2"})


@pytest.mark.asyncio
async def test_get_manual_tasks_by_user_id_returns_only_own_tasks_without_mongo_id():
    """列出任務只會回傳自己的（不含別人的），而且每筆都不含 Mongo 內部的 _id。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"id": "crud-t3", "user_id": "alice", "title": "Alice 的任務一"},
        {"id": "crud-t4", "user_id": "alice", "title": "Alice 的任務二"},
        {"id": "crud-t5", "user_id": "bob", "title": "Bob 的任務"},
    ])
    try:
        tasks = await manual_task_crud.get_manual_tasks_by_user_id("alice")
        assert sorted(t["id"] for t in tasks) == ["crud-t3", "crud-t4"]
        assert all("_id" not in t for t in tasks)
    finally:
        await collection.delete_many({"id": {"$in": ["crud-t3", "crud-t4", "crud-t5"]}})


# ---------- get_manual_task_by_id ----------

@pytest.mark.asyncio
async def test_get_manual_task_by_id_raises_404_when_not_found(monkeypatch):
    """查無此任務 → 404。"""
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.get_manual_task_by_id("task1", "uid123")

    assert exc_info.value.status_code == 404


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
        {"id": "confirm-t1", "user_id": "alice", "title": "任務一"},
        {"id": "confirm-t2", "user_id": "alice", "title": "任務二"},
    ])
    try:
        await manual_task_crud.set_calendar_event_id("confirm-t1", "alice", "event-abc")

        task1 = await collection.find_one({"id": "confirm-t1"})
        task2 = await collection.find_one({"id": "confirm-t2"})
        assert task1["calendar_event_id"] == "event-abc"
        assert task2.get("calendar_event_id") is None
    finally:
        await collection.delete_many({"id": {"$in": ["confirm-t1", "confirm-t2"]}})


# ---------- reorder_manual_tasks ----------

def _reorder_item(task_id, priority, sort_order):
    return {"task_id": task_id, "priority": priority, "sort_order": sort_order}


@pytest.mark.asyncio
async def test_reorder_manual_tasks_writes_sort_order_from_each_item():
    """依每筆傳入的 sort_order 寫回（呼叫端指定，不是這裡自己算的——見函式內的說明）。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"id": "reorder-t1", "user_id": "alice", "title": "任務一", "priority": "Medium"},
        {"id": "reorder-t2", "user_id": "alice", "title": "任務二", "priority": "Medium"},
        {"id": "reorder-t3", "user_id": "alice", "title": "任務三", "priority": "Medium"},
    ])
    try:
        result = await manual_task_crud.reorder_manual_tasks("alice", [
            _reorder_item("reorder-t3", "Medium", 0),
            _reorder_item("reorder-t1", "Medium", 1),
            _reorder_item("reorder-t2", "Medium", 2),
        ])

        by_id = {t["id"]: t["sort_order"] for t in result}
        assert by_id == {"reorder-t3": 0, "reorder-t1": 1, "reorder-t2": 2}
    finally:
        await collection.delete_many({"id": {"$in": ["reorder-t1", "reorder-t2", "reorder-t3"]}})


@pytest.mark.asyncio
async def test_reorder_manual_tasks_writes_priority_from_which_column_task_was_dropped_in():
    """拖到不同欄（priority）要跟著寫回去——這是三欄式拖拉排序畫面「拖去別欄＝改優先權」的核心行為。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"id": "reorder-t8", "user_id": "alice", "title": "任務", "priority": "Low"},
    ])
    try:
        result = await manual_task_crud.reorder_manual_tasks("alice", [
            _reorder_item("reorder-t8", "High", 0),  # 使用者把它從 Low 欄拖到 High 欄
        ])

        assert result[0]["priority"] == "High"
    finally:
        await collection.delete_many({"id": "reorder-t8"})


@pytest.mark.asyncio
async def test_reorder_manual_tasks_rejects_id_belonging_to_another_user():
    """傳入的 id 裡混了別人的任務 → 400，不能藉此竄改不屬於自己的任務。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"id": "reorder-t4", "user_id": "alice", "title": "Alice 的任務", "priority": "Medium"},
        {"id": "reorder-t5", "user_id": "bob", "title": "Bob 的任務", "priority": "Medium"},
    ])
    try:
        with pytest.raises(HTTPException) as exc_info:
            await manual_task_crud.reorder_manual_tasks("alice", [
                _reorder_item("reorder-t4", "Medium", 0),
                _reorder_item("reorder-t5", "Medium", 1),
            ])
        assert exc_info.value.status_code == 400
    finally:
        await collection.delete_many({"id": {"$in": ["reorder-t4", "reorder-t5"]}})


@pytest.mark.asyncio
async def test_reorder_manual_tasks_same_order_again_does_not_raise():
    """重新提交跟現在一模一樣的順序（sort_order 沒有真的變動）→ 不能因此噴錯。"""
    collection = manual_task_crud.db.manual_tasks
    await collection.insert_many([
        {"id": "reorder-t6", "user_id": "alice", "title": "任務一", "priority": "Medium", "sort_order": 0},
        {"id": "reorder-t7", "user_id": "alice", "title": "任務二", "priority": "Medium", "sort_order": 1},
    ])
    try:
        result = await manual_task_crud.reorder_manual_tasks("alice", [
            _reorder_item("reorder-t6", "Medium", 0),
            _reorder_item("reorder-t7", "Medium", 1),
        ])
        by_id = {t["id"]: t["sort_order"] for t in result}
        assert by_id == {"reorder-t6": 0, "reorder-t7": 1}
    finally:
        await collection.delete_many({"id": {"$in": ["reorder-t6", "reorder-t7"]}})


# ---------- update_manual_task_by_id ----------

@pytest.mark.asyncio
async def test_update_manual_task_by_id_raises_400_when_nothing_modified(monkeypatch):
    """更新後沒有任何欄位真的變動 → 400。"""
    async def mock_update_one(query, update):
        return type("Result", (), {"modified_count": 0})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "update_one", mock_update_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.update_manual_task_by_id("task1", {"title": "沒變"})

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_manual_task_by_id_returns_updated_doc(monkeypatch):
    """更新成功 → 重新查一次，回傳更新後的完整文件。"""
    async def mock_update_one(query, update):
        return type("Result", (), {"modified_count": 1})()

    async def mock_find_one(query):
        return {"id": "task1", "title": "新標題"}

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "update_one", mock_update_one)
    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find_one", mock_find_one)

    result = await manual_task_crud.update_manual_task_by_id("task1", {"title": "新標題"})

    assert result == {"id": "task1", "title": "新標題"}


# ---------- delete_manual_task_by_id ----------

@pytest.mark.asyncio
async def test_delete_manual_task_by_id_raises_404_when_nothing_deleted(monkeypatch):
    """要刪除的任務不存在 → 404。"""
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 0})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "delete_one", mock_delete_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.delete_manual_task_by_id("task1")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_manual_task_by_id_succeeds(monkeypatch):
    """刪除任務成功 → 不出錯。"""
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 1})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "delete_one", mock_delete_one)

    # 不丟例外就代表成功
    await manual_task_crud.delete_manual_task_by_id("task1")
