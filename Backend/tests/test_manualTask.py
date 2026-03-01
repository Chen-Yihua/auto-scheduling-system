import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from main import app  # 假設 FastAPI app 是定義在 main.py 裡
from schemas.manualTask import ManualTaskInput, ManualTaskOut

client = TestClient(app)

@pytest.fixture
def fake_clerk_user():
    return {"sub": "clerk_user_id"}

# override get jwt token function to return a fake token
@pytest.fixture(autouse=True)
def override_get_current_user(fake_clerk_user):
    from db.security import get_current_clerk_user
    app.dependency_overrides[get_current_clerk_user] = lambda: fake_clerk_user
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def fake_task_input():
    return ManualTaskInput(
        user_id="clerk_user_id",
        title="Test Task",
        description="This is a test task.",
        due_date=None,
        status="To Do",
        priority="Low"
    )

@pytest.fixture
def fake_task_out():
    return ManualTaskOut(
        id="task_id",
        user_id="clerk_user_id",
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
        user_id="clerk_user_id",
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
@patch("crud.manualTask.create_manual_task", new_callable=AsyncMock)
def test_create_manual_task_success(mock_create_manual_task, fake_task_input, fake_task_out):
    mock_create_manual_task.return_value = fake_task_out

    response = client.post("/manual_tasks/", json=fake_task_input.model_dump())

    assert response.status_code == 200
    assert response.json()["id"] == "task_id"
    assert response.json()["created"] == "2023-10-01T00:00:00Z"

def test_create_manual_task_invalid_input():
    response = client.post("/manual_tasks/", json={})
    assert response.status_code == 422  # FastAPI 的預設驗證


"""
測試取得帳號底下任務
"""
@patch("crud.manualTask.get_manual_tasks_by_user_id", new_callable=AsyncMock)
def test_get_user_tasks_success(mock_get_tasks, fake_task_out):
    mock_get_tasks.return_value = [fake_task_out, fake_task_out]

    response = client.get("/manual_tasks/me")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    assert tasks[0]["id"] == "task_id"

@patch("crud.manualTask.get_manual_tasks_by_user_id", new_callable=AsyncMock)
def test_get_user_tasks_empty(mock_get_tasks):
    mock_get_tasks.return_value = []

    response = client.get("/manual_tasks/me")
    assert response.status_code == 404
    assert response.json()["detail"] == "No tasks found"


"""
測試查詢單一任務
"""
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
def test_get_manual_task_success(mock_get_task, fake_task_out):
    mock_get_task.return_value = fake_task_out


    response = client.get("/manual_tasks/task-id")

    assert response.status_code == 200
    task = response.json()
    assert task["id"] == "task_id"

@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
def test_get_manual_task_not_found(mock_get_task):
    mock_get_task.return_value = None  # 模擬查不到

    response = client.get("/manual_tasks/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試更新任務
"""
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
@patch("crud.manualTask.update_manual_task_by_id", new_callable=AsyncMock)
def test_update_manual_task_success(mock_update_task, mock_get_task, fake_task_out, fake_task_out_updated):
    mock_get_task.return_value = fake_task_out.model_dump()
    mock_update_task.return_value = fake_task_out_updated.model_dump()

    response = client.put("/manual_tasks/task-id", json=fake_task_out.model_dump(mode="json"))

    assert response.status_code == 200
    task = response.json()
    assert task["description"] == "This is a test task (updated)."
    assert task["updated"] == "2023-10-10T00:00:00Z"

@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
def test_update_manual_task_not_found(mock_get_task, fake_task_out):
    mock_get_task.return_value = None  # 查無此任務

    response = client.put("/manual_tasks/does-not-exist", json=fake_task_out.model_dump(mode="json"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


"""
測試刪除任務
"""
@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
@patch("crud.manualTask.delete_manual_task_by_id", new_callable=AsyncMock)
def test_delete_manual_task_success(mock_delete_task, mock_get_task, fake_task_out):
    mock_get_task.return_value = fake_task_out.model_dump()
    mock_delete_task.return_value = True

    response = client.delete("/manual_tasks/task-id")

    assert response.status_code == 200
    assert response.json() == {"task ID": "task-id", "deleted": True}

@patch("crud.manualTask.get_manual_task_by_id", new_callable=AsyncMock)
def test_delete_manual_task_not_found(mock_get_task):
    mock_get_task.return_value = None  # 查無任務

    response = client.delete("/manual_tasks/task-999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"
