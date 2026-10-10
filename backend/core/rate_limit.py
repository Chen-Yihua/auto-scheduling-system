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
    有 Authorization header 就以使用者為單位限流，否則（例如 webhook）用來源 IP。
    header 先雜湊，避免明文 token 存進 Redis。
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

# 測試環境關閉，避免測試短時間內重複呼叫而被限流
_enabled = os.getenv("DISABLE_RATE_LIMIT", "false").lower() != "true"

limiter = Limiter(key_func=rate_limit_key, storage_uri=_storage_uri, enabled=_enabled)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """回 JSON 和 error_code，讓前端能辨識是被限流。"""
    return JSONResponse(
        status_code=429,
        content={"detail": "請求太頻繁，請稍後再試", "error_code": "RATE_LIMITED"},
    )
