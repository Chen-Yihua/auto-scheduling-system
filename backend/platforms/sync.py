"""外部平台抓資料的重試規則與失敗分類，以及項目怎麼寫進資料庫。一次同步的完整流程在 platforms/account_sync.py。"""
import asyncio
import logging
from datetime import datetime
from typing import Awaitable, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class NonRetryableError(Exception):
    """
    重試也沒用的失敗，不重試直接退回舊資料；沒有舊資料時 router 依 error_code 回錯誤。

    重試和原因分開判斷：error_code 是原因（ADR 0011），只有 REAUTH_REQUIRED 算憑證失效
    （有舊資料時設 X-Auth-Error）。message 可能帶第三方回應原文，只記 log；detail 會回給前端。
    headers 是要轉送給呼叫者的 header（例如限流的 Retry-After）。
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "REAUTH_REQUIRED",
        detail: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.detail = detail
        self.headers = headers or {}

    @property
    def auth_error(self) -> bool:
        return self.error_code == "REAUTH_REQUIRED"


class UpstreamError(Exception):
    """外部平台暫時性失敗（5xx、限流、連不上），會重試；沒有舊資料時 router 依 error_code 回錯誤。message 只記 log。"""

    def __init__(self, message: str, *, error_code: str = "UPSTREAM_ERROR", headers: dict[str, str] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.headers = headers or {}


class InvalidResponseError(Exception):
    """外部平台的回應無法解析（不是 JSON、少欄位），會重試；沒有舊資料時 router 回 UPSTREAM_ERROR。"""


async def fetch_with_retry(
    user_id: str,
    fetch_fn: Callable[[], Awaitable[list[dict]]],
    max_attempts: int = 2,
    retry_delay_seconds: float = 1.0,
) -> list[dict]:
    """
    即時抓資料，失敗就以指數退避重試（NonRetryableError 不重試）；
    最後仍失敗就把最後一次的例外往外拋，由呼叫端決定要不要退回舊資料。
    """
    last_exc: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            return await fetch_fn()
        except Exception as exc:
            last_exc = exc
            if isinstance(exc, NonRetryableError):
                logger.info("Non-retryable error for user_id=%s, skipping retry: %s", user_id, exc)
                break

            # 最後一次失敗不用再等
            if attempt < max_attempts - 1:
                delay = retry_delay_seconds * (2 ** attempt)
                logger.warning(
                    "Live fetch failed for user_id=%s (attempt %d/%d), retrying in %.1fs",
                    user_id, attempt + 1, max_attempts, delay,
                    exc_info=True,
                )
                await asyncio.sleep(delay)

    assert last_exc is not None  # 沒有成功回傳代表至少失敗過一次
    logger.warning("Live fetch failed for user_id=%s after %d attempt(s)", user_id, max_attempts, exc_info=last_exc)
    raise last_exc


def fetch_error_code(exc: Exception) -> str:
    """抓取失敗的原因（ADR 0011 的 error_code），記成同步結果，也決定沒有舊資料時回哪種錯誤。"""
    if isinstance(exc, (NonRetryableError, UpstreamError)):
        return exc.error_code
    if isinstance(exc, httpx.TimeoutException):
        return "UPSTREAM_TIMEOUT"
    if isinstance(exc, (httpx.HTTPError, InvalidResponseError)):
        return "UPSTREAM_ERROR"
    return "INTERNAL_ERROR"


async def upsert_items(collection, user_id: str, id_field: str, items: list[dict], now: datetime) -> list[dict]:
    """
    寫入抓到的項目，回傳去掉重複 id 後的清單。
    只 $set 平台回傳的欄位，使用者設定的排程欄位（priority、done 等）才不會被覆蓋。
    """
    # 翻頁期間資料有變動時，同一個項目可能出現在兩頁；保留最後一次的內容
    unique = list({item[id_field]: item for item in items}.values())
    for item in unique:
        await collection.update_one(
            {"user_id": user_id, id_field: item[id_field]},
            {"$set": {**item, "user_id": user_id, "synced_at": now}},
            upsert=True,
        )
    return unique


async def delete_missing_items(collection, user_id: str, id_field: str, current_ids: list) -> None:
    """清掉平台上已不存在的項目，否則畫面會一直顯示早就被刪掉的項目。"""
    await collection.delete_many({"user_id": user_id, id_field: {"$nin": current_ids}})


async def read_items(collection, user_id: str) -> list[dict]:
    docs = await collection.find({"user_id": user_id}).to_list(length=None)
    # _id 是 MongoDB 的 ObjectId，不能轉成 JSON
    for doc in docs:
        doc.pop("_id", None)
    return docs
