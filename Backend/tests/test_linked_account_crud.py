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
    fetch_jira_userinfo,
)
from crud.errors import NonRetryableError
from schemas.linkedAccount import LinkedAccountCreate
import httpx


# ========== 建立 Linked Account ==========

@pytest.mark.asyncio
async def test_create_github_account_success(monkeypatch):
    updated_doc = {}

    async def mock_update_one(filter, update, upsert=False):
        nonlocal updated_doc
        updated_doc = update["$set"]
        return type("Mock", (), {"upserted_id": "uid123_github"})()

    async def mock_fetch_github_userinfo(token):
        return {"username": "mock_user", "avatar_url": "https://avatar"}

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch_github_userinfo)

    account = LinkedAccountCreate(platform="github", apiKey="token123", status="", username="")
    result = await create_linked_account("uid123", account)

    assert updated_doc["username"] == "mock_user"
    assert updated_doc["apiKey"] != "token123"  # 落地前一定要加密，不是明文
    assert result["linkedAccounts"]["github"]["avatar_url"] == "https://avatar"


@pytest.mark.asyncio
async def test_create_github_missing_token():
    account = LinkedAccountCreate(platform="github", apiKey="", status="", username="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_jira_missing_domain():
    account = LinkedAccountCreate(platform="jira", apiKey="abc123", domain=None, status="", username="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_moodle_missing_password():
    account = LinkedAccountCreate(platform="moodle", username="stu001", password="", status="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_moodle_wrong_password_rejected(monkeypatch):
    # verify_moodle_login 本身是同步函式（真正的實作用 Selenium），
    # create_linked_account 用 run_in_threadpool 呼叫它——mock 也要是同步的
    def mock_verify_fails(username, password):
        raise NonRetryableError(f"Moodle 登入失敗，使用者：{username}")

    monkeypatch.setattr(linked_mod, "verify_moodle_login", mock_verify_fails)

    account = LinkedAccountCreate(platform="moodle", username="stu001", password="wrong", status="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_create_duplicate_account_returns_409(monkeypatch):
    async def mock_update_one(filter, update, upsert=False):
        raise DuplicateKeyError("duplicate")

    async def mock_fetch_github_userinfo(token):
        return {"username": "mock", "avatar_url": "mock"}

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
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


@pytest.mark.asyncio
async def test_get_linked_accounts_masks_sensitive_fields(monkeypatch):
    from db.crypto import encrypt_secret

    class MockCursor:
        def __aiter__(self):
            async def generator():
                yield {
                    "_id": "uid123_moodle",
                    "platform": "moodle",
                    "username": "stu001",
                    "password": encrypt_secret("real-password"),
                }
            return generator()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find", lambda q: MockCursor())
    result = await get_linked_accounts_by_clerk_id("uid123")

    # 絕不把解密後的明文密碼回傳給呼叫端，只回遮罩過的字串
    assert result[0]["password"] != "real-password"
    assert result[0]["password"].endswith("word")  # mask_secret 保留最後幾碼


# ========== 更新 Linked Account ==========

@pytest.mark.asyncio
async def test_update_github_account_with_token(monkeypatch):
    updated = {}

    async def mock_fetch_github_userinfo(token):
        return {"username": "updated_user", "avatar_url": "https://avatar"}

    async def mock_update_one(filter, update, upsert=False):
        nonlocal updated
        updated = update["$set"]
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "fetch_github_userinfo", mock_fetch_github_userinfo)

    result = await update_linked_account_by_clerk_id(
        "uid123", "github", {"payload": {"apiKey": "token"}}
    )
    assert result is True
    assert updated["username"] == "updated_user"
    assert updated["apiKey"] != "token"  # 落地前加密


@pytest.mark.asyncio
async def test_update_linked_account_no_valid_fields():
    result = await update_linked_account_by_clerk_id(
        "uid123", "github", {"payload": {"foo": "bar"}}
    )
    assert result is False


@pytest.mark.asyncio
async def test_update_github_account_basic(monkeypatch):
    async def mock_update_one(*args, **kwargs):
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    result = await update_linked_account_by_clerk_id(
        "uid123", "github", {"payload": {"status": "connected"}}
    )
    assert result is True


@pytest.mark.asyncio
async def test_update_jira_account_with_domain_reverifies(monkeypatch):
    updated = {}

    async def mock_fetch_jira_userinfo(api_key, domain):
        return {"username": "jira_user", "avatar_url": "https://avatar"}

    async def mock_update_one(filter, update, upsert=False):
        nonlocal updated
        updated = update["$set"]
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "fetch_jira_userinfo", mock_fetch_jira_userinfo)

    result = await update_linked_account_by_clerk_id(
        "uid123", "jira", {"payload": {"apiKey": "newkey", "domain": "foo.atlassian.net"}}
    )
    assert result is True
    assert updated["username"] == "jira_user"
    assert updated["apiKey"] != "newkey"  # 落地前加密


@pytest.mark.asyncio
async def test_update_moodle_password_reverifies_with_existing_username(monkeypatch):
    verify_calls = []

    async def mock_find_one(filter):
        return {"username": "stu001"}

    def mock_verify(username, password):
        verify_calls.append((username, password))

    updated = {}

    async def mock_update_one(filter, update, upsert=False):
        nonlocal updated
        updated = update["$set"]
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find_one", mock_find_one)
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "verify_moodle_login", mock_verify)

    result = await update_linked_account_by_clerk_id(
        "uid123", "moodle", {"payload": {"password": "newpass"}}
    )
    assert result is True
    # 更新密碼時沒帶 username -> 要去查現有帳號的 username 一起驗證
    assert verify_calls == [("stu001", "newpass")]
    assert updated["password"] != "newpass"  # 落地前加密


@pytest.mark.asyncio
async def test_update_moodle_wrong_password_raises_401(monkeypatch):
    async def mock_find_one(filter):
        return {"username": "stu001"}

    def mock_verify_fails(username, password):
        raise NonRetryableError("wrong password")

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find_one", mock_find_one)
    monkeypatch.setattr(linked_mod, "verify_moodle_login", mock_verify_fails)

    with pytest.raises(HTTPException) as exc_info:
        await update_linked_account_by_clerk_id(
            "uid123", "moodle", {"payload": {"password": "wrong"}}
        )
    assert exc_info.value.status_code == 401


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


# ========== 第三方帳號驗證 API ==========

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

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    result = await fetch_github_userinfo("token123")
    assert result["username"] == "tester"


@pytest.mark.asyncio
async def test_fetch_github_userinfo_unauthorized(monkeypatch):
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            return httpx.Response(status_code=401)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    with pytest.raises(HTTPException) as exc_info:
        await fetch_github_userinfo("bad_token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_fetch_jira_userinfo_success(monkeypatch):
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            return httpx.Response(
                status_code=200,
                json={"displayName": "Jira Tester", "avatarUrls": {"48x48": "https://avatar.com"}}
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    result = await fetch_jira_userinfo("base64key", "example.atlassian.net")
    assert result["username"] == "Jira Tester"


@pytest.mark.asyncio
async def test_fetch_jira_userinfo_unauthorized(monkeypatch):
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            return httpx.Response(status_code=401)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    with pytest.raises(HTTPException) as exc_info:
        await fetch_jira_userinfo("bad_key", "example.atlassian.net")
    assert exc_info.value.status_code == 401
