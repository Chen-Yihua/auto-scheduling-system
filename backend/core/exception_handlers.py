"""
例外統一轉成 {"detail", "error_code"} 的錯誤回應（ADR 0011）：AppError 用它帶的 error_code 與狀態碼；
HTTPException 依狀態碼補預設的 error_code；422 拿掉輸入值；DB 連不上回 503，Redis 失敗、
其他 DB 錯誤和未預期例外回 500。例外內容只記在 log，不回傳給前端。
"""
import logging
from collections.abc import Mapping

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure, PyMongoError
from redis.exceptions import RedisError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.errors import AppError

logger = logging.getLogger(__name__)


def error_response(status_code: int, detail, error_code: str, headers: Mapping[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "error_code": error_code}, headers=headers)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.detail, exc.error_code)


# router 還沒改成 AppError 的 HTTPException、未知路由、不支援的方法；403 只有 Clerk 驗證 library 會丟
_ERROR_CODE_BY_HTTP_STATUS = {
    400: "INVALID_REQUEST",
    401: "UNAUTHENTICATED",
    403: "UNAUTHENTICATED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "ALREADY_EXISTS",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
}


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    error_code = _ERROR_CODE_BY_HTTP_STATUS.get(exc.status_code)
    if error_code is None:
        error_code = "INTERNAL_ERROR" if exc.status_code >= 500 else "INVALID_REQUEST"
    return error_response(exc.status_code, exc.detail, error_code, headers=exc.headers)


# input 在缺欄位時是整個 request body（含 apiKey、password），ctx 也可能帶輸入值
_DROPPED_VALIDATION_FIELDS = ("input", "ctx")


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {key: value for key, value in error.items() if key not in _DROPPED_VALIDATION_FIELDS}
        for error in exc.errors()
    ]
    return error_response(422, jsonable_encoder(errors), "VALIDATION_ERROR")


async def database_unavailable_handler(request: Request, exc: ConnectionFailure) -> JSONResponse:
    logger.error("資料庫連線失敗 %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(503, "資料庫暫時無法使用，請稍後再試", "SERVICE_UNAVAILABLE")


async def database_error_handler(request: Request, exc: PyMongoError) -> JSONResponse:
    logger.error("資料庫錯誤 %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(500, "伺服器發生錯誤，請稍後再試", "INTERNAL_ERROR")


async def redis_error_handler(request: Request, exc: RedisError) -> JSONResponse:
    """快取讀寫與限流計數都用 Redis；狀態碼維持 500（ADR 0011「過渡期間」）。"""
    logger.error("Redis 錯誤 %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(500, "服務暫時無法使用，請稍後再試", "SERVICE_UNAVAILABLE")


class UnhandledExceptionMiddleware:
    """
    接住所有沒被處理的例外，回 JSON 500。

    不用 add_exception_handler(Exception, ...)：它會在 CORS 外層，回應沒有 CORS 標頭，
    瀏覽器只會看到 CORS 錯誤。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_tracking_start(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking_start)
        except Exception:
            logger.exception("未處理的例外 %s %s", scope["method"], scope["path"])
            if response_started:
                # 回應已開始送出，無法改成 500
                raise
            response = error_response(500, "伺服器發生未預期的錯誤，請稍後再試", "INTERNAL_ERROR")
            await response(scope, receive, send)
