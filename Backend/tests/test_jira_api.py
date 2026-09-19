# 透過 HTTP 測試 /jira 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟錯誤狀態碼真的送得出去。
# 各種錯誤分支（503/500/401、header）由 test_jira_router.py 負責，這裡不重複測。
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from main import app
import routers.jira as jira_router


class MockLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者有綁定 Jira。"""

    async def find_one(self, query):
        return {"apiKey": "unused-because-sync-is-mocked", "domain": "fake.atlassian.net"}


class EmptyLinkedAccounts:
    """模擬 db.linkedAccounts.find_one：使用者還沒綁定 Jira。"""

    async def find_one(self, query):
        return None


# 測試 GET /jira/issues —— 抓 Jira issues 並用統一格式回傳
@pytest.mark.asyncio
async def test_get_jira_issues(monkeypatch, logged_in_user):
    # 解密、抓資料、同步各自有 router/crud 測試，這裡只確認 HTTP 這一層，所以直接讓 sync 回傳結果
    issue = {
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

    async def mock_sync(user_id, fetch_fn):
        return [issue], False, None, False

    monkeypatch.setattr(jira_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(jira_router, "decrypt_secret", lambda value: "fake_api_key")
    monkeypatch.setattr(jira_router, "sync_jira_issues", mock_sync)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert res.status_code == status.HTTP_200_OK
    assert res.json() == [issue]
    assert res.headers["X-Data-Stale"] == "false"


# 使用者還沒綁定 Jira：HTTP 回應要是 400 加上說明，前端才能顯示「請先設定帳號」
@pytest.mark.asyncio
async def test_get_jira_issues_when_account_not_linked(monkeypatch, logged_in_user):
    monkeypatch.setattr(jira_router.db, "linkedAccounts", EmptyLinkedAccounts())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json() == {"detail": "No Jira linked account"}


# 沒帶登入 token（這個測試沒有用 logged_in_user）-> 要被擋在門外，不能進到函式裡
@pytest.mark.asyncio
async def test_get_jira_issues_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/jira/issues")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
