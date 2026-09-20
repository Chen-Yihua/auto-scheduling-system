# 透過 HTTP 測試 /user/linked-accounts 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟錯誤狀態碼真的送得出去。
# crud 層在這裡被 mock 掉；crud 本身由 test_linked_account_crud.py 負責，
# 多步驟的情境由 test_linked_account_scenario.py 負責。
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
from crud import linkedAccount as linked_mod
from schemas.linkedAccount import LinkedAccountCreate

test_account = LinkedAccountCreate(
    platform="github",
    status="connected",
    username="mock_user",
    apiKey="fake_token"
)


@pytest.mark.asyncio
async def test_create_linked_account(monkeypatch, logged_in_user):
    """POST /user/linked-accounts/create：建立 GitHub 綁定帳號成功，回 200。"""
    async def mock_fetch(token):
        return {"username": "mock_user", "avatar_url": "https://mock.avatar"}

    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch)

    async def mock_update_one(filter, update, upsert=False):
        return type("Mock", (), {"upserted_id": "test_user_123_github"})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/user/linked-accounts/create", json=test_account.model_dump())

    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_get_linked_accounts(monkeypatch, logged_in_user):
    """GET /user/linked-accounts/me：回傳目前使用者綁定的帳號清單。"""
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


@pytest.mark.asyncio
async def test_update_linked_account(monkeypatch, logged_in_user):
    """PUT /user/linked-accounts/：更新綁定帳號成功，回 200。"""
    async def mock_update(clerk_id, platform, data):
        return True

    monkeypatch.setattr(linked_mod, "update_linked_account_by_clerk_id", mock_update)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.put("/user/linked-accounts/", json={
            "platform": "github",
            "data": {"payload": {"status": "connected"}}
        })

    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_delete_linked_account(monkeypatch, logged_in_user):
    """DELETE /user/linked-accounts/{platform}：刪除綁定帳號成功，回 200。"""
    async def mock_delete(composite_id):
        return True

    monkeypatch.setattr(linked_mod, "delete_linked_account_by_id", mock_delete)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.delete("/user/linked-accounts/github")

    assert res.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_update_linked_account_not_found(monkeypatch, logged_in_user):
    """要更新的綁定帳號不存在（或沒有任何合法欄位可更新）→ 404 加說明。"""
    async def mock_update(clerk_id, platform, data):
        return False

    monkeypatch.setattr(linked_mod, "update_linked_account_by_clerk_id", mock_update)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.put("/user/linked-accounts/", json={
            "platform": "github",
            "data": {"payload": {"status": "connected"}}
        })

    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json() == {"detail": "Linked account not found or no valid fields to update"}


@pytest.mark.asyncio
async def test_get_linked_accounts_requires_login():
    """沒帶登入 token → 被擋在門外（401/403），不能進到函式裡。"""
    # 這個測試刻意不用 logged_in_user，所以請求是沒登入的
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/user/linked-accounts/me")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
