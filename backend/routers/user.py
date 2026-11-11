import json
import logging
import os

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from svix.webhooks import Webhook, WebhookVerificationError

from core.errors import AppError, ConflictError
from crud import user as user_crud
from schemas.user import UserCreate, UserOut, UserUpdate
from typing import Optional
from core.security import get_current_clerk_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# Clerk Dashboard > Webhooks 的 Signing Secret（whsec_ 開頭），用 svix 驗證請求來自 Clerk
CLERK_WEBHOOK_SIGNING_SECRET = os.getenv("CLERK_WEBHOOK_SIGNING_SECRET")
if not CLERK_WEBHOOK_SIGNING_SECRET:
    # 啟動時記一次就好，請求時不再記，否則每個 webhook 請求都會多一筆 error
    logger.error("CLERK_WEBHOOK_SIGNING_SECRET 未設定，Clerk webhook 會一律拒絕")


def _invalid_signature() -> AppError:
    # 沒設定密鑰也用這個 code（對照表 401，ADR 0011「例外」）：回 500 會讓外部知道伺服器漏了設定
    return AppError("Invalid webhook signature", error_code="INVALID_WEBHOOK_SIGNATURE")


def _verify_clerk_webhook_signature(raw_body: bytes, headers: dict) -> None:
    """沒設定密鑰、簽章錯誤、header 格式錯誤都回 401。"""
    if not CLERK_WEBHOOK_SIGNING_SECRET:
        raise _invalid_signature()
    try:
        Webhook(CLERK_WEBHOOK_SIGNING_SECRET).verify(raw_body, headers)
    except WebhookVerificationError:
        raise _invalid_signature()
    except Exception:
        # header 格式錯誤時 svix 可能丟其他例外（例如 binascii.Error），也當成驗證失敗
        logger.warning("Unexpected error while verifying Clerk webhook signature", exc_info=True)
        raise _invalid_signature()

@router.get("/me",response_model=UserOut)
async def get_current_user(
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """取得目前登入的使用者。"""
    user = await user_crud.get_user_by_clerk_id(clerk_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=UserOut, status_code=201)
async def register_user(
    user_data: UserCreate,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    """註冊目前登入的使用者，已註冊回 409。"""
    clerk_id = clerk_user["sub"]

    existing_user = await user_crud.get_user_by_clerk_id(clerk_id)
    if existing_user:
        raise ConflictError("User already registered")

    new_user = await user_crud.create_user(
        UserCreate(
            clerk_id=clerk_id,
            name=user_data.name,
            email=user_data.email,
        )
    )
    return new_user

# 只能改自己：clerk_id 從 JWT 取得，不接受路徑或 body 指定
@router.put("/me")
async def update_user(data: UserUpdate, clerk_user: dict = Depends(get_current_clerk_user)):
    await user_crud.update_user_by_clerk_id(clerk_user['sub'], data)
    return {"success": True}

@router.delete("/me")
async def delete_user(clerk_user: dict = Depends(get_current_clerk_user)):
    success = await user_crud.delete_user_by_clerk_id(clerk_user['sub'])
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True}

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
            # 本來就沒有這個使用者，已是想要的結果，回 200 避免 Clerk 重試
            logger.info("Clerk webhook user.deleted: no local record for clerk_id=%s", clerk_id)

    return {"status": "ok"}