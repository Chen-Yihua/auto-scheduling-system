import logging
from core.database import db
from core.crypto import encrypt_secret, decrypt_secret, mask_secret
from schemas.linked_account import LinkedAccountCreate
from platforms import PLATFORMS
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException

logger = logging.getLogger(__name__)


# 存 DB 前加密，回傳前端前遮罩
SENSITIVE_FIELDS = ("apiKey", "password")


def _to_public(account: dict) -> dict:
    """轉成回傳給前端的格式：敏感欄位遮罩、_id 改成 id。"""
    account = dict(account)
    for field in SENSITIVE_FIELDS:
        if account.get(field):
            account[field] = mask_secret(decrypt_secret(account[field]))
    account["id"] = account.pop("_id")
    return account


# 各平台的帳號驗證寫在 platforms/ 的 adapter 裡
async def create_linked_account(clerk_id: str, account: LinkedAccountCreate) -> dict:
    doc = account.model_dump()
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
    doc[platform.secret_field] = encrypt_secret(doc[platform.secret_field])

    try:
        await db.linkedAccounts.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Linked account already exists")

    return _to_public(doc)


async def get_linked_accounts_by_clerk_id(clerk_id: str):
    cursor = db.linkedAccounts.find({"clerk_id": clerk_id})
    return [_to_public(account) async for account in cursor]


async def update_linked_account_by_clerk_id(clerk_id: str, platform: str, data: dict):
    composite_id = f"{clerk_id}_{platform}"
    if not data:
        return False

    adapter = PLATFORMS.get(platform)
    if adapter and adapter.needs_reverify(data):
        data = await adapter.apply_update(data, composite_id)

    # 不 upsert：帳號不存在要回 404
    # 用 matched_count：值沒變時 modified_count 是 0，但不算失敗
    result = await db.linkedAccounts.update_one({"_id": composite_id}, {"$set": data})
    return result.matched_count > 0


async def delete_linked_account_by_id(composite_id: str):
    result = await db.linkedAccounts.delete_one({"_id": composite_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Linked account not found")
