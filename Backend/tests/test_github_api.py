# 透過 HTTP 測試 /github 這組 API：路由有註冊、登入驗證有掛上、
# 回傳的 JSON 格式（response_model）跟錯誤狀態碼真的送得出去。
# 各種錯誤分支（503/500/401、header）由 test_github_router.py 負責，這裡不重複測。
import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from datetime import datetime, timezone

from main import app
from db.crypto import encrypt_secret
import routers.github as github_router

# 測試 GET /github/issues —— 從 GitHub 抓使用者的 issues 並轉換為統一格式後回傳
@pytest.mark.asyncio
async def test_get_github_issues(monkeypatch, logged_in_user):
    async def mock_find_one(*args, **kwargs):
        return {"apiKey": encrypt_secret("fake_token"), "clerk_id": logged_in_user["sub"]}

    async def mock_fetch(token):
        return [
            {
                "number": 999,
                "title": "Fix bug",
                "state": "open",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "html_url": "https://github.com/user/repo/issues/999",
                "user": {"login": "mock_user", "avatar_url": "https://mock.avatar"},
                "labels": [{"name": "bug"}],
                "comments": 2,
                "pull_request": {}
            }
        ]

    class MockUpdateResult:
        def __init__(self, upserted_id="mock_id"):
            self._upserted_id = upserted_id

        @property
        def upserted_id(self):
            return self._upserted_id

    class MockCollection:
        async def find_one(self, *args, **kwargs):
            return await mock_find_one(*args, **kwargs)

        async def update_one(self, *args, **kwargs):
            return MockUpdateResult()

        async def delete_many(self, *args, **kwargs):
            return MockUpdateResult()

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockCollection())
    monkeypatch.setattr(github_router.db, "github_issues", MockCollection())
    monkeypatch.setattr(github_router, "fetch_github_user_issues", mock_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert res.status_code == status.HTTP_200_OK
    assert any(issue["title"] == "Fix bug" for issue in res.json())


# 使用者還沒綁定 GitHub：HTTP 回應要是 400 加上說明，前端才能顯示「請先設定帳號」
@pytest.mark.asyncio
async def test_get_github_issues_when_account_not_linked(monkeypatch, logged_in_user):
    class EmptyLinkedAccounts:
        async def find_one(self, *args, **kwargs):
            return None

    monkeypatch.setattr(github_router.db, "linkedAccounts", EmptyLinkedAccounts())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json() == {"detail": "No GitHub token linked"}


# 沒帶登入 token（這個測試沒有用 logged_in_user）-> 要被擋在門外，不能進到函式裡
@pytest.mark.asyncio
async def test_get_github_issues_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
