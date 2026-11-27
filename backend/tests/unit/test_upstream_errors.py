"""外部服務錯誤轉成對外 error_code 的共用規則：各平台只判斷限流與憑證被拒，相同的情況要得到相同的 error_code。"""
import httpx
import pytest

from platforms.http_errors import fetch_error, verify_error
from services.google_errors import google_error_code


def _github(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, headers=headers, request=httpx.Request("GET", "https://api.github.com/x"))


def _google(status: int, reason: str | None = None) -> httpx.Response:
    body = {"error": {"errors": [{"reason": reason}]}} if reason else {}
    return httpx.Response(status, json=body, request=httpx.Request("GET", "https://www.googleapis.com/x"))


@pytest.mark.parametrize("github, google, stored_code, submitted_code", [
    (_github(429), _google(429), "RATE_LIMITED", "RATE_LIMITED"),
    (_github(403, {"x-ratelimit-remaining": "0"}), _google(403, "rateLimitExceeded"), "RATE_LIMITED", "RATE_LIMITED"),
    (_github(403), _google(403, "insufficientPermissions"), "REAUTH_REQUIRED", "INVALID_CREDENTIALS"),
    (_github(400), _google(400), "INTERNAL_ERROR", "INTERNAL_ERROR"),
    (_github(503), _google(503), "UPSTREAM_ERROR", "UPSTREAM_ERROR"),
], ids=["429", "403-rate-limit", "403-permission", "400", "5xx"])
def test_same_upstream_condition_gives_same_error_code(github, google, stored_code, submitted_code):
    """同一種外部錯誤：GitHub 與 Google 的 error_code 相同；憑證被拒時，已存的憑證要重新連結，連結時送出的憑證是表單錯誤。"""
    assert getattr(fetch_error(github, "GitHub"), "error_code") == stored_code
    assert google_error_code(google) == stored_code
    assert verify_error(github, "GitHub").error_code == submitted_code


def test_jira_missing_domain_is_credentials_error():
    """Jira 網域不存在：連結時是 INVALID_CREDENTIALS（使用者修正表單），已存的網域失效是 REAUTH_REQUIRED。"""
    response = httpx.Response(404, request=httpx.Request("GET", "https://x.atlassian.net"))

    assert verify_error(response, "Jira", check_domain=True).error_code == "INVALID_CREDENTIALS"
    assert getattr(fetch_error(response, "Jira", not_found_detail="網域失效"), "error_code") == "REAUTH_REQUIRED"
