"""
例外統一轉成 {"detail", "error_code"} 的錯誤回應（ADR 0011）：狀態碼一律依 error_code 查 core/error_codes.py 的對照表。
AppError 用它帶的 error_code；HTTPException 先依狀態碼補 error_code；422 拿掉輸入值；DB 連不上、Redis 失敗是
SERVICE_UNAVAILABLE，其他 DB 錯誤和未預期例外是 INTERNAL_ERROR。例外內容只記在 log，不回傳給前端。
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

from core.error_codes import status_for_error_code
from core.errors import AppError

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR_DETAIL = "伺服器發生未預期的錯誤，請稍後再試"


def error_response(
    request: Request,
    detail,
    error_code: str,
    *,
    headers: Mapping[str, str] | None = None,
    exc: BaseException | None = None,
) -> JSONResponse:
    status_code = status_for_error_code(error_code)
    if status_code is None:
        # 不回傳原始的 error_code 與 detail：會把內部的原因名稱與文字暴露給呼叫者
        logger.error(
            "對照表沒有的 error_code=%s %s %s trace=%s",
            error_code, request.method, request.url.path, request.headers.get("x-cloud-trace-context"),
            exc_info=exc,
        )
        return JSONResponse(status_code=500, content={"detail": UNEXPECTED_ERROR_DETAIL, "error_code": "INTERNAL_ERROR"})
    return JSONResponse(status_code=status_code, content={"detail": detail, "error_code": error_code}, headers=headers)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(request, exc.detail, exc.error_code, headers=exc.headers, exc=exc)


# 未知路由、不支援的方法、Clerk 驗證 library 的 403（沒帶 token、scheme 錯、token 無效），以及 FastAPI 或其他 library 丟的 HTTPException
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
    return error_response(request, exc.detail, error_code, headers=exc.headers, exc=exc)


# input 在缺欄位時是整個 request body（含 apiKey、password），ctx 也可能帶輸入值
_DROPPED_VALIDATION_FIELDS = ("input", "ctx")


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {key: value for key, value in error.items() if key not in _DROPPED_VALIDATION_FIELDS}
        for error in exc.errors()
    ]
    return error_response(request, jsonable_encoder(errors), "VALIDATION_ERROR")


async def database_unavailable_handler(request: Request, exc: ConnectionFailure) -> JSONResponse:
    logger.error("資料庫連線失敗 %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(request, "資料庫暫時無法使用，請稍後再試", "SERVICE_UNAVAILABLE")


async def database_error_handler(request: Request, exc: PyMongoError) -> JSONResponse:
    logger.error("資料庫錯誤 %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(request, "伺服器發生錯誤，請稍後再試", "INTERNAL_ERROR")


async def redis_error_handler(request: Request, exc: RedisError) -> JSONResponse:
    """快取讀寫與限流計數都用 Redis。"""
    logger.error("Redis 錯誤 %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(request, "服務暫時無法使用，請稍後再試", "SERVICE_UNAVAILABLE")


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
            response = error_response(Request(scope), UNEXPECTED_ERROR_DETAIL, "INTERNAL_ERROR")
            await response(scope, receive, send)
