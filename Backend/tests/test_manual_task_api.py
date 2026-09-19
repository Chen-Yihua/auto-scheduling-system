# 透過 HTTP 測試 /manual_tasks 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟錯誤狀態碼真的送得出去，以及建立任務時
# 「哪些欄位交給 LLM 推斷」的規則。crud 層在這裡被 mock 掉；crud 本身由
# test_manual_task_crud.py 負責。
import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from unittest.mock import AsyncMock, patch

from main import app  # 假設 FastAPI app 是定義在 main.py 裡
from schemas.manualTask import ManualTaskInput, ManualTaskOut


@pytest.fixture
def fake_task_input():
    return ManualTaskInput(
        title="Test Task",
        description="This is a test task.",
        due_date=None,
        status="To Do",
        priority="Low",
        duration=30,  # 兩個不確定欄位都填了，才不會觸發 LLM 推斷
    )

@pytest.fixture
def fake_task_out():
    return ManualTaskOut(
        id="task_id",
        user_id="test_user_123",
        title="Test Task",
        description="This is a test task.",
        due_date=None,
        created="2023-10-01T00:00:00Z",
        updated="2023-10-01T00:00:00Z",
        status="To Do",
        priority="Low"
    )

@pytest.fixture
def fake_task_out_updated():
    return ManualTaskOut(
        id="task_id",
        user_id="test_user_123",
        title="Test Task",
        description="This is a test task (updated).",
        due_date=None,
        created="2023-10-01T00:00:00Z",
        updated="2023-10-10T00:00:00Z",
        status="To Do",
        priority="Low"
    )

"""
測試建立任務
"""
@pytest.mark.asyncio
@patch("routers.manualTask.infer_missing_task_fields", new_callable=AsyncMock)
@patch("crud.manualTask.create_manual_task", new_callable=AsyncMock)
async def test_create_manual_task_success(mock_create_manual_task, mock_infer, fake_task_input, fake_task_out, logged_in_user):
    mock_create_manual_task.return_value = fake_task_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual_tasks/", json=fake_task_input.model_dump())

    assert response.status_code == 200
    assert response.json()["id"] == "task_id"
    assert response.json()["created"] == "2023-10-01T00:00:00Z"
    # priority/duration 兩個都填了，不該去問 LLM
    mock_infer.assert_not_called()

@pytest.mark.asyncio
async def test_create_manual_task_invalid_input(logged_in_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual_tasks/", json={})
    assert response.status_code == 422  # FastAPI 的預設驗證


@pytest.mark.asyncio
@patch("routers.manualTask.infer_missing_task_fields", new_callable=AsyncMock)
@patch("crud.manualTask.create_manual_task", new_callable=AsyncMock)
async def test_create_manual_task_infers_missing_priority_and_duration(mock_create_manual_task, mock_infer, fake_task_input, fake_task_out, logged_in_user):
    mock_infer.return_value = {"priority": "High", "duration": 120, "reason": "看起來很重要"}
    mock_create_manual_task.return_value = fake_task_out

    payload = fake_task_input.model_dump()
    payload["priority"] = None
    payload["duration"] = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual_tasks/", json=payload)

    assert response.status_code == 200
    mock_infer.assert_called_once_with(
        fake_task_input.title, fake_task_input.description, fake_task_input.inference_hint
    )

    # 檢查真正存進去的任務資料，確認 priority/duration 有被 LLM 推斷值取代
    saved_task = mock_create_manual_task.call_args[0][0]
    assert saved_task.priority == "High"
    assert saved_task.duration == 120
    assert saved_task.inferred_fields == ["priority", "duration"]
    assert saved_task.inference_reason == "看起來很重要"


@pytest.mark.asyncio
@patch("routers.manualTask.infer_missing_task_fields", new_callable=AsyncMock)
@patch("crud.manualTask.create_manual_task", new_callable=AsyncMock)
async def test_create_manual_task_infers_only_missing_field(mock_create_manual_task, mock_infer, fake_task_input, fake_task_out, logged_in_user):
    mock_infer.return_value = {"priority": "Medium", "duration": 45, "reason": "普通任務"}
    mock_create_manual_task.return_value = fake_task_out

    payload = fake_task_input.model_dump()
    payload["duration"] = None  # 只有 duration 沒填，priority 使用者已經選了 "Low"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual_tasks/", json=payload)

    assert response.status_code == 200
    saved_task = mock_create_manual_task.call_args[0][0]
    # priority 是使用者自己選的，不該被 LLM 的推斷值覆蓋
    assert saved_task.priority == "Low"
    assert saved_task.duration == 45
    assert saved_task.inferred_fields == ["duration"]


"""
測試取得帳號底下任務
"""
@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_tasks_by_user_id", new_callable=AsyncMock)
async def test_get_user_tasks_success(mock_get_tasks, fake_task_out, logged_in_user):
    mock_get_tasks.return_value = [fake_task_out, fake_task_out]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual_tasks/me")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    assert tasks[0]["id"] == "task_id"

@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_tasks_by_user_id", new_callable=AsyncMock)
async def test_get_user_tasks_empty(mock_get_tasks, logged_in_user):
    # 沒有任何任務是正常狀態（新使用者、或剛好清空清單），該回 200 + 空陣列，
    # 不是 404——不然使用者刪掉最後一個任務後，前端重新整理清單會誤判成錯誤
    mock_get_tasks.return_value = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual_tasks/me")
    assert response.status_code == 200
    assert response.json() == []


"""
測試查詢單一任務
"""
@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
async def test_get_manual_task_success(mock_get_task, fake_task_out, logged_in_user):
    mock_get_task.return_value = fake_task_out


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual_tasks/task-id")

    assert response.status_code == 200
    task = response.json()
    assert task["id"] == "task_id"

@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
async def test_get_manual_task_not_found(mock_get_task, logged_in_user):
    # 查不到時，crud 現在直接 raise 404，不是回傳 None 讓 router 判斷
    mock_get_task.side_effect = HTTPException(status_code=404, detail="Task not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual_tasks/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試更新任務
"""
@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
@patch("crud.manualTask.update_manual_task_by_id", new_callable=AsyncMock)
async def test_update_manual_task_success(mock_update_task, mock_get_task, fake_task_out, fake_task_out_updated, logged_in_user):
    mock_get_task.return_value = fake_task_out.model_dump()
    mock_update_task.return_value = fake_task_out_updated.model_dump()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/manual_tasks/task-id", json=fake_task_out.model_dump(mode="json"))

    assert response.status_code == 200
    task = response.json()
    assert task["description"] == "This is a test task (updated)."
    assert task["updated"] == "2023-10-10T00:00:00Z"

@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
async def test_update_manual_task_not_found(mock_get_task, fake_task_out, logged_in_user):
    # 查無此任務，crud 現在直接 raise 404
    mock_get_task.side_effect = HTTPException(status_code=404, detail="Task not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/manual_tasks/does-not-exist", json=fake_task_out.model_dump(mode="json"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試刪除任務
"""
@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
@patch("crud.manualTask.delete_manual_task_by_id", new_callable=AsyncMock)
async def test_delete_manual_task_success(mock_delete_task, mock_get_task, fake_task_out, logged_in_user):
    mock_get_task.return_value = fake_task_out.model_dump()
    mock_delete_task.return_value = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/manual_tasks/task-id")

    assert response.status_code == 200
    assert response.json() == {"task ID": "task-id", "deleted": True}

@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
async def test_delete_manual_task_not_found(mock_get_task, logged_in_user):
    # 查無任務，crud 現在直接 raise 404
    mock_get_task.side_effect = HTTPException(status_code=404, detail="Task not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/manual_tasks/task-999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試沒登入
"""
# 沒帶登入 token（這個測試沒有用 logged_in_user）-> 要被擋在門外，不能進到函式裡
@pytest.mark.asyncio
async def test_get_user_tasks_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual_tasks/me")

    assert response.status_code in (401, 403)
