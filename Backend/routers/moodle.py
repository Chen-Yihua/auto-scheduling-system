from fastapi import APIRouter, Depends, HTTPException, Response
from db.mongodb import db
from db.security import get_current_clerk_user
from crud.moodle import get_user_account, fetch_assignments
from crud.external_sync import sync_platform_items
from fastapi.concurrency import run_in_threadpool

router = APIRouter(prefix="/moodle", tags=["moodle"])

# 即時爬 Moodle；失敗（登入失敗、逾時、頁面改版等）時退回 DB 裡最後一次成功同步的資料
# （見 crud/external_sync.py）—— Moodle 用 Selenium 爬蟲，是三個平台裡最容易失敗的一個，
# 最需要這層 fallback。
@router.get("/assignments")
async def get_assignments(response: Response = None, clerk_user: dict = Depends(get_current_clerk_user)):
    """
    Get the assignments for the user.
    """
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
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    if response is not None:
        response.headers["X-Data-Stale"] = str(stale).lower()
        if synced_at:
            response.headers["X-Synced-At"] = synced_at.isoformat()
    return assignments
