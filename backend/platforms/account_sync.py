"""
同步一個使用者在一個平台的項目，並記下同步結果。定時同步、立即同步、連結帳號後的同步都呼叫 sync_account。

同一個帳號同時有兩次同步時，以比較晚開始抓資料的那次為準：抓資料時不上鎖，
寫入前先拿 linkedAccounts 上的鎖，再比對已存的開始時間，比較早開始的那次就放棄。
帳號在同步途中被刪除或換成另一次連結（link_id 不同）時，整次放棄、不寫入。
"""
import asyncio
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from core.crypto import SecretDecryptError, decrypt_secret
from core.database import db
from platforms.base import PlatformAdapter
from platforms.sync import delete_missing_items, fetch_error_code, fetch_with_retry, upsert_items

logger = logging.getLogger(__name__)

ID_FIELD = "id"
LOCK_TTL = timedelta(minutes=5)
LOCK_WAIT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.2


class SyncOutcome(Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"                    # 抓取失敗，已記下 error_code，項目沒動
    LOCK_TIMEOUT = "lock_timeout"        # 等不到寫入鎖，什麼都沒寫
    SUPERSEDED = "superseded"            # 已經有比較晚開始的同步寫入過
    LOCK_LOST = "lock_lost"              # 寫入途中鎖過期或被別人拿走
    ACCOUNT_CHANGED = "account_changed"  # 帳號已刪除或換成另一次連結
    UNDECRYPTABLE = "undecryptable"      # 憑證解不開（可能是另一個環境的金鑰加密的）
    INCOMPLETE_CREDENTIALS = "incomplete_credentials"


@dataclass
class SyncResult:
    outcome: SyncOutcome
    items: list[dict] = field(default_factory=list)  # 只有 SUCCEEDED 有
    synced_at: Optional[datetime] = None             # 只有 SUCCEEDED 有
    error: Optional[Exception] = None                # FAILED 時抓取的例外
    error_code: Optional[str] = None                 # FAILED、LOCK_TIMEOUT 時的原因


def _now() -> datetime:
    # MongoDB 只存到毫秒；先截掉，比對開始時間時才不會因為存進去被截斷而判斷錯
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


def _link_filter(link_id: Optional[str]) -> dict:
    # 上線前建立的帳號沒有 link_id，只對到同樣沒有 link_id 的帳號
    return {"link_id": link_id} if link_id is not None else {"link_id": {"$exists": False}}


def _same_link(account: Optional[dict], link_id: Optional[str]) -> bool:
    return account is not None and account.get("link_id") == link_id


async def _changed_or_lost(account_id: str, link_id: Optional[str]) -> SyncResult:
    current = await db.linkedAccounts.find_one({"_id": account_id})
    if not _same_link(current, link_id):
        return SyncResult(SyncOutcome.ACCOUNT_CHANGED)
    return SyncResult(SyncOutcome.LOCK_LOST)


async def _acquire_lock(account_id: str, link_id: Optional[str], owner: str) -> Optional[SyncResult]:
    """拿到鎖回 None；帳號已變更或等太久回對應的結果。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + LOCK_WAIT_SECONDS
    while True:
        now = _now()
        result = await db.linkedAccounts.update_one(
            {
                "_id": account_id,
                **_link_filter(link_id),
                # 欄位不存在時 None 也對得到
                "$or": [{"sync_lock_until": None}, {"sync_lock_until": {"$lte": now}}],
            },
            {"$set": {"sync_lock_owner": owner, "sync_lock_until": now + LOCK_TTL}},
        )
        if result.matched_count:
            return None
        if not _same_link(await db.linkedAccounts.find_one({"_id": account_id}), link_id):
            return SyncResult(SyncOutcome.ACCOUNT_CHANGED)
        if loop.time() >= deadline:
            return SyncResult(SyncOutcome.LOCK_TIMEOUT, error_code="SERVICE_UNAVAILABLE")
        await asyncio.sleep(LOCK_POLL_SECONDS)


async def _write_with_lock(
    platform: PlatformAdapter,
    user_id: str,
    account_id: str,
    link_id: Optional[str],
    owner: str,
    started_at: datetime,
    items: Optional[list[dict]],
    fetch_error: Optional[Exception],
) -> SyncResult:
    accounts = db.linkedAccounts
    ours = {"_id": account_id, "sync_lock_owner": owner, **_link_filter(link_id)}

    current = await accounts.find_one({"_id": account_id})
    if not _same_link(current, link_id):
        return SyncResult(SyncOutcome.ACCOUNT_CHANGED)
    assert current is not None
    stored_started_at = current.get("sync_started_at")
    if stored_started_at is not None and stored_started_at > started_at:
        return SyncResult(SyncOutcome.SUPERSEDED)
    # 先寫開始時間：鎖過期後比較早開始的同步拿到鎖時，才看得出自己已被取代
    if not (await accounts.update_one(ours, {"$set": {"sync_started_at": started_at}})).matched_count:
        return await _changed_or_lost(account_id, link_id)

    now = _now()
    written: list[dict] = []
    if items is not None:
        written = await upsert_items(platform.collection, user_id, ID_FIELD, items, now)

    # 寫入項目期間鎖可能過期或連結變了；這時不能刪項目，也不能蓋掉別人的同步結果
    current = await accounts.find_one({"_id": account_id})
    if not _same_link(current, link_id):
        return SyncResult(SyncOutcome.ACCOUNT_CHANGED)
    assert current is not None
    lock_until = current.get("sync_lock_until")
    if current.get("sync_lock_owner") != owner or lock_until is None or lock_until <= _now():
        return SyncResult(SyncOutcome.LOCK_LOST)

    if items is not None:
        await delete_missing_items(platform.collection, user_id, ID_FIELD, [i[ID_FIELD] for i in written])
        update = {"last_sync_error_code": None, "last_synced_at": now}
        error_code = None
    else:
        assert fetch_error is not None
        error_code = fetch_error_code(fetch_error)
        update = {"last_sync_error_code": error_code}

    if not (await accounts.update_one(ours, {"$set": update})).matched_count:
        return await _changed_or_lost(account_id, link_id)

    if items is None:
        return SyncResult(SyncOutcome.FAILED, error=fetch_error, error_code=error_code)
    return SyncResult(SyncOutcome.SUCCEEDED, items=written, synced_at=now)


async def sync_account(platform: PlatformAdapter, user_id: str) -> SyncResult:
    """
    即時抓資料並寫進資料庫，回傳這次同步的結果。抓取失敗時不動項目，只記下 error_code；
    要不要退回舊資料由呼叫端決定。資料庫的例外與憑證解密以外的例外會往外丟。
    """
    started_at = _now()
    account_id = f"{user_id}_{platform.name}"
    account = await db.linkedAccounts.find_one({"_id": account_id})
    if account is None:
        return SyncResult(SyncOutcome.ACCOUNT_CHANGED)
    link_id = account.get("link_id")

    # 解不開時不搶鎖、不寫任何欄位：開發與正式環境共用資料庫，可能是另一個環境的金鑰加密的
    try:
        credentials = platform.credentials_from_account(account, decrypt_secret)
    except SecretDecryptError:
        return SyncResult(SyncOutcome.UNDECRYPTABLE)
    if credentials is None:
        return SyncResult(SyncOutcome.INCOMPLETE_CREDENTIALS)

    items: Optional[list[dict]] = None
    fetch_error: Optional[Exception] = None
    try:
        items = await fetch_with_retry(user_id, lambda: platform.fetch_items(credentials))
    except Exception as exc:
        fetch_error = exc

    owner = secrets.token_hex(16)
    not_acquired = await _acquire_lock(account_id, link_id, owner)
    if not_acquired is not None:
        return not_acquired
    try:
        return await _write_with_lock(platform, user_id, account_id, link_id, owner, started_at, items, fetch_error)
    finally:
        # 條件帶上自己的 owner：鎖過期被別人拿走時，不能釋放別人的鎖
        await db.linkedAccounts.update_one(
            {"_id": account_id, "sync_lock_owner": owner},
            {"$unset": {"sync_lock_owner": "", "sync_lock_until": ""}},
        )
