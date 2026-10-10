"""
沒被處理的例外統一轉成錯誤回應：DB 連不上回 503，其他 DB 錯誤和未預期例外回 500。
例外內容只記在 log，不回傳給前端。
"""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure, PyMongoError

logger = logging.getLogger(__name__)


async def database_unavailable_handler(request: Request, exc: ConnectionFailure) -> JSONResponse:
    logger.error("資料庫連線失敗 %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "資料庫暫時無法使用，請稍後再試"})


async def database_error_handler(request: Request, exc: PyMongoError) -> JSONResponse:
    logger.error("資料庫錯誤 %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "伺服器發生錯誤，請稍後再試"})


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
            response = JSONResponse(status_code=500, content={"detail": "伺服器發生未預期的錯誤，請稍後再試"})
            await response(scope, receive, send)
