"""
Google 錯誤回應的判斷：這裡只依狀態碼與 error.errors[].reason 判斷限流與權限不足，
對外的 error_code 由 core/errors.py 的共用規則決定。
"""
import httpx

from core.errors import retry_after_header, upstream_detail, upstream_error_code

# Google Calendar API 用 403 或 429 加這些 reason 回報限流與用量上限；dailyLimitExceeded 是舊文件的 reason
RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded", "dailyLimitExceeded"}
PERMISSION_REASONS = {"insufficientPermissions", "forbidden"}

PERMISSION_DETAIL = "Google 授權的權限不足，請重新連接 Google Calendar"


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
    return upstream_error_code(
        response.status_code,
        rate_limited=is_rate_limited(response),
        credentials_rejected=response.status_code == 403 and bool(google_error_reasons(response) & PERMISSION_REASONS),
        stored_credentials=True,
    )


def google_detail(error_code: str) -> str:
    return PERMISSION_DETAIL if error_code == "REAUTH_REQUIRED" else upstream_detail("Google", error_code)


def rate_limit_headers(response: httpx.Response) -> dict[str, str]:
    """限流時要轉送給呼叫者的 header（Google 帶秒數的 Retry-After）；不是限流回空的。"""
    return retry_after_header(response.headers) if is_rate_limited(response) else {}
