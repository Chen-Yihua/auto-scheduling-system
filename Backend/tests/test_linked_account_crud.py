import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
import crud.linkedAccount as linked_mod
from crud.linkedAccount import (
    create_linked_account,
    update_linked_account_by_clerk_id,
    get_linked_accounts_by_clerk_id,
    delete_linked_account_by_id,
    fetch_github_userinfo,
)
from schemas.linkedAccount import LinkedAccountCreate
import httpx


# ========== 建立 Linked Account ==========

@pytest.mark.asyncio
async def test_create_github_account_success(monkeypatch):
    inserted_doc = {}

    async def mock_insert_one(doc):
        nonlocal inserted_doc
        inserted_doc = doc

    async def mock_fetch_github_userinfo(token):
        return {"username": "mock_user", "avatar_url": "https://avatar"}

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "insert_one", mock_insert_one)
    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch_github_userinfo)

    account = LinkedAccountCreate(platform="github", apiKey="token123", status="", username="")
    result = await create_linked_account("uid123", account)

    assert inserted_doc["username"] == "mock_user"
    assert result["linkedAccounts"]["github"]["avatar_url"] == "https://avatar"


@pytest.mark.asyncio
async def test_create_github_missing_token():
    account = LinkedAccountCreate(platform="github", apiKey="", status="", username="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_duplicate_account(monkeypatch):
    async def mock_insert_one(doc):
        raise DuplicateKeyError("duplicate")

    async def mock_fetch_github_userinfo(token):
        return {"username": "mock", "avatar_url": "mock"}

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "insert_one", mock_insert_one)
    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch_github_userinfo)

    account = LinkedAccountCreate(platform="github", apiKey="abc123", status="", username="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 409


# ========== 查詢 Linked Accounts ==========

@pytest.mark.asyncio
async def test_get_linked_accounts(monkeypatch):
    class MockCursor:
        def __aiter__(self):
            async def generator():
                yield {"_id": "uid123_github", "platform": "github", "username": "test"}
            return generator()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find", lambda q: MockCursor())
    result = await get_linked_accounts_by_clerk_id("uid123")

    assert isinstance(result, list)
    assert result[0]["id"] == "uid123_github"


# ========== 更新 Linked Account ==========

@pytest.mark.asyncio
async def test_update_github_account_with_token(monkeypatch):
    updated = {}

    async def mock_fetch_github_userinfo(token):
        return {"username": "updated_user", "avatar_url": "https://avatar"}

    async def mock_update_one(filter, update):
        nonlocal updated
        updated = update["$set"]
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch_github_userinfo)

    result = await update_linked_account_by_clerk_id("uid123", "github", {"apiKey": "token"})
    assert result is True
    assert updated["username"] == "updated_user"


@pytest.mark.asyncio
async def test_update_linked_account_no_valid_fields():
    result = await update_linked_account_by_clerk_id("uid123", "github", {"foo": "bar"})
    assert result is False


@pytest.mark.asyncio
async def test_update_github_account_basic(monkeypatch):
    async def mock_update_one(*args, **kwargs):
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    result = await update_linked_account_by_clerk_id("uid123", "github", {"status": "connected"})
    assert result is True


# ========== 刪除 Linked Account ==========

@pytest.mark.asyncio
async def test_delete_linked_account_success(monkeypatch):
    async def mock_delete_one(filter):
        return type("Mock", (), {"deleted_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "delete_one", mock_delete_one)
    result = await delete_linked_account_by_id("uid123_github")
    assert result is True


@pytest.mark.asyncio
async def test_delete_linked_account_not_found(monkeypatch):
    async def mock_delete_one(filter):
        return type("Mock", (), {"deleted_count": 0})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "delete_one", mock_delete_one)
    result = await delete_linked_account_by_id("uid123_github")
    assert result is False


# ========== GitHub Token 驗證 API ==========

@pytest.mark.asyncio
async def test_fetch_github_userinfo_success(monkeypatch):
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            return httpx.Response(
                status_code=200,
                json={"login": "tester", "avatar_url": "https://avatar.com"}
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda: MockClient())
    result = await fetch_github_userinfo("token123")
    assert result["username"] == "tester"


@pytest.mark.asyncio
async def test_fetch_github_userinfo_unauthorized(monkeypatch):
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            return httpx.Response(status_code=401)

    monkeypatch.setattr(httpx, "AsyncClient", lambda: MockClient())
    with pytest.raises(HTTPException) as exc_info:
        await fetch_github_userinfo("bad_token")
    assert exc_info.value.status_code == 401
