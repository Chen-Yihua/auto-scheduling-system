"""crud、services 和各平台用的例外，不帶 HTTP 狀態碼；由 core/exception_handlers.py 轉成對應的回應。"""


class AppError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class InvalidRequestError(AppError):
    """請求的內容不合法，或前置條件還沒完成（例如還沒連接帳號）。"""


class ReauthRequiredError(AppError):
    """使用者綁定的第三方憑證失效，需要重新連結。"""


class AccessDeniedError(AppError):
    """第三方平台拒絕存取，例如 token 沒有足夠的權限。"""


class NotFoundError(AppError):
    """要操作的資料不存在，或不屬於目前的使用者。"""


class ConflictError(AppError):
    """和現有的資料衝突，例如重複建立。"""


class ConfigurationError(AppError):
    """伺服器設定錯誤，例如第三方服務的 client 設定不正確。"""


class ExternalServiceError(AppError):
    """外部服務故障或連不上。"""
