import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from main import app  # 假設 FastAPI app 是定義在 main.py 裡
from schemas.user import UserOut, UserCreate

client = TestClient(app)

@pytest.fixture
def fake_clerk_user():
    return {"sub": "clerk_user_id"}

@pytest.fixture
def fake_user_out():
    return UserOut(
        id="clerk_user_id",
        name="John Doe",
        email="john@example.com"
    )

@pytest.fixture
def fake_user_create():
    return UserCreate(
        clerk_id="clerk_user_id",
        name="John Doe",
        email="john@example.com"
    )

# override get jwt token function to return a fake token
@pytest.fixture(autouse=True)
def override_get_current_user(fake_clerk_user):
    from db.security import get_current_clerk_user
    app.dependency_overrides[get_current_clerk_user] = lambda: fake_clerk_user
    yield
    app.dependency_overrides.clear()


"""
測試get me
"""
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
def test_get_current_user_success(mock_get_user_by_clerk_id, fake_user_out):
    mock_get_user_by_clerk_id.return_value = fake_user_out

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["name"] == "John Doe"
    assert response.json()["email"] == "john@example.com"

@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
def test_get_current_user_not_found(mock_get_user_by_clerk_id):
    mock_get_user_by_clerk_id.return_value = None

    response = client.get("/users/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

"""
測試查詢使用者
"""
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
def test_get_user_success(mock_get_user_by_clerk_id, fake_user_out):
    mock_get_user_by_clerk_id.return_value = fake_user_out

    response = client.get("/users/abc123")

    assert response.status_code == 200
    assert response.json()["name"] == "John Doe"
    assert response.json()["email"] == "john@example.com"

@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
def test_get_user_not_found(mock_get_user_by_clerk_id):
    mock_get_user_by_clerk_id.return_value = None

    response = client.get("/users/abc123")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


"""
測試註冊新使用者
"""
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
@patch("crud.user.create_user", new_callable=AsyncMock)
def test_register_user_success(mock_create_user, mock_get_user_by_clerk_id, fake_clerk_user, fake_user_create, fake_user_out):
    mock_get_user_by_clerk_id.return_value = None
    mock_create_user.return_value = fake_user_out

    response = client.post("/users/", json=fake_user_create.model_dump())

    assert response.status_code == 200
    assert response.json()["name"] == "John Doe"

@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
@patch("crud.user.create_user", new_callable=AsyncMock)
def test_register_user_already_registered(mock_create_user, mock_get_user_by_clerk_id, fake_clerk_user, fake_user_create, fake_user_out):
    mock_get_user_by_clerk_id.return_value = fake_user_out
    mock_create_user.return_value = fake_user_out

    response = client.post("/users/", json=fake_user_create.model_dump())

    assert response.status_code == 409
    assert response.json()["detail"] == "User already registered"


"""
測試更新使用者
"""
@patch("crud.user.update_user_by_clerk_id", new_callable=AsyncMock)
def test_update_user_success(mock_update_user):
    mock_update_user.return_value = True  # 模擬成功更新

    response = client.put("/users/abc123", json={"name": "Updated Name"})
    
    assert response.status_code == 200
    assert response.json() == {"success": True}

@patch("crud.user.update_user_by_clerk_id", new_callable=AsyncMock)
def test_update_user_not_found(mock_update_user):
    mock_update_user.return_value = False  # 模擬失敗

    response = client.put("/users/abc123", json={"name": "No Change"})
    
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found or no changes made"


"""
測試刪除使用者
"""
@patch("crud.user.delete_user_by_clerk_id", new_callable=AsyncMock)
def test_delete_user_success(mock_delete_user):
    mock_delete_user.return_value = True  # 模擬刪除成功

    response = client.delete("/users/abc123")

    assert response.status_code == 200
    assert response.json() == {"deleted": True}

@patch("crud.user.delete_user_by_clerk_id", new_callable=AsyncMock)
def test_delete_user_not_found(mock_delete_user):
    mock_delete_user.return_value = False  # 模擬找不到使用者

    response = client.delete("/users/abc123")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"