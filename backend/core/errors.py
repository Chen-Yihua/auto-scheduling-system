"""
crud、services 和各平台用的例外，由 core/exception_handlers.py 轉成錯誤回應。

丟例外時只決定 error_code（照 ADR 0011 選原因），狀態碼由 core/error_codes.py 的對照表決定；
原因和類別預設不同時在建構時另外指定 error_code。
"""
from collections.abc import Mapping


class AppError(Exception):
    default_error_code = "INTERNAL_ERROR"

    def __init__(self, detail: str, *, error_code: str | None = None, headers: Mapping[str, str] | None = None):
        super().__init__(detail)
        # 只能是固定的文字或使用者自己送出、非機密的值：會原樣回給前端
        self.detail = detail
        self.error_code = error_code or self.default_error_code
        self.headers = dict(headers) if headers else None


class InvalidRequestError(AppError):
    """請求的內容不合法，或前置條件還沒完成（例如還沒連接帳號）。"""
    default_error_code = "INVALID_REQUEST"


class ReauthRequiredError(AppError):
    """使用者綁定的第三方憑證失效，需要重新連結。"""
    default_error_code = "REAUTH_REQUIRED"


class AccessDeniedError(AppError):
    """外部平台拒絕這次驗證用的憑證，例如 token 沒有足夠的權限。"""
    default_error_code = "INVALID_CREDENTIALS"


class NotFoundError(AppError):
    """要操作的資料不存在，或不屬於目前的使用者。"""
    default_error_code = "NOT_FOUND"


class ConflictError(AppError):
    """和現有的資料衝突，例如重複建立。"""
    default_error_code = "ALREADY_EXISTS"


class ConfigurationError(AppError):
    """伺服器設定錯誤，例如第三方服務的 client 設定不正確。"""
    default_error_code = "INTERNAL_ERROR"


class ExternalServiceError(AppError):
    """外部服務故障或連不上。"""
    default_error_code = "UPSTREAM_ERROR"


def retry_after_header(upstream_headers: Mapping[str, str]) -> dict[str, str]:
    """
    外部回應的 Retry-After 是非負整數秒數時原樣轉送；日期格式或其他值不帶。
    不從 x-ratelimit-reset 等 header 換算：要依賴伺服器時鐘，換算錯了反而誤導呼叫者。
    upstream_headers 要能不分大小寫查詢（例如 httpx.Headers）。
    """
    value = (upstream_headers.get("retry-after") or "").strip()
    return {"Retry-After": value} if value.isascii() and value.isdigit() else {}
