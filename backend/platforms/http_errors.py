"""
GitHub、Jira 錯誤回應的分類（ADR 0011 的 error_code）。

抓項目時丟 platforms/sync.py 的例外（決定重試）；連結帳號時丟 core/errors.py 的例外。
限流時帶出對方回應的 Retry-After。第三方回應原文只放進例外訊息與 log，detail 都是固定的文字。
"""
import logging
import socket

import httpx

from core.errors import AccessDeniedError, AppError, ExternalServiceError, ReauthRequiredError, retry_after_header
from platforms.sync import NonRetryableError, UpstreamError

logger = logging.getLogger(__name__)

# GitHub 的 secondary rate limit 回 403，不一定帶 header，只能從訊息判斷
_SECONDARY_RATE_LIMIT_TEXT = "secondary rate limit"


def has_rate_limit_signal(response: httpx.Response) -> bool:
    """403 是不是限流：GitHub 主要限流帶 x-ratelimit-remaining: 0，secondary rate limit 可能帶 retry-after 或只寫在訊息裡。"""
    if response.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in response.headers:
        return True
    return _SECONDARY_RATE_LIMIT_TEXT in response.text.lower()


def fetch_error(response: httpx.Response, label: str, *, not_found_detail: str | None = None) -> Exception:
    """
    抓項目時的非 200 回應。400、401、403、404 不重試，其他會重試。
    not_found_detail 有給時，404 代表已存的網域失效，算憑證失效（Jira）。
    """
    status = response.status_code
    message = f"{label} API failed: {status} {response.text}"
    if status == 403 and has_rate_limit_signal(response):
        return NonRetryableError(message, error_code="UPSTREAM_RATE_LIMITED", headers=retry_after_header(response.headers))
    if status in (401, 403):
        return NonRetryableError(message, error_code="REAUTH_REQUIRED")
    if status == 404:
        if not_found_detail:
            return NonRetryableError(message, error_code="REAUTH_REQUIRED", detail=not_found_detail)
        return NonRetryableError(message, error_code="UPSTREAM_ERROR")
    if status == 400:
        # 我們送錯了請求
        return NonRetryableError(message, error_code="INTERNAL_ERROR")
    if status == 429:
        return UpstreamError(message, error_code="UPSTREAM_RATE_LIMITED", headers=retry_after_header(response.headers))
    return UpstreamError(message, error_code="UPSTREAM_ERROR")


def verify_error(response: httpx.Response, label: str, *, check_domain: bool = False) -> AppError:
    """
    連結或更新帳號時驗證憑證的非 200 回應。check_domain：404 代表網域不存在（Jira）。
    """
    status = response.status_code
    logger.warning("%s 驗證失敗: %s %s", label, status, response.text)
    if status == 401:
        return ReauthRequiredError(f"{label} token 無效，請確認後重新輸入", error_code="INVALID_CREDENTIALS")
    if status == 429 or (status == 403 and has_rate_limit_signal(response)):
        return AccessDeniedError(
            f"{label} 請求太頻繁，請稍後再試", error_code="UPSTREAM_RATE_LIMITED", headers=retry_after_header(response.headers)
        )
    if status == 403:
        return AccessDeniedError(f"{label} token 權限不足，請換一個有權限的 token", error_code="INVALID_CREDENTIALS")
    if status == 404 and check_domain:
        return AccessDeniedError(f"找不到這個 {label} 網域，請確認網域是否正確", error_code="INVALID_PLATFORM_DOMAIN")
    if status == 400:
        return AccessDeniedError(f"伺服器驗證 {label} 帳號時發生錯誤，請稍後再試", error_code="INTERNAL_ERROR")
    if status >= 500:
        return AccessDeniedError(f"{label} 暫時無法處理請求，請稍後再試", error_code="UPSTREAM_ERROR")
    return AccessDeniedError(f"{label} 回應異常，請稍後再試", error_code="UPSTREAM_ERROR")


def _caused_by_dns_failure(exc: BaseException) -> bool:
    seen = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, socket.gaierror):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def verify_request_error(exc: httpx.RequestError, label: str, *, check_domain: bool = False) -> ExternalServiceError:
    """連結或更新帳號時連不上或逾時。check_domain：DNS 找不到網域代表網域錯（Jira）。"""
    logger.error("%s 驗證連線失敗: %s", label, exc)
    if check_domain and isinstance(exc, httpx.ConnectError) and _caused_by_dns_failure(exc):
        return ExternalServiceError(f"找不到這個 {label} 網域，請確認網域是否正確", error_code="INVALID_PLATFORM_DOMAIN")
    if isinstance(exc, httpx.TimeoutException):
        return ExternalServiceError(f"{label} 回應逾時，請稍後再試", error_code="UPSTREAM_TIMEOUT")
    return ExternalServiceError(f"無法連線至 {label}，請稍後再試", error_code="UPSTREAM_ERROR")


def unparsable_verify_response(label: str) -> ExternalServiceError:
    """連結時對方回應無法解析。"""
    return ExternalServiceError(f"{label} 的回應無法解析，請稍後再試")
