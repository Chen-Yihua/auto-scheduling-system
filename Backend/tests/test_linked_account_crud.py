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
    """建立 GitHub 綁定帳號成功：用 GitHub 回傳的使用者資訊填 username / avatar，apiKey 存進資料庫前要加密。"""
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
    """GitHub 沒帶 apiKey → 400。"""
    account = LinkedAccountCreate(platform="github", apiKey="", status="", username="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_jira_missing_domain():
    """Jira 沒帶 domain → 400。"""
    account = LinkedAccountCreate(platform="jira", apiKey="abc123", domain=None, status="", username="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_moodle_missing_password():
    """Moodle 沒帶密碼 → 400。"""
    account = LinkedAccountCreate(platform="moodle", username="stu001", password="", status="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_moodle_wrong_password_rejected(monkeypatch):
    """Moodle 帳密驗證失敗（NonRetryableError）→ 401。"""
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
    """該平台已經綁定過 → 409。"""
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


@pytest.mark.asyncio
async def test_create_account_unsupported_platform_returns_400():
    """不支援的平台（例如 notion）→ 400。"""
    account = LinkedAccountCreate(platform="notion", apiKey="abc123", status="", username="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_jira_account_success(monkeypatch):
    """建立 Jira 綁定帳號成功：用 Jira 回傳的使用者資訊填 username / avatar。"""
    updated_doc = {}

    async def mock_update_one(filter, update, upsert=False):
        nonlocal updated_doc
        updated_doc = update["$set"]
        return type("Mock", (), {"upserted_id": "uid123_jira"})()

    async def mock_fetch_jira_userinfo(api_key, domain):
        return {"username": "jira_user", "avatar_url": "https://avatar"}

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "fetch_jira_userinfo", mock_fetch_jira_userinfo)

    account = LinkedAccountCreate(
        platform="jira", apiKey="abc123", domain="example.atlassian.net", status="", username=""
    )
    result = await create_linked_account("uid123", account)

    assert updated_doc["username"] == "jira_user"
    assert result["linkedAccounts"]["jira"]["avatar_url"] == "https://avatar"


@pytest.mark.asyncio
async def test_create_moodle_account_success(monkeypatch):
    """建立 Moodle 綁定帳號成功：帳密驗證通過後 status 為 connected，密碼存進資料庫前要加密。"""
    updated_doc = {}

    async def mock_update_one(filter, update, upsert=False):
        nonlocal updated_doc
        updated_doc = update["$set"]
        return type("Mock", (), {"upserted_id": "uid123_moodle"})()

    def mock_verify_succeeds(username, password):
        return True

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "verify_moodle_login", mock_verify_succeeds)

    account = LinkedAccountCreate(platform="moodle", username="stu001", password="pw123", status="")
    result = await create_linked_account("uid123", account)

    assert updated_doc["status"] == "connected"
    assert updated_doc["password"] != "pw123"  # 落地前一定要加密
    assert result["linkedAccounts"]["moodle"]["status"] == "connected"


@pytest.mark.asyncio
async def test_create_moodle_webdriver_exception_raises_503(monkeypatch):
    """Selenium/WebDriver 本身出包（不是帳密錯誤）→ 503。這是我方服務暫時有問題，要跟使用者輸入錯誤的 401 分開。"""
    from selenium.common.exceptions import WebDriverException

    def mock_verify_raises(username, password):
        raise WebDriverException("driver crashed")

    monkeypatch.setattr(linked_mod, "verify_moodle_login", mock_verify_raises)

    account = LinkedAccountCreate(platform="moodle", username="stu001", password="pw123", status="")
    with pytest.raises(HTTPException) as exc_info:
        await create_linked_account("uid123", account)
    assert exc_info.value.status_code == 503


# ========== 查詢 Linked Accounts ==========

@pytest.mark.asyncio
async def test_get_linked_accounts(monkeypatch):
    """查詢綁定帳號 → 回傳清單，每筆用 id 欄位識別，不含資料庫內部的 _id。"""
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
    """查詢時敏感欄位（密碼）只回遮罩過的字串，絕不回傳明文。"""
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

    assert result[0]["password"] != "real-password"
    assert result[0]["password"].endswith("word")  # mask_secret 保留最後幾碼


# ========== 更新 Linked Account ==========

@pytest.mark.asyncio
async def test_update_github_account_with_token(monkeypatch):
    """更新 GitHub 的 apiKey → 用新 token 重新驗證並更新 username，apiKey 存進資料庫前要加密。"""
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
    """payload 裡沒有任何合法欄位（例如只有 foo）→ 回傳 False（router 會轉成 404）。"""
    result = await update_linked_account_by_clerk_id(
        "uid123", "github", {"payload": {"foo": "bar"}}
    )
    assert result is False


@pytest.mark.asyncio
async def test_update_linked_account_invalid_payload_raises_400():
    """payload 不是 dict → 400。"""
    with pytest.raises(HTTPException) as exc_info:
        await update_linked_account_by_clerk_id("uid123", "github", {"payload": "not-a-dict"})
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_github_account_basic(monkeypatch):
    """只更新 status 這類不需要重新驗證的欄位 → 直接更新，回傳 True。"""
    async def mock_update_one(*args, **kwargs):
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    result = await update_linked_account_by_clerk_id(
        "uid123", "github", {"payload": {"status": "connected"}}
    )
    assert result is True


@pytest.mark.asyncio
async def test_update_jira_account_with_domain_reverifies(monkeypatch):
    """同時更新 Jira 的 apiKey 和 domain → 用新值重新驗證，apiKey 存進資料庫前要加密。"""
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
async def test_update_jira_apikey_only_reverifies_with_existing_domain(monkeypatch):
    """只改 apiKey、沒帶 domain → 要去查現有的 domain，一起驗證新 token。"""
    verify_calls = []

    async def mock_find_one(filter):
        return {"domain": "existing.atlassian.net"}

    async def mock_fetch_jira_userinfo(api_key, domain):
        verify_calls.append((api_key, domain))
        return {"username": "jira_user", "avatar_url": "https://avatar"}

    updated = {}

    async def mock_update_one(filter, update, upsert=False):
        nonlocal updated
        updated = update["$set"]
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find_one", mock_find_one)
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "fetch_jira_userinfo", mock_fetch_jira_userinfo)

    result = await update_linked_account_by_clerk_id(
        "uid123", "jira", {"payload": {"apiKey": "newkey"}}
    )
    assert result is True
    assert verify_calls == [("newkey", "existing.atlassian.net")]
    assert updated["apiKey"] != "newkey"  # 落地前加密


@pytest.mark.asyncio
async def test_update_jira_domain_only_reverifies_with_existing_apikey(monkeypatch):
    """只改 domain、沒帶 apiKey → 要去查現有的 apiKey（解密後）一起驗證新 domain，而且不能把 apiKey 塞進要更新的欄位。"""
    from db.crypto import encrypt_secret

    verify_calls = []

    async def mock_find_one(filter):
        return {"apiKey": encrypt_secret("existingkey")}

    async def mock_fetch_jira_userinfo(api_key, domain):
        verify_calls.append((api_key, domain))
        return {"username": "jira_user", "avatar_url": "https://avatar"}

    updated = {}

    async def mock_update_one(filter, update, upsert=False):
        nonlocal updated
        updated = update["$set"]
        return type("Mock", (), {"modified_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "find_one", mock_find_one)
    monkeypatch.setattr(linked_mod.db.linkedAccounts, "update_one", mock_update_one)
    monkeypatch.setattr(linked_mod, "fetch_jira_userinfo", mock_fetch_jira_userinfo)

    result = await update_linked_account_by_clerk_id(
        "uid123", "jira", {"payload": {"domain": "new-instance.atlassian.net"}}
    )
    assert result is True
    assert verify_calls == [("existingkey", "new-instance.atlassian.net")]
    assert "apiKey" not in updated
    assert updated["domain"] == "new-instance.atlassian.net"


@pytest.mark.asyncio
async def test_update_moodle_password_reverifies_with_existing_username(monkeypatch):
    """更新 Moodle 密碼時沒帶 username → 要去查現有帳號的 username，一起驗證新密碼。"""
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
    assert verify_calls == [("stu001", "newpass")]
    assert updated["password"] != "newpass"  # 落地前加密


@pytest.mark.asyncio
async def test_update_moodle_username_only_reverifies_with_existing_password(monkeypatch):
    """只改 Moodle 帳號、沒帶新密碼 → 要去查現有密碼（解密後）一起驗證新帳號，而且不能把 password 塞進要更新的欄位。"""
    from db.crypto import encrypt_secret

    verify_calls = []

    async def mock_find_one(filter):
        return {"username": "stu001", "password": encrypt_secret("oldpass")}

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
        "uid123", "moodle", {"payload": {"username": "stu002"}}
    )
    assert result is True
    assert verify_calls == [("stu002", "oldpass")]
    assert "password" not in updated
    assert updated["username"] == "stu002"
    assert updated["status"] == "connected"


@pytest.mark.asyncio
async def test_update_moodle_wrong_password_raises_401(monkeypatch):
    """更新 Moodle 密碼但驗證失敗 → 401。"""
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
    """刪除綁定帳號成功 → 不出錯。"""
    async def mock_delete_one(filter):
        return type("Mock", (), {"deleted_count": 1})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "delete_one", mock_delete_one)
    await delete_linked_account_by_id("uid123_github")


@pytest.mark.asyncio
async def test_delete_linked_account_not_found(monkeypatch):
    """要刪除的綁定帳號不存在 → 404。"""
    async def mock_delete_one(filter):
        return type("Mock", (), {"deleted_count": 0})()

    monkeypatch.setattr(linked_mod.db.linkedAccounts, "delete_one", mock_delete_one)
    with pytest.raises(HTTPException) as exc_info:
        await delete_linked_account_by_id("uid123_github")
    assert exc_info.value.status_code == 404


# ========== 第三方帳號驗證 API ==========

@pytest.mark.asyncio
async def test_fetch_github_userinfo_success(monkeypatch):
    """GitHub 回 200 → 回傳統一格式的使用者資訊（username 來自 login）。"""
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
    """GitHub 回 401（token 無效）→ 401。"""
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
async def test_fetch_github_userinfo_connection_error_raises_502(monkeypatch):
    """連不上 GitHub → 502。"""
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("GitHub 掛了")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    with pytest.raises(HTTPException) as exc_info:
        await fetch_github_userinfo("token123")
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_fetch_github_userinfo_other_error_status_raises_403(monkeypatch):
    """GitHub 回 401 以外的錯誤狀態（例如 404）→ 403。"""
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            return httpx.Response(status_code=404)  # 不是 401，但也不是 200

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    with pytest.raises(HTTPException) as exc_info:
        await fetch_github_userinfo("token123")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_fetch_jira_userinfo_success(monkeypatch):
    """Jira 回 200 → 回傳統一格式的使用者資訊（username 來自 displayName）。"""
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
    """Jira 回 401（API key 無效）→ 401。"""
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            return httpx.Response(status_code=401)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    with pytest.raises(HTTPException) as exc_info:
        await fetch_jira_userinfo("bad_key", "example.atlassian.net")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_fetch_jira_userinfo_connection_error_raises_502(monkeypatch):
    """連不上 Jira → 502。"""
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("Jira 掛了")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    with pytest.raises(HTTPException) as exc_info:
        await fetch_jira_userinfo("base64key", "example.atlassian.net")
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_fetch_jira_userinfo_other_error_status_raises_403(monkeypatch):
    """Jira 回 401 以外的錯誤狀態（例如 404）→ 403。"""
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *args, **kwargs):
            return httpx.Response(status_code=404)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: MockClient())
    with pytest.raises(HTTPException) as exc_info:
        await fetch_jira_userinfo("base64key", "example.atlassian.net")
    assert exc_info.value.status_code == 403
