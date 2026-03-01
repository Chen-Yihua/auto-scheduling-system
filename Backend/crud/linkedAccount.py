from db.mongodb import db
from schemas.linkedAccount import LinkedAccountCreate, LinkedAccountInDB
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException
from datetime import datetime
import httpx

# 建立 Linked Account
async def create_linked_account(clerk_id: str, account: LinkedAccountCreate) -> dict:
    doc = account.model_dump()
    doc["_id"] = f"{clerk_id}_{account.platform}"
    doc["clerk_id"] = clerk_id
    print(account.domain)

    # 若是 GitHub，自動驗證 token 並抓 login + avatar
    if account.platform == "github":
        if not account.apiKey:
            raise HTTPException(status_code=400, detail="GitHub API key is required")

        info = await fetch_github_userinfo(account.apiKey)
        doc["username"] = info["username"]
        doc["avatar_url"] = info["avatar_url"]
        doc["status"] = "connected"

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

    # Moodle 不需要驗證
    elif account.platform == "moodle":
        doc["username"] = account.username
        doc["avatar_url"] = ""
        doc["password"] = account.password
        doc["status"] = "connected"

    try:
        await db.linkedAccounts.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Linked account already exists")

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
        account["id"] = account["_id"]
        del account["_id"]
        accounts.append(account)
    return accounts

# 更新 Linked Account
# 可以允許更新的欄位只有以下三種
ALLOWED_UPDATE_FIELDS = {"status", "username","password","apiKey", "domain"}

async def update_linked_account_by_clerk_id(clerk_id: str, platform: str, data: dict):
    composite_id = f"{clerk_id}_{platform}"

    # 過濾掉允許更新的欄位
    filtered_data = {k: v for k, v in data.items() if k in ALLOWED_UPDATE_FIELDS}
    if not filtered_data:
        return False

    # 若是 jira，並且 apiKey & domain 都提供，執行驗證
    if platform == "jira" and "apiKey" in filtered_data and "domain" in filtered_data:
        info = await fetch_jira_userinfo(filtered_data["apiKey"], filtered_data["domain"])
        filtered_data["username"] = info["username"]
        filtered_data["avatar_url"] = info["avatar_url"]
        filtered_data["status"] = "connected"

    # 若是 moodle，提供 username & password 做更新
    if platform == "moodle" and "password" in filtered_data and "username" in filtered_data:
        filtered_data["username"] = filtered_data["username"]
        filtered_data["password"] = filtered_data["password"]
        filtered_data["status"] = "connected"

    # 若是 github，也支援驗證（可選）
    if platform == "github" and "apiKey" in filtered_data:
        from .linkedAccount import fetch_github_userinfo
        info = await fetch_github_userinfo(filtered_data["apiKey"])
        filtered_data["username"] = info["username"]
        filtered_data["avatar_url"] = info["avatar_url"]
        filtered_data["status"] = "connected"

    result = await db.linkedAccounts.update_one({"_id": composite_id}, {"$set": filtered_data})
    return result.modified_count > 0




# 刪除 Linked Account
async def delete_linked_account_by_id(composite_id: str):
    result = await db.linkedAccounts.delete_one({"_id": composite_id})
    return result.deleted_count > 0


# 檢查 Linked Account 是否存在 （Github）
async def fetch_github_userinfo(token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )
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
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized Jira token")
        if response.status_code != 200:
            raise HTTPException(status_code=403, detail="Invalid Jira token or access denied")

        data = response.json()
        return {
            "username": data.get("displayName"),
            "avatar_url": data.get("avatarUrls", {}).get("48x48", ""),  # 取一個大小
        }
