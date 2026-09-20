import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from db.mongodb import db
from db.security import get_current_clerk_user
from db.crypto import decrypt_secret
from crud.errors import NonRetryableError
from crud.moodle import fetch_assignments, sync_moodle_assignments
from schemas.moodle import MoodleAssignment
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
@router.get("/assignments", response_model=List[MoodleAssignment])
@limiter.limit("5/minute")
async def get_assignments(request: Request, response: Response = None, clerk_user: dict = Depends(get_current_clerk_user)):
    """
    Get the assignments for the user.
    """
    # 查快取
    cache_key = f"moodle_assignments:{clerk_user['sub']}"
    cached = await cache_get(cache_key)
    if cached is not None:
        if response is not None:
            response.headers["X-Data-Stale"] = "false"
            if cached.get("synced_at"):
                response.headers["X-Synced-At"] = cached["synced_at"]
        return cached["assignments"]

    # 查綁定帳號
    user = await db.linkedAccounts.find_one({"platform": "moodle", "clerk_id": clerk_user["sub"]})

    if not user:
        raise HTTPException(status_code=400, detail="No Moodle linked account")

    # 解密
    # 密碼只在這裡（伺服器內部、準備拿去登入 Moodle 的當下）解密，
    # 絕不印出來、絕不回傳給呼叫端以外的地方。
    try:
        password = decrypt_secret(user["password"])
    except Exception:
        logger.exception("Failed to decrypt Moodle password for user_id=%s", clerk_user["sub"])
        raise HTTPException(status_code=500, detail="無法取得 Moodle 資料，請稍後再試")

    # 抓資料
    async def fetch():
        return await run_in_threadpool(
            fetch_assignments, user["username"], password
        )

    try:
        assignments, stale, synced_at, auth_error = await sync_moodle_assignments(
            user_id=clerk_user["sub"],
            fetch_fn=fetch,
        )
    except NonRetryableError:
        logger.warning("Moodle login failed for user_id=%s", clerk_user["sub"])
        raise HTTPException(status_code=401, detail="無法取得 Moodle 資料，請確認帳號密碼是否正確")
    except Exception:
        logger.exception("Failed to sync Moodle assignments for user_id=%s", clerk_user["sub"])
        raise HTTPException(status_code=500, detail="無法取得 Moodle 資料，請稍後再試")

    if response is not None:
        response.headers["X-Data-Stale"] = str(stale).lower()
        if auth_error:
            response.headers["X-Auth-Error"] = "true"
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
