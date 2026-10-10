"""
所有外部平台共用的「取得使用者在這個平台的項目」API。每個平台的路徑
（/github/issues、/jira/issues、/moodle/assignments）由 PLATFORMS 自動產生，
流程都一樣，平台之間的差異都在各自的 adapter 裡（見 platforms/base.py）：

查連結帳號 → 解密憑證 →（有設快取就先查快取）→ 即時抓資料，失敗時退回上次成功的
資料（見 platforms/sync.py）→ 用回應 header 告訴前端資料新不新、要不要重新連結。
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

    # clerk_id + platform 這個組合保證唯一
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
        # stale, synced_at 決定要不要顯示「資料可能過期」的提示
        # auth_error 決定要不要顯示「請重新連結帳號」的提示
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

    # 只有真的抓到新鮮資料才值得快取；如果這次是退回 DB 舊資料（stale=True），
    # 代表上次抓取失敗，應該讓下一次呼叫正常重試，不要把「已知是舊的」資料
    # 又快取起來、變相延長 fallback 的時間
    if platform.cache_ttl_seconds and not stale:
        await cache_set(
            _cache_key(platform, user_id),
            {"items": items, "synced_at": synced_at.isoformat() if synced_at else None},
            platform.cache_ttl_seconds,
        )

    return items


def build_platform_router(platform: PlatformAdapter) -> APIRouter:
    router = APIRouter(tags=[platform.name])

    # slowapi 的 limiter 要求 endpoint 帶 request 參數；response 讓上面設回應 header
    async def endpoint(request: Request, response: Response, clerk_user: dict = Depends(get_current_clerk_user)):
        return await get_platform_items(platform, clerk_user["sub"], response)

    # slowapi 用「模組.函式名稱」登記每個 endpoint 的限流規則跟計數；每個平台的 endpoint
    # 都是這同一個內部函式，不改名的話，兩個有限流的平台會共用同一組規則跟計數
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
