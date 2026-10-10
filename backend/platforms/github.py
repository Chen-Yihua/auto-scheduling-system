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

# 鎖定 API 版本，避免 GitHub 更換預設版本時回傳格式悄悄改變
GITHUB_API_VERSION = "2022-11-28"

# 重試也不會成功的狀態碼
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}

# search API 同一查詢最多回 1000 筆，10 頁 x 100 筆剛好拿滿
GITHUB_MAX_PAGES = 10


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


# issue 和 PR 分開查詢，各自翻頁到底後合併
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
                    break  # 沒抓滿代表是最後一頁
                page += 1

    return all_items


def transform_github_item(raw: dict) -> dict:
    return {
        # 不能用 number 當 id：number 只在 repo 內唯一，不同 repo 會互相覆蓋
        "id": raw["id"],
        "number": raw["number"],  # 顯示用
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


# 連結帳號時驗證 token，並取得使用者名稱和頭像
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
    id_type = int

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
        # 搬移要在 upsert 和刪除舊項目之前做，所以包在 fetch 裡
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

    # 舊資料用 issue number 當 id 且沒有 number 欄位。用 url 對應到新 id，
    # 否則同步時會被當成已刪除，連帶丟掉使用者設定的排程欄位
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
