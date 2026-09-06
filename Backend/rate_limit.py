import hashlib
import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def rate_limit_key(request: Request) -> str:
    """
    優先用 Authorization header 當限流的 key——同一個使用者（同一個 token）
    算同一組配額，不管他從哪個 IP 打進來。沒有帶 token 的請求（例如 /webhook，
    GitHub 不會登入）才退回用來源 IP。

    Header 內容雜湊過才拿去當 key，不把明文 token 存進 Redis。
    """
    auth_header = request.headers.get("Authorization")
    if auth_header:
        return "user:" + hashlib.sha256(auth_header.encode()).hexdigest()
    return "ip:" + get_remote_address(request)


REDIS_URL = os.getenv("REDIS_URL")
_storage_uri = REDIS_URL or "memory://"
if not REDIS_URL:
    logger.warning(
        "REDIS_URL 未設定，rate limit 改用記憶體儲存"
        "（多個 Cloud Run instance 各自算配額，不是全域共用，僅供本機開發/尚未接 Redis 時使用）"
    )

# 測試環境把這個關掉，避免同一支測試檔在短時間內重複打同個 endpoint 時
# 互相干擾、被自己的限流誤傷。正式環境不會設這個變數，預設是開啟的。
_enabled = os.getenv("DISABLE_RATE_LIMIT", "false").lower() != "true"

limiter = Limiter(key_func=rate_limit_key, storage_uri=_storage_uri, enabled=_enabled)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    自訂 429 回應內容（不用 slowapi 預設的純文字格式），讓前端可以明確判斷
    「這次失敗是流量限制」，顯示對使用者友善的訊息，而不是當成隨機錯誤處理。
    """
    return JSONResponse(
        status_code=429,
        content={"detail": "請求太頻繁，請稍後再試", "error_code": "RATE_LIMITED"},
    )
