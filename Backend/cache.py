import json
import logging
import os
import time
from typing import Any, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")

_redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

# REDIS_URL 沒設定時的退路：存在這個 process 自己的記憶體裡。
# 跟 rate_limit.py 一樣的取捨——多個 Cloud Run instance 各自快取、不是全域共用，
# 但至少同一個 instance 內重複請求不用每次都真的打外部 API。
_memory_store: dict[str, tuple[float, str]] = {}

if not REDIS_URL:
    logger.warning(
        "REDIS_URL 未設定，快取改用記憶體儲存"
        "（多個 Cloud Run instance 各自快取，不是全域共用，僅供本機開發/尚未接 Redis 時使用）"
    )


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
