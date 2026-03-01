# FastAPI + pytest 的 API 單元測試，用來驗證系統中「使用者綁定帳號的 API」是否正確運作
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from db.security import get_current_clerk_user
from crud import linkedAccount as linked_mod
from schemas.linkedAccount import LinkedAccountCreate

mock_user = {"sub": "test_user_123"}

test_account = LinkedAccountCreate(
    platform="github",
    status="connected",
    username="mock_user",
    apiKey="fake_token"
)

@pytest.mark.asyncio
async def test_create_linked_account(monkeypatch):
    async def mock_get_user():
        return mock_user
    app.dependency_overrides[get_current_clerk_user] = mock_get_user

    async def mock_fetch(token):
        return {"username": "mock_user", "avatar_url": "https://mock.avatar"}

    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch)

    async def mock_insert(doc):
        return None

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "insert_one", mock_insert)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/user/linked-accounts/create", json=test_account.model_dump())

    assert res.status_code == status.HTTP_200_OK
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_linked_accounts(monkeypatch):
    async def mock_get_user():
        return mock_user
    app.dependency_overrides[get_current_clerk_user] = mock_get_user

    # 定義 MockCursor 支援 async for
    class MockCursor:
        def __aiter__(self):
            async def generator():
                yield {
                    "_id": "test_user_123_github",
                    "platform": "github",
                    "status": "connected",
                    "username": "mock_user",
                    "avatar_url": "https://mock.avatar"
                }
            return generator()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find", lambda q: MockCursor())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/user/linked-accounts/me")

    assert res.status_code == status.HTTP_200_OK
    assert res.json()[0]["platform"] == "github"
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_update_linked_account(monkeypatch):
    async def mock_get_user():
        return mock_user
    app.dependency_overrides[get_current_clerk_user] = mock_get_user

    async def mock_update(clerk_id, platform, data):
        return True

    monkeypatch.setattr(linked_mod, "update_linked_account_by_clerk_id", mock_update)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.put("/user/linked-accounts/", json={
            "platform": "github",
            "data": {"status": "connected"}
        })

    assert res.status_code == status.HTTP_200_OK
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_delete_linked_account(monkeypatch):
    async def mock_get_user():
        return mock_user
    app.dependency_overrides[get_current_clerk_user] = mock_get_user

    async def mock_delete(composite_id):
        return True

    monkeypatch.setattr(linked_mod, "delete_linked_account_by_id", mock_delete)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.delete("/user/linked-accounts/github")

    assert res.status_code == status.HTTP_200_OK
    app.dependency_overrides = {}
