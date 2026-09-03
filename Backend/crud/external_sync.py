import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


async def sync_platform_items(
    collection,
    user_id: str,
    id_field: str,
    fetch_fn: Callable[[], Awaitable[list[dict]]],
    max_attempts: int = 2,
    retry_delay_seconds: float = 1.0,
) -> tuple[list[dict], bool, Optional[datetime]]:
    """
    GitHub / Jira / Moodle 共用的「即時優先、重試、DB 當最終退路」讀取邏輯：
    - 即時抓資料成功 -> upsert 進 collection，回傳最新資料（stale=False）
    - 即時抓資料失敗 -> 用指數退避重試最多 max_attempts 次（預設抓不到只重試 1 次，
      總共 2 次嘗試），只處理「這次沒抓到，等一下可能就好了」的暫時性失敗
      （網路抖動、API 短暫 5xx、Moodle 頁面還沒載完）——不特別分辨錯誤種類，
      所以像 token 失效這種一定會再次失敗的情況，也會多花一次重試的成本，
      這是為了不用重寫三個平台的例外處理而接受的取捨。
    - 重試全部失敗 -> 退回 collection 裡該使用者最後一次成功的快照（stale=True）
    - 兩者都沒有 -> 讓最後一次的例外往外拋，由呼叫端決定要回什麼錯誤
    """
    last_exc: Optional[Exception] = None
    items: Optional[list[dict]] = None

    for attempt in range(max_attempts):
        try:
            items = await fetch_fn()
            break
        except Exception as exc:
            last_exc = exc
            is_last_attempt = attempt == max_attempts - 1
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
            "Live fetch failed for user_id=%s after %d attempt(s), falling back to cached data",
            user_id, max_attempts,
            exc_info=last_exc,
        )
        cached = await collection.find({"user_id": user_id}).to_list(length=None)
        if not cached:
            raise last_exc
        synced_at = cached[0].get("synced_at")
        for doc in cached:
            doc.pop("_id", None)
        return cached, True, synced_at

    now = datetime.now(timezone.utc)
    for item in items:
        doc = {**item, "user_id": user_id, "synced_at": now}
        await collection.update_one(
            {"user_id": user_id, id_field: item[id_field]},
            {"$set": doc},
            upsert=True,
        )
    return items, False, now
