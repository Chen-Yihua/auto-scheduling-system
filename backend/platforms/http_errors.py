"""
GitHub、Jira 錯誤回應的判斷：這裡只判斷限流與憑證被拒，對外的 error_code 由 core/errors.py 的共用規則決定。

抓項目時丟 platforms/sync.py 的例外（決定重試）；連結帳號時丟 AppError。
限流時帶出對方回應的 Retry-After。第三方回應原文只放進例外訊息與 log，detail 都是固定的文字。
"""
import logging
import socket

import httpx

from core.errors import AppError, request_error_code, retry_after_header, upstream_detail, upstream_error_code
from platforms.sync import NonRetryableError, UpstreamError

logger = logging.getLogger(__name__)

# GitHub 的 secondary rate limit 回 403，不一定帶 header，只能從訊息判斷
_SECONDARY_RATE_LIMIT_TEXT = "secondary rate limit"
_NON_RETRYABLE_STATUSES = {400, 401, 403, 404}


def has_rate_limit_signal(response: httpx.Response) -> bool:
    """403 是不是限流：GitHub 主要限流帶 x-ratelimit-remaining: 0，secondary rate limit 可能帶 retry-after 或只寫在訊息裡。"""
    if response.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in response.headers:
        return True
    return _SECONDARY_RATE_LIMIT_TEXT in response.text.lower()


def _is_rate_limited(response: httpx.Response) -> bool:
    return response.status_code == 429 or (response.status_code == 403 and has_rate_limit_signal(response))


def fetch_error(response: httpx.Response, label: str, *, not_found_detail: str | None = None) -> Exception:
    """
    抓項目時的非 200 回應。400、401、403、404 不重試，其他會重試。
    not_found_detail 有給時，404 代表已存的網域失效，算憑證被拒（Jira）。
    """
    status = response.status_code
    message = f"{label} API failed: {status} {response.text}"
    rate_limited = _is_rate_limited(response)
    domain_gone = status == 404 and not_found_detail is not None
    error_code = upstream_error_code(
        status,
        rate_limited=rate_limited,
        credentials_rejected=status in (401, 403) or domain_gone,
        stored_credentials=True,
    )
    headers = retry_after_header(response.headers) if rate_limited else {}
    if status in _NON_RETRYABLE_STATUSES:
        return NonRetryableError(message, error_code=error_code, detail=not_found_detail if domain_gone else None, headers=headers)
    return UpstreamError(message, error_code=error_code, headers=headers)


def verify_error(response: httpx.Response, label: str, *, check_domain: bool = False) -> AppError:
    """
    連結或更新帳號時驗證憑證的非 200 回應。check_domain：404 代表網域不存在（Jira）。
    """
    status = response.status_code
    logger.warning("%s 驗證失敗: %s %s", label, status, response.text)
    rate_limited = _is_rate_limited(response)
    domain_missing = status == 404 and check_domain
    error_code = upstream_error_code(
        status,
        rate_limited=rate_limited,
        credentials_rejected=status in (401, 403) or domain_missing,
        stored_credentials=False,
    )
    if error_code == "INVALID_CREDENTIALS":
        if domain_missing:
            detail = f"找不到這個 {label} 網域，請確認網域是否正確"
        elif status == 403:
            detail = f"{label} token 權限不足，請換一個有權限的 token"
        else:
            detail = f"{label} token 無效，請確認後重新輸入"
    else:
        detail = upstream_detail(label, error_code)
    headers = retry_after_header(response.headers) if rate_limited else None
    return AppError(detail, error_code=error_code, headers=headers)


def _caused_by_dns_failure(exc: BaseException) -> bool:
    seen = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, socket.gaierror):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def verify_request_error(exc: httpx.RequestError, label: str, *, check_domain: bool = False) -> AppError:
    """連結或更新帳號時連不上或逾時。check_domain：DNS 找不到網域代表網域錯（Jira）。"""
    logger.error("%s 驗證連線失敗: %s", label, exc)
    if check_domain and isinstance(exc, httpx.ConnectError) and _caused_by_dns_failure(exc):
        return AppError(f"找不到這個 {label} 網域，請確認網域是否正確", error_code="INVALID_CREDENTIALS")
    error_code = request_error_code(exc)
    return AppError(upstream_detail(label, error_code), error_code=error_code)


def unparsable_verify_response(label: str) -> AppError:
    """連結時對方回應無法解析。"""
    return AppError(f"{label} 的回應無法解析，請稍後再試", error_code="UPSTREAM_ERROR")
