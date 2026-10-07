import logging
from typing import Optional, TypedDict
from core.database import db
from core.crypto import encrypt_secret, decrypt_secret, mask_secret
from schemas.linked_account import LinkedAccountCreate
from platforms import PLATFORMS
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException

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


# 這些欄位存進 DB 前一律加密，回傳給前端前一律遮罩，絕不明文往返
SENSITIVE_FIELDS = ("apiKey", "password")

# 可以允許更新的欄位只有以下幾種
ALLOWED_UPDATE_FIELDS = {"status", "username", "password", "apiKey", "domain"}


# 各平台怎麼驗證帳號（打一次平台 API、或登入一次 Moodle），寫在各自的 adapter 裡
# （見 platforms/）；這裡只負責共通的流程：必填欄位檢查、加密、寫入資料庫。


# 建立 Linked Account
async def create_linked_account(clerk_id: str, account: LinkedAccountCreate) -> dict:
    doc: LinkedAccountDoc = account.model_dump()
    doc["_id"] = f"{clerk_id}_{account.platform}"
    doc["clerk_id"] = clerk_id
    logger.debug("create_linked_account platform=%s domain=%s", account.platform, account.domain)

    platform = PLATFORMS.get(account.platform)
    if not platform:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {account.platform}")

    missing = [f for f in platform.required_create_fields if not getattr(account, f, None)]
    if missing:
        raise HTTPException(status_code=400, detail=f"{', '.join(missing)} required for {account.platform}")

    result = await platform.verify_new(doc)
    doc.update(result)
    doc[platform.secret_field] = encrypt_secret(doc[platform.secret_field])  # 驗證用明文，落地前才加密

    try:
        await db.linkedAccounts.update_one(
            {"_id": doc["_id"]},           # 找條件
            {"$set": doc},                  # 更新內容
            upsert=True                     # 插入或更新
        )
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
    # 過濾掉允許更新的欄位
    filtered_data: LinkedAccountDoc = {k: v for k, v in data.items() if k in ALLOWED_UPDATE_FIELDS}
    if not filtered_data:
        return False

    adapter = PLATFORMS.get(platform)
    if adapter and adapter.needs_reverify(filtered_data):
        filtered_data = await adapter.apply_update(filtered_data, composite_id)

    # 不能 upsert：這是「更新既有帳號」，帳號不存在時要回 404，不能偷偷建立一筆只有部分欄位的紀錄。
    # 用 matched_count 判斷「帳號存在」，不能用 modified_count——送出的值跟資料庫一樣時
    # （例如打開編輯沒改就按儲存）modified_count 是 0，但這不是失敗
    result = await db.linkedAccounts.update_one({"_id": composite_id}, {"$set": filtered_data})
    return result.matched_count > 0




# 刪除 Linked Account
async def delete_linked_account_by_id(composite_id: str):
    result = await db.linkedAccounts.delete_one({"_id": composite_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Linked account not found")
