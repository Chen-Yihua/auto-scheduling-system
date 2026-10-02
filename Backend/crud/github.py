import httpx
from db.mongodb import db
from crud.errors import NonRetryableError
from crud.external_sync import sync_platform_items

# GitHub 官方建議每個 REST 請求都帶 X-GitHub-Api-Version，鎖定在這個版本的行為；
# 沒帶的話 GitHub 會用預設版本，哪天預設版本換了，回傳格式就可能悄悄改變。
# 專案裡所有打 api.github.com 的地方（linkedAccount、webhook）都共用這個常數
GITHUB_API_VERSION = "2022-11-28"

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
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
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
        # id 用 GitHub 全域唯一的 id，不能用 number——number 只是 repo 內的編號，
        # 不同 repo 都有 #1，拿來當 id 會互相覆蓋（同步時 upsert 撞在同一筆、前端列表 key 重複）
        "id": raw["id"],
        "number": raw["number"],  # 顯示用的 "#123"
        "title": raw["title"],
        "status": raw["state"],
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


# 舊版用 issue number 當 id（見 transform_github_item），改用全域 id 之後，DB 裡的舊資料
# 如果不處理，會在這次同步被當成「已經不存在」刪掉，連帶把使用者設定的排程欄位
# （priority、duration、done、calendar_event_id 等）一起丟掉。這裡用 url（全域唯一）
# 把舊資料對到新抓回來的項目，直接把 id 改成新值，排程欄位就跟著保留下來。
# 舊資料的特徵是沒有 number 欄位；搬過一次之後就不會再有，之後每次同步只多一次 count 查詢
async def _migrate_legacy_github_ids(user_id: str, items: list[dict]) -> None:
    legacy_filter = {"user_id": user_id, "number": {"$exists": False}}
    if not await db.github_issues.count_documents(legacy_filter):
        return
    for item in items:
        await db.github_issues.update_one(
            {**legacy_filter, "url": item["url"]},
            {"$set": {"id": item["id"], "number": item["number"]}},
        )


# 包一層 sync_platform_items，把「用哪個 collection」這個細節封裝在這裡，
# router 就不用自己 import db、知道 collection 叫 github_issues
async def sync_github_issues(user_id: str, fetch_fn):
    # 搬移要在 sync_platform_items upsert／刪除舊項目之前做，所以包在 fetch 裡面
    async def fetch_and_migrate():
        items = await fetch_fn()
        await _migrate_legacy_github_ids(user_id, items)
        return items

    return await sync_platform_items(
        collection=db.github_issues,
        user_id=user_id,
        id_field="id",
        fetch_fn=fetch_and_migrate,
    )
