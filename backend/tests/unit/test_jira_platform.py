import pytest
from unittest.mock import AsyncMock, patch
from platforms import jira
from platforms.sync import NonRetryableError


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_success():
    """成功時回傳 Jira 的 issue 清單。"""
    from unittest.mock import AsyncMock, MagicMock

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"issues": [{"id": "123", "key": "JIRA-1"}]}
        mock_get.return_value = mock_response

        issues = await jira.fetch_jira_user_issues("fake_key", "fake.atlassian.net")
        assert isinstance(issues, list)
        assert issues[0]["key"] == "JIRA-1"


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_uses_enhanced_search_endpoint_with_explicit_fields():
    """要打新版的 /rest/api/3/search/jql（舊的 /search 已被淘汰），而且要明確指定 fields——
    新端點預設只回傳 issue id，沒指定的話 transform_jira_item 會拿到一堆空欄位。"""
    from unittest.mock import AsyncMock, MagicMock

    page = MagicMock()
    page.status_code = 200
    page.json.return_value = {"issues": [], "isLast": True}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = page

        await jira.fetch_jira_user_issues("key", "https://fake.atlassian.net")

        url = mock_get.call_args.args[0]
        params = mock_get.call_args.kwargs["params"]
        assert url == "https://fake.atlassian.net/rest/api/3/search/jql"
        assert params["fields"] == jira.JIRA_ISSUE_FIELDS
        # 第一頁不能帶 nextPageToken，也不該再出現舊端點的 startAt
        assert "nextPageToken" not in params
        assert "startAt" not in params


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_paginates_across_multiple_pages():
    """一頁抓不完（第一頁回傳 nextPageToken）要繼續抓下一頁、把 issue 收齊；下一頁要帶上一頁給的 nextPageToken，不能每次都從頭抓。"""
    from unittest.mock import AsyncMock, MagicMock

    first_page = MagicMock()
    first_page.status_code = 200
    first_page.json.return_value = {"issues": [{"id": "1"}, {"id": "2"}], "nextPageToken": "tok-2", "isLast": False}

    second_page = MagicMock()
    second_page.status_code = 200
    second_page.json.return_value = {"issues": [{"id": "3"}], "isLast": True}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [first_page, second_page]

        issues = await jira.fetch_jira_user_issues("key", "domain", max_results=2)

        assert [i["id"] for i in issues] == ["1", "2", "3"]
        assert mock_get.call_count == 2
        # 第二次呼叫要帶第一頁給的 nextPageToken，不能每次都從第一頁重抓
        assert mock_get.call_args_list[1].kwargs["params"]["nextPageToken"] == "tok-2"


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_stops_when_no_next_page_token():
    """回應裡沒有 nextPageToken 就要停止翻頁：就算 isLast 欄位缺漏，也不能繼續翻下去。"""
    from unittest.mock import AsyncMock, MagicMock

    page = MagicMock()
    page.status_code = 200
    page.json.return_value = {"issues": [{"id": "1"}]}  # 沒有 nextPageToken，也沒有 isLast

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = page

        issues = await jira.fetch_jira_user_issues("key", "domain")

        assert [i["id"] for i in issues] == ["1"]
        assert mock_get.call_count == 1  # 第一頁就停了，不會繼續翻頁


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_stops_when_is_last_even_with_token():
    """isLast=True 就是最後一頁，就算回應裡還附了 nextPageToken 也要停。"""
    from unittest.mock import AsyncMock, MagicMock

    page = MagicMock()
    page.status_code = 200
    page.json.return_value = {"issues": [{"id": "1"}], "nextPageToken": "tok", "isLast": True}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = page

        await jira.fetch_jira_user_issues("key", "domain")

        assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_stops_at_max_pages_safety_cap():
    """就算 Jira 一直回傳 nextPageToken、isLast 永遠是 false，也要在 JIRA_MAX_PAGES 停下來，不能無限翻頁。"""
    from unittest.mock import AsyncMock, MagicMock

    page = MagicMock()
    page.status_code = 200
    page.json.return_value = {"issues": [{"id": "x"}], "nextPageToken": "again", "isLast": False}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = page

        await jira.fetch_jira_user_issues("key", "domain", max_results=1)

        assert mock_get.call_count == jira.JIRA_MAX_PAGES


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
async def test_fetch_jira_user_issues_client_error_is_non_retryable(status_code):
    """400/401/403/404 是客戶端錯誤（token 過期、沒權限、請求不對、資源不存在），重試也沒用 → 要丟 NonRetryableError。"""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = status_code
        mock_get.return_value.text = "error"

        with pytest.raises(NonRetryableError) as exc_info:
            await jira.fetch_jira_user_issues("fake_key", "fake.atlassian.net")

        assert f"Jira API failed: {status_code}" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 500, 502, 503])
async def test_fetch_jira_user_issues_transient_error_is_retryable(status_code):
    """429（被限流）和 5xx（伺服器錯誤）是暫時性問題，重試可能成功 → 要丟一般例外，不能是 NonRetryableError。"""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = status_code
        mock_get.return_value.text = "error"

        with pytest.raises(Exception) as exc_info:
            await jira.fetch_jira_user_issues("fake_key", "fake.atlassian.net")

        assert not isinstance(exc_info.value, NonRetryableError)
        assert f"Jira API failed: {status_code}" in str(exc_info.value)


# ---------- transform_jira_item ----------

def test_transform_jira_item_captures_status_category():
    """status.statusCategory.key 是 Jira 正規化過的完成狀態（"new"／"indeterminate"／"done"），
    跟專案自訂的 status.name 分開存，排程要用這個判斷完成與否，不是猜 status.name 的字串。"""
    raw = {
        "id": "1",
        "key": "JIRA-1",
        "fields": {
            "summary": "已完成的任務",
            "status": {"name": "已完成", "statusCategory": {"key": "done"}},
        },
    }

    result = jira.transform_jira_item(raw)

    assert result["status"] == "已完成"
    assert result["status_category"] == "done"


def test_transform_jira_item_falls_back_to_empty_status_category_when_missing():
    """Jira 回應裡沒有 statusCategory（理論上不該發生，但資料格式不保證）→ 空字串，不噴例外。"""
    raw = {"id": "1", "key": "JIRA-1", "fields": {"status": {"name": "To Do"}}}

    result = jira.transform_jira_item(raw)

    assert result["status_category"] == ""


@pytest.mark.asyncio
async def test_jira_fetch_items_uses_api_key_and_domain_and_returns_transformed_items(monkeypatch):
    """adapter 的 fetch_items：用解密後的 API key 加上網域抓資料，回傳已經拉平成前端格式的 issue。"""
    calls = []

    async def fake_fetch(api_key, domain):
        calls.append((api_key, domain))
        return [{"id": "1", "key": "JIRA-1", "fields": {"summary": "任務", "status": {"name": "To Do"}}}]

    monkeypatch.setattr(jira, "fetch_jira_user_issues", fake_fetch)

    items = await jira.JIRA.fetch_items({"api_key": "jira-key", "domain": "team.atlassian.net"})

    assert calls == [("jira-key", "team.atlassian.net")]
    assert items[0]["key"] == "JIRA-1"
    assert items[0]["title"] == "任務"
