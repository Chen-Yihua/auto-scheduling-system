from fastapi import APIRouter, HTTPException, Depends, Request
from crud import user as user_crud
from schemas.user import UserCreate,UserInDB, UserOut
from typing import Optional
from db.security import get_current_clerk_user
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/users", tags=["users"])

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

# 建立使用者
@router.post("/create")
async def create_user(user: UserCreate):
    user_id = await user_crud.create_user(user)
    return {"id": user_id}

# 查詢使用者
@router.get("/{user_id}")
async def get_user(clerk_user: dict = Depends(get_current_clerk_user)):
    user = await user_crud.get_user_by_clerk_id(clerk_user['sub'])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 更新使用者
@router.put("/{user_id}")
async def update_user(data: dict,clerk_user: dict = Depends(get_current_clerk_user)):
    success = await user_crud.update_user_by_clerk_id(clerk_user['sub'], data)
    if not success:
        raise HTTPException(status_code=404, detail="User not found or no changes made")
    return {"success": True}

# 刪除使用者
@router.delete("/{user_id}")
async def delete_user(clerk_user: dict = Depends(get_current_clerk_user)):
    success = await user_crud.delete_user_by_clerk_id(clerk_user['sub'])
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True}

# Webhook 接收 Clerk 的事件
@router.post("/webhook/clerk")
async def clerk_webhook(request: Request):
    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data", {})

    #print(f"Webhook received: {event_type}")

    if event_type == "user.deleted":
        clerk_id = data.get("id")
        if clerk_id:
            success = await user_crud.delete_user_by_clerk_id(clerk_id)
            if success:
                return {"status": "ok"}
            else:
                return {"error": "User not found in database"}
        else:
            return {"error": "Clerk ID not found in payload"}

    return {"status": "ok"}