import logging
from db.mongodb import db
from db.crypto import encrypt_secret, decrypt_secret, mask_secret
from schemas.linkedAccount import LinkedAccountCreate, LinkedAccountInDB
from crud.moodle import verify_moodle_login
from crud.errors import NonRetryableError
from pymongo.errors import DuplicateKeyError, PyMongoError
from selenium.common.exceptions import WebDriverException
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from datetime import datetime
import httpx

HTTP_TIMEOUT = httpx.Timeout(10.0)

logger = logging.getLogger(__name__)

# 這些欄位存進 DB 前一律加密，回傳給前端前一律遮罩，絕不明文往返
SENSITIVE_FIELDS = ("apiKey", "password")

# 建立 Linked Account
async def create_linked_account(clerk_id: str, account: LinkedAccountCreate) -> dict:
    doc = account.model_dump()
    doc["_id"] = f"{clerk_id}_{account.platform}"
    doc["clerk_id"] = clerk_id
    logger.debug("create_linked_account platform=%s domain=%s", account.platform, account.domain)

    # 若是 GitHub，自動驗證 token 並抓 login + avatar
    if account.platform == "github":
        if not account.apiKey:
            raise HTTPException(status_code=400, detail="GitHub API key is required")

        info = await fetch_github_userinfo(account.apiKey)
        doc["username"] = info["username"]
        doc["avatar_url"] = info["avatar_url"]
        doc["status"] = "connected"
        doc["apiKey"] = encrypt_secret(account.apiKey)  # 驗證用明文，落地前才加密

    # 若是 Jira，也驗證
    elif account.platform == "jira":
        if not account.apiKey:
            raise HTTPException(status_code=400, detail="Jira API key is required")
        if not account.domain:
            raise HTTPException(status_code=400, detail="Jira domain is required")
        info = await fetch_jira_userinfo(account.apiKey, account.domain)
        doc["username"] = info["username"]
        doc["avatar_url"] = info["avatar_url"]
        doc["domain"] = account.domain
        doc["status"] = "connected"
        doc["apiKey"] = encrypt_secret(account.apiKey)  # 驗證用明文，落地前才加密

    # 若是 Moodle，也驗證（帳密真的登入得進去才存）
    elif account.platform == "moodle":
        if not account.username or not account.password:
            raise HTTPException(status_code=400, detail="Moodle username and password are required")
        try:
            await run_in_threadpool(verify_moodle_login, account.username, account.password)
        except NonRetryableError:
            raise HTTPException(status_code=401, detail="Moodle 帳號或密碼錯誤")
        except WebDriverException as e:
            logger.error("Moodle 驗證發生非預期錯誤: %s", e)
            raise HTTPException(status_code=503, detail="Moodle 服務暫時無法使用，請稍後再試")
        doc["username"] = account.username
        doc["avatar_url"] = ""
        doc["password"] = encrypt_secret(account.password)
        doc["status"] = "connected"

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
# 可以允許更新的欄位只有以下三種
ALLOWED_UPDATE_FIELDS = {"status", "username","password","apiKey", "domain"}

async def update_linked_account_by_clerk_id(clerk_id: str, platform: str, data: dict):
    composite_id = f"{clerk_id}_{platform}"
    data = data.get("payload")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Missing or invalid 'payload' field")
    # 過濾掉允許更新的欄位
    filtered_data = {k: v for k, v in data.items() if k in ALLOWED_UPDATE_FIELDS}
    if not filtered_data:
        return False

    # 若是 jira 且有提供 apiKey：有 domain 就順便驗證，沒有也一定要加密落地
    if platform == "jira" and "apiKey" in filtered_data:
        if "domain" in filtered_data:
            info = await fetch_jira_userinfo(filtered_data["apiKey"], filtered_data["domain"])
            filtered_data["username"] = info["username"]
            filtered_data["avatar_url"] = info["avatar_url"]
            filtered_data["status"] = "connected"
        filtered_data["apiKey"] = encrypt_secret(filtered_data["apiKey"])

    # 若是 moodle 且有更新 password：username 有一起帶就用新的，
    # 沒帶就查現有帳號的 username 一起驗證（密碼常單獨更新，帳號通常不變）
    if platform == "moodle" and "password" in filtered_data:
        username = filtered_data.get("username")
        if not username:
            existing = await db.linkedAccounts.find_one({"_id": composite_id})
            username = existing.get("username") if existing else None
        if username:
            try:
                await run_in_threadpool(verify_moodle_login, username, filtered_data["password"])
            except NonRetryableError:
                raise HTTPException(status_code=401, detail="Moodle 帳號或密碼錯誤")
            except WebDriverException as e:
                logger.error("Moodle 驗證發生非預期錯誤: %s", e)
                raise HTTPException(status_code=503, detail="Moodle 服務暫時無法使用，請稍後再試")
        filtered_data["password"] = encrypt_secret(filtered_data["password"])
        filtered_data["status"] = "connected"

    # 若是 github，也支援驗證（可選）
    if platform == "github" and "apiKey" in filtered_data:
        from .linkedAccount import fetch_github_userinfo
        info = await fetch_github_userinfo(filtered_data["apiKey"])
        filtered_data["username"] = info["username"]
        filtered_data["avatar_url"] = info["avatar_url"]
        filtered_data["status"] = "connected"
        filtered_data["apiKey"] = encrypt_secret(filtered_data["apiKey"])

    try:
        result = await db.linkedAccounts.update_one({"_id": composite_id}, {"$set": filtered_data}, upsert=True)
    except PyMongoError as e:
        logger.error("DB error while updating linked account: %s", e)
        raise HTTPException(status_code=503, detail="資料庫暫時無法使用，請稍後再試")
    return result.modified_count > 0




# 刪除 Linked Account
async def delete_linked_account_by_id(composite_id: str):
    result = await db.linkedAccounts.delete_one({"_id": composite_id})
    return result.deleted_count > 0


# 檢查 Linked Account 是否存在 （Github）
async def fetch_github_userinfo(token: str) -> dict:
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
async def fetch_jira_userinfo(api_key_base64: str, domain: str) -> dict:
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
