import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class NonRetryableError(Exception):
    """重試也沒用的失敗（憑證錯誤、找不到資源），不重試直接退回舊資料。"""
    pass


class UpstreamError(Exception):
    """外部平台暫時性失敗（5xx、限流、連不上），router 回 502。"""
    pass


async def sync_platform_items(
    collection,
    user_id: str,
    id_field: str,
    fetch_fn: Callable[[], Awaitable[list[dict]]],
    max_attempts: int = 2,
    retry_delay_seconds: float = 1.0,
) -> tuple[list[dict], bool, Optional[datetime], bool]:
    """
    即時抓資料，失敗就以指數退避重試（若非 NonRetryableError 不重試），
    最後仍失敗則退回 DB 裡上次成功的資料；沒有舊資料就把最後的例外往外拋。

    回傳 (items, stale, synced_at, auth_error)：
    stale 表示是退回的舊資料；auth_error 表示是憑證失效造成的退回。
    """
    last_exc: Optional[Exception] = None # 最後一次發生的異常
    items: Optional[list[dict]] = None # 抓取到的資料

    for attempt in range(max_attempts):
        try:
            # 執行抓取任務
            items = await fetch_fn()
            break
        except Exception as exc:
            last_exc = exc
            is_last_attempt = attempt == max_attempts - 1 # 避免最後一次等待，直接跳出迴圈
            is_retryable = not isinstance(exc, NonRetryableError)

            if not is_retryable:
                logger.info(
                    "Non-retryable error for user_id=%s, skipping retry: %s",
                    user_id, exc,
                )
                break

            if not is_last_attempt:
                delay = retry_delay_seconds * (2 ** attempt)
                logger.warning(
                    "Live fetch failed for user_id=%s (attempt %d/%d), retrying in %.1fs",
                    user_id, attempt + 1, max_attempts, delay,
                    exc_info=True,
                )
                await asyncio.sleep(delay)

    if items is None:
        logger.warning(
            "Live fetch failed for user_id=%s after %d attempt(s), falling back to last synced data",
            user_id, max_attempts,
            exc_info=last_exc,
        )
        last_synced = await collection.find({"user_id": user_id}).to_list(length=None)
        if not last_synced: # 沒有舊資料可退，這時才把例外拋出去
            assert last_exc is not None  # items 是 None 代表至少失敗過一次
            raise last_exc
        synced_at = last_synced[0].get("synced_at")
        # _id 是 MongoDB 的 ObjectId，不能轉成 JSON，新抓的資料也沒有這個欄位，需移除 _id
        for doc in last_synced:
            doc.pop("_id", None)
        auth_error = isinstance(last_exc, NonRetryableError)
        return last_synced, True, synced_at, auth_error

    now = datetime.now(timezone.utc)
    for item in items:
        doc = {**item, "user_id": user_id, "synced_at": now}
        await collection.update_one(
            {"user_id": user_id, id_field: item[id_field]},
            {"$set": doc},
            upsert=True,
        )

    # 清掉平台上已不存在的項目，否則退回舊資料時會出現早就被刪掉的項目
    current_ids = [item[id_field] for item in items]
    await collection.delete_many({
        "user_id": user_id,
        id_field: {"$nin": current_ids},
    })

    return items, False, now, False
