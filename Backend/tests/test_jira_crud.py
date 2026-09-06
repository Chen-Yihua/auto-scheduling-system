# Backend/tests/test_jira.py

import pytest
from unittest.mock import AsyncMock, patch
from crud import jira
from crud.errors import NonRetryableError


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_success():
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
async def test_fetch_jira_user_issues_paginates_across_multiple_pages():
    from unittest.mock import AsyncMock, MagicMock

    first_page = MagicMock()
    first_page.status_code = 200
    first_page.json.return_value = {"issues": [{"id": "1"}, {"id": "2"}], "total": 3}

    second_page = MagicMock()
    second_page.status_code = 200
    second_page.json.return_value = {"issues": [{"id": "3"}], "total": 3}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [first_page, second_page]

        issues = await jira.fetch_jira_user_issues("key", "domain", max_results=2)

        assert [i["id"] for i in issues] == ["1", "2", "3"]
        assert mock_get.call_count == 2
        # 第二次呼叫的 startAt 該是第一頁已經拿到的筆數，不能每次都從 0 開始重抓
        assert mock_get.call_args_list[1].kwargs["params"]["startAt"] == 2


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_stops_at_max_pages_safety_cap():
    from unittest.mock import AsyncMock, MagicMock

    page = MagicMock()
    page.status_code = 200
    # total 遠大於實際能拿到的，且每頁都回滿，理論上會一直翻下去
    page.json.return_value = {"issues": [{"id": "x"}], "total": 999999}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = page

        await jira.fetch_jira_user_issues("key", "domain", max_results=1)

        assert mock_get.call_count == jira.JIRA_MAX_PAGES


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_failure():
    # 401（帳密/token 錯誤）屬於客戶端錯誤，重試也沒用 -> 應該是 NonRetryableError
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 401
        mock_get.return_value.text = "Unauthorized"

        with pytest.raises(NonRetryableError) as exc_info:
            await jira.fetch_jira_user_issues("invalid", "wrong.domain")

        assert "Jira API failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_server_error_is_retryable():
    # 503 是伺服器端暫時性問題，重試可能會成功 -> 不該是 NonRetryableError
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 503
        mock_get.return_value.text = "Service Unavailable"

        with pytest.raises(Exception) as exc_info:
            await jira.fetch_jira_user_issues("key", "domain")

        assert not isinstance(exc_info.value, NonRetryableError)
        assert "Jira API failed" in str(exc_info.value)
