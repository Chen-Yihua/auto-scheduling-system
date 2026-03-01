import pytest
import crud.github as github_mod
from httpx import Response, Request

@pytest.mark.asyncio
async def test_fetch_github_user_issues(monkeypatch):
    calls = []

    class MockResponse:
        def __init__(self, query):
            self.status_code = 200
            self._query = query

        def json(self):
            if "is:issue" in self._query:
                return {"items": [{"number": 1, "title": "Issue 1"}]}
            else:
                return {"items": [{"number": 2, "title": "PR 2", "pull_request": {}}]}

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            calls.append(params["q"])
            return MockResponse(params["q"])

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    result = await github_mod.fetch_github_user_issues("fake_token")

    assert isinstance(result, list)
    assert len(result) == 2
    assert any(item["title"] == "Issue 1" for item in result)
    assert any(item["title"] == "PR 2" for item in result)
    assert calls == ["involves:@me is:issue", "involves:@me is:pull-request"]


@pytest.mark.asyncio
async def test_fetch_github_user_issues_api_fail(monkeypatch):
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            return Response(status_code=403, content=b"Forbidden", request=Request("GET", url))

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    with pytest.raises(Exception) as exc_info:
        await github_mod.fetch_github_user_issues("invalid_token")

    assert "GitHub API failed" in str(exc_info.value)


def test_transform_github_item_issue():
    raw = {
        "number": 123,
        "title": "Test issue",
        "state": "open",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "html_url": "https://github.com/example/repo/issues/123",
        "user": {"login": "alice", "avatar_url": "https://avatar"},
        "labels": [{"name": "bug"}],
        "comments": 3
    }

    result = github_mod.transform_github_item(raw)

    assert result["id"] == 123
    assert result["title"] == "Test issue"
    assert result["isPR"] is False
    assert result["author"]["username"] == "alice"
    assert result["labels"] == ["bug"]
    assert result["comments"] == 3


def test_transform_github_item_pr():
    raw = {
        "number": 456,
        "title": "Add feature",
        "state": "open",
        "created_at": "2024-01-03T00:00:00Z",
        "updated_at": "2024-01-04T00:00:00Z",
        "html_url": "https://github.com/example/repo/pull/456",
        "user": {"login": "bob", "avatar_url": "https://avatar2"},
        "labels": [],
        "comments": 1,
        "pull_request": {} 
    }

    result = github_mod.transform_github_item(raw)

    assert result["id"] == 456
    assert result["isPR"] is True
