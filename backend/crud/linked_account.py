import logging
import secrets

from core.database import db
from core.crypto import SecretDecryptError, encrypt_secret, decrypt_secret, mask_secret
from schemas.linked_account import LinkedAccountCreate
from platforms import PLATFORMS
from platforms.account_sync import SyncOutcome, sync_account
from platforms.base import PlatformAdapter
from pymongo.errors import DuplicateKeyError
from core.errors import ConflictError, InvalidRequestError, NotFoundError

logger = logging.getLogger(__name__)


# 存 DB 前加密，回傳前端前遮罩
SENSITIVE_FIELDS = ("apiKey", "password")


def _new_link_id() -> str:
    """每次連結、更新憑證都換一個：同步途中連結變了，那次同步就整次放棄（見 platforms/account_sync.py）。"""
    return secrets.token_hex(16)


async def _sync_after_link(platform: PlatformAdapter, clerk_id: str) -> None:
    """連結或更新憑證後馬上同步一次；同步失敗不影響連結的結果，只記 log。"""
    try:
        result = await sync_account(platform, clerk_id)
    except Exception as exc:
        logger.error("Sync after linking %s failed for user_id=%s: %s", platform.name, clerk_id, type(exc).__name__)
        return
    if result.outcome is not SyncOutcome.SUCCEEDED:
        logger.warning(
            "Sync after linking %s did not succeed for user_id=%s: outcome=%s error_code=%s",
            platform.name, clerk_id, result.outcome.value, result.error_code,
        )


def _to_public(account: dict) -> dict:
    """
    轉成回傳給前端的格式：敏感欄位遮罩、_id 改成 id。
    憑證解不開時標 needs_reauth、不回傳憑證欄位，不讓整個清單失敗；其他例外（例如沒設金鑰）照常往外丟。
    """
    account = dict(account)
    account["id"] = account.pop("_id")
    try:
        masked = {field: mask_secret(decrypt_secret(account[field])) for field in SENSITIVE_FIELDS if account.get(field)}
    except SecretDecryptError:
        # 不刪憑證：正式和開發環境共用 DB，可能是另一個環境用它自己的金鑰加密的
        logger.warning("linked account 憑證解密失敗 id=%s", account["id"])
        for field in SENSITIVE_FIELDS:
            account.pop(field, None)
        account["needs_reauth"] = True
        return account
    account.update(masked)
    account["needs_reauth"] = False
    return account


# 各平台的帳號驗證寫在 platforms/ 的 adapter 裡
async def create_linked_account(clerk_id: str, account: LinkedAccountCreate) -> dict:
    doc = account.model_dump()
    doc["_id"] = f"{clerk_id}_{account.platform}"
    doc["clerk_id"] = clerk_id
    logger.debug("create_linked_account platform=%s domain=%s", account.platform, account.domain)

    platform = PLATFORMS.get(account.platform)
    if not platform:
        raise InvalidRequestError(f"Unsupported platform: {account.platform}")

    missing = [f for f in platform.required_create_fields if not getattr(account, f, None)]
    if missing:
        raise InvalidRequestError(f"{', '.join(missing)} required for {account.platform}")

    result = await platform.verify_new_account(doc)
    doc.update(result)
    doc[platform.secret_field] = encrypt_secret(doc[platform.secret_field])
    doc["link_id"] = _new_link_id()

    try:
        await db.linkedAccounts.insert_one(doc)
    except DuplicateKeyError:
        raise ConflictError("Linked account already exists")

    await _sync_after_link(platform, clerk_id)
    return _to_public(doc)


async def get_linked_accounts_by_clerk_id(clerk_id: str):
    cursor = db.linkedAccounts.find({"clerk_id": clerk_id})
    return [_to_public(account) async for account in cursor]


async def find_linked_account(clerk_id: str, platform: str) -> dict | None:
    """資料庫裡的原始資料，憑證是密文。"""
    return await db.linkedAccounts.find_one({"_id": f"{clerk_id}_{platform}"})


async def update_linked_account_by_clerk_id(clerk_id: str, platform: str, data: dict):
    composite_id = f"{clerk_id}_{platform}"
    if not data:
        raise InvalidRequestError("沒有可更新的欄位")

    adapter = PLATFORMS.get(platform)
    reverified_platform = adapter if adapter and adapter.needs_reverify(data) else None
    if reverified_platform:
        existing = await find_linked_account(clerk_id, platform)
        if existing is None:
            return False  # 帳號不存在，不用呼叫平台驗證
        data = await reverified_platform.verify_account_update(data, existing)
        data["link_id"] = _new_link_id()

    # 不 upsert：帳號不存在要回 404
    # 用 matched_count：值沒變時 modified_count 是 0，但不算失敗
    result = await db.linkedAccounts.update_one({"_id": composite_id}, {"$set": data})
    if result.matched_count == 0:
        return False
    if reverified_platform:
        await _sync_after_link(reverified_platform, clerk_id)
    return True


async def delete_linked_account_by_id(composite_id: str):
    result = await db.linkedAccounts.delete_one({"_id": composite_id})
    if result.deleted_count == 0:
        raise NotFoundError("Linked account not found")
