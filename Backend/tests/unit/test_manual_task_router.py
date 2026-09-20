# 直接呼叫 router 函式（await manual_task_router.create_manual_task(...)）測試它自己的規則：
# 建立時要不要問 LLM、任務的擁有者一律是登入者本人、更新時沒帶的欄位保留原值，
# 以及「只能動自己的任務」。不經過 HTTP，所以不涉及路由註冊、登入驗證、response_model ——
# 那些由 integration/test_manual_task_api.py 負責。
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID
from fastapi import HTTPException

import routers.manualTask as manual_task_router
from db.mongodb import db
from schemas.manualTask import ManualTaskInput, ManualTaskUpdate

mock_user = {"sub": "test_user_123"}


def _task_input(**overrides):
    fields = dict(
        title="期末報告", description="整理資料並簡報", status="To Do",
        priority="Low", duration=30, inference_hint="提醒",
    )
    fields.update(overrides)
    return ManualTaskInput(**fields)


async def _create(task_input):
    return await manual_task_router.create_manual_task(
        request=MagicMock(), taskInput=task_input, clerk_user=mock_user
    )


@pytest.fixture
def created_tasks(monkeypatch):
    """收集 router 交給 crud 要存起來的任務（不真的寫資料庫）。"""
    saved = []

    async def fake_create(task):
        saved.append(task)
        return task

    monkeypatch.setattr(manual_task_router.manualTask_crud, "create_manual_task", fake_create)
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

    monkeypatch.setattr(manual_task_router.manualTask_crud, "get_manual_task_by_id", fake_get)
    monkeypatch.setattr(manual_task_router.manualTask_crud, "update_manual_task_by_id", fake_update)

    await manual_task_router.update_manual_task("t1", ManualTaskUpdate(title="新標題"), clerk_user=mock_user)

    assert saved["title"] == "新標題"
    assert saved["priority"] == "High"
    assert saved["duration"] == 90
    assert saved["updated"] > existing["updated"]  # 更新時間有刷新


# ---------- 只能動自己的任務（用真的 crud 加記憶體資料庫，才測得到 router 與 crud 的串接）----------

async def _insert_alice_task(task_id):
    await db.manual_tasks.insert_one({"id": task_id, "user_id": "alice", "title": "Alice 的任務"})


async def _remove_task(task_id):
    await db.manual_tasks.delete_many({"id": task_id})


@pytest.mark.asyncio
async def test_get_manual_task_hides_other_users_task():
    """使用者 bob 查 alice 的任務 → 404，看不到內容。"""
    await _insert_alice_task("router-t1")
    try:
        with pytest.raises(HTTPException) as exc_info:
            await manual_task_router.get_manual_task("router-t1", clerk_user={"sub": "bob"})
        assert exc_info.value.status_code == 404
    finally:
        await _remove_task("router-t1")


@pytest.mark.asyncio
async def test_update_manual_task_refuses_other_users_task_and_leaves_it_unchanged():
    """使用者 bob 更新 alice 的任務 → 404，alice 的任務內容不會被改動。"""
    await _insert_alice_task("router-t2")
    try:
        with pytest.raises(HTTPException) as exc_info:
            await manual_task_router.update_manual_task(
                "router-t2", ManualTaskUpdate(title="被 bob 改掉了"), clerk_user={"sub": "bob"}
            )
        assert exc_info.value.status_code == 404
        assert (await db.manual_tasks.find_one({"id": "router-t2"}))["title"] == "Alice 的任務"
    finally:
        await _remove_task("router-t2")


@pytest.mark.asyncio
async def test_delete_manual_task_refuses_other_users_task_and_keeps_it():
    """使用者 bob 刪除 alice 的任務 → 404，任務仍在資料庫裡。"""
    await _insert_alice_task("router-t3")
    try:
        with pytest.raises(HTTPException) as exc_info:
            await manual_task_router.delete_manual_task("router-t3", clerk_user={"sub": "bob"})
        assert exc_info.value.status_code == 404
        assert await db.manual_tasks.find_one({"id": "router-t3"}) is not None
    finally:
        await _remove_task("router-t3")
