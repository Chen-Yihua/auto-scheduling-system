import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from db.mongodb import db
from db.security import get_current_clerk_user
from crud.moodle import get_user_account, fetch_assignments
from crud.external_sync import sync_platform_items
from fastapi.concurrency import run_in_threadpool
from rate_limit import limiter
from cache import cache_get, cache_set

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/moodle", tags=["moodle"])

# 作業內容變動很慢（通常一天頂多變一次），但每次爬蟲都是真的開一個
# headless Chrome、跑好幾秒——快取設長一點，同一個使用者短時間內重複整理頁面
# 不用每次都重爬一次。
CACHE_TTL_SECONDS = 15 * 60


# 即時爬 Moodle；失敗（登入失敗、逾時、頁面改版等）時退回 DB 裡最後一次成功同步的資料
# （見 crud/external_sync.py）—— Moodle 用 Selenium 爬蟲，是三個平台裡最容易失敗的一個，
# 最需要這層 fallback。
# 每次呼叫都是真的開一個 headless Chrome，成本比一般 API 呼叫高很多，限流限得比較嚴。
@router.get("/assignments")
@limiter.limit("5/minute")
async def get_assignments(request: Request, response: Response = None, clerk_user: dict = Depends(get_current_clerk_user)):
    """
    Get the assignments for the user.
    """
    cache_key = f"moodle_assignments:{clerk_user['sub']}"
    cached = await cache_get(cache_key)
    if cached is not None:
        if response is not None:
            response.headers["X-Data-Stale"] = "false"
            if cached.get("synced_at"):
                response.headers["X-Synced-At"] = cached["synced_at"]
        return cached["assignments"]

    user = await get_user_account(clerk_user["sub"])

    async def fetch():
        return await run_in_threadpool(
            fetch_assignments, user["username"], user["password"]
        )

    try:
        assignments, stale, synced_at = await sync_platform_items(
            collection=db.moodle_assignments,
            user_id=clerk_user["sub"],
            id_field="id",
            fetch_fn=fetch,
        )
    except Exception:
        logger.exception("Failed to sync Moodle assignments for user_id=%s", clerk_user["sub"])
        raise HTTPException(status_code=401, detail="無法取得 Moodle 資料，請確認帳號密碼是否正確")

    if response is not None:
        response.headers["X-Data-Stale"] = str(stale).lower()
        if synced_at:
            response.headers["X-Synced-At"] = synced_at.isoformat()

    # 只有真的爬到新鮮資料才值得快取；如果這次是退回 DB 舊資料（stale=True），
    # 代表上次爬蟲失敗，應該讓下一次呼叫正常重試，不要把「已知是舊的」資料
    # 又快取 15 分鐘、變相延長 fallback 的時間。
    if not stale:
        await cache_set(
            cache_key,
            {"assignments": assignments, "synced_at": synced_at.isoformat() if synced_at else None},
            CACHE_TTL_SECONDS,
        )

    return assignments
