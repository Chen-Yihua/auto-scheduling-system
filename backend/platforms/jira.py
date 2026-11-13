"""Jira：指派給使用者的 issue。用 API Token（email:token 的 Base64）加上站台網域驗證。"""
import logging

import httpx
from core.crypto import SecretDecryptError, encrypt_secret, decrypt_secret
from core.errors import ReauthRequiredError
from platforms.http_errors import fetch_error, unparsable_verify_response, verify_error, verify_request_error
from platforms.sync import InvalidResponseError
from core.datetimes import to_utc_datetime
from platforms.base import PlatformAdapter, PlatformUserInfo
from schemas.jira import JiraIssue

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = httpx.Timeout(10.0)

# 已存的網域回 404：網域可能改了或站台關了
DOMAIN_GONE_DETAIL = "Jira 網域可能已失效，請到設定確認或重新連結"

# 避免 Jira 一直回傳 nextPageToken 時無限迴圈
JIRA_MAX_PAGES = 10

# /search/jql 預設只回 id，要明確列出欄位；和 transform_jira_item 用到的欄位一致
JIRA_ISSUE_FIELDS = "summary,status,updated,assignee,issuetype,resolutiondate"


def _base_url(domain: str) -> str:
    return f"https://{domain.replace('https://', '')}"


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Basic {api_key}",
        "Accept": "application/json",
    }


# 新端點沒有 total，只能靠 nextPageToken 判斷是否還有下一頁
async def fetch_jira_user_issues(api_key: str, domain: str, max_results: int = 100) -> list:
    url = f"{_base_url(domain)}/rest/api/3/search/jql"

    all_issues = []
    next_page_token = None # 下一頁從哪個 issue 開始

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for _ in range(JIRA_MAX_PAGES):
            params = {
                "jql": "assignee=currentUser() ORDER BY updated DESC",
                "maxResults": max_results,
                "fields": JIRA_ISSUE_FIELDS,
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token
            response = await client.get(url, headers=_headers(api_key), params=params)

            if response.status_code != 200:
                raise fetch_error(response, "Jira", not_found_detail=DOMAIN_GONE_DETAIL)

            try:
                data = response.json()
            except ValueError as e:
                raise InvalidResponseError(f"Jira 回應不是 JSON: {response.text}") from e
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
        "updated_at": to_utc_datetime(fields.get("updated")),
        "resolved_at": to_utc_datetime(fields.get("resolutiondate")),
        "assignee": assignee.get("displayName") or "",
        "avatar": avatar_urls.get("48x48") or "",
        "type": issuetype.get("name") or "",
        "iconUrl": issuetype.get("iconUrl") or "",
    }


# 連結帳號時驗證 API Token 和網域，並取得使用者名稱和頭像
async def fetch_jira_userinfo(api_key_base64: str, domain: str) -> PlatformUserInfo:
    url = f"{_base_url(domain)}/rest/api/3/myself"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(url, headers=_headers(api_key_base64))
    except httpx.RequestError as e:
        raise verify_request_error(e, "Jira", check_domain=True)

    if response.status_code != 200:
        raise verify_error(response, "Jira", check_domain=True)

    try:
        data = response.json()
    except ValueError:
        logger.warning("Jira 驗證回應不是 JSON: %s", response.text)
        raise unparsable_verify_response("Jira")
    return {
        "username": data.get("displayName"),
        "avatar_url": data.get("avatarUrls", {}).get("48x48", ""),
    }


STORED_CREDENTIALS_UNREADABLE_DETAIL = "已存的 Jira API Key 無法讀取，請重新輸入完整的憑證"


class JiraPlatform(PlatformAdapter):
    name = "jira"
    display_name = "Jira"

    route_path = "/jira/issues"
    response_model = JiraIssue
    rate_limit = "30/minute"

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
        try:
            return [transform_jira_item(issue) for issue in raw_issues]
        except (KeyError, TypeError, AttributeError) as e:
            raise InvalidResponseError(f"Jira 回應缺少欄位: {e!r}") from e

    def is_done(self, item):
        return item.get("status_category") == "done"

    def completed_at(self, item):
        # 資料庫裡可能還是舊的字串，下次同步才會換成 datetime
        return to_utc_datetime(item.get("resolved_at"))

    async def verify_new_account(self, account):
        info = await fetch_jira_userinfo(account["apiKey"], account["domain"])
        return {**info, "status": "connected"}

    def needs_reverify(self, changes):
        return "apiKey" in changes or "domain" in changes

    async def verify_account_update(self, changes, existing):
        # 只改其中一個時，另一個用現有值補齊再驗證
        domain = changes.get("domain") or existing.get("domain")
        api_key = changes.get("apiKey")
        if not api_key and existing.get("apiKey"):
            try:
                api_key = decrypt_secret(existing["apiKey"])
            except SecretDecryptError:
                # 不刪憑證：正式和開發環境共用 DB，可能是另一個環境用它自己的金鑰加密的
                logger.warning("已存的 Jira API key 解密失敗 account=%s", existing.get("_id"))
                raise ReauthRequiredError(STORED_CREDENTIALS_UNREADABLE_DETAIL)

        if api_key and domain:
            info = await fetch_jira_userinfo(api_key, domain)
            changes["username"] = info["username"]
            changes["avatar_url"] = info["avatar_url"]
            changes["status"] = "connected"

        if "apiKey" in changes:
            changes["apiKey"] = encrypt_secret(changes["apiKey"])
        return changes


JIRA = JiraPlatform()
