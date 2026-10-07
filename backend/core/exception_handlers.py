"""
集中處理資料庫例外：crud / router 遇到資料庫錯誤時不用各自 try/except 再轉成 HTTPException，
直接讓例外往外丟，由這裡統一轉成回應。

- 連線類錯誤（連不上、伺服器選擇逾時、網路逾時、主節點切換中…）是暫時性的基礎設施問題，
  稍後可能恢復 → 503，客戶端和監控才能把它跟「程式有 bug」的 500 分開。
- 其他資料庫錯誤（查詢寫錯、資料驗證失敗…）多半是程式問題，重試也沒用 → 500。

兩種回應都只回固定的中文訊息，不把例外內容（可能含連線字串或查詢細節）回傳給前端；
完整的例外與 traceback 記在後端 log。格式跟 HTTPException 一樣是 {"detail": "..."}，
前端不用另外處理。

這兩個 handler 註冊在 PyMongoError / ConnectionFailure 這種具體的例外類別上（不是 Exception），
所以回應會經過 CORS middleware，瀏覽器看得到真正的狀態碼，而不是被 CORS 錯誤蓋掉。

另外有一層兜底：任何沒被上面接住的例外（程式 bug）由 UnhandledExceptionMiddleware 轉成 JSON 500。
不能只註冊 `Exception` 的 handler——那種 handler 由 Starlette 最外層的 ServerErrorMiddleware 處理，
回應不會經過 CORS，瀏覽器只會顯示「CORS 錯誤」，看不到真正的 500。所以這裡用 middleware，
並在 main.py 讓它放在 CORS 的內層。
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
    兜底：沒被任何 handler 接住的例外 → 記 log，回固定訊息的 JSON 500。
    HTTPException、資料庫例外、驗證錯誤等都會先被內層的 exception handler 處理，不會走到這裡。
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
