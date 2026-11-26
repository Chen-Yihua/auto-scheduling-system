import json
import logging
import os
import time
from typing import Any, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")

# 連線在 app 啟動（main.py 的 lifespan）時才建立；import 時不連線
_redis_client: redis.Redis | None = None

# 沒設定 REDIS_URL 時用記憶體，多個 instance 之間不共用
_memory_store: dict[str, tuple[float, str]] = {}

if not REDIS_URL:
    logger.warning(
        "REDIS_URL 未設定，快取改用記憶體儲存"
        "（多個 Cloud Run instance 各自快取，不是全域共用，僅供本機開發/尚未接 Redis 時使用）"
    )


def open_cache() -> None:
    global _redis_client
    if REDIS_URL and _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)


async def close_cache() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def cache_get(key: str) -> Optional[Any]:
    if _redis_client:
        raw = await _redis_client.get(key)
        return json.loads(raw) if raw else None

    entry = _memory_store.get(key)
    if not entry:
        return None
    expire_at, value = entry
    if time.time() > expire_at:
        _memory_store.pop(key, None)
        return None
    return json.loads(value)


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    payload = json.dumps(value, default=str)
    if _redis_client:
        await _redis_client.set(key, payload, ex=ttl_seconds)
        return
    _memory_store[key] = (time.time() + ttl_seconds, payload)


async def cache_delete(key: str) -> None:
    if _redis_client:
        await _redis_client.delete(key)
        return
    _memory_store.pop(key, None)
