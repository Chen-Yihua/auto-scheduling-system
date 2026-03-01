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
        "apiKey": "fake_api_key",
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

    with patch("routers.jira.db", mock_db), \
         patch("routers.jira.fetch_jira_user_issues", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_issues

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 200
        assert response.json() == mock_issues


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
        "apiKey": "fake_api_key",
        "domain": "fake.atlassian.net"
    }

    mock_db = MagicMock()
    mock_db.linkedAccounts.find_one = AsyncMock(return_value=mock_linked_account)

    with patch("routers.jira.db", mock_db), \
         patch("routers.jira.fetch_jira_user_issues", side_effect=Exception("boom!")):
        
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            response = await ac.get("/jira/issues")

        assert response.status_code == 500
        assert response.json()["detail"] == "boom!"
