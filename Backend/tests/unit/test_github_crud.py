import pytest
import crud.github as github_mod
from crud.errors import NonRetryableError
from httpx import Response, Request

@pytest.mark.asyncio
async def test_fetch_github_user_issues(monkeypatch):
    """使用者同時有 issue 和 PR → 回傳的清單兩種都要包含。"""
    calls = []  # 記錄函式實際問了哪些 query，最後用來驗證「問了什麼、順序對不對」

    class MockResponse:
        """模擬 GitHub 的 HTTP 回應：有 status_code，也有 json()"""
        status_code = 200

        def __init__(self, query):
            self._query = query  # 記下這次問的是什麼，json() 才知道要回 issue 還是 PR

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
async def test_fetch_github_user_issues_pins_api_version_header(monkeypatch):
    """每個請求都要帶 X-GitHub-Api-Version（GitHub 官方建議），鎖定回傳格式，
    不會因為 GitHub 換了預設版本就悄悄改變。"""
    sent_headers = []

    class MockResponse:
        status_code = 200

        def json(self):
            return {"items": []}

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            sent_headers.append(headers)
            return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    await github_mod.fetch_github_user_issues("fake_token")

    assert sent_headers  # 確實有發出請求
    assert all(h["X-GitHub-Api-Version"] == github_mod.GITHUB_API_VERSION for h in sent_headers)


@pytest.mark.asyncio
async def test_fetch_github_user_issues_paginates_full_pages(monkeypatch):
    """一頁抓滿代表可能還有下一頁，要繼續抓，不能只抓第一頁。"""
    calls = []

    class MockResponse:
        """模擬 GitHub 的 HTTP 回應：有 status_code，也有 json()"""
        status_code = 200

        def __init__(self, page):
            self._page = page  # 記下這次問的是第幾頁，json() 才知道要回滿頁還是最後一頁

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
        """模擬 GitHub 的 HTTP 回應：有 status_code，也有 json()"""
        status_code = 200

        def json(self):
            return {"items": [{"number": 1}]}  # 每頁都回滿（per_page=1）

    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            call_count["n"] += 1
            return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    await github_mod.fetch_github_user_issues("fake_token", per_page=1)

    # 2 個 query x GITHUB_MAX_PAGES(10) 頁 = 20 次呼叫，不能超過
    assert call_count["n"] == 2 * github_mod.GITHUB_MAX_PAGES


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
async def test_fetch_github_user_issues_client_error_is_non_retryable(monkeypatch, status_code):
    """400/401/403/404 是客戶端錯誤（token 過期、沒權限、請求不對、資源不存在），重試也沒用 → 要丟 NonRetryableError。"""
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            return Response(status_code=status_code, content=b"error", request=Request("GET", url))

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    with pytest.raises(NonRetryableError) as exc_info:
        await github_mod.fetch_github_user_issues("fake_token")

    assert f"GitHub API failed: {status_code}" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 500, 502, 503])
async def test_fetch_github_user_issues_transient_error_is_retryable(monkeypatch, status_code):
    """429（被限流）和 5xx（伺服器錯誤）是暫時性問題，重試可能成功 → 要丟一般例外，不能是 NonRetryableError。"""
    class MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, headers, params):
            return Response(status_code=status_code, content=b"error", request=Request("GET", url))

    monkeypatch.setattr("httpx.AsyncClient", lambda: MockClient())

    with pytest.raises(Exception) as exc_info:
        await github_mod.fetch_github_user_issues("fake_token")

    assert not isinstance(exc_info.value, NonRetryableError)
    assert f"GitHub API failed: {status_code}" in str(exc_info.value)


def test_transform_github_item_issue():
    """一般 issue：GitHub 原始欄位要正確對應到統一格式的每個欄位（id、number、status、url、author、labels…），isPR 為 False。
    id 要用 GitHub 全域唯一的 id，不能用 repo 內的 number——不同 repo 都有 #1，會互相覆蓋。"""
    raw = {
        "id": 9000123,
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

    assert result["id"] == 9000123
    assert result["number"] == 123
    assert result["title"] == "Test issue"
    assert result["status"] == "open"
    assert result["created_at"] == "2024-01-01T00:00:00Z"
    assert result["updated_at"] == "2024-01-02T00:00:00Z"
    assert result["url"] == "https://github.com/example/repo/issues/123"
    assert result["isPR"] is False
    assert result["author"]["username"] == "alice"
    assert result["author"]["avatar"] == "https://avatar"
    assert result["labels"] == ["bug"]
    assert result["comments"] == 3


def test_transform_github_item_pr():
    """有 pull_request 欄位代表是 PR → isPR 為 True；沒有任何 label 時要是空清單。"""
    raw = {
        "id": 9000456,
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

    assert result["id"] == 9000456
    assert result["number"] == 456
    assert result["isPR"] is True
    assert result["labels"] == []  # 沒有任何 label 是正常狀態，該回空清單，不是 None 或例外


def test_transform_github_item_tolerates_missing_optional_fields():
    """只帶必要欄位時也不能出錯：選填欄位（updated_at、user、labels、comments）缺了就退回 None 或空清單。"""
    raw = {
        "id": 9000789,
        "number": 789,
        "title": "Minimal item",
        "state": "closed",
        "created_at": "2024-01-05T00:00:00Z",
        "html_url": "https://github.com/example/repo/issues/789",
    }

    result = github_mod.transform_github_item(raw)

    assert result["id"] == 9000789
    assert result["number"] == 789
    assert result["updated_at"] is None
    assert result["author"] == {"username": None, "avatar": None}
    assert result["labels"] == []
    assert result["comments"] is None
    assert result["isPR"] is False


# ---------- sync_github_issues：舊資料（用 number 當 id）搬移 ----------

class _FakeGithubIssues:
    """只模擬搬移邏輯用到的 count_documents／update_one，記錄 update_one 收到的參數。"""
    def __init__(self, legacy_count):
        self.legacy_count = legacy_count
        self.updates = []

    async def count_documents(self, query):
        return self.legacy_count

    async def update_one(self, query, update):
        self.updates.append((query, update))


@pytest.mark.asyncio
async def test_sync_github_issues_migrates_legacy_ids_by_url(monkeypatch):
    """DB 裡還有舊版用 number 當 id 的資料（沒有 number 欄位）→ 用 url 對到新抓回來的項目，
    把 id 改成全域 id、補上 number，使用者設定的排程欄位才不會在這次同步被當成過期資料刪掉。
    搬移要在 sync_platform_items 寫入／清除舊資料之前完成。"""
    fake = _FakeGithubIssues(legacy_count=1)
    monkeypatch.setattr(github_mod.db, "github_issues", fake)
    items = [{"id": 9000001, "number": 1, "url": "https://github.com/a/repo/issues/1"}]

    async def fake_sync_platform_items(collection, user_id, id_field, fetch_fn):
        result = await fetch_fn()
        assert fake.updates, "搬移要在 fetch_fn 回傳前做完，sync_platform_items 才不會先刪掉舊資料"
        return result, False, None, False

    monkeypatch.setattr(github_mod, "sync_platform_items", fake_sync_platform_items)

    async def fetch():
        return items

    result, *_ = await github_mod.sync_github_issues("user_1", fetch)

    assert result == items
    assert fake.updates == [(
        {"user_id": "user_1", "number": {"$exists": False}, "url": "https://github.com/a/repo/issues/1"},
        {"$set": {"id": 9000001, "number": 1}},
    )]


@pytest.mark.asyncio
async def test_sync_github_issues_skips_migration_when_no_legacy_docs(monkeypatch):
    """已經沒有舊資料 → 只多一次 count 查詢，不能每次同步都對每個項目跑一次 update。"""
    fake = _FakeGithubIssues(legacy_count=0)
    monkeypatch.setattr(github_mod.db, "github_issues", fake)

    async def fake_sync_platform_items(collection, user_id, id_field, fetch_fn):
        return await fetch_fn(), False, None, False

    monkeypatch.setattr(github_mod, "sync_platform_items", fake_sync_platform_items)

    async def fetch():
        return [{"id": 9000001, "number": 1, "url": "https://github.com/a/repo/issues/1"}]

    await github_mod.sync_github_issues("user_1", fetch)

    assert fake.updates == []
