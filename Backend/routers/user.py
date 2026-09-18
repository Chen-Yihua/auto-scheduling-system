import json
import logging
import os

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from svix.webhooks import Webhook, WebhookVerificationError

from crud import user as user_crud
from schemas.user import UserCreate, UserOut, UserUpdate
from typing import Optional
from db.security import get_current_clerk_user
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# Clerk Dashboard > Webhooks 設定 endpoint 時給的 Signing Secret（whsec_ 開頭）。
# Clerk 的 webhook 底層是 Svix，用 svix-id/svix-timestamp/svix-signature 三個
# header 加上這組密鑰驗證，確認請求真的是 Clerk 發的
CLERK_WEBHOOK_SIGNING_SECRET = os.getenv("CLERK_WEBHOOK_SIGNING_SECRET")


def _verify_clerk_webhook_signature(raw_body: bytes, headers: dict) -> None:
    """
    沒設定密鑰就直接全部拒絕——避免忘記設定時，變成完全沒有保護。
    驗證委託給 svix 官方函式庫（Clerk webhook 底層就是 Svix），
    不自己刻比對邏輯。

    三種情況都會回 401：沒設定密鑰、簽章驗證不通過（WebhookVerificationError）、
    或 header 格式本身就有問題（例如 svix-signature 不是合法 base64，svix 底層
    函式庫這種情況丟的不是 WebhookVerificationError，見下面 except Exception）。
    """
    if not CLERK_WEBHOOK_SIGNING_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        Webhook(CLERK_WEBHOOK_SIGNING_SECRET).verify(raw_body, headers)
    except WebhookVerificationError:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    except Exception:
        # header 是外部可控的輸入——格式不對（例如 signature 不是合法 base64）時，
        # svix 底層函式庫可能丟出 WebhookVerificationError 以外的例外（例如
        # binascii.Error），一律當成驗證失敗處理，不能讓 500 漏出去
        logger.warning("Unexpected error while verifying Clerk webhook signature", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

# 回傳登入者資訊
@router.get("/me",response_model=UserOut)
async def get_current_user(
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    取得目前登入的使用者資訊（需驗證 JWT）
    """
    user = await user_crud.get_user_by_clerk_id(clerk_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 註冊新使用者
@router.post("/", response_model=UserOut)
async def register_user(
    user_data: UserCreate,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """
    註冊新使用者（需驗證 JWT）
    """
    clerk_id = clerk_user["sub"]

    # 檢查是否已註冊
    existing_user = await user_crud.get_user_by_clerk_id(clerk_id)
    if existing_user:
        raise HTTPException(status_code=409, detail="User already registered")

    # 建立新使用者
    new_user = await user_crud.create_user(
        UserCreate(
            clerk_id=clerk_id,
            name=user_data.name,
            email=user_data.email,
        )
    )
    return new_user

# 更新使用者（只能改自己，clerk_id 從 JWT 來，不接受路徑/body 指定別人）
@router.put("/me")
async def update_user(data: UserUpdate, clerk_user: dict = Depends(get_current_clerk_user)):
    await user_crud.update_user_by_clerk_id(clerk_user['sub'], data) # 找不到或沒有變更由 crud 直接 raise 404
    return {"success": True}

# 刪除使用者（只能刪自己）
@router.delete("/me")
async def delete_user(clerk_user: dict = Depends(get_current_clerk_user)):
    success = await user_crud.delete_user_by_clerk_id(clerk_user['sub'])
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True}

# Webhook 接收 Clerk 的事件
@router.post("/webhook/clerk")
async def clerk_webhook(
    request: Request,
    svix_id: str | None = Header(default=None, alias="svix-id"),
    svix_timestamp: str | None = Header(default=None, alias="svix-timestamp"),
    svix_signature: str | None = Header(default=None, alias="svix-signature"),
):
    raw_body = await request.body()
    _verify_clerk_webhook_signature(
        raw_body,
        {
            "svix-id": svix_id or "",
            "svix-timestamp": svix_timestamp or "",
            "svix-signature": svix_signature or "",
        },
    )

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("type")
    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}

    if event_type == "user.deleted":
        clerk_id = data.get("id")
        if not clerk_id:
            logger.warning("Clerk webhook user.deleted event missing data.id")
            raise HTTPException(status_code=400, detail="Clerk ID not found in payload")

        success = await user_crud.delete_user_by_clerk_id(clerk_id)
        if not success:
            # 本地資料庫本來就沒有這個使用者（例如從未呼叫過註冊），
            # 對這次事件來說已經是「想要的狀態」了，回 200、不用讓 Clerk 重試
            logger.info("Clerk webhook user.deleted: no local record for clerk_id=%s", clerk_id)

    return {"status": "ok"}