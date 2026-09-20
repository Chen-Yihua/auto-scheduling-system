# 透過 HTTP 測試 /manual_tasks 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟錯誤狀態碼真的送得出去。
# crud 層在這裡被 mock 掉；建立任務時「哪些欄位交給 LLM 推斷」、更新時保留原值、
# 只能動自己的任務等規則，由 unit/test_manual_task_router.py 和 unit/test_manual_task_crud.py 負責。
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
    """POST /manual_tasks/：建立任務成功；priority 和 duration 都填了，就不該去問 LLM 推斷。"""
    mock_create_manual_task.return_value = fake_task_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual_tasks/", json=fake_task_input.model_dump())

    assert response.status_code == 200
    assert response.json()["id"] == "task_id"
    assert response.json()["created"] == "2023-10-01T00:00:00Z"
    # priority/duration 兩個都填了，不該去問 LLM
    mock_infer.assert_not_called()

@pytest.mark.asyncio
@patch("crud.manualTask.create_manual_task", new_callable=AsyncMock)
async def test_create_manual_task_ignores_client_supplied_user_id(mock_create_manual_task, fake_task_input, fake_task_out, logged_in_user):
    """建立任務時，就算請求裡帶了別人的 user_id，任務的擁有者仍是登入者本人。"""
    mock_create_manual_task.return_value = fake_task_out
    payload = fake_task_input.model_dump()
    payload["user_id"] = "someone_else"  # 冒充別人

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual_tasks/", json=payload)

    assert response.status_code == 200
    saved_task = mock_create_manual_task.call_args[0][0]
    assert saved_task.user_id == logged_in_user["sub"]


@pytest.mark.asyncio
async def test_create_manual_task_invalid_input(logged_in_user):
    """請求內容缺必填欄位 → 回 422。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/manual_tasks/", json={})
    assert response.status_code == 422  # FastAPI 的預設驗證


"""
測試取得帳號底下任務
"""
@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_tasks_by_user_id", new_callable=AsyncMock)
async def test_get_user_tasks_success(mock_get_tasks, fake_task_out, logged_in_user):
    """GET /manual_tasks/me：回傳目前使用者的所有任務。"""
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
    """沒有任何任務是正常狀態（新使用者、或剛清空清單）→ 回 200 加空陣列，不是 404；否則刪掉最後一個任務後，前端重新整理會誤判成錯誤。"""
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
    """GET /manual_tasks/{id}：查到任務就回傳它。"""
    mock_get_task.return_value = fake_task_out


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual_tasks/task-id")

    assert response.status_code == 200
    task = response.json()
    assert task["id"] == "task_id"

@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
async def test_get_manual_task_not_found(mock_get_task, logged_in_user):
    """查無此任務 → 404 "Task not found"。"""
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
    """PUT /manual_tasks/{id}：更新成功，回傳更新後的任務（description、updated 都是新值）。"""
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
    """更新不存在的任務 → 404 "Task not found"。"""
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
    """DELETE /manual_tasks/{id}：刪除成功，回傳被刪的任務 ID 和 deleted 為 True。"""
    mock_get_task.return_value = fake_task_out.model_dump()
    mock_delete_task.return_value = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/manual_tasks/task-id")

    assert response.status_code == 200
    assert response.json() == {"task ID": "task-id", "deleted": True}

@pytest.mark.asyncio
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
async def test_delete_manual_task_not_found(mock_get_task, logged_in_user):
    """刪除不存在的任務 → 404 "Task not found"。"""
    mock_get_task.side_effect = HTTPException(status_code=404, detail="Task not found")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/manual_tasks/task-999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試沒登入
"""
@pytest.mark.asyncio
async def test_get_user_tasks_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/manual_tasks/me")

    assert response.status_code in (401, 403)
