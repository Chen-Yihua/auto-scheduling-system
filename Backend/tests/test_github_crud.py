import pytest
import crud.github as github_mod
from crud.errors import NonRetryableError
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
async def test_fetch_github_user_issues_paginates_full_pages(monkeypatch):
    """一頁抓滿（等於 per_page）代表可能還有下一頁，該繼續翻頁，不能只抓第一頁。"""
    calls = []

    class MockResponse:
        def __init__(self, page):
            self.status_code = 200
            self._page = page

        def json(self):
            # 第 1 頁回滿 2 筆（等於這次測試用的 per_page=2），第 2 頁只回 1 筆代表抓到底了
            if self._page == 1:
                return {"items": [{"number": 1}, {"number": 2}]}
            return {"items": [{"number": 3}]}

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            calls.append((params["q"], params["page"]))
            return MockResponse(params["page"])

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    result = await github_mod.fetch_github_user_issues("fake_token", per_page=2)

    # 兩個 query（issue / PR）各自都要翻到第 2 頁才停下來
    assert calls == [
        ("involves:@me is:issue", 1),
        ("involves:@me is:issue", 2),
        ("involves:@me is:pull-request", 1),
        ("involves:@me is:pull-request", 2),
    ]
    assert len(result) == 6  # 每個 query 3 筆 x 2 個 query


@pytest.mark.asyncio
async def test_fetch_github_user_issues_stops_at_max_pages_safety_cap(monkeypatch):
    """就算 GitHub 一直回滿頁（理論上不該發生），也要在 GITHUB_MAX_PAGES 停下來，不能無限翻頁。"""
    call_count = {"n": 0}

    class MockResponse:
        def json(self):
            return {"items": [{"number": 1}]}  # 每頁都回滿（per_page=1）

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            call_count["n"] += 1
            resp = MockResponse()
            resp.status_code = 200
            return resp

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    await github_mod.fetch_github_user_issues("fake_token", per_page=1)

    # 2 個 query x GITHUB_MAX_PAGES(10) 頁 = 20 次呼叫，不能超過
    assert call_count["n"] == 2 * github_mod.GITHUB_MAX_PAGES


@pytest.mark.asyncio
async def test_fetch_github_user_issues_api_fail(monkeypatch):
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            return Response(status_code=403, content=b"Forbidden", request=Request("GET", url))

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    # 403（token 沒權限）屬於客戶端錯誤，重試也沒用 -> 應該是 NonRetryableError
    with pytest.raises(NonRetryableError) as exc_info:
        await github_mod.fetch_github_user_issues("invalid_token")

    assert "GitHub API failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_github_user_issues_server_error_is_retryable(monkeypatch):
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            return Response(status_code=500, content=b"Internal Server Error", request=Request("GET", url))

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    # 500 是伺服器端暫時性問題，重試可能會成功 -> 不該是 NonRetryableError
    with pytest.raises(Exception) as exc_info:
        await github_mod.fetch_github_user_issues("token")

    assert not isinstance(exc_info.value, NonRetryableError)
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
