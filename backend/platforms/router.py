"""
外部平台共用的「取得使用者在這個平台的項目」API，路由依 PLATFORMS 自動產生。

回應 header：X-Data-Stale 表示是退回的舊資料，X-Auth-Error 表示憑證已失效需要重新連結
（只有 REAUTH_REQUIRED 的失敗才設；限流、平台故障等不重試的失敗不設）。
"""
import logging

import httpx
from fastapi import APIRouter, Depends, Request, Response
from pymongo.errors import ConnectionFailure

from core.cache import cache_get, cache_set
from core.errors import AppError, ExternalServiceError, InvalidRequestError, ReauthRequiredError
from platforms.sync import InvalidResponseError, NonRetryableError, UpstreamError
from core.crypto import SecretDecryptError, decrypt_secret
from crud.linked_account import find_linked_account
from core.security import get_current_clerk_user
from platforms import PLATFORMS
from platforms.base import PlatformAdapter
from core.rate_limit import limiter

logger = logging.getLogger(__name__)


def _cache_key(platform: PlatformAdapter, user_id: str) -> str:
    return f"platform_items:{platform.name}:{user_id}"


def _fetch_error_detail(platform: PlatformAdapter, error_code: str) -> str:
    if error_code == "REAUTH_REQUIRED":
        return platform.auth_failed_detail
    if error_code == "UPSTREAM_RATE_LIMITED":
        return f"{platform.display_name} 請求太頻繁，請稍後再試"
    if error_code == "UPSTREAM_TIMEOUT":
        return f"{platform.display_name} 回應逾時，請稍後再試"
    return platform.fetch_failed_detail


def _credentials_unreadable_detail(platform: PlatformAdapter) -> str:
    return f"{platform.display_name} 的憑證無法讀取，請重新連結帳號"


async def get_platform_items(platform: PlatformAdapter, user_id: str, response: Response) -> list[dict]:
    # 先嘗試從快取拿資料
    if platform.cache_ttl_seconds:
        cached = await cache_get(_cache_key(platform, user_id))
        if cached is not None:
            response.headers["X-Data-Stale"] = "false"
            if cached.get("synced_at"):
                response.headers["X-Synced-At"] = cached["synced_at"]
            return cached["items"]

    # 若快取沒有或過期就去抓取
    account = await find_linked_account(user_id, platform.name)
    if not account:
        raise InvalidRequestError(platform.not_linked_detail, error_code="NOT_LINKED")

    try:
        credentials = platform.credentials_from_account(account, decrypt_secret)
    except SecretDecryptError:
        # 不刪憑證：正式和開發環境共用 DB，可能是另一個環境用它自己的金鑰加密的
        logger.warning("Failed to decrypt %s credentials for user_id=%s", platform.name, user_id)
        raise ReauthRequiredError(_credentials_unreadable_detail(platform), status_code=500)
    except Exception:
        logger.exception("Failed to read %s credentials for user_id=%s", platform.name, user_id)
        raise AppError(platform.fetch_failed_detail)
    if credentials is None:
        raise InvalidRequestError(platform.not_linked_detail, error_code="NOT_LINKED")

    async def fetch():
        return await platform.fetch_items(credentials)

    # 沒有舊資料時的狀態碼維持目前的值，依例外類別決定；error_code 照例外帶的原因
    try:
        items, stale, synced_at, auth_error = await platform.sync_items(user_id, fetch)
    except NonRetryableError as e:
        logger.warning("%s fetch failed without retry for user_id=%s: %s", platform.name, user_id, e.error_code)
        raise AppError(e.detail or _fetch_error_detail(platform, e.error_code), error_code=e.error_code, status_code=401)
    except UpstreamError as e:
        logger.warning("%s unavailable for user_id=%s", platform.name, user_id, exc_info=True)
        raise ExternalServiceError(_fetch_error_detail(platform, e.error_code), error_code=e.error_code)
    except httpx.HTTPError as e:
        logger.warning("%s unavailable for user_id=%s", platform.name, user_id, exc_info=True)
        error_code = "UPSTREAM_TIMEOUT" if isinstance(e, httpx.TimeoutException) else "UPSTREAM_ERROR"
        raise ExternalServiceError(_fetch_error_detail(platform, error_code), error_code=error_code)
    except InvalidResponseError:
        logger.warning("%s returned an unparsable response for user_id=%s", platform.name, user_id, exc_info=True)
        raise ExternalServiceError(platform.fetch_failed_detail, status_code=500)
    except ConnectionFailure:
        logger.exception("Database unavailable while syncing %s items for user_id=%s", platform.name, user_id)
        raise AppError(platform.fetch_failed_detail, error_code="SERVICE_UNAVAILABLE")
    except Exception:
        logger.exception("Failed to sync %s items for user_id=%s", platform.name, user_id)
        raise AppError(platform.fetch_failed_detail)

    # 回傳 header，讓前端知道資料是否過期、憑證是否失效、最後同步時間
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
