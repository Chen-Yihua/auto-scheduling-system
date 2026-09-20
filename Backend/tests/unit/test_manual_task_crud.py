"""
crud/manualTask.py 的邊界情境：查無資料、沒有變更、刪不到東西等。
資料庫連不上這類錯誤不在這裡處理，crud 直接讓例外往外丟，由全域 handler 統一轉成回應，
見 test_db_error_handling.py。
"""
import pytest
from fastapi import HTTPException

import crud.manualTask as manual_task_crud


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
