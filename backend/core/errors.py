"""
crud、services 和各平台用的例外，由 core/exception_handlers.py 轉成錯誤回應。

error_code 照 ADR 0011 的對照表選原因；各類別的預設狀態碼是過渡期間目前的值（ADR 0011「過渡期間」），
原因和類別預設不同時在建構時另外指定 error_code，要維持和類別預設不同的狀態碼時明確指定 status_code。
"""


class AppError(Exception):
    default_error_code = "INTERNAL_ERROR"
    default_status_code = 500

    def __init__(self, detail: str, *, error_code: str | None = None, status_code: int | None = None):
        super().__init__(detail)
        # 只能是固定的文字或使用者自己送出、非機密的值：會原樣回給前端
        self.detail = detail
        self.error_code = error_code or self.default_error_code
        self.status_code = status_code or self.default_status_code


class InvalidRequestError(AppError):
    """請求的內容不合法，或前置條件還沒完成（例如還沒連接帳號）。"""
    default_error_code = "INVALID_REQUEST"
    default_status_code = 400


class ReauthRequiredError(AppError):
    """使用者綁定的第三方憑證失效，需要重新連結。"""
    default_error_code = "REAUTH_REQUIRED"
    default_status_code = 401


class AccessDeniedError(AppError):
    """外部平台拒絕這次驗證用的憑證，例如 token 沒有足夠的權限。"""
    default_error_code = "INVALID_CREDENTIALS"
    default_status_code = 403


class NotFoundError(AppError):
    """要操作的資料不存在，或不屬於目前的使用者。"""
    default_error_code = "NOT_FOUND"
    default_status_code = 404


class ConflictError(AppError):
    """和現有的資料衝突，例如重複建立。"""
    default_error_code = "ALREADY_EXISTS"
    default_status_code = 409


class ConfigurationError(AppError):
    """伺服器設定錯誤，例如第三方服務的 client 設定不正確。"""
    default_error_code = "INTERNAL_ERROR"
    default_status_code = 500


class ExternalServiceError(AppError):
    """外部服務故障或連不上。"""
    default_error_code = "UPSTREAM_ERROR"
    default_status_code = 502
