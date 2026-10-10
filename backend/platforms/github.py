"""GitHub：使用者參與（involves:@me）的 issue 與 PR。用 Personal Access Token 驗證。"""
import logging

import httpx
from fastapi import HTTPException

from core.crypto import encrypt_secret
from platforms.sync import NonRetryableError, UpstreamError
from platforms.sync import sync_platform_items
from platforms.base import PlatformAdapter, PlatformUserInfo
from schemas.github import GitHubIssue

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = httpx.Timeout(10.0)

# GitHub 官方建議每個 REST 請求都帶 X-GitHub-Api-Version，鎖定在這個版本的行為；
# 沒帶的話 GitHub 會用預設版本，哪天預設版本換了，回傳格式就可能悄悄改變。
# 專案裡所有打 api.github.com 的地方（這裡、webhook）都共用這個常數
GITHUB_API_VERSION = "2022-11-28"

# 客戶端錯誤：帳密/token 問題、資源不存在——重試也不會變成功
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}

# GitHub search API 每頁最多 100 筆；且不管怎麼分頁，同一組查詢條件最多只能拿到
# 前 1000 筆（GitHub API 本身的硬限制，不是我們自己加的）——10 頁 x 100 筆剛好打滿。
GITHUB_MAX_PAGES = 10


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


# 抓 GitHub PR 與 Issue，分開查詢再合併；每個查詢都會自動翻頁抓到底
# （或抓滿 GitHub 自己的 1000 筆上限為止），避免使用者相關項目超過一頁就被漏掉。
async def fetch_github_user_issues(token: str, per_page: int = 100) -> list:
    url = "https://api.github.com/search/issues"
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
                response = await client.get(url, headers=_headers(token), params=params)
                if response.status_code != 200:
                    message = f"GitHub API failed: {response.status_code} {response.text}"
                    if response.status_code in NON_RETRYABLE_STATUS_CODES:
                        raise NonRetryableError(message)
                    raise UpstreamError(message)
                items = response.json().get("items", [])
                all_items.extend(items)
                if len(items) < per_page:
                    break  # 這頁沒抓滿，代表已經是最後一頁
                page += 1

    return all_items


# 將 raw 資料轉換成 GitHubIssue 格式（前端也用這格式）
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


# 連結帳號時驗證 token，順便拿使用者名稱、頭像
async def fetch_github_userinfo(token: str) -> PlatformUserInfo:
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get("https://api.github.com/user", headers=_headers(token))
    except httpx.RequestError as e:
        logger.error("GitHub 驗證連線失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 GitHub，請稍後再試")

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Unauthorized GitHub token")
    if response.status_code != 200:
        raise HTTPException(status_code=403, detail="Invalid GitHub token or access denied")

    data = response.json()
    return {
        "username": data.get("login"),
        "avatar_url": data.get("avatar_url"),
    }


class GithubPlatform(PlatformAdapter):
    name = "github"
    display_name = "GitHub"

    route_path = "/github/issues"
    response_model = GitHubIssue

    not_linked_detail = "No GitHub token linked"
    auth_failed_detail = "GitHub 授權已失效，請重新連結帳號"
    fetch_failed_detail = "無法取得 GitHub 資料，請稍後再試"

    collection_name = "github_issues"
    id_type = int  # GitHub 的全域 id 是數字

    required_create_fields = ("apiKey",)
    secret_field = "apiKey"

    def credentials_from_account(self, account, decrypt):
        if not account.get("apiKey"):
            return None
        return {"token": decrypt(account["apiKey"])}

    async def fetch_items(self, credentials):
        raw_items = await fetch_github_user_issues(token=credentials["token"])
        return [transform_github_item(item) for item in raw_items]

    async def sync(self, user_id, fetch_fn):
        # 搬移要在 sync_platform_items upsert／刪除舊項目之前做，所以包在 fetch 裡面
        async def fetch_and_migrate():
            items = await fetch_fn()
            await self._migrate_legacy_ids(user_id, items)
            return items

        return await sync_platform_items(
            collection=self.collection,
            user_id=user_id,
            id_field="id",
            fetch_fn=fetch_and_migrate,
        )

    # 舊版用 issue number 當 id（見 transform_github_item），改用全域 id 之後，DB 裡的舊資料
    # 如果不處理，會在這次同步被當成「已經不存在」刪掉，連帶把使用者設定的排程欄位
    # （priority、duration、done、calendar_event_id 等）一起丟掉。這裡用 url（全域唯一）
    # 把舊資料對到新抓回來的項目，直接把 id 改成新值，排程欄位就跟著保留下來。
    # 舊資料的特徵是沒有 number 欄位；搬過一次之後就不會再有，之後每次同步只多一次 count 查詢
    async def _migrate_legacy_ids(self, user_id: str, items: list[dict]) -> None:
        legacy_filter = {"user_id": user_id, "number": {"$exists": False}}
        if not await self.collection.count_documents(legacy_filter):
            return
        for item in items:
            await self.collection.update_one(
                {**legacy_filter, "url": item["url"]},
                {"$set": {"id": item["id"], "number": item["number"]}},
            )

    def is_done(self, item):
        return item.get("status") == "closed"

    async def verify_new(self, account):
        info = await fetch_github_userinfo(account["apiKey"])
        return {**info, "status": "connected"}

    async def apply_update(self, changes, composite_id):
        info = await fetch_github_userinfo(changes["apiKey"])
        changes["username"] = info["username"]
        changes["avatar_url"] = info["avatar_url"]
        changes["status"] = "connected"
        changes["apiKey"] = encrypt_secret(changes["apiKey"])
        return changes


GITHUB = GithubPlatform()
