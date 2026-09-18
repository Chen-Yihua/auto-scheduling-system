import httpx
from db.mongodb import db
from crud.errors import NonRetryableError
from crud.external_sync import sync_platform_items

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


# 將 raw 資料轉換成 JiraIssue 格式（見 schemas/jira.py）——直接拉平成單層，
# 不留 Jira 原始 API 那種多層巢狀（一堆用不到的自訂欄位、changelog、self 連結等
# 也一併濾掉），前端拿到就是最終顯示用的格式，不用再自己轉換一次
def transform_jira_item(raw: dict) -> dict:
    fields = raw.get("fields") or {}
    assignee = fields.get("assignee") or {}
    status = fields.get("status") or {}
    issuetype = fields.get("issuetype") or {}
    avatar_urls = assignee.get("avatarUrls") or {}

    return {
        "id": raw["id"],
        "key": raw["key"],
        "title": fields.get("summary") or "",
        "status": status.get("name") or "",
        "updated_at": fields.get("updated") or "",
        "assignee": assignee.get("displayName") or "",
        "avatar": avatar_urls.get("48x48") or "",
        "type": issuetype.get("name") or "",
        "iconUrl": issuetype.get("iconUrl") or "",
    }


# 包一層 sync_platform_items，把「用哪個 collection」這個細節封裝在這裡，
# router 就不用自己 import db、知道 collection 叫 jira_issues
async def sync_jira_issues(user_id: str, fetch_fn):
    return await sync_platform_items(
        collection=db.jira_issues,
        user_id=user_id,
        id_field="id",
        fetch_fn=fetch_fn,
    )
