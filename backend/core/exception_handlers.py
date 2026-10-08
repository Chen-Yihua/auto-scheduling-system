"""
把沒在 crud / router 裡處理的例外，統一轉成給前端的錯誤回應：
- 資料庫連不上 → 503
- 其他資料庫錯誤 → 500
- 其他沒被接住的例外（程式 bug）→ 500

回應只帶固定的中文訊息，例外內容與 traceback 只記在 log。
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
    沒被任何 handler 接住的例外 → 記 log，回固定訊息的 JSON 500。
    HTTPException、資料庫例外、驗證錯誤等都會先被內層的 exception handler 處理，不會走到這裡。

    用 middleware 而不是 app.add_exception_handler(Exception, ...)：後者會被放到最外層
    （比 CORS 還外面），回應不會帶 CORS 標頭，瀏覽器只會看到 CORS 錯誤，看不到真正的 500。
    這個 middleware 排在 CORS 內層（見 main.py），回應才會經過 CORS，加上標頭。
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
                # 回應已經送出一半，沒辦法再改成 500，只能讓連線中斷
                raise
            response = JSONResponse(status_code=500, content={"detail": "伺服器發生未預期的錯誤，請稍後再試"})
            await response(scope, receive, send)
