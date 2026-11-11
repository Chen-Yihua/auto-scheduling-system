"""
error_code → 狀態碼的對照表，是程式裡唯一決定錯誤狀態碼的地方。

內容和 ADR 0011（docs/decisions/0011-api-error-status-codes.md）的「對照表」相同；新增錯誤原因時兩邊一起改。
"""

STATUS_BY_ERROR_CODE: dict[str, int] = {
    "INVALID_REQUEST": 400,
    "INVALID_CREDENTIALS": 400,
    "INVALID_PLATFORM_DOMAIN": 400,
    "INVALID_AUTHORIZATION_CODE": 400,
    "UNAUTHENTICATED": 401,
    "INVALID_WEBHOOK_SIGNATURE": 401,
    "NOT_FOUND": 404,
    "METHOD_NOT_ALLOWED": 405,
    "NOT_LINKED": 409,
    "REAUTH_REQUIRED": 409,
    "ALREADY_EXISTS": 409,
    "SUGGESTION_EXPIRED": 409,
    "IDEMPOTENCY_KEY_REUSED": 409,
    "REQUEST_IN_PROGRESS": 409,
    "NO_PRIMARY_CALENDAR": 409,
    "VALIDATION_ERROR": 422,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
    "UPSTREAM_ERROR": 502,
    "UPSTREAM_RATE_LIMITED": 503,
    "SERVICE_UNAVAILABLE": 503,
    "UPSTREAM_TIMEOUT": 504,
}


def status_for_error_code(error_code: str) -> int | None:
    """查不到時回 None，由 core/exception_handlers.py 改回固定的 500。"""
    return STATUS_BY_ERROR_CODE.get(error_code)
