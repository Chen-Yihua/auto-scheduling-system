"""
外部平台共用的 API，路由依 PLATFORMS 自動產生：
GET {route_path} 只讀資料庫裡的項目；POST {sync_route_path}（立即同步）即時向平台抓資料、寫進資料庫再回傳。

回應 header：X-Synced-At 是最近一次成功同步的時間；X-Auth-Error 表示憑證已失效需要重新連結
（只有 REAUTH_REQUIRED 的失敗才設；限流、平台故障等不設）；X-Data-Stale 表示立即同步失敗、退回的是舊資料。
"""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Request, Response
from pymongo.errors import ConnectionFailure

from core.errors import AppError, ExternalServiceError, InvalidRequestError, ReauthRequiredError
from core.rate_limit import limiter
from core.security import get_current_clerk_user
from crud.linked_account import find_linked_account
from platforms import PLATFORMS
from platforms.account_sync import SyncOutcome, SyncResult, sync_account
from platforms.base import PlatformAdapter
from platforms.sync import InvalidResponseError, NonRetryableError, UpstreamError, read_items

logger = logging.getLogger(__name__)


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


def _not_linked(platform: PlatformAdapter) -> InvalidRequestError:
    return InvalidRequestError(platform.not_linked_detail, error_code="NOT_LINKED")


def _fetch_failure_error(platform: PlatformAdapter, user_id: str, exc: Optional[Exception]) -> AppError:
    """抓取失敗而且沒有舊資料時回的錯誤：照例外帶的 error_code。"""
    if isinstance(exc, NonRetryableError):
        logger.warning("%s fetch failed without retry for user_id=%s: %s", platform.name, user_id, exc.error_code)
        return AppError(exc.detail or _fetch_error_detail(platform, exc.error_code), error_code=exc.error_code, headers=exc.headers)
    if isinstance(exc, UpstreamError):
        logger.warning("%s unavailable for user_id=%s", platform.name, user_id, exc_info=exc)
        return ExternalServiceError(_fetch_error_detail(platform, exc.error_code), error_code=exc.error_code, headers=exc.headers)
    if isinstance(exc, httpx.HTTPError):
        logger.warning("%s unavailable for user_id=%s", platform.name, user_id, exc_info=exc)
        error_code = "UPSTREAM_TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "UPSTREAM_ERROR"
        return ExternalServiceError(_fetch_error_detail(platform, error_code), error_code=error_code)
    if isinstance(exc, InvalidResponseError):
        logger.warning("%s returned an unparsable response for user_id=%s", platform.name, user_id, exc_info=exc)
        return ExternalServiceError(platform.fetch_failed_detail)
    logger.error("Failed to sync %s items for user_id=%s", platform.name, user_id, exc_info=exc)
    return AppError(platform.fetch_failed_detail)


def _set_sync_status_headers(response: Response, account: dict) -> None:
    if account.get("last_synced_at"):
        response.headers["X-Synced-At"] = account["last_synced_at"].isoformat()
    if account.get("last_sync_error_code") == "REAUTH_REQUIRED":
        response.headers["X-Auth-Error"] = "true"


async def _items_in_db(platform: PlatformAdapter, user_id: str, response: Response, account: dict) -> list[dict]:
    response.headers["X-Data-Stale"] = "false"
    _set_sync_status_headers(response, account)
    return await read_items(platform.collection, user_id)


async def get_platform_items(platform: PlatformAdapter, user_id: str, response: Response) -> list[dict]:
    """只讀資料庫，不解密憑證、不向平台抓資料。"""
    account = await find_linked_account(user_id, platform.name)
    if not account:
        raise _not_linked(platform)
    return await _items_in_db(platform, user_id, response, account)


async def _stale_or_raise(platform: PlatformAdapter, user_id: str, response: Response, result: SyncResult) -> list[dict]:
    """立即同步失敗：有舊資料就退回舊資料，沒有就回錯誤。"""
    old_items = await read_items(platform.collection, user_id)
    if not old_items:
        if result.outcome is SyncOutcome.LOCK_TIMEOUT:
            raise AppError(platform.fetch_failed_detail, error_code="SERVICE_UNAVAILABLE")
        raise _fetch_failure_error(platform, user_id, result.error)

    response.headers["X-Data-Stale"] = "true"
    account = await find_linked_account(user_id, platform.name)
    if account and account.get("last_synced_at"):
        response.headers["X-Synced-At"] = account["last_synced_at"].isoformat()
    if result.error_code == "REAUTH_REQUIRED":
        response.headers["X-Auth-Error"] = "true"
    return old_items


async def sync_platform_items_now(platform: PlatformAdapter, user_id: str, response: Response) -> list[dict]:
    """立即同步：一律即時抓資料；被別的同步取代時回資料庫目前的項目。"""
    try:
        result = await sync_account(platform, user_id)
    except ConnectionFailure:
        logger.exception("Database unavailable while syncing %s items for user_id=%s", platform.name, user_id)
        raise AppError(platform.fetch_failed_detail, error_code="SERVICE_UNAVAILABLE")
    except Exception:
        logger.exception("Failed to sync %s items for user_id=%s", platform.name, user_id)
        raise AppError(platform.fetch_failed_detail)

    outcome = result.outcome
    if outcome is SyncOutcome.SUCCEEDED:
        response.headers["X-Data-Stale"] = "false"
        if result.synced_at:
            response.headers["X-Synced-At"] = result.synced_at.isoformat()
        return result.items
    if outcome is SyncOutcome.UNDECRYPTABLE:
        logger.warning("Failed to decrypt %s credentials for user_id=%s", platform.name, user_id)
        raise ReauthRequiredError(_credentials_unreadable_detail(platform))
    if outcome is SyncOutcome.INCOMPLETE_CREDENTIALS:
        raise _not_linked(platform)
    if outcome in (SyncOutcome.FAILED, SyncOutcome.LOCK_TIMEOUT):
        return await _stale_or_raise(platform, user_id, response, result)

    # 被取代、鎖被拿走、帳號已變更：回資料庫目前的狀態
    account = await find_linked_account(user_id, platform.name)
    if not account:
        raise _not_linked(platform)
    return await _items_in_db(platform, user_id, response, account)


def build_platform_router(platform: PlatformAdapter) -> APIRouter:
    router = APIRouter(tags=[platform.name])

    async def get_endpoint(response: Response, clerk_user: dict = Depends(get_current_clerk_user)):
        return await get_platform_items(platform, clerk_user["sub"], response)

    # slowapi 要求 endpoint 帶 request 參數
    async def sync_endpoint(request: Request, response: Response, clerk_user: dict = Depends(get_current_clerk_user)):
        return await sync_platform_items_now(platform, clerk_user["sub"], response)

    # slowapi 用函式名稱區分 endpoint，不改名的話各平台會共用同一組限流計數
    sync_endpoint.__name__ = sync_endpoint.__qualname__ = f"sync_{platform.name}_items"
    if platform.rate_limit:
        sync_endpoint = limiter.limit(platform.rate_limit)(sync_endpoint)

    router.add_api_route(
        platform.route_path,
        get_endpoint,
        methods=["GET"],
        response_model=list[platform.response_model],
        name=f"get_{platform.name}_items",
    )
    router.add_api_route(
        platform.sync_route_path,
        sync_endpoint,
        methods=["POST"],
        response_model=list[platform.response_model],
        name=f"sync_{platform.name}_items",
    )
    return router


platform_routers = [build_platform_router(platform) for platform in PLATFORMS.values()]
