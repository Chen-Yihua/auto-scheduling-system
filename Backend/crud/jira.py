import httpx
from crud.errors import NonRetryableError

# 客戶端錯誤：帳密/token 問題、資源不存在——重試也不會變成功
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}

async def fetch_jira_user_issues(api_key: str, domain: str, max_results: int = 30) -> list:
    url = f"https://{domain.replace('https://','')}/rest/api/3/search"
    headers = {
        "Authorization": f"Basic {api_key}",
        "Accept": "application/json"
    }
    params = {
        "jql": "assignee=currentUser() ORDER BY updated DESC",
        "maxResults": max_results
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)

    if response.status_code != 200:
        message = f"Jira API failed: {response.status_code} {response.text}"
        if response.status_code in NON_RETRYABLE_STATUS_CODES:
            raise NonRetryableError(message)
        raise Exception(message)

    data = response.json()
    return data.get("issues", [])
