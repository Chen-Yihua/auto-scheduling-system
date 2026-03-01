import pytest
from fastapi import status
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List

from main import app
from db.security import get_current_clerk_user
import routers.github as github_router

class MockGitHubIssue(BaseModel):
    id: int
    title: str
    state: str
    created_at: datetime
    updated_at: Optional[datetime]
    url: str
    isPR: bool
    author: Optional[dict]
    labels: Optional[List[str]]
    comments: Optional[int]

mock_user = {"sub": "test_user_123"}

mock_issues = [
    MockGitHubIssue(
        id=999,
        title="Fix bug",
        state="open",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        url="https://github.com/user/repo/issues/999",
        isPR=False,
        author={"username": "mock_user", "avatar": "https://mock.avatar"},
        labels=["bug"],
        comments=2,
    )
]

#測試 POST /github/sync 這個 API —— 把 GitHub issue 傳進後端，並確認資料是否成功儲存
@pytest.mark.anyio
async def test_sync_github_issues(monkeypatch):
    async def mock_get_user():
        return mock_user
    app.dependency_overrides[get_current_clerk_user] = mock_get_user

    class MockUpdateResult:
        def __init__(self, upserted_id="mock_id"):
            self._upserted_id = upserted_id

        @property
        def upserted_id(self):
            return self._upserted_id

    class MockCollection:
        async def update_one(self, *args, **kwargs):
            return MockUpdateResult()

    monkeypatch.setattr(github_router.db, "github_issues", MockCollection())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/github/sync", json=[issue.model_dump(mode="json") for issue in mock_issues])

    print("Response JSON:", res.json())
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["inserted"] == 1

    app.dependency_overrides.clear()

#測試 GET /github/issues 這個 API —— 從 GitHub 抓使用者的 issues 並轉換為統一格式後回傳
@pytest.mark.anyio
async def test_get_github_issues(monkeypatch):
    async def mock_get_user():
        return mock_user
    app.dependency_overrides[get_current_clerk_user] = mock_get_user

    async def mock_find_one(*args, **kwargs):
        return {"apiKey": "fake_token", "clerk_id": mock_user["sub"]}

    async def mock_fetch(token):
        return [
            {
                "number": 999,
                "title": "Fix bug",
                "state": "open",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
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

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockCollection())
    monkeypatch.setattr(github_router.db, "github_issues", MockCollection())
    monkeypatch.setattr(github_router, "fetch_github_user_issues", mock_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/github/issues")

    print("GET Response JSON:", res.json())
    assert res.status_code == status.HTTP_200_OK
    assert any(issue["title"] == "Fix bug" for issue in res.json())

    app.dependency_overrides.clear()
