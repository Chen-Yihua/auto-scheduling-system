from typing import List
from fastapi import APIRouter, HTTPException, Depends, Request
from crud import linked_account as linked_account_crud
from schemas.linked_account import LinkedAccountCreate, LinkedAccountOut, LinkedAccountUpdate
from core.security import get_current_clerk_user
from core.rate_limit import limiter

router = APIRouter(prefix="/users/me/linked-accounts", tags=["linked-accounts"])

@router.get("/", response_model=List[LinkedAccountOut])
async def get_current_linked_accounts(
    clerk_user: dict = Depends(get_current_clerk_user)
):
    # 沒有綁定帳號時回空陣列，不是 404
    return await linked_account_crud.get_linked_accounts_by_clerk_id(clerk_user["sub"])

# 會實際呼叫平台驗證（Moodle 要開 Selenium），所以限流
@router.post("/", response_model=LinkedAccountOut, status_code=201)
@limiter.limit("10/minute")
async def create_linked_account(
    request: Request,
    account_data: LinkedAccountCreate,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    clerk_id = clerk_user["sub"]

    new_account_response = await linked_account_crud.create_linked_account(
        clerk_id=clerk_id,
        account=account_data
    )
    return new_account_response


# 改到憑證時會重新驗證，所以同樣限流
@router.patch("/{platform}")
@limiter.limit("10/minute")
async def update_linked_account(
    request: Request,
    platform: str,
    data: LinkedAccountUpdate,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    success = await linked_account_crud.update_linked_account_by_clerk_id(
        clerk_user['sub'],
        platform,
        data.model_dump(exclude_none=True)
    )
    if not success:
        raise HTTPException(status_code=404, detail="Linked account not found or no valid fields to update")
    return {"success": True}


@router.delete("/{platform}")
async def delete_linked_account(
    platform: str,
    clerk_user: dict = Depends(get_current_clerk_user)
):
    clerk_id = clerk_user["sub"]
    composite_id = f"{clerk_id}_{platform}"

    await linked_account_crud.delete_linked_account_by_id(composite_id)
    return {"deleted": True}

