"""
crud/manualTask.py 的 PyMongoError 分支跟其他邊界情境——先前 test_manualTask.py
是 TestClient 層級的測試，把 crud 整層 mock 掉，這幾個分支從沒被真的觸發過。
"""
import pytest
from datetime import datetime, timezone
from pymongo.errors import PyMongoError
from fastapi import HTTPException

import crud.manualTask as manual_task_crud
from schemas.manualTask import ManualTaskOut


def _task_out(**overrides):
    defaults = dict(
        id="task1",
        user_id="uid123",
        title="任務",
        description="描述",
        due_date=None,
        created=datetime.now(timezone.utc),
        updated=datetime.now(timezone.utc),
        status="To Do",
        priority="Low",
        duration=30,
    )
    defaults.update(overrides)
    return ManualTaskOut(**defaults)


# ---------- create_manual_task ----------

@pytest.mark.asyncio
async def test_create_manual_task_raises_500_when_db_down(monkeypatch):
    async def mock_insert_one(doc):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "insert_one", mock_insert_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.create_manual_task(_task_out())

    assert exc_info.value.status_code == 500


# ---------- get_manual_task_by_id ----------

@pytest.mark.asyncio
async def test_get_manual_task_by_id_raises_503_when_db_down(monkeypatch):
    async def mock_find_one(query):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.get_manual_task_by_id("task1", "uid123")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_manual_task_by_id_raises_404_when_not_found(monkeypatch):
    async def mock_find_one(query):
        return None

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find_one", mock_find_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.get_manual_task_by_id("task1", "uid123")

    assert exc_info.value.status_code == 404


# ---------- get_manual_tasks_by_user_id ----------

@pytest.mark.asyncio
async def test_get_manual_tasks_by_user_id_raises_503_when_db_down(monkeypatch):
    class FakeCursor:
        async def to_list(self):
            raise PyMongoError("connection lost")

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find", lambda query: FakeCursor())

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.get_manual_tasks_by_user_id("uid123")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_manual_tasks_by_user_id_returns_none_when_empty(monkeypatch):
    class FakeCursor:
        async def to_list(self):
            return []

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "find", lambda query: FakeCursor())

    result = await manual_task_crud.get_manual_tasks_by_user_id("uid123")

    assert result is None


# ---------- update_manual_task_by_id ----------

@pytest.mark.asyncio
async def test_update_manual_task_by_id_raises_503_when_db_down(monkeypatch):
    async def mock_update_one(query, update):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "update_one", mock_update_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.update_manual_task_by_id("task1", {"title": "新標題"})

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_update_manual_task_by_id_raises_400_when_nothing_modified(monkeypatch):
    async def mock_update_one(query, update):
        return type("Result", (), {"modified_count": 0})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "update_one", mock_update_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.update_manual_task_by_id("task1", {"title": "沒變"})

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_manual_task_by_id_returns_updated_doc(monkeypatch):
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
async def test_delete_manual_task_by_id_raises_503_when_db_down(monkeypatch):
    async def mock_delete_one(query):
        raise PyMongoError("connection lost")

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "delete_one", mock_delete_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.delete_manual_task_by_id("task1")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_delete_manual_task_by_id_raises_404_when_nothing_deleted(monkeypatch):
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 0})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "delete_one", mock_delete_one)

    with pytest.raises(HTTPException) as exc_info:
        await manual_task_crud.delete_manual_task_by_id("task1")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_manual_task_by_id_succeeds(monkeypatch):
    async def mock_delete_one(query):
        return type("Result", (), {"deleted_count": 1})()

    monkeypatch.setattr(manual_task_crud.db.manual_tasks, "delete_one", mock_delete_one)

    # 不丟例外就代表成功
    await manual_task_crud.delete_manual_task_by_id("task1")
