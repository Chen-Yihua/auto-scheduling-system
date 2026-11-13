"""依 Google 回應的狀態碼與 error.errors[].reason 判斷錯誤原因（ADR 0011 的 error_code）。"""
import httpx

from core.errors import retry_after_header

# Google Calendar API 用 403 或 429 加這些 reason 回報限流與用量上限；dailyLimitExceeded 是舊文件的 reason
RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded", "dailyLimitExceeded"}
PERMISSION_REASONS = {"insufficientPermissions", "forbidden"}

RATE_LIMITED_DETAIL = "Google 請求太頻繁，請稍後再試"
PERMISSION_DETAIL = "Google 授權的權限不足，請重新連接 Google Calendar"
UPSTREAM_DETAIL = "Google 暫時無法處理請求，請稍後再試"
TIMEOUT_DETAIL = "Google 回應逾時，請稍後再試"
UNREACHABLE_DETAIL = "無法連線至 Google，請稍後再試"
INTERNAL_DETAIL = "伺服器處理 Google 請求時發生錯誤，請稍後再試"


def google_error_reasons(response: httpx.Response) -> set[str]:
    try:
        body = response.json()
    except ValueError:
        return set()
    error = body.get("error") if isinstance(body, dict) else None
    errors = error.get("errors") if isinstance(error, dict) else None
    if not isinstance(errors, list):
        return set()
    return {e["reason"] for e in errors if isinstance(e, dict) and isinstance(e.get("reason"), str)}


def is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    return response.status_code == 403 and bool(google_error_reasons(response) & RATE_LIMIT_REASONS)


def google_error_code(response: httpx.Response) -> str:
    """Google Calendar API 錯誤回應的原因；401 由呼叫端換新 token，不在這裡判斷。"""
    status = response.status_code
    if is_rate_limited(response):
        return "UPSTREAM_RATE_LIMITED"
    if status == 403 and google_error_reasons(response) & PERMISSION_REASONS:
        return "REAUTH_REQUIRED"
    if status == 400:
        # 我們送錯了請求
        return "INTERNAL_ERROR"
    return "UPSTREAM_ERROR"


DETAIL_BY_ERROR_CODE = {
    "UPSTREAM_RATE_LIMITED": RATE_LIMITED_DETAIL,
    "REAUTH_REQUIRED": PERMISSION_DETAIL,
    "INTERNAL_ERROR": INTERNAL_DETAIL,
    "UPSTREAM_ERROR": UPSTREAM_DETAIL,
}


def rate_limit_headers(response: httpx.Response) -> dict[str, str]:
    """限流時要轉送給呼叫者的 header（Google 帶秒數的 Retry-After）；不是限流回空的。"""
    return retry_after_header(response.headers) if is_rate_limited(response) else {}


def request_error_code(e: httpx.RequestError) -> tuple[str, str]:
    """連不上或逾時的 (error_code, detail)。"""
    if isinstance(e, httpx.TimeoutException):
        return "UPSTREAM_TIMEOUT", TIMEOUT_DETAIL
    return "UPSTREAM_ERROR", UNREACHABLE_DETAIL
