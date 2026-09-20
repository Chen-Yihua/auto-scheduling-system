# Backend/tests/unit/test_jira_crud.py

import pytest
from unittest.mock import AsyncMock, patch
from crud import jira
from crud.errors import NonRetryableError


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
async def test_fetch_jira_user_issues_paginates_across_multiple_pages():
    """一頁抓不完（共 3 筆、第一頁只有 2 筆）要繼續抓下一頁、把 issue 收齊；下一頁要從已抓到的筆數之後開始，不能每次都從頭抓。"""
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
async def test_fetch_jira_user_issues_stops_early_when_page_returns_no_issues():
    """某一頁完全沒有 issue 就要停止翻頁：就算 total 欄位缺漏或對不上，也不能繼續翻下去。"""
    from unittest.mock import AsyncMock, MagicMock

    page = MagicMock()
    page.status_code = 200
    page.json.return_value = {"issues": []}  # 沒有 total 欄位，也沒有任何 issue

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = page

        issues = await jira.fetch_jira_user_issues("key", "domain")

        assert issues == []
        assert mock_get.call_count == 1  # 第一頁就停了，不會繼續翻頁


@pytest.mark.asyncio
async def test_fetch_jira_user_issues_stops_at_max_pages_safety_cap():
    """就算 total 一直說還有（999999 筆）、每頁也都回滿，也要在 JIRA_MAX_PAGES 停下來，不能無限翻頁。"""
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
