import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


async def sync_platform_items(
    collection,
    user_id: str,
    id_field: str,
    fetch_fn: Callable[[], Awaitable[list[dict]]],
) -> tuple[list[dict], bool, Optional[datetime]]:
    """
    GitHub / Jira / Moodle 共用的「即時優先、DB 當退路」讀取邏輯：
    - 即時抓資料成功 -> upsert 進 collection，回傳最新資料（stale=False）
    - 即時抓資料失敗（rate limit、API 掛掉、Selenium 逾時等）
      -> 退回 collection 裡該使用者最後一次成功的快照（stale=True）
    - 兩者都沒有 -> 讓原本的例外往外拋，由呼叫端決定要回什麼錯誤
    """
    try:
        items = await fetch_fn()
    except Exception:
        logger.warning(
            "Live fetch failed for user_id=%s, falling back to cached data",
            user_id,
            exc_info=True,
        )
        cached = await collection.find({"user_id": user_id}).to_list(length=None)
        if not cached:
            raise
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
