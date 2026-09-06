import httpx
from crud.errors import NonRetryableError

# 客戶端錯誤：帳密/token 問題、資源不存在——重試也不會變成功
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}

# 安全上限，避免 Jira 回傳的 total 異常（或一直回傳非空但 total 對不上）時無限迴圈
JIRA_MAX_PAGES = 10

# 用 startAt/total 分頁抓完使用者所有相關的 issue，避免超過一頁就被漏掉
async def fetch_jira_user_issues(api_key: str, domain: str, max_results: int = 100) -> list:
    url = f"https://{domain.replace('https://','')}/rest/api/3/search"
    headers = {
        "Authorization": f"Basic {api_key}",
        "Accept": "application/json"
    }

    all_issues = []
    start_at = 0

    async with httpx.AsyncClient() as client:
        for _ in range(JIRA_MAX_PAGES):
            params = {
                "jql": "assignee=currentUser() ORDER BY updated DESC",
                "maxResults": max_results,
                "startAt": start_at,
            }
            response = await client.get(url, headers=headers, params=params)

            if response.status_code != 200:
                message = f"Jira API failed: {response.status_code} {response.text}"
                if response.status_code in NON_RETRYABLE_STATUS_CODES:
                    raise NonRetryableError(message)
                raise Exception(message)

            data = response.json()
            issues = data.get("issues", [])
            all_issues.extend(issues)

            if not issues:
                break
            start_at += len(issues)
            total = data.get("total", start_at)
            if start_at >= total:
                break

    return all_issues
