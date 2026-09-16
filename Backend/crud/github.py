import httpx
from crud.errors import NonRetryableError

# 客戶端錯誤：帳密/token 問題、資源不存在——重試也不會變成功
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}

# GitHub search API 每頁最多 100 筆；且不管怎麼分頁，同一組查詢條件最多只能拿到
# 前 1000 筆（GitHub API 本身的硬限制，不是我們自己加的）——10 頁 x 100 筆剛好打滿。
GITHUB_MAX_PAGES = 10

# 抓 GitHub PR 與 Issue，分開查詢再合併；每個查詢都會自動翻頁抓到底
# （或抓滿 GitHub 自己的 1000 筆上限為止），避免使用者相關項目超過一頁就被漏掉。
async def fetch_github_user_issues(token: str, per_page: int = 100) -> list:
    url = "https://api.github.com/search/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    queries = [
        "involves:@me is:issue",
        "involves:@me is:pull-request"
    ]

    all_items = []

    async with httpx.AsyncClient() as client:
        for q in queries:
            page = 1
            while page <= GITHUB_MAX_PAGES:
                params = {
                    "q": q,
                    "per_page": per_page,
                    "page": page,
                }
                response = await client.get(url, headers=headers, params=params)
                if response.status_code != 200:
                    message = f"GitHub API failed: {response.status_code} {response.text}"
                    if response.status_code in NON_RETRYABLE_STATUS_CODES:
                        raise NonRetryableError(message)
                    raise Exception(message)
                items = response.json().get("items", [])
                all_items.extend(items)
                if len(items) < per_page:
                    break  # 這頁沒抓滿，代表已經是最後一頁
                page += 1

    return all_items


# 2. 將 raw 資料轉換成 GitHubIssue 格式（前端也用這格式）
def transform_github_item(raw: dict) -> dict:
    return {
        "id": raw["number"],
        "title": raw["title"],
        "state": raw["state"],
        "created_at": raw["created_at"],
        "updated_at": raw.get("updated_at"),
        "url": raw["html_url"],
        "isPR": "pull_request" in raw,
        "author": {
            "username": raw.get("user", {}).get("login"),
            "avatar": raw.get("user", {}).get("avatar_url")
        },
        "labels": [label["name"] for label in raw.get("labels", [])],
        "comments": raw.get("comments")
    }
