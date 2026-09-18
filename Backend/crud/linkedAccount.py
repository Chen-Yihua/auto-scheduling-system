import logging
from typing import Optional, TypedDict
from db.mongodb import db
from db.crypto import encrypt_secret, decrypt_secret, mask_secret
from schemas.linkedAccount import LinkedAccountCreate
from crud.moodle import verify_moodle_login
from crud.errors import NonRetryableError
from pymongo.errors import DuplicateKeyError, PyMongoError
from selenium.common.exceptions import WebDriverException
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import httpx

HTTP_TIMEOUT = httpx.Timeout(10.0)

logger = logging.getLogger(__name__)


# 純粹給 IDE/型別檢查器用的形狀提示，不是 Pydantic model——不會在 runtime 驗證或擋資料。
# 欄位天生因平台而異（Jira 才有 domain 等），所以全部宣告成非必填。
class LinkedAccountDoc(TypedDict, total=False):
    _id: str
    clerk_id: str
    platform: str
    status: str
    username: str
    password: Optional[str]
    apiKey: Optional[str]
    domain: Optional[str]
    avatar_url: Optional[str]


class PlatformUserInfo(TypedDict):
    username: str
    avatar_url: str


# 這些欄位存進 DB 前一律加密，回傳給前端前一律遮罩，絕不明文往返
SENSITIVE_FIELDS = ("apiKey", "password")

# 可以允許更新的欄位只有以下幾種
ALLOWED_UPDATE_FIELDS = {"status", "username", "password", "apiKey", "domain"}


# ========== 平台驗證 Provider ==========
# 要支援新平台，只要在這裡加一個 Provider class 並在 PLATFORM_PROVIDERS 註冊，
# create_linked_account / update_linked_account_by_clerk_id 不用再改。
# 呼叫 fetch_github_userinfo 等用的是模組層級函式（不是綁死的 import），
# 是為了讓既有測試能用 monkeypatch.setattr(linked_mod, "fetch_github_userinfo", ...) 照樣運作。

class _GithubProvider:
    required_create_fields = ("apiKey",)
    secret_field = "apiKey"

    async def verify_new(self, doc: LinkedAccountDoc) -> LinkedAccountDoc:
        info = await fetch_github_userinfo(doc["apiKey"])
        return {**info, "status": "connected"}

    def needs_reverify(self, filtered_data: LinkedAccountDoc) -> bool:
        return self.secret_field in filtered_data

    async def apply_update(self, filtered_data: LinkedAccountDoc, _composite_id: str) -> LinkedAccountDoc:
        info = await fetch_github_userinfo(filtered_data["apiKey"])
        filtered_data["username"] = info["username"]
        filtered_data["avatar_url"] = info["avatar_url"]
        filtered_data["status"] = "connected"
        filtered_data["apiKey"] = encrypt_secret(filtered_data["apiKey"])
        return filtered_data


class _JiraProvider:
    required_create_fields = ("apiKey", "domain")
    secret_field = "apiKey"

    async def verify_new(self, doc: LinkedAccountDoc) -> LinkedAccountDoc:
        info = await fetch_jira_userinfo(doc["apiKey"], doc["domain"])
        return {**info, "status": "connected"}

    def needs_reverify(self, filtered_data: LinkedAccountDoc) -> bool:
        # apiKey、domain 只要改其中一個都要重新驗證——兩者合起來才是完整的登入資訊
        return "apiKey" in filtered_data or "domain" in filtered_data

    async def apply_update(self, filtered_data: LinkedAccountDoc, composite_id: str) -> LinkedAccountDoc:
        # apiKey、domain 改其中一個，另一個沒帶的話就用現有值湊成完整一組再驗證，
        # 確保不管改哪一個欄位，存進資料庫前都真的用新的組合驗證過一次
        api_key = filtered_data.get("apiKey")
        domain = filtered_data.get("domain")

        existing = None
        if not api_key or not domain:
            existing = await db.linkedAccounts.find_one({"_id": composite_id})

        if not domain:
            domain = existing.get("domain") if existing else None
        if not api_key and existing and existing.get("apiKey"):
            api_key = decrypt_secret(existing["apiKey"])

        if api_key and domain:
            info = await fetch_jira_userinfo(api_key, domain)
            filtered_data["username"] = info["username"]
            filtered_data["avatar_url"] = info["avatar_url"]
            filtered_data["status"] = "connected"

        if "apiKey" in filtered_data:
            filtered_data["apiKey"] = encrypt_secret(filtered_data["apiKey"])
        return filtered_data


class _MoodleProvider:
    required_create_fields = ("username", "password")
    secret_field = "password"

    async def _verify(self, username: str, password: str) -> None:
        try:
            await run_in_threadpool(verify_moodle_login, username, password)
        except NonRetryableError:
            raise HTTPException(status_code=401, detail="Moodle 帳號或密碼錯誤")
        except WebDriverException as e:
            logger.error("Moodle 驗證發生非預期錯誤: %s", e)
            raise HTTPException(status_code=503, detail="Moodle 服務暫時無法使用，請稍後再試")

    async def verify_new(self, doc: LinkedAccountDoc) -> LinkedAccountDoc:
        await self._verify(doc["username"], doc["password"])
        return {"avatar_url": "", "status": "connected"}

    def needs_reverify(self, filtered_data: LinkedAccountDoc) -> bool:
        # 帳號、密碼只要改其中一個都要重新驗證
        return "username" in filtered_data or "password" in filtered_data

    async def apply_update(self, filtered_data: LinkedAccountDoc, composite_id: str) -> LinkedAccountDoc:
        # 帳號、密碼改其中一個，另一個沒帶的話就用現有值湊成完整一組再驗證，
        # 確保不管改哪一個欄位，存進資料庫前都真的登入驗證過一次
        username = filtered_data.get("username")
        password = filtered_data.get("password")

        existing = None
        if not username or not password:
            existing = await db.linkedAccounts.find_one({"_id": composite_id})

        if not username:
            username = existing.get("username") if existing else None
        if not password and existing and existing.get("password"):
            password = decrypt_secret(existing["password"])

        if username and password:
            await self._verify(username, password)

        if "password" in filtered_data:
            filtered_data["password"] = encrypt_secret(filtered_data["password"])
        filtered_data["status"] = "connected"
        return filtered_data


PLATFORM_PROVIDERS = {
    "github": _GithubProvider(),
    "jira": _JiraProvider(),
    "moodle": _MoodleProvider(),
}


# 建立 Linked Account
async def create_linked_account(clerk_id: str, account: LinkedAccountCreate) -> dict:
    doc: LinkedAccountDoc = account.model_dump()
    doc["_id"] = f"{clerk_id}_{account.platform}"
    doc["clerk_id"] = clerk_id
    logger.debug("create_linked_account platform=%s domain=%s", account.platform, account.domain)

    provider = PLATFORM_PROVIDERS.get(account.platform)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {account.platform}")

    missing = [f for f in provider.required_create_fields if not getattr(account, f, None)]
    if missing:
        raise HTTPException(status_code=400, detail=f"{', '.join(missing)} required for {account.platform}")

    result = await provider.verify_new(doc)
    doc.update(result)
    doc[provider.secret_field] = encrypt_secret(doc[provider.secret_field])  # 驗證用明文，落地前才加密

    try:
        await db.linkedAccounts.update_one(
            {"_id": doc["_id"]},           # 找條件
            {"$set": doc},                  # 更新內容
            upsert=True                     # 插入或更新
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Linked account already exists")
    except PyMongoError as e:
        logger.error("DB error while creating linked account: %s", e)
        raise HTTPException(status_code=503, detail="資料庫暫時無法使用，請稍後再試")

    return {
        "message": "Linked account updated",
        "linkedAccounts": {
            account.platform: {
                "status": doc["status"],
                "username": doc["username"],
                "avatar_url": doc["avatar_url"]
            }
        }
    }


# 查詢 Linked Account
async def get_linked_accounts_by_clerk_id(clerk_id: str):
    cursor = db.linkedAccounts.find({"clerk_id": clerk_id})
    accounts = []
    async for account in cursor:
        # 密文只在伺服器內解密後立刻遮罩，絕不把可用的明文回傳給前端
        for field in SENSITIVE_FIELDS:
            if account.get(field):
                account[field] = mask_secret(decrypt_secret(account[field]))
        account["id"] = account["_id"]
        del account["_id"]
        accounts.append(account)
    return accounts

# 更新 Linked Account
async def update_linked_account_by_clerk_id(clerk_id: str, platform: str, data: dict):
    composite_id = f"{clerk_id}_{platform}"
    data = data.get("payload")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Missing or invalid 'payload' field")
    # 過濾掉允許更新的欄位
    filtered_data: LinkedAccountDoc = {k: v for k, v in data.items() if k in ALLOWED_UPDATE_FIELDS}
    if not filtered_data:
        return False

    provider = PLATFORM_PROVIDERS.get(platform)
    if provider and provider.needs_reverify(filtered_data):
        filtered_data = await provider.apply_update(filtered_data, composite_id)

    try:
        result = await db.linkedAccounts.update_one({"_id": composite_id}, {"$set": filtered_data}, upsert=True)
    except PyMongoError as e:
        logger.error("DB error while updating linked account: %s", e)
        raise HTTPException(status_code=503, detail="資料庫暫時無法使用，請稍後再試")
    return result.modified_count > 0




# 刪除 Linked Account
async def delete_linked_account_by_id(composite_id: str):
    try:
        result = await db.linkedAccounts.delete_one({"_id": composite_id})
    except PyMongoError as e:
        logger.error("DB error while deleting linked account: %s", e)
        raise HTTPException(status_code=503, detail="資料庫暫時無法使用，請稍後再試")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Linked account not found")


# 檢查 Linked Account 是否存在 （Github）
async def fetch_github_userinfo(token: str) -> PlatformUserInfo:
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                }
            )
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

# 檢查 Linked Account 是否存在 （Jira）
async def fetch_jira_userinfo(api_key_base64: str, domain: str) -> PlatformUserInfo:
    url = f"https://{domain.replace('https://','')}/rest/api/3/myself"
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
        "avatar_url": data.get("avatarUrls", {}).get("48x48", ""),  # 取一個大小
    }
