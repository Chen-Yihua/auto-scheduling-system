# 透過 HTTP 測試 /users 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟錯誤狀態碼真的送得出去。
# crud 層在這裡整個被 mock 掉；crud 本身由 test_user_crud.py 負責。
import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from unittest.mock import AsyncMock, patch

from main import app  # 假設 FastAPI app 是定義在 main.py 裡
from schemas.user import UserOut, UserCreate


@pytest.fixture
def fake_user_out():
    return UserOut(
        id="test_user_123",
        name="John Doe",
        email="john@example.com"
    )

@pytest.fixture
def fake_user_create():
    return UserCreate(
        clerk_id="test_user_123",
        name="John Doe",
        email="john@example.com"
    )


"""
測試get me
"""
@pytest.mark.asyncio
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
async def test_get_current_user_success(mock_get_user_by_clerk_id, fake_user_out, logged_in_user):
    """GET /users/me：回傳目前登入使用者的資料。"""
    mock_get_user_by_clerk_id.return_value = fake_user_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/users/me")

    assert response.status_code == 200
    assert response.json()["name"] == "John Doe"
    assert response.json()["email"] == "john@example.com"

@pytest.mark.asyncio
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
async def test_get_current_user_not_found(mock_get_user_by_clerk_id, logged_in_user):
    """已登入、但資料庫裡沒有這個使用者 → 404 "User not found"。"""
    mock_get_user_by_clerk_id.return_value = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/users/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

"""
測試註冊新使用者
"""
@pytest.mark.asyncio
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
@patch("crud.user.create_user", new_callable=AsyncMock)
async def test_register_user_success(mock_create_user, mock_get_user_by_clerk_id, fake_user_create, fake_user_out, logged_in_user):
    """POST /users/：還沒註冊過的使用者註冊成功，回傳新使用者。"""
    mock_get_user_by_clerk_id.return_value = None
    mock_create_user.return_value = fake_user_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/users/", json=fake_user_create.model_dump())

    assert response.status_code == 200
    assert response.json()["name"] == "John Doe"

@pytest.mark.asyncio
@patch("crud.user.get_user_by_clerk_id", new_callable=AsyncMock)
@patch("crud.user.create_user", new_callable=AsyncMock)
async def test_register_user_already_registered(mock_create_user, mock_get_user_by_clerk_id, fake_user_create, fake_user_out, logged_in_user):
    """已經註冊過又重複註冊 → 409 "User already registered"。"""
    mock_get_user_by_clerk_id.return_value = fake_user_out
    mock_create_user.return_value = fake_user_out

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/users/", json=fake_user_create.model_dump())

    assert response.status_code == 409
    assert response.json()["detail"] == "User already registered"


"""
測試更新使用者
"""
@pytest.mark.asyncio
@patch("crud.user.update_user_by_clerk_id", new_callable=AsyncMock)
async def test_update_user_success(mock_update_user, logged_in_user):
    """PUT /users/me：更新自己的資料成功，回 {"success": True}。"""
    mock_update_user.return_value = True  # 模擬成功更新

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/users/me", json={"name": "Updated Name"})

    assert response.status_code == 200
    assert response.json() == {"success": True}

@pytest.mark.asyncio
@patch("crud.user.update_user_by_clerk_id", new_callable=AsyncMock)
async def test_update_user_not_found(mock_update_user, logged_in_user):
    """找不到使用者或沒有任何變更 → 404。"""
    from fastapi import HTTPException
    mock_update_user.side_effect = HTTPException(status_code=404, detail="User not found or no changes made")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.put("/users/me", json={"name": "No Change"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found or no changes made"


"""
測試刪除使用者
"""
@pytest.mark.asyncio
@patch("crud.user.delete_user_by_clerk_id", new_callable=AsyncMock)
async def test_delete_user_success(mock_delete_user, logged_in_user):
    """DELETE /users/me：刪除自己成功，回 {"deleted": True}。"""
    mock_delete_user.return_value = True  # 模擬刪除成功

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/users/me")

    assert response.status_code == 200
    assert response.json() == {"deleted": True}

@pytest.mark.asyncio
@patch("crud.user.delete_user_by_clerk_id", new_callable=AsyncMock)
async def test_delete_user_not_found(mock_delete_user, logged_in_user):
    """要刪除的使用者不存在 → 404。"""
    mock_delete_user.return_value = False  # 模擬找不到使用者

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.delete("/users/me")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


"""
測試沒登入
"""
@pytest.mark.asyncio
async def test_get_current_user_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/users/me")

    assert response.status_code in (401, 403)
