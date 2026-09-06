import pytest
from fastapi import HTTPException
import routers.github as github_router
from db.crypto import encrypt_secret

mock_user = {"sub": "test_user_123"}

@pytest.mark.asyncio
async def test_get_github_issues(monkeypatch):
    # 模擬資料庫與 GitHub API 行為
    class MockLinkedAccounts:
        async def find_one(self, query):
            return {"apiKey": encrypt_secret("fake_token"), "clerk_id": mock_user["sub"]}

    class MockGithubIssues:
        async def update_one(self, *args, **kwargs):
            return type("MockResult", (), {"upserted_id": "mock_id"})()

        async def delete_many(self, *args, **kwargs):
            return type("MockResult", (), {"deleted_count": 0})()

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
            return {"apiKey": encrypt_secret("fake_token")}

    class MockCursor:
        async def to_list(self, length=None):
            return []  # 沒有任何快取可退回

    class MockGithubIssues:
        def find(self, *args, **kwargs):
            return MockCursor()

    async def mock_fetch(token):
        raise Exception("GitHub API down")

    async def instant_sleep(seconds):
        pass

    monkeypatch.setattr(github_router.db, "linkedAccounts", MockLinkedAccounts())
    monkeypatch.setattr(github_router.db, "github_issues", MockGithubIssues())
    monkeypatch.setattr(github_router, "fetch_github_user_issues", mock_fetch)
    monkeypatch.setattr("crud.external_sync.asyncio.sleep", instant_sleep)

    with pytest.raises(HTTPException) as exc_info:
        await github_router.get_github_issues(clerk_user=mock_user)

    assert exc_info.value.status_code == 500
    # detail 應該是給使用者看的固定訊息，內部例外原因（"GitHub API down"）
    # 只會寫進 log，不會回傳給前端（避免洩漏內部細節）
    assert exc_info.value.detail == "無法取得 GitHub 資料，請稍後再試"
