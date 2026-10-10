"""
外部平台共用的「取得使用者在這個平台的項目」API，路由依 PLATFORMS 自動產生。

回應 header：X-Data-Stale 表示是退回的舊資料，X-Auth-Error 表示憑證已失效需要重新連結。
"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from core.cache import cache_get, cache_set
from platforms.sync import NonRetryableError, UpstreamError
from core.crypto import decrypt_secret
from core.database import db
from core.security import get_current_clerk_user
from platforms import PLATFORMS
from platforms.base import PlatformAdapter
from core.rate_limit import limiter

logger = logging.getLogger(__name__)


def _cache_key(platform: PlatformAdapter, user_id: str) -> str:
    return f"platform_items:{platform.name}:{user_id}"


async def get_platform_items(platform: PlatformAdapter, user_id: str, response: Response) -> list[dict]:
    if platform.cache_ttl_seconds:
        cached = await cache_get(_cache_key(platform, user_id))
        if cached is not None:
            response.headers["X-Data-Stale"] = "false"
            if cached.get("synced_at"):
                response.headers["X-Synced-At"] = cached["synced_at"]
            return cached["items"]

    account = await db.linkedAccounts.find_one({"clerk_id": user_id, "platform": platform.name})
    if not account:
        raise HTTPException(status_code=400, detail=platform.not_linked_detail)

    try:
        credentials = platform.credentials_from_account(account, decrypt_secret)
    except Exception:
        logger.exception("Failed to decrypt %s credentials for user_id=%s", platform.name, user_id)
        raise HTTPException(status_code=500, detail=platform.fetch_failed_detail)
    if credentials is None:
        raise HTTPException(status_code=400, detail=platform.not_linked_detail)

    async def fetch():
        return await platform.fetch_items(credentials)

    try:
        items, stale, synced_at, auth_error = await platform.sync(user_id, fetch)
    except NonRetryableError:
        logger.warning("%s credentials invalid/expired for user_id=%s", platform.name, user_id)
        raise HTTPException(status_code=401, detail=platform.auth_failed_detail)
    except (UpstreamError, httpx.HTTPError):
        logger.warning("%s unavailable for user_id=%s", platform.name, user_id, exc_info=True)
        raise HTTPException(status_code=502, detail=platform.fetch_failed_detail)
    except Exception:
        logger.exception("Failed to sync %s items for user_id=%s", platform.name, user_id)
        raise HTTPException(status_code=500, detail=platform.fetch_failed_detail)

    response.headers["X-Data-Stale"] = str(stale).lower()
    if auth_error:
        response.headers["X-Auth-Error"] = "true"
    if synced_at:
        response.headers["X-Synced-At"] = synced_at.isoformat()

    # 不快取舊資料，讓下次請求重新嘗試抓取
    if platform.cache_ttl_seconds and not stale:
        await cache_set(
            _cache_key(platform, user_id),
            {"items": items, "synced_at": synced_at.isoformat() if synced_at else None},
            platform.cache_ttl_seconds,
        )

    return items


def build_platform_router(platform: PlatformAdapter) -> APIRouter:
    router = APIRouter(tags=[platform.name])

    # slowapi 要求 endpoint 帶 request 參數
    async def endpoint(request: Request, response: Response, clerk_user: dict = Depends(get_current_clerk_user)):
        return await get_platform_items(platform, clerk_user["sub"], response)

    # slowapi 用函式名稱區分 endpoint，不改名的話各平台會共用同一組限流計數
    endpoint.__name__ = endpoint.__qualname__ = f"get_{platform.name}_items"

    if platform.rate_limit:
        endpoint = limiter.limit(platform.rate_limit)(endpoint)

    router.add_api_route(
        platform.route_path,
        endpoint,
        methods=["GET"],
        response_model=list[platform.response_model],
        name=f"get_{platform.name}_items",
    )
    return router


platform_routers = [build_platform_router(platform) for platform in PLATFORMS.values()]
