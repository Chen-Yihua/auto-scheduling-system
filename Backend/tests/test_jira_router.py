# 直接呼叫 router 函式（await jira_router.get_jira_issues(...)）測試它自己的判斷分支：
# 查不到帳號、DB 掛掉、解密失敗、同步失敗各回什麼狀態碼，以及有沒有設定回應 header。
# 不經過 HTTP，所以不涉及路由註冊、登入驗證、response_model —— 那些由 test_jira_api.py 負責。
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException, Response
import routers.jira as jira_router
from db.crypto import encrypt_secret
from crud.errors import NonRetryableError

mock_user = {"sub": "test_user_123"}


@pytest.mark.asyncio
async def test_get_jira_issues_success(monkeypatch):
    """成功流程：查到帳號 → 解密 API key → 抓 Jira → 轉成統一格式（把巢狀欄位拉平）→ 回傳清單，X-Data-Stale 為 false；抓資料時用的是解密後的明文 key，不是資料庫裡的密文。"""
    fetch_calls = []

    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_api_key"), "domain": "fake.atlassian.net"}

    async def mock_fetch_jira_user_issues(api_key, domain):
        fetch_calls.append((api_key, domain))
        return [
            {
                "id": "1",
                "key": "JIRA-1",
                "fields": {
                    "summary": "Test Issue 1",
                    "status": {"name": "In Progress"},
                    "assignee": {"displayName": "User One", "avatarUrls": {}},
                    "issuetype": {"name": "Task", "iconUrl": ""},
                    "updated": "2024-01-01T00:00:00.000+0000",
                },
            }
        ]

    async def mock_sync(user_id, fetch_fn):
        # 真的執行 router 交給 sync 的 fetch_fn，才測得到「解密 -> 抓資料 -> 轉格式」這段
        return (await fetch_fn(), False, None, False)

    monkeypatch.setattr(jira_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(jira_router, "fetch_jira_user_issues", mock_fetch_jira_user_issues)
    monkeypatch.setattr(jira_router, "sync_jira_issues", mock_sync)

    response = Response()
    result = await jira_router.get_jira_issues(response=response, user=mock_user)

    # transform_jira_item 把 Jira 原始 API 的多層巢狀拉平成單層
    assert result == [
        {
            "id": "1",
            "key": "JIRA-1",
            "title": "Test Issue 1",
            "status": "In Progress",
            "updated_at": "2024-01-01T00:00:00.000+0000",
            "assignee": "User One",
            "avatar": "",
            "type": "Task",
            "iconUrl": "",
        }
    ]
    assert response.headers["X-Data-Stale"] == "false"
    # API key 在資料庫裡是加密的，抓資料前一定要先在伺服器內部解密回明文
    assert fetch_calls == [("fake_api_key", "fake.atlassian.net")]


@pytest.mark.asyncio
async def test_get_jira_issues_raises_400_when_account_not_linked(monkeypatch):
    """使用者還沒綁定 Jira → 回 400 "No Jira linked account"。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return None

    monkeypatch.setattr(jira_router.db, "linkedAccounts", MockLinkedAccounts())

    with pytest.raises(HTTPException) as exc_info:
        await jira_router.get_jira_issues(user=mock_user)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "No Jira linked account"


@pytest.mark.asyncio
async def test_get_jira_issues_raises_500_when_decrypt_fails(monkeypatch):
    """API key 解密失敗（資料壞掉或金鑰不對）→ 回 500。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": "not-actually-encrypted", "domain": "fake.atlassian.net"}

    monkeypatch.setattr(jira_router.db, "linkedAccounts", MockLinkedAccounts())

    with pytest.raises(HTTPException) as exc_info:
        await jira_router.get_jira_issues(user=mock_user)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_jira_issues_raises_500_on_unexpected_sync_error(monkeypatch):
    """同步時出現未預期的錯誤 → 回 500 和固定中文訊息；內部錯誤原因只寫進 log，不回傳給前端。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_api_key"), "domain": "fake.atlassian.net"}

    async def mock_sync(user_id, fetch_fn):
        raise Exception("boom!")

    monkeypatch.setattr(jira_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(jira_router, "sync_jira_issues", mock_sync)

    with pytest.raises(HTTPException) as exc_info:
        await jira_router.get_jira_issues(user=mock_user)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "無法取得 Jira 資料，請稍後再試"


@pytest.mark.asyncio
async def test_get_jira_issues_token_expired_raises_401(monkeypatch):
    """token 失效（NonRetryableError）要回 401，跟一般暫時性失敗（500）分開——重試也沒用，使用者要重新連結帳號才能解決。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_api_key"), "domain": "fake.atlassian.net"}

    async def mock_sync(user_id, fetch_fn):
        raise NonRetryableError("401 Unauthorized")

    monkeypatch.setattr(jira_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(jira_router, "sync_jira_issues", mock_sync)

    with pytest.raises(HTTPException) as exc_info:
        await jira_router.get_jira_issues(user=mock_user)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Jira 授權已失效，請重新連結帳號"


@pytest.mark.asyncio
async def test_get_jira_issues_sets_auth_error_header(monkeypatch):
    """token 已失效但還有舊資料可退回時：回舊資料，並設定 X-Auth-Error、X-Data-Stale、X-Synced-At。"""
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_api_key"), "domain": "fake.atlassian.net"}

    synced_at = datetime(2026, 9, 10, tzinfo=timezone.utc)

    async def mock_sync(user_id, fetch_fn):
        # stale=True、auth_error=True：token 失效但還有快取可以退回顯示
        return ([{"id": "1"}], True, synced_at, True)

    monkeypatch.setattr(jira_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(jira_router, "sync_jira_issues", mock_sync)

    response = Response()
    result = await jira_router.get_jira_issues(response=response, user=mock_user)

    assert result == [{"id": "1"}]
    assert response.headers["X-Auth-Error"] == "true"
    assert response.headers["X-Data-Stale"] == "true"
    assert response.headers["X-Synced-At"] == synced_at.isoformat()
