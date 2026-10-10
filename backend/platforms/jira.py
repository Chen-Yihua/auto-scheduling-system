"""Jira：指派給使用者的 issue。用 API Token（email:token 的 Base64）加上站台網域驗證。"""
import logging

import httpx
from fastapi import HTTPException

from core.database import db
from core.crypto import encrypt_secret, decrypt_secret
from platforms.sync import NonRetryableError, UpstreamError
from platforms.base import PlatformAdapter, PlatformUserInfo
from schemas.jira import JiraIssue

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = httpx.Timeout(10.0)

# 重試也不會成功的狀態碼
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}

# 避免 Jira 一直回傳 nextPageToken 時無限迴圈
JIRA_MAX_PAGES = 10

# /search/jql 預設只回 id，要明確列出欄位；和 transform_jira_item 用到的欄位一致
JIRA_ISSUE_FIELDS = "summary,status,updated,assignee,issuetype"


def _base_url(domain: str) -> str:
    return f"https://{domain.replace('https://', '')}"


# 新端點沒有 total，只能靠 nextPageToken 判斷是否還有下一頁
async def fetch_jira_user_issues(api_key: str, domain: str, max_results: int = 100) -> list:
    url = f"{_base_url(domain)}/rest/api/3/search/jql"
    headers = {
        "Authorization": f"Basic {api_key}",
        "Accept": "application/json"
    }

    all_issues = []
    next_page_token = None

    async with httpx.AsyncClient() as client:
        for _ in range(JIRA_MAX_PAGES):
            params = {
                "jql": "assignee=currentUser() ORDER BY updated DESC",
                "maxResults": max_results,
                "fields": JIRA_ISSUE_FIELDS,
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token
            response = await client.get(url, headers=headers, params=params)

            if response.status_code != 200:
                message = f"Jira API failed: {response.status_code} {response.text}"
                if response.status_code in NON_RETRYABLE_STATUS_CODES:
                    raise NonRetryableError(message)
                raise UpstreamError(message)

            data = response.json()
            all_issues.extend(data.get("issues", []))

            next_page_token = data.get("nextPageToken")
            if not next_page_token or data.get("isLast"):
                break

    return all_issues


def transform_jira_item(raw: dict) -> dict:
    fields = raw.get("fields") or {}
    assignee = fields.get("assignee") or {}
    status = fields.get("status") or {}
    status_category = status.get("statusCategory") or {}
    issuetype = fields.get("issuetype") or {}
    avatar_urls = assignee.get("avatarUrls") or {}

    return {
        "id": raw["id"],
        "key": raw["key"],
        "title": fields.get("summary") or "",
        "status": status.get("name") or "",
        # 用 statusCategory 判斷完成：status.name 是各專案自訂的字串
        "status_category": status_category.get("key") or "",
        "updated_at": fields.get("updated") or "",
        "assignee": assignee.get("displayName") or "",
        "avatar": avatar_urls.get("48x48") or "",
        "type": issuetype.get("name") or "",
        "iconUrl": issuetype.get("iconUrl") or "",
    }


# 連結帳號時驗證 API Token 和網域，並取得使用者名稱和頭像
async def fetch_jira_userinfo(api_key_base64: str, domain: str) -> PlatformUserInfo:
    url = f"{_base_url(domain)}/rest/api/3/myself"
    headers = {
        "Authorization": f"Basic {api_key_base64}",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError as e:
        logger.error("Jira 驗證連線失敗: %s", e)
        raise HTTPException(status_code=502, detail="無法連線至 Jira，請稍後再試")

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Unauthorized Jira token")
    if response.status_code != 200:
        raise HTTPException(status_code=403, detail="Invalid Jira token or access denied")

    data = response.json()
    return {
        "username": data.get("displayName"),
        "avatar_url": data.get("avatarUrls", {}).get("48x48", ""),
    }


class JiraPlatform(PlatformAdapter):
    name = "jira"
    display_name = "Jira"

    route_path = "/jira/issues"
    response_model = JiraIssue

    not_linked_detail = "No Jira linked account"
    auth_failed_detail = "Jira 授權已失效，請重新連結帳號"
    fetch_failed_detail = "無法取得 Jira 資料，請稍後再試"

    collection_name = "jira_issues"
    id_type = str

    required_create_fields = ("apiKey", "domain")
    secret_field = "apiKey"

    def credentials_from_account(self, account, decrypt):
        if not account.get("apiKey"):
            return None
        return {"api_key": decrypt(account["apiKey"]), "domain": account.get("domain")}

    async def fetch_items(self, credentials):
        raw_issues = await fetch_jira_user_issues(credentials["api_key"], credentials["domain"])
        return [transform_jira_item(issue) for issue in raw_issues]

    def is_done(self, item):
        return item.get("status_category") == "done"

    async def verify_new(self, account):
        info = await fetch_jira_userinfo(account["apiKey"], account["domain"])
        return {**info, "status": "connected"}

    def needs_reverify(self, changes):
        return "apiKey" in changes or "domain" in changes

    async def apply_update(self, changes, composite_id):
        # 只改其中一個時，另一個用現有值補齊再驗證
        api_key = changes.get("apiKey")
        domain = changes.get("domain")

        existing = None
        if not api_key or not domain:
            existing = await db.linkedAccounts.find_one({"_id": composite_id})

        if not domain:
            domain = existing.get("domain") if existing else None
        if not api_key and existing and existing.get("apiKey"):
            api_key = decrypt_secret(existing["apiKey"])

        if api_key and domain:
            info = await fetch_jira_userinfo(api_key, domain)
            changes["username"] = info["username"]
            changes["avatar_url"] = info["avatar_url"]
            changes["status"] = "connected"

        if "apiKey" in changes:
            changes["apiKey"] = encrypt_secret(changes["apiKey"])
        return changes


JIRA = JiraPlatform()
