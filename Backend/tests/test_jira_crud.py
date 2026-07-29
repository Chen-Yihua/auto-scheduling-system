# Backend/tests/test_jira.py

import pytest
from unittest.mock import AsyncMock, patch
from crud import jira


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
async def test_fetch_jira_user_issues_failure():
    # 模擬非 200 回應
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 401
        mock_get.return_value.text = "Unauthorized"

        with pytest.raises(Exception) as exc_info:
            await jira.fetch_jira_user_issues("invalid", "wrong.domain")

        assert "Jira API failed" in str(exc_info.value)
