import os
os.environ["CLERK_SECRET_KEY"] = "dummy"
os.environ["CLERK_PUBLISHABLE_KEY"] = "dummy"
os.environ["CLERK_API_URL"] = "https://api.clerk.dev"
os.environ["CLERK_JWKS_URL"] = "https://fake.clerk.dev/.well-known/jwks.json"
os.environ["CLERK_ISSUER"] = "https://fake.clerk.dev"
os.environ["MONGO_URL"] = "mongodb://fake"
os.environ["ENV"] = "test"

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from db.security import get_current_clerk_user
from db.crypto import encrypt_secret
from routers import jira as router


# 測試用 FastAPI 應用，掛載路由並覆寫依賴
@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_current_clerk_user] = lambda: {"sub": "user123"}
    return app


# 成功取得 Jira issues
@pytest.mark.asyncio
async def test_get_jira_issues_success(test_app):
    mock_linked_account = {
        "apiKey": encrypt_secret("fake_api_key"),
        "domain": "fake.atlassian.net"
    }
    mock_issues = [
        {
            "id": "1",
            "key": "JIRA-1",
            "fields": {
                "summary": "Test Issue 1",
                "status": {"name": "In Progress"},
                "assignee": {"displayName": "User One", "avatarUrls": {}},
                "issuetype": {"name": "Task", "iconUrl": ""},
                "updated": "2024-01-01T00:00:00.000+0000"
            }
        }
    ]

    mock_db = MagicMock()
    mock_db.linkedAccounts.find_one = AsyncMock(return_value=mock_linked_account)
    mock_db.jira_issues.update_one = AsyncMock()
    mock_db.jira_issues.delete_many = AsyncMock()

    # linkedAccounts 查詢還在 router 裡，jira_issues 的存取現在包進 crud/jira.py 的
    # sync_jira_issues，兩邊各自 import 了自己的 db，要一起 patch 才會用到同一個 mock
    with patch("routers.jira.db", mock_db), \
         patch("crud.jira.db", mock_db), \
         patch("routers.jira.fetch_jira_user_issues", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_issues

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 200
        # transform_jira_item 把 Jira 原始 API 的多層巢狀拉平成單層，回傳的不再是
        # mock_issues 那種 fields.xxx 巢狀格式
        assert response.json() == [
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
        assert response.headers["x-data-stale"] == "false"


# 沒有連結的帳號，預期返回 400
@pytest.mark.asyncio
async def test_get_jira_issues_not_linked(test_app):
    mock_db = MagicMock()
    mock_db.linkedAccounts.find_one = AsyncMock(return_value=None)

    with patch("routers.jira.db", mock_db):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 400
        assert response.json()["detail"] == "No Jira linked account"


# fetch_jira_user_issues 出錯，預期返回 500
@pytest.mark.asyncio
async def test_get_jira_issues_internal_error(test_app):
    mock_linked_account = {
        "apiKey": encrypt_secret("fake_api_key"),
        "domain": "fake.atlassian.net"
    }

    mock_db = MagicMock()
    mock_db.linkedAccounts.find_one = AsyncMock(return_value=mock_linked_account)
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])  # 沒有任何快取可退回
    mock_db.jira_issues.find = MagicMock(return_value=mock_cursor)

    with patch("routers.jira.db", mock_db), \
         patch("crud.jira.db", mock_db), \
         patch("routers.jira.fetch_jira_user_issues", side_effect=Exception("boom!")), \
         patch("crud.external_sync.asyncio.sleep", new_callable=AsyncMock):

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 500
        # detail 應該是給使用者看的固定訊息，內部例外原因（"boom!"）只會寫進 log，
        # 不會回傳給前端（避免洩漏內部細節）
        assert response.json()["detail"] == "無法取得 Jira 資料，請稍後再試"


# DB 連不上，預期回 503
@pytest.mark.asyncio
async def test_get_jira_issues_raises_503_when_db_down(test_app):
    from pymongo.errors import PyMongoError

    mock_db = MagicMock()
    mock_db.linkedAccounts.find_one = AsyncMock(side_effect=PyMongoError("connection lost"))

    with patch("routers.jira.db", mock_db):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 503


# apiKey 解密失敗，預期回 500
@pytest.mark.asyncio
async def test_get_jira_issues_raises_500_when_decrypt_fails(test_app):
    mock_db = MagicMock()
    mock_db.linkedAccounts.find_one = AsyncMock(
        return_value={"apiKey": "not-actually-encrypted", "domain": "fake.atlassian.net"}
    )

    with patch("routers.jira.db", mock_db):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 500


# token 失效（NonRetryableError）是 401，跟一般暫時性失敗（500）要分開——
# 這種情況重試也沒用，使用者要重新連結帳號才能解決
@pytest.mark.asyncio
async def test_get_jira_issues_token_expired_raises_401(test_app):
    from crud.errors import NonRetryableError

    mock_linked_account = {
        "apiKey": encrypt_secret("fake_api_key"),
        "domain": "fake.atlassian.net",
    }

    mock_db = MagicMock()
    mock_db.linkedAccounts.find_one = AsyncMock(return_value=mock_linked_account)
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_db.jira_issues.find = MagicMock(return_value=mock_cursor)

    with patch("routers.jira.db", mock_db), \
         patch("crud.jira.db", mock_db), \
         patch("routers.jira.fetch_jira_user_issues", side_effect=NonRetryableError("401 Unauthorized")):

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 401
        assert response.json()["detail"] == "Jira 授權已失效，請重新連結帳號"


# 有快取可退回、但 token 已失效：確認 X-Auth-Error header 有正確設定
@pytest.mark.asyncio
async def test_get_jira_issues_sets_auth_error_header(test_app):
    mock_linked_account = {
        "apiKey": encrypt_secret("fake_api_key"),
        "domain": "fake.atlassian.net",
    }

    mock_db = MagicMock()
    mock_db.linkedAccounts.find_one = AsyncMock(return_value=mock_linked_account)

    mock_issue = {
        "id": "1",
        "key": "JIRA-1",
        "title": "Test Issue",
        "status": "Open",
        "updated_at": "2024-01-01T00:00:00.000+0000",
        "assignee": "",
        "avatar": "",
        "type": "Task",
        "iconUrl": "",
    }

    async def mock_sync(user_id, fetch_fn):
        return ([mock_issue], True, None, True)

    with patch("routers.jira.db", mock_db), \
         patch("routers.jira.sync_jira_issues", mock_sync):

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 200
        assert response.json() == [mock_issue]
        assert response.headers["x-auth-error"] == "true"
        assert response.headers["x-data-stale"] == "true"
