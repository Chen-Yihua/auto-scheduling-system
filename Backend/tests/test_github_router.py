import pytest
from fastapi import HTTPException
from datetime import datetime
import routers.github as github_router
from schemas.github import GitHubIssue, GitHubAuthor

mock_user = {"sub": "test_user_123"}

mock_issue = GitHubIssue(
    id=999,
    title="Fix bug",
    state="open",
    created_at=datetime(2024, 1, 1),
    updated_at=datetime(2024, 1, 1),
    url="https://github.com/example/repo/issues/999",
    isPR=False,
    author=GitHubAuthor(username="tester", avatar="https://avatar"),
    labels=["bug"],
    comments=0
)

@pytest.mark.asyncio
async def test_sync_github_issues(monkeypatch):
    inserted = []

    class MockResult:
        @property
        def upserted_id(self):
            return "mock_id"

    class MockCollection:
        async def update_one(self, *args, **kwargs):
            inserted.append(args[1])  # capture {"$set": doc}
            return MockResult()

    monkeypatch.setattr(github_router.db, "github_issues", MockCollection())

    result = await github_router.sync_github_issues([mock_issue], clerk_user=mock_user)

    assert result["status"] == "success"
    assert result["inserted"] == 1
    assert inserted[0]["$set"]["id"] == 999


@pytest.mark.asyncio
async def test_get_github_issues(monkeypatch):
    # 模擬資料庫與 GitHub API 行為
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": "fake_token", "clerk_id": mock_user["sub"]}

    class MockGithubIssues:
        async def update_one(self, *args, **kwargs):
            return type("MockResult", (), {"upserted_id": "mock_id"})()

    async def mock_fetch(token):
        return [
            {
                "number": 999,
                "title": "Fix bug",
                "state": "open",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "html_url": "https://github.com/example/repo/issues/999",
                "user": {"login": "tester", "avatar_url": "https://avatar"},
                "labels": [{"name": "bug"}],
                "comments": 2
            }
        ]

    def mock_transform(raw):
        return {
            "id": raw["number"],
            "title": raw["title"],
            "state": raw["state"],
            "created_at": raw["created_at"],
            "updated_at": raw["updated_at"],
            "url": raw["html_url"],
            "isPR": "pull_request" in raw,
            "author": {
                "username": raw["user"]["login"],
                "avatar": raw["user"]["avatar_url"]
            },
            "labels": [l["name"] for l in raw.get("labels", [])],
            "comments": raw["comments"]
        }

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(github_router.db, "github_issues", MockGithubIssues())
    monkeypatch.setattr(github_router, "fetch_github_user_issues", mock_fetch)
    monkeypatch.setattr(github_router, "transform_github_item", mock_transform)

    result = await github_router.get_github_issues(clerk_user=mock_user)
    assert isinstance(result, list)
    assert result[0]["id"] == 999


@pytest.mark.asyncio
async def test_get_github_issues_missing_token(monkeypatch):
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {}  # 沒有 apiKey

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())

    with pytest.raises(HTTPException) as exc_info:
        await github_router.get_github_issues(clerk_user=mock_user)

    assert exc_info.value.status_code == 400
    assert "No GitHub token linked" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_github_issues_api_fail(monkeypatch):
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": "fake_token"}

    async def mock_fetch(token):
        raise Exception("GitHub API down")

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(github_router, "fetch_github_user_issues", mock_fetch)

    with pytest.raises(HTTPException) as exc_info:
        await github_router.get_github_issues(clerk_user=mock_user)

    assert exc_info.value.status_code == 500
    assert "GitHub API down" in str(exc_info.value.detail)
