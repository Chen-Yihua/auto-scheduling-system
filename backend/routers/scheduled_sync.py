"""
定時同步：GitHub Actions 每天呼叫一次（ADR 0013），依序同步所有已連結的平台帳號。
用共用密鑰驗證，不用 Clerk 登入。
"""
import hmac
import logging
import os

from fastapi import APIRouter, Request

from core.database import db
from core.errors import AppError
from core.rate_limit import limiter
from platforms import PLATFORMS
from platforms.account_sync import SyncOutcome, sync_account
from schemas.scheduled_sync import ScheduledSyncResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])

SCHEDULED_SYNC_SECRET = os.getenv("SCHEDULED_SYNC_SECRET")
if not SCHEDULED_SYNC_SECRET:
    # 啟動時記一次就好，請求時不再記
    logger.error("SCHEDULED_SYNC_SECRET 未設定，定時同步會一律拒絕")

_BEARER_PREFIX = "Bearer "

_SKIPPED = {
    SyncOutcome.SUPERSEDED,
    SyncOutcome.ACCOUNT_CHANGED,
    SyncOutcome.UNDECRYPTABLE,
    SyncOutcome.INCOMPLETE_CREDENTIALS,
}


def _invalid_token() -> AppError:
    # 沒設定密鑰也用這個 code（對照表 401，ADR 0011「例外」）：回 500 會讓外部知道伺服器漏了設定
    return AppError("Invalid scheduler token", error_code="INVALID_SCHEDULER_TOKEN")


def _verify_token(authorization: str | None) -> None:
    """沒設定密鑰時一律拒絕，避免漏設時完全沒有保護；用 compare_digest 防 timing attack。"""
    if not SCHEDULED_SYNC_SECRET or not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise _invalid_token()
    token = authorization[len(_BEARER_PREFIX):]
    if not token.strip() or not hmac.compare_digest(token.encode(), SCHEDULED_SYNC_SECRET.encode()):
        raise _invalid_token()


async def run_scheduled_sync() -> dict[str, int]:
    """一次只同步一個帳號；每個帳號的失敗只記 log，接著處理下一個。"""
    counts = {"succeeded": 0, "failed": 0, "skipped": 0}
    accounts = await db.linkedAccounts.find({}, {"clerk_id": 1, "platform": 1}).to_list(length=None)
    for account in accounts:
        platform = PLATFORMS.get(account.get("platform", ""))
        user_id = account.get("clerk_id")
        if platform is None or not user_id:
            continue
        try:
            result = await sync_account(platform, user_id)
        except Exception as exc:
            # 只記例外類別：例外訊息可能帶第三方回應原文
            logger.error("Scheduled sync failed user_id=%s platform=%s error=%s", user_id, platform.name, type(exc).__name__)
            counts["failed"] += 1
            continue

        if result.outcome is SyncOutcome.SUCCEEDED:
            counts["succeeded"] += 1
        elif result.outcome in _SKIPPED:
            logger.info("Scheduled sync skipped user_id=%s platform=%s outcome=%s", user_id, platform.name, result.outcome.value)
            counts["skipped"] += 1
        else:
            logger.warning(
                "Scheduled sync failed user_id=%s platform=%s outcome=%s error_code=%s",
                user_id, platform.name, result.outcome.value, result.error_code,
            )
            counts["failed"] += 1
    return counts


# 密鑰外洩時降低濫用
@router.post("/scheduled-sync", response_model=ScheduledSyncResult)
@limiter.limit("5/hour")
async def scheduled_sync(request: Request):
    _verify_token(request.headers.get("Authorization"))
    return await run_scheduled_sync()
