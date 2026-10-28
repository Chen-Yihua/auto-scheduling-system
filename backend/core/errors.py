"""crud 用的例外，不帶 HTTP 狀態碼；由 core/exception_handlers.py 轉成對應的回應。"""


class AppError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class InvalidRequestError(AppError):
    """請求的內容不合法，例如缺少必填欄位、帶了不屬於自己的資料。"""


class NotFoundError(AppError):
    """要操作的資料不存在，或不屬於目前的使用者。"""


class ConflictError(AppError):
    """和現有的資料衝突，例如重複建立。"""
